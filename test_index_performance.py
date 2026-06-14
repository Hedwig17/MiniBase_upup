#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试索引性能对比
作者: 郑许博雅
功能: 创建 students 表，对 s_id 建立索引，插入测试数据，对比有/无索引的查询性能
"""

import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage_db import Storage
from index_db import Index
import schema_db


def setup_schema():
    """初始化 schema 对象"""
    schema_obj = schema_db.Schema()
    return schema_obj


def create_students_table(schema_obj):
    """创建 students 表"""
    table_name = 'students'
    table_name_bytes = table_name.encode('utf-8')

    # 检查表是否已存在，如果存在先删除
    if schema_obj.find_table(table_name_bytes):
        print(f"表 {table_name} 已存在，正在删除...")
        schema_obj.delete_table(table_name_bytes)
        Storage.remove_table_file(table_name)

    # 字段定义: (字段名, 类型, 长度)
    # 类型: 0=str, 1=varstr, 2=int, 3=bool, 4=float
    field_list = [
        ('s_id', 1, 10),      # varstr, 长度10，存储如 S00001
        ('name', 1, 20),      # varstr, 长度20
        ('gender', 1, 10),    # varstr, 长度10
        ('age', 2, 4),        # int, 长度4
    ]

    # 创建表
    storage = Storage(table_name_bytes, field_list=field_list)
    schema_obj.appendTable(table_name_bytes, field_list)
    del storage

    print(f"表 {table_name} 创建成功")
    print(f"  字段: s_id(10), name(20), gender(10), age(4)")
    return True


def insert_test_data(schema_obj, num_records=10000):
    """插入测试数据"""
    table_name = 'students'
    table_name_bytes = table_name.encode('utf-8')

    if not schema_obj.find_table(table_name_bytes):
        print("表不存在，请先创建表")
        return False

    storage = Storage(table_name)

    print(f"\n开始插入 {num_records} 条测试数据...")
    start_time = time.time()

    genders = ['Male', 'Female', 'Other']
    names = ['Alice', 'Bob', 'Charlie', 'David', 'Eva', 'Frank', 'Grace', 'Henry', 'Ivy', 'Jack']

    success_count = 0
    last_report = 0
    report_interval = max(1000, num_records // 10)

    for i in range(num_records):
        # 生成 s_id: S00001, S00002, ..., S99999
        s_id = f"S{i:07d}"
        name = names[i % len(names)] + str(i)
        gender = genders[i % len(genders)]
        age = 18 + (i % 50)

        record = [s_id, name, gender, str(age)]

        try:
            if hasattr(storage, 'insert_record_simple'):
                success = storage.insert_record_simple(record)
            else:
                success = storage.insert_record(record)

            if success:
                success_count += 1
        except Exception as e:
            if i < 5:
                print(f"  插入异常 (i={i}): {e}")

        if (i + 1) - last_report >= report_interval:
            last_report = i + 1
            percent = (i + 1) * 100 // num_records
            print(f"  进度: {percent}% ({i + 1}/{num_records}), 成功 {success_count} 条")

    elapsed = time.time() - start_time
    print(f"\n数据插入完成！")
    print(f"  成功: {success_count}/{num_records} 条")
    print(f"  耗时: {elapsed:.2f} 秒")
    print(f"  速度: {success_count/elapsed:.0f} 条/秒")

    # 验证数据
    storage2 = Storage(table_name)
    record_count = len(storage2.getRecord())
    print(f"\n验证: storage 中实际有 {record_count} 条记录")
    if record_count > 0:
        print(f"  第一条记录: {storage2.getRecord()[0]}")
        print(f"  最后一条记录: {storage2.getRecord()[-1]}")
    del storage2
    del storage

    return success_count > 0


def query_without_index(schema_obj, s_id_value):
    """无索引查询（全表扫描）"""
    table_name = 'students'
    table_name_bytes = table_name.encode('utf-8')

    if not schema_obj.find_table(table_name_bytes):
        print("表不存在")
        return None, 0

    storage = Storage(table_name)

    field_list = storage.getFieldList()
    field_idx = None
    for i, (fname, _, _) in enumerate(field_list):
        fname_str = fname.decode('utf-8').strip() if isinstance(fname, bytes) else str(fname).strip()
        if fname_str == 's_id':
            field_idx = i
            break

    if field_idx is None:
        print("找不到 s_id 字段")
        return None, 0

    records = storage.getRecord()

    start_time = time.time()

    results = []
    for record in records:
        val = record[field_idx]
        if isinstance(val, bytes):
            val = val.decode('utf-8').strip()
        if str(val) == s_id_value:
            results.append(record)

    elapsed = time.time() - start_time

    del storage
    return results, elapsed


def query_with_index_reuse(idx, s_id_value):
    """有索引查询（复用 Index 对象）"""
    start_time = time.time()

    positions = idx.search(s_id_value)

    storage = Storage('students')

    # 建立位置映射
    position_map = {}
    for i, pos in enumerate(storage.record_Position):
        position_map[pos] = i

    results = []
    for pos in positions:
        if pos in position_map:
            idx_in_list = position_map[pos]
            record = storage.record_list[idx_in_list]
            results.append(record)

    elapsed = time.time() - start_time

    del storage
    return results, elapsed


def query_range_without_index(start_key, end_key):
    """无索引范围查询（全表扫描）"""
    storage = Storage('students')

    field_list = storage.getFieldList()
    field_idx = None
    for i, (fname, _, _) in enumerate(field_list):
        if fname.decode('utf-8').strip() == 's_id':
            field_idx = i
            break

    records = storage.getRecord()

    start_time = time.time()

    results = []
    for record in records:
        val = record[field_idx]
        if isinstance(val, bytes):
            val = val.decode('utf-8').strip()
        if start_key <= val <= end_key:
            results.append(record)

    elapsed = time.time() - start_time

    del storage
    return results, elapsed


def query_range_with_index(idx, start_key, end_key):
    """有索引范围查询（复用 Index 对象）"""
    start_time = time.time()

    positions = idx.range_search(start_key, end_key)

    storage = Storage('students')

    position_map = {}
    for i, pos in enumerate(storage.record_Position):
        position_map[pos] = i

    results = []
    for _, blk, off in positions:
        pos = (blk, off)
        if pos in position_map:
            idx_in_list = position_map[pos]
            record = storage.record_list[idx_in_list]
            results.append(record)

    elapsed = time.time() - start_time

    del storage
    return results, elapsed


def create_index_on_sid():
    """在 s_id 字段上创建索引"""
    table_name = 'students'

    index_file = table_name + '.ind'
    if os.path.exists(index_file):
        os.remove(index_file)
        print(f"已删除旧索引文件 {index_file}")

    storage = Storage(table_name)
    record_count = len(storage.getRecord())
    print(f"表中当前有 {record_count} 条记录")
    del storage

    if record_count == 0:
        print("表中没有数据，无需创建索引")
        return None

    print("正在创建索引...")
    start_time = time.time()

    idx = Index(table_name)
    idx.create_index('s_id')

    elapsed = time.time() - start_time
    print(f"索引创建完成，耗时: {elapsed:.2f} 秒")

    return idx


def run_performance_test(schema_obj):
    """运行性能对比测试（精确查询 + 范围查询）"""
    print("\n" + "=" * 70)
    print("索引性能对比测试")
    print("=" * 70)

    # 测试精确查询
    test_s_id = "S0000001"

    print(f"\n【精确查询测试】s_id = '{test_s_id}'")
    print("-" * 50)

    # 1. 无索引查询
    print("\n[1] 无索引查询（全表扫描）")
    results_no_idx, time_no_idx = query_without_index(schema_obj, test_s_id)
    if results_no_idx is not None:
        print(f"  找到 {len(results_no_idx)} 条记录")
        print(f"  耗时: {time_no_idx:.6f} 秒")

    # 2. 创建索引
    print("\n[2] 创建索引")
    idx = create_index_on_sid()
    if idx is None:
        print("索引创建失败")
        return

    # 3. 有索引查询（复用 Index）
    print("\n[3] 有索引查询（复用 Index 对象）")
    results_with_idx, time_with_idx = query_with_index_reuse(idx, test_s_id)
    if results_with_idx is not None:
        print(f"  找到 {len(results_with_idx)} 条记录")
        print(f"  耗时: {time_with_idx:.6f} 秒")

    # 4. 精确查询性能对比
    print("\n" + "=" * 70)
    print("精确查询性能对比")
    print("=" * 70)
    print(f"无索引查询耗时: {time_no_idx:.6f} 秒")
    print(f"有索引查询耗时: {time_with_idx:.6f} 秒")
    if time_with_idx > 0 and time_no_idx > 0:
        speedup = time_no_idx / time_with_idx
        print(f"性能提升: {speedup:.2f} 倍")

    # 测试范围查询
    print("\n" + "=" * 70)
    print("范围查询性能测试")
    print("=" * 70)

    start_key = "S0000001"
    end_key = "S0000010"

    print(f"\n查询范围: {start_key} 到 {end_key}")
    print("-" * 50)

    # 5. 无索引范围查询
    print("\n[4] 无索引范围查询（全表扫描）")
    results_range_no_idx, time_range_no_idx = query_range_without_index(start_key, end_key)
    print(f"  找到 {len(results_range_no_idx)} 条记录")
    print(f"  耗时: {time_range_no_idx:.4f} 秒")

    # 6. 有索引范围查询（复用 Index）
    print("\n[5] 有索引范围查询（复用 Index 对象）")
    results_range_idx, time_range_idx = query_range_with_index(idx, start_key, end_key)
    print(f"  找到 {len(results_range_idx)} 条记录")
    print(f"  耗时: {time_range_idx:.4f} 秒")

    # 7. 范围查询性能对比
    print("\n" + "=" * 70)
    print("范围查询性能对比")
    print("=" * 70)
    print(f"无索引范围查询耗时: {time_range_no_idx:.4f} 秒")
    print(f"有索引范围查询耗时: {time_range_idx:.4f} 秒")
    if time_range_idx > 0 and time_range_no_idx > 0:
        speedup = time_range_no_idx / time_range_idx
        print(f"性能提升: {speedup:.2f} 倍")

    # 清理
    del idx


def cleanup():
    """清理测试数据"""
    print("\n是否清理测试数据？(y/n): ", end="")
    choice = input().strip().lower()
    if choice == 'y':
        table_name = 'students'
        table_name_bytes = table_name.encode('utf-8')

        schema_obj = schema_db.Schema()
        if schema_obj.find_table(table_name_bytes):
            schema_obj.delete_table(table_name_bytes)
        Storage.remove_table_file(table_name)

        index_file = table_name + '.ind'
        if os.path.exists(index_file):
            os.remove(index_file)

        print("测试数据已清理")
    else:
        print("保留测试数据")


def main():
    """主函数"""
    print("=" * 70)
    print("索引性能测试程序")
    print("=" * 70)
    print("\n说明:")
    print("  1. 先选择选项1创建表并插入数据")
    print("  2. 再选择选项2进行性能对比测试（精确查询 + 范围查询）")
    print("=" * 70)

    schema_obj = setup_schema()

    while True:
        print("\n请选择测试选项:")
        print("  1. 创建 students 表并插入测试数据")
        print("  2. 运行性能对比测试（精确查询 + 范围查询）")
        print("  3. 清理测试数据")
        print("  4. 退出")

        choice = input("请输入选项 (1-4): ").strip()

        if choice == '1':
            create_students_table(schema_obj)
            num_records = input("请输入要插入的记录数 (默认 50000): ").strip()
            if not num_records:
                num_records = 50000
            else:
                num_records = int(num_records)
            insert_test_data(schema_obj, num_records)

        elif choice == '2':
            run_performance_test(schema_obj)

        elif choice == '3':
            cleanup()

        elif choice == '4':
            print("测试结束")
            break

        else:
            print("无效选项，请重新输入")


if __name__ == '__main__':
    main()