# Author：马焱涵
import time
import os
import storage_db


ACTIVE_FILE = "active.trx"
COMMIT_FILE = "commit.trx"
BEFORE_FILE = "before.img"
AFTER_FILE = "after.img"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SYSTEM_FLAG = "system.flag"

# 事务号
def generate_txn_id():
    """
    功能描述：生成唯一事务编号，作为事务在日志文件和事务表中的标识
    输入参数：无
    返回值：str，基于当前时间戳生成的事务编号
    """
    return str(int(time.time() * 1000))

# 开始事务
def begin_transaction(txn_id):
    """
    功能描述：开启事务，将事务编号写入活动事务表 ATL（active.trx）
    输入参数：txn_id: str，事务编号
    返回值：无
    """
    with open(ACTIVE_FILE, "a", encoding="utf8") as f:
        f.write(txn_id + "\n")

# 写前像
def write_before_image(txn_id, operation_type, table_name, old_record=None):
    """
    功能描述：记录事务执行前的数据镜像（Before Image），用于事务恢复时参考原始状态
    输入参数：txn_id: str，事务编号；
             operation_type: str，操作类型（INSERT 或 UPDATE）；
             table_name: str/bytes，表名；
             old_record: list，可选参数，修改前记录内容
    返回值：无
    """
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
    """
    功能描述：记录事务执行后的数据镜像（After Image），并按照 WAL 规则强制写入磁盘
    输入参数：txn_id: str，事务编号；
             operation_type: str，操作类型（INSERT 或 UPDATE）；
             table_name: str/bytes，表名；
             record: list，事务执行后的记录内容
    返回值：无
    """
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
    """
    功能描述：提交事务，将事务编号写入提交事务表 CTL（commit.trx），表示事务已成功提交
    输入参数：txn_id: str，事务编号
    返回值：无
    """
    with open(COMMIT_FILE,"a",encoding="utf8") as f:
        f.write(txn_id + "\n")
        f.flush()
        os.fsync(f.fileno())

# 从活动事务表中删除已提交事务
def remove_active_transaction(txn_id):
    """
    功能描述：从活动事务表 ATL（active.trx）中删除指定事务编号，表示事务生命周期结束
    输入参数：txn_id: str，事务编号
    返回值：无
    """
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
    """
    功能描述：系统启动时执行故障恢复。首先读取 ATL（活动事务表） 和 CTL（提交事务表），判断事务处于未提交、已提交未完成或已完成状态；随后扫描 After Image 日志，根据事务状态决定是否执行 REDO 操作，最终将数据库恢复到所有已提交事务完成后的正确状态。
    输入参数：无
    返回值：无
    """
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
            # 事务状态分类
            # =====================================================
            in_ctl = txn_id in committed_txns
            in_atl = txn_id in active_txns
            # ATL + CTL 状态判断
            if in_atl and not in_ctl:
                txn_state = "ACTIVE"
            elif in_atl and in_ctl:
                txn_state = "COMMIT_NOT_FINISH"
            elif (not in_atl) and in_ctl:
                txn_state = "FINISHED"
            else:
                txn_state = "IGNORE"

            # =========================
            # 决策逻辑
            # =========================
            if txn_state == "ACTIVE":
                print("Abort txn:", txn_id)
                remove_active_transaction(txn_id)
                continue
            elif txn_state == "COMMIT_NOT_FINISH":
                # 已提交但未完成
                pass
            elif txn_state == "FINISHED":
                # 已完成事务
                continue
            else:
                continue

            # =====================================================
            # INSERT REDO
            # =====================================================
            if operation_type == "INSERT":
                # 记录主键是否已经存在
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
                    # 主键存在但内容不同
                    if target_idx is not None:
                        dataObj.record_list[target_idx] = tuple(record)
                        dataObj._rebuild_storage_records(
                            dataObj.record_list
                        )
                    # 主键不存在
                    else:
                        dataObj.insert_record(
                            record,
                            is_recovery=True
                        )

                    recovered = True

            # =====================================================
            # UPDATE REDO
            # =====================================================
            elif operation_type == "UPDATE":

                target_idx = None
                # 根据主键查找目标记录
                for i, r in enumerate(dataObj.record_list):

                    cur_pk = r[0]
                    if isinstance(cur_pk, bytes):
                        cur_pk = cur_pk.decode("utf8")

                    if str(cur_pk).strip() == primary_key:
                        target_idx = i
                        break
                # 找到对应记录
                if target_idx is not None:
                    # 当前数据库内容与日志后像不一致
                    if list(dataObj.record_list[target_idx]) != record:
                        # 使用后像覆盖当前记录
                        dataObj.record_list[target_idx] = tuple(record)
                        # 重建数据文件并落盘
                        if hasattr(dataObj, "_rebuild_storage_records"):
                            dataObj._rebuild_storage_records(
                                dataObj.record_list
                            )

                        recovered = True
                # 记录不存在，数据库可能在崩溃时丢失该记录
                else:
                    # 根据日志后像重新插入记录
                    dataObj.insert_record(
                        record,
                        is_recovery=True
                    )

                    recovered = True

            del dataObj

            if recovered:
                print("Redo LSN:", lsn, "Txn:", txn_id)
                # 恢复完成后删除ATL
                remove_active_transaction(txn_id)

    print("恢复完成")