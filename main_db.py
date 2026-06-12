# -----------------------
# main_db.py
# author: Jingyu Han   hjymail@163.com
# modified by: Ning Wang, Yidan Xu, 胡丹，但芸妍
# -----------------------------------
# This is the main loop of the program
# ---------------------------------------

import struct
import sys
import ctypes
import os

import head_db  # the main memory structure of table schema
import schema_db  # the module to process table schema
import storage_db  # the module to process the storage of instance

import query_plan_db  # for SQL clause of which data is stored in binary format
import lex_db  # for lex, where data is stored in binary format
import parser_db  # for yacc, where ddata is tored in binary format
import common_db  # the global variables, functions, constants in the program
import query_plan_db  # construct the query plan and execute it

PROMPT_STR = 'Input your choice  \n1:add a new table structure and data \n2:delete a table structure and data\
\n3:view a table structure and data \n4:delete all tables and data \n5:select from where clause\
\n6:delete a row according to field keyword \n7:update a row according to field keyword\
\n8:DDL(CREATE TABLE) \n9:DML(INSERT INTO) \n10:DML(DELETE FROM) \n11:DML(UPDATE SET) \n12:DDL(DROP TABLE) \n. to quit):\n'


def _read_non_empty_text(prompt_text):
    """
    功能描述：读取用户输入的非空字符串，避免主流程因为空输入进入异常分支
    输入参数：prompt_text: str，输入提示语
    返回值：str，去除首尾空白后的非空字符串
    异常处理：无；当输入为空时持续提示重新输入
    """
    while True:
        # 修改原因：统一处理非空输入校验，减少主流程中的重复判断逻辑
        input_text = input(prompt_text).strip()
        if input_text:
            return input_text
        print('input cannot be empty, please try again.')


def _read_table_name_bytes(prompt_text):
    """
    功能描述：读取表名并转换为 UTF-8 编码的 bytes，适配当前项目的字节串处理风格
    输入参数：prompt_text: str，输入提示语
    返回值：bytes，去除首尾空白后的表名字节串
    异常处理：无；内部依赖非空输入函数保证表名合法
    """
    table_name = _read_non_empty_text(prompt_text)
    # 修改原因：Python 3 中 input 返回 str，项目内部大量逻辑基于 bytes，需要在入口统一转换
    return table_name.encode('utf-8')


def _collect_record_values(data_obj):
    """
    功能描述：根据表字段定义逐项采集一条记录的输入值
    输入参数：data_obj: storage_db.Storage，当前表对应的数据文件操作对象
    返回值：list[str]，按字段顺序采集得到的记录值列表
    异常处理：无；字段级合法性由底层插入函数继续校验
    """
    record = []
    field_list = data_obj.getFieldList()
    for field_name, field_type, field_length in field_list:
        if isinstance(field_name, bytes):
            display_field_name = field_name.decode('utf-8').strip()
        else:
            display_field_name = str(field_name).strip()
        prompt = 'Input field name is: {0}  field type is: {1} field maximum length is: {2}\n'.format(
            display_field_name, field_type, field_length)
        # 修改原因：把单条记录采集逻辑抽取成公共函数，便于后续批量插入复用
        record.append(input(prompt))
    return record


def _handle_batch_insert(data_obj):
    """
    功能描述：批量插入表记录，支持用户在插入成功后选择是否继续录入下一条
    输入参数：data_obj: storage_db.Storage，当前表对应的数据文件操作对象
    返回值：int，成功插入的记录条数
    异常处理：无；插入失败时给出提示并终止本轮批量录入
    """
    inserted_count = 0
    while True:
        record = _collect_record_values(data_obj)
        # 修改原因：支持连续录入多条数据，满足实验要求中的批量插入功能
        if data_obj.insert_record(record):
            inserted_count += 1
            print('OK!')
        else:
            print('Wrong input!')
            break

        continue_flag = input('whether to continue insert next row(y/n):').strip().lower()
        if continue_flag != 'y':
            break
    return inserted_count


def _run_sql_parser(sql_str):
    """
    功能：初始化 lex/parser，解析 SQL 字符串，返回语法树根节点
    输入参数：sql_str: str，用户输入的 SQL 文本
    返回值：tuple[bool, Node/None, str]，(解析成功, 根节点, 错误信息)
    """
    sql_str = sql_str.strip().rstrip(';').strip()
    if common_db.global_lexer is None:
        lex_db.set_lex_handle()
    if common_db.global_parser is None:
        parser_db.set_handle()
    common_db.global_lexer.input(sql_str)
    parse_result = common_db.global_parser.parse(sql_str)
    root = common_db.global_syn_tree if parse_result is not None else None
    if root is None:
        return False, None, 'WRONG SQL INPUT!'
    return True, root, ''





# --------------------------
# the main loop, which needs further implementation
# ---------------------------

def main():
    print('main function begins to execute')

    # The instance data of table is stored in binary format, which corresponds to chapter 2-8 of textbook

    schemaObj = schema_db.Schema()  # to create a schema object, which contains the schema of all tables
    dataObj = None
    choice = input(PROMPT_STR)

    while True:

        if choice == '1':  # add a new table and lines of data
            # 修改原因：统一在入口校验表名非空，并转为 bytes 以兼容现有存储逻辑
            tableName = _read_table_name_bytes('please enter your new table name:')
            #  tableName not in all.sch
            insertFieldList = []
            if tableName.strip() not in list(schemaObj.get_table_name_list()):
                # 防线 1：表名长度校验提前到 Storage 创建之前，避免产生孤儿 .dat 文件
                if len(tableName.strip()) > 10:
                    print('表名 "{0}" 长度 {1} 超过上限 10，请缩短后重试'.format(
                        tableName.strip().decode('utf-8'), len(tableName.strip())))
                else:
                    dataObj = storage_db.Storage(tableName)
                    insertFieldList = dataObj.getFieldList()
                    # 防线 2：检查 appendTable 返回值，失败时清理孤儿 .dat 文件
                    if not schemaObj.appendTable(tableName, insertFieldList):
                        print('schema 写入失败，正在清理数据文件...')
                        del dataObj  # 先关闭文件句柄，否则 Windows 无法删除被占用的文件
                        storage_db.Storage.remove_table_file(tableName)
                    else:
                        print('table schema has been created successfully.')
                    # 修改原因：建表后引导用户插入数据，避免空表即返回菜单
                        insert_choice = input('是否立即插入数据？(y/n):').strip().lower()
                        if insert_choice == 'y':
                            inserted_count = _handle_batch_insert(dataObj)
                            print('successfully inserted {0} row(s).'.format(inserted_count))
                        del dataObj
            else:
                dataObj = storage_db.Storage(tableName)

                # 修改原因：原逻辑只支持插入单条记录，这里扩展为可连续插入多条记录
                inserted_count = _handle_batch_insert(dataObj)
                print('successfully inserted {0} row(s).'.format(inserted_count))

                del dataObj

            choice = input(PROMPT_STR)





        elif choice == '2':  # delete a table from schema file and data file
            # 修改原因：补全完整删除流程，增加存在性校验和二次确认，避免误删表结构与数据文件
            table_name = _read_table_name_bytes('please input the name of the table to be deleted:')
            if schemaObj.find_table(table_name.strip()):
                confirm_flag = input(
                    '确定要删除表{0}吗？此操作不可恢复(y/n):'.format(table_name.decode('utf-8'))).strip().lower()
                if confirm_flag == 'y':
                    if schemaObj.delete_table(table_name):  # delete the schema from the schema file
                        storage_db.Storage.remove_table_file(table_name.strip())  # delete table content from the table file
                        print('table deleted successfully.')
                    else:
                        print('the deletion from schema file fail')
                else:
                    print('deletion cancelled.')
            else:
                print('there is no table '.encode('utf-8') + table_name + ' in the schema file'.encode('utf-8'))

            choice = input(PROMPT_STR)



        elif choice == '3':  # view the table structure and all the data
            # 修改原因：支持 all 查看全部表名，并将单表查看拆分为结构展示和数据展示两部分
            table_name_input = _read_non_empty_text('please input the name of the table to be displayed:')
            if table_name_input.lower() == 'all':
                schemaObj.viewTableNames()
            else:
                table_name = table_name_input.encode('utf-8')
                if schemaObj.find_table(table_name.strip()):
                    print('table structure:')
                    schemaObj.viewTableStructure(table_name)
                    print('table data:')
                    dataObj = storage_db.Storage(table_name)  # create an object for the data of table
                    dataObj.show_table_data()  # view all the data of the table
                    del dataObj
                else:
                    print('table does not exist.')

            choice = input(PROMPT_STR)



        elif choice == '4':  # delete all the table structures and their data
            # 修改原因：补全“删除所有”强确认流程，并同步删除所有 .dat 文件与重建空 all.sch
            confirm_text = input('警告！此操作将删除所有表和数据，无法恢复，确定继续吗？(输入YES确认):').strip()
            if confirm_text == 'YES':
                removed_dat_count = storage_db.Storage.remove_all_data_files()
                schemaObj.reset_schema_file()
                print('all tables and data have been deleted. removed {0} dat file(s).'.format(removed_dat_count))
            else:
                print('delete all operation cancelled.')

            choice = input(PROMPT_STR)


        elif choice == '5':  # DQL：SELECT ... FROM ... WHERE
            print('#        DQL -- SELECT QUERY                      #')
            sql_str = input('please enter the SELECT statement:')
            ok, root, err = _run_sql_parser(sql_str)
            if not ok:
                print(err)
            elif root.value != 'Query':
                print('选项 5 仅支持 SELECT 查询，当前语句类型为: ' + str(root.value))
            else:
                try:
                    query_plan_db.construct_logical_tree()
                    query_plan_db.execute_logical_tree()
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print('查询执行错误:', str(e))
            print('#----------------------------------------------------#')
            choice = input(PROMPT_STR)


        elif choice == '6':  # delete a line of data from the storage file given the keyword
            # 修改原因：补全按字段关键字删除记录的完整交互流程，增加表存在性和字段值合法性校验
            table_name = _read_table_name_bytes('please input the name of the table to be deleted from:')
            if schemaObj.find_table(table_name.strip()):
                field_name = _read_non_empty_text('please input the field name:')
                field_value = _read_non_empty_text('please input the keyword value:')
                dataObj = storage_db.Storage(table_name)
                is_delete_success, delete_result = dataObj.delete_record_by_field(field_name, field_value)
                if is_delete_success:
                    print('成功删除{0}条记录'.format(delete_result))
                else:
                    print(delete_result)
                del dataObj
            else:
                print('table does not exist.')

            choice = input(PROMPT_STR)

        elif choice == '7':  # update a line of data given the keyword
            # 修改原因：补全按字段关键字更新记录的完整交互流程，增加表存在性、字段存在性和新值合法性校验
            table_name = _read_table_name_bytes('please input the name of the table:')
            if schemaObj.find_table(table_name.strip()):
                condition_field_name = _read_non_empty_text('please input the condition field name:')
                condition_field_value = _read_non_empty_text('please input the matching value of the condition field:')
                target_field_name = _read_non_empty_text('please input the field name to be updated:')
                new_field_value = _read_non_empty_text('please input the new value:')
                dataObj = storage_db.Storage(table_name)
                is_update_success, update_result = dataObj.update_record_by_field(
                    condition_field_name, condition_field_value, target_field_name, new_field_value)
                if is_update_success:
                    print('成功更新{0}条记录'.format(update_result))
                else:
                    print(update_result)
                del dataObj
            else:
                print('table does not exist.')

            choice = input(PROMPT_STR)

        # Author: 但芸妍
        # 新增：CREATE TABLE
        elif choice == '8':
            print('#        DDL -- CREATE TABLE                       #')
            sql_str = input('please enter the CREATE TABLE statement:')
            ok, root, err = _run_sql_parser(sql_str)
            if not ok:
                print(err)
            elif root.value != 'CreateStmt':
                print('选项 8 仅支持 CREATE TABLE')
            else:
                try:
                    query_plan_db.execute_create_table(schemaObj)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print('建表执行错误:', str(e))
            print('#----------------------------------------------------#')
            choice = input(PROMPT_STR)

        # Author: 但芸妍
        elif choice == '9':  # DML: INSERT INTO
            print('#        DML -- INSERT INTO                        #')
            sql_str = input('please enter the INSERT INTO statement:')
            ok, root, err = _run_sql_parser(sql_str)
            if not ok:
                print(err)
            elif root.value != 'InsertStmt':
                print('选项 9 仅支持 INSERT INTO')
            else:
                try:
                    query_plan_db.execute_insert(schemaObj)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print('插入执行错误:', str(e))
            print('#----------------------------------------------------#')
            choice = input(PROMPT_STR)

        # Author: 但芸妍
        elif choice == '10':  # DML: DELETE FROM
            print('#        DML -- DELETE FROM                       #')
            sql_str = input('please enter the DELETE FROM statement:')
            ok, root, err = _run_sql_parser(sql_str)
            if not ok:
                print(err)
            elif root.value != 'DeleteStmt':
                print('选项 10 仅支持 DELETE FROM')
            else:
                try:
                    query_plan_db.execute_delete(schemaObj)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print('删除执行错误:', str(e))
            print('#----------------------------------------------------#')
            choice = input(PROMPT_STR)

        # Author: 但芸妍
        elif choice == '11':  # DML: UPDATE SET
            print('#        DML -- UPDATE SET                        #')
            sql_str = input('please enter the UPDATE statement:')
            ok, root, err = _run_sql_parser(sql_str)
            if not ok:
                print(err)
            elif root.value != 'UpdateStmt':
                print('选项 11 仅支持 UPDATE SET')
            else:
                try:
                    query_plan_db.execute_update(schemaObj)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print('更新执行错误:', str(e))
            print('#----------------------------------------------------#')
            choice = input(PROMPT_STR)

        # Author: 但芸妍
        elif choice == '12':  # DDL: DROP TABLE
            print('#        DDL -- DROP TABLE                        #')
            sql_str = input('please enter the DROP TABLE statement:')
            ok, root, err = _run_sql_parser(sql_str)
            if not ok:
                print(err)
            elif root.value != 'DropStmt':
                print('选项 12 仅支持 DROP TABLE')
            else:
                try:
                    query_plan_db.execute_drop(schemaObj)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print('删除表执行错误:', str(e))
            print('#----------------------------------------------------#')
            choice = input(PROMPT_STR)

        elif choice == '.':
            print('main loop finishies')
            del schemaObj
            break

        else:
            # 修改原因：原主循环缺少非法菜单输入兜底分支，输入未定义选项后会一直停留在当前无效 choice，表现为程序卡住
            print('invalid menu choice, please input 1, 2, 3, 4, 5, 6, 7, 8, 9 or .')
            choice = input(PROMPT_STR)

    print('main loop finish!')


if __name__ == '__main__':
    main()
