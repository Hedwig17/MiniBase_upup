# Author：马焱涵
import time
import os
import storage_db


ACTIVE_FILE = "active.trx"
COMMIT_FILE = "commit.trx"
BEFORE_FILE = "before.img"
AFTER_FILE = "after.img"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# REDO_FILE = os.path.join(BASE_DIR, "redo.done")
SYSTEM_FLAG = "system.flag"

# 事务号
def generate_txn_id():
    return str(int(time.time() * 1000))

# 开始事务
def begin_transaction(txn_id):
    with open(ACTIVE_FILE, "a", encoding="utf8") as f:
        f.write(txn_id + "\n")

# 写前像
def write_before_image(txn_id, operation_type, table_name, old_record=None):
    # 去掉 b''
    if isinstance(table_name, bytes):
        table_name = table_name.decode("utf8")

    with open(BEFORE_FILE, "a", encoding="utf8") as f:
        # 【M】insert写NULL
        if old_record is None:
            image = "NULL"
        # 【M】update写old_record
        else:
            clean_record = []
            for item in old_record:
                if isinstance(item, bytes):
                    clean_record.append(
                        item.decode("utf8").strip()
                    )
                else:
                    clean_record.append(item)

            image = "#".join(
                map(str, clean_record)
            )
        f.write(
            f"{txn_id}|{operation_type}|{table_name}|{image}\n"
        )

# 写后像
def write_after_image(txn_id, operation_type, table_name, record):
    # 去掉 b''
    if isinstance(table_name, bytes):
        table_name = table_name.decode("utf8")
    with open(AFTER_FILE,"a",encoding="utf8") as f:
        # 改日志格式为：1001|students|s01#Tom#male#19
        clean_record = []
        for item in record:
            if isinstance(item, bytes):
                clean_record.append(
                    item.decode("utf8").strip()
                )
            else:
                clean_record.append(str(item))
        record_str = "#".join(clean_record)

        f.write(
            f"{txn_id}|{operation_type}|{table_name}|{record_str}\n"
        )

        f.flush()
        # 提交规则：后像必须在事务提交前写入非易失存储器
        os.fsync(f.fileno())

# 提交事务
def commit_transaction(txn_id):
    with open(COMMIT_FILE,"a",encoding="utf8") as f:
        f.write(txn_id + "\n")
        f.flush()
        os.fsync(f.fileno())
    # 提交成功后从活动事务表删除
    remove_active_transaction(txn_id)

# 从活动事务表中删除已提交事务
def remove_active_transaction(txn_id):

    if not os.path.exists(ACTIVE_FILE):
        return

    with open(ACTIVE_FILE, "r", encoding="utf8") as f:
        lines = f.readlines()

    with open(ACTIVE_FILE, "w", encoding="utf8") as f:
        for line in lines:
            if line.strip() != txn_id:
                f.write(line)

# 事务恢复
def recover():

    committed_txns = set()
    active_txns = set()

    # =========================
    # 读取 CTL（已提交事务）
    # =========================
    if os.path.exists(COMMIT_FILE):
        with open(COMMIT_FILE, "r", encoding="utf8") as f:
            for line in f:
                committed_txns.add(line.strip())

    # =========================
    # 读取 ATL（未完成事务）
    # =========================
    if os.path.exists(ACTIVE_FILE):
        with open(ACTIVE_FILE, "r", encoding="utf8") as f:
            for line in f:
                active_txns.add(line.strip())

    if not os.path.exists(AFTER_FILE):
        return

    print("开始事务恢复（ATL + CTL enhanced）...")

    executed_lsn = set()
    global_lsn = 0

    with open(AFTER_FILE, "r", encoding="utf8") as f:

        logs = f.readlines()

        for line in logs:

            global_lsn += 1
            lsn = global_lsn

            if lsn in executed_lsn:
                continue
            executed_lsn.add(lsn)

            parts = line.strip().split("|")
            if len(parts) != 4:
                continue

            txn_id = parts[0]
            operation_type = parts[1]
            table_name = parts[2]
            record_str = parts[3]

            record = record_str.split("#")
            primary_key = str(record[0]).strip()

            dataObj = storage_db.Storage(table_name.encode("utf8"))

            print("当前表记录:", dataObj.record_list)
            print("日志记录:", record)

            recovered = False

            # =====================================================
            # 事务状态分类（关键新增）
            # =====================================================
            in_ctl = txn_id in committed_txns
            in_atl = txn_id in active_txns

            if in_ctl:
                # 已提交事务 → 必须redo
                txn_state = "COMMIT"

            elif in_atl:
                # 崩溃时仍在active → 未提交事务
                txn_state = "ABORT"

            else:
                # 不在任何表 → 无效事务
                txn_state = "IGNORE"

            # =========================
            # 决策逻辑（关键）
            # =========================
            if txn_state == "COMMIT":
                # 已提交 → redo
                pass

            elif txn_state == "ABORT" and in_atl:
                # 崩溃中断事务（必须显式说明）
                print("Skip uncommitted txn:", txn_id)
                continue

            else:
                # unknown事务（可能crash中途丢失）
                continue

            # =====================================================
            # INSERT REDO
            # =====================================================
            if operation_type == "INSERT":

                target_idx = None
                identical = False

                for i, r in enumerate(dataObj.record_list):

                    cur_pk = r[0]
                    if isinstance(cur_pk, bytes):
                        cur_pk = cur_pk.decode("utf8")

                    if str(cur_pk).strip() == primary_key:
                        target_idx = i
                        if list(r) == record:
                            identical = True
                        break

                if not identical:

                    if target_idx is not None:
                        dataObj.record_list[target_idx] = tuple(record)
                    else:
                        dataObj.insert_record(record, is_recovery=True)

                    recovered = True

            # =====================================================
            # UPDATE REDO
            # =====================================================
            elif operation_type == "UPDATE":

                target_idx = None

                for i, r in enumerate(dataObj.record_list):

                    cur_pk = r[0]
                    if isinstance(cur_pk, bytes):
                        cur_pk = cur_pk.decode("utf8")

                    if str(cur_pk).strip() == primary_key:
                        target_idx = i
                        break

                if target_idx is not None:

                    if list(dataObj.record_list[target_idx]) != record:

                        dataObj.record_list[target_idx] = tuple(record)

                        if hasattr(dataObj, "_rebuild_storage_records"):
                            dataObj._rebuild_storage_records(dataObj.record_list)

                        recovered = True

            del dataObj

            if recovered:
                print("Redo LSN:", lsn, "Txn:", txn_id)

    print("恢复完成")