# ------------------------------------------------
# query_plan_db.py
# author: Jingyu Han  hjymail@163.com
# modified by:但芸妍，郑许博雅
# ------------------------------------------------


# ----------------------------------------------------------
# this module can turn a syntax tree into a query plan tree
# ----------------------------------------------------------

import common_db
import storage_db
import itertools

# --------------------------------
# to import the syntax tree, which is defined in parser_db.py
# -------------------------------------------
# from common_db import global_syn_tree as syn_tree


'''
    把语法树转换成可执行的查询计划，然后执行并返回结果
'''

class parseNode:
    def __init__(self):
        self.sel_list = []
        self.from_list = []
        self.where_list = []

    def get_sel_list(self):
        return self.sel_list

    def get_from_list(self):
        return self.from_list

    def get_where_list(self):
        return self.where_list

    def update_sel_list(self, self_list):
        self.sel_list = self_list

    def update_from_list(self, from_list):
        self.from_list = from_list

    def update_where_list(self, where_list):
        self.where_list = where_list


# --------------------------------
# Author: Shuting Guo shutingnjupt@gmail.com
# to extract data from gloal variable syn_tree
# output:
#       sel_list
#       from_list
#       where_list
# --------------------------------
def extract_sfw_data():
    print('extract_sfw_data begins to execute')
    if common_db.global_syn_tree is None:
        print('wrong')
    else:
        # common_db.show(syn_tree)
        PN = parseNode()
        destruct(common_db.global_syn_tree, PN)  # 遍历语法树，提取信息
        return PN.get_sel_list(), PN.get_from_list(), PN.get_where_list()


# ---------------------------------
# Author: Shuting Guo shutingnjupt@gmail.com
# Query  : SFW
#   SFW  : SELECT SelList FROM FromList WHERE Condition
# SelList: TCNAME COMMA SelList
# SelList: TCNAME
#
# FromList:TCNAME COMMA FromList
# FromList:TCNAME
# Condition: TCNAME EQX CONSTANT
# ---------------------------------

def destruct(nodeobj, PN):
    if isinstance(nodeobj, common_db.Node):  # it is a Node object
        if nodeobj.children:
            if nodeobj.value == 'SelList':
                tmpList = []
                show(nodeobj, tmpList)
                PN.update_sel_list(tmpList)
            elif nodeobj.value == 'FromList':
                tmpList = []
                show(nodeobj, tmpList)
                PN.update_from_list(tmpList)
            elif nodeobj.value == 'Cond':
                tmpList = []
                show(nodeobj, tmpList)
                PN.update_where_list(tmpList)
            else:
                for i in range(len(nodeobj.children)):
                    destruct(nodeobj.children[i], PN)


def show(nodeobj, tmpList):
    if isinstance(nodeobj, common_db.Node):
        if not nodeobj.children:  # 叶子结点，这个if根本不会执行（TCNAME或其他token永远有子结点）
            tmpList.append(nodeobj.value)
        else:
            for i in range(len(nodeobj.children)):
                show(nodeobj.children[i], tmpList)
    if isinstance(nodeobj, str):
        tmpList.append(nodeobj)


# ---------------------------
# input:
#       from_list
# output:
#       a tree
# -----------------------------------
'''
    把表名列表转换成一棵左深连接树
    
    ·X 节点：计算笛卡尔积
    ·Filter 节点：过滤数据
    ·Proj 节点：投影，返回最终结果
    
    
                        Proj (投影)
                       ↓
                    Filter (过滤)  ← 如果有 WHERE 条件
                       ↓
                      X (连接)     ← 这是最外层的 X
                     / \
                    X   takes      ← 右子树是 takes 表
                   / \
            students courses       ← 左子树是 students × courses 的结果
'''
def construct_from_node(from_list):
    if from_list:
        if len(from_list) == 1:
            temp_node = common_db.Node(from_list[0], None)
            return common_db.Node('X', [temp_node])
        elif len(from_list) == 2:
            temp_node_first = common_db.Node(from_list[0], None)
            temp_node_second = common_db.Node(from_list[1], None)

            return common_db.Node('X', [temp_node_first, temp_node_second])

        elif len(from_list) > 2:

            right_node = common_db.Node(from_list[len(from_list) - 1], None)

            return common_db.Node('X', [construct_from_node(from_list[0:len(from_list) - 1]), right_node])


# ---------------------------
# input:
#       where_list
#       from_node
# output:
#       a tree
# -----------------------------------
def construct_where_node(from_node, where_list):
    if from_node and len(where_list) > 0:
        return common_db.Node('Filter', [from_node], where_list)
    elif from_node and len(where_list) == 0:  # there is no where clause
        return from_node


# ---------------------------
# input:
#       sel_list
#       wf_node
# output:
#       a tree
# -----------------------------------
def construct_select_node(wf_node, sel_list):
    if wf_node and len(sel_list) > 0:
        return common_db.Node('Proj', [wf_node], sel_list)


# ----------------------------------
# Author: Shuting Guo shutingnjupt@gmail.com
# to execute the query plan and return the result
# input
#       global logical tree
# ---------------------------------------------

def execute_logical_tree():
    if common_db.global_logical_tree:
        def excute_tree():

            idx = 0
            dict_ = {}

            # 遍历查询计划树，记录每个节点的值和它在树中的层级（深度）
            def show(node_obj, idx, dict_):
                if isinstance(node_obj, common_db.Node):  # it is a Node object
                    dict_.setdefault(idx, [])
                    dict_[idx].append(node_obj.value)
                    if node_obj.var:
                        dict_[idx][-1] = tuple((dict_[idx][-1], node_obj.var))
                    if node_obj.children:
                        for i in range(len(node_obj.children)):
                            show(node_obj.children[i], idx + 1, dict_)

            show(common_db.global_logical_tree, idx, dict_)
            idx = sorted(dict_.keys(), reverse=True)[0]  # 找出字典中最大的键（最深的那一层）

            # 根据条件中的字段名，找出它属于哪张表、是第几个字段、是什么类型
            def GetFilterParam(tableName_Order, current_field, param):
                # print tableName_Order,current_field
                if '.' in param:
                    tableName = param.split('.')[0]
                    FieldName = param.split('.')[1]
                    if tableName in tableName_Order:
                        TableIndex = tableName_Order.index(tableName)
                elif len(tableName_Order) == 1:
                    TableIndex = 0
                    FieldName = param
                else:
                    return 0, 0, 0, False

                tmp = list(map(lambda x: x[0].strip().decode('utf-8'), current_field[TableIndex]))  # 取出该表所有字段名，去掉空格，转成列表
                if FieldName in tmp:
                    FieldIndex = tmp.index(FieldName)  # 字段在第几个位置
                    FieldType = current_field[TableIndex][FieldIndex][1]  # 字段类型
                    return TableIndex, FieldIndex, FieldType, True
                else:
                    return 0, 0, 0, False

            current_field = []  # 记录每张表的字段信息
            current_list = []  # 记录当前中间结果（数据）
            # print dict_
            while (idx >= 0):
                if idx == sorted(dict_.keys(), reverse=True)[0]:  # 最深层
                    if len(dict_[idx]) > 1:  # 该层有多个表
                        # 读取两个表
                        a_1 = storage_db.Storage(dict_[idx][0])
                        a_2 = storage_db.Storage(dict_[idx][1])
                        current_list = []
                        # 记录表名顺序和字段信息
                        tableName_Order = [dict_[idx][0], dict_[idx][1]]
                        current_field = [a_1.getFieldList(), a_2.getFieldList()]
                        # 做笛卡尔积
                        for x in itertools.product(a_1.getRecord(), a_2.getRecord()):
                            current_list.append(list(x))
                    else:  # 该层只有一个表
                        a_1 = storage_db.Storage(dict_[idx][0])
                        table_name = dict_[idx][0] 
                        current_list = a_1.getRecord()
                        # ========== 新增：检查是否可以使用索引 ==========
                        # 先获取 WHERE 条件（来自上一层 Filter）
                        use_index = False
                        positions = None
                        
                        # 检查上一层是否有 Filter 节点
                        if idx - 1 >= 0 and 'Filter' in dict_[idx - 1]:
                            filter_info = dict_[idx - 1][0][1]
                            if filter_info and len(filter_info) >= 3:
                                filter_field_name = filter_info[0]
                                filter_field_value = filter_info[2].strip()
                                
                                # 检查索引文件是否存在
                                import os
                                from index_db import Index
                                
                                index_file = table_name + '.ind'
                                if os.path.exists(index_file):
                                    try:
                                        idx_obj = Index(table_name)
                                        positions = idx_obj.search(filter_field_value)
                                        if positions:
                                            use_index = True
                                            print(f"[Index] 使用索引查询 '{filter_field_name}={filter_field_value}'，找到 {len(positions)} 条记录")
                                    except Exception as e:
                                        print(f"[Index] 索引查询失败: {e}")
                        
                        if use_index and positions:
                            # 使用索引查询，根据位置读取记录
                            current_list = []
                            # 获取字段索引（用于后续过滤，索引已经精确匹配，但可能需要验证）
                            field_idx = None
                            field_list = a_1.getFieldList()
                            for i, (fname, _, _) in enumerate(field_list):
                                fname_str = fname.decode('utf-8').strip() if isinstance(fname, bytes) else str(fname).strip()
                                if fname_str == filter_field_name:
                                    field_idx = i
                                    break
                            
                            for blk, off in positions:
                                try:
                                    record = a_1.read_record_by_position(blk, off)
                                    if record:
                                        # 验证记录确实匹配（可选，用于安全）
                                        val = record[field_idx]
                                        if isinstance(val, bytes):
                                            val = val.decode('utf-8').strip()
                                        if str(val) == filter_field_value:
                                            current_list.append(record)
                                except Exception as e:
                                    print(f"读取记录失败: {e}")
                        else:
                            # 全表扫描
                            current_list = a_1.getRecord()
                            print(f"[Index] 未使用索引，执行全表扫描，共 {len(current_list)} 条记录")
                        tableName_Order = [dict_[idx][0]]
                        current_field = [a_1.getFieldList()]

                elif 'X' in dict_[idx] and len(dict_[idx]) > 1:
                    a_2 = storage_db.Storage(dict_[idx][1])
                    tableName_Order.append(dict_[idx][1])
                    current_field.append(a_2.getFieldList())
                    tmp_List = current_list[:]
                    current_list = []
                    for x in itertools.product(tmp_List, a_2.getRecord()):
                        current_list.append(list((x[0][0], x[0][1], x[1])))

                elif 'X' not in dict_[idx]:
                    if 'Filter' in dict_[idx][0]:
                        FilterChoice = dict_[idx][0][1]
                        TableIndex, FieldIndex, FieldType, isTrue = GetFilterParam(tableName_Order, current_field,
                                                                                   FilterChoice[0])
                        if not isTrue:
                            return [], [], False
                        else:
                            if FieldType == 2:
                                FilterParam = int(FilterChoice[2].strip())
                            elif FieldType == 3:
                                FilterParam = bool(FilterChoice[2].strip())
                            else:
                                FilterParam = FilterChoice[2].strip()
                            # print FilterParam
                        tmp_List = current_list[:]
                        current_list = []
                        for tmpRecord in tmp_List:
                            if len(current_field) == 1:
                                ans = tmpRecord[FieldIndex]
                            else:
                                ans = tmpRecord[TableIndex][FieldIndex]
                            if FieldType == 0 or FieldType == 1:
                                ans = ans.strip()
                            if FilterParam == ans:
                                current_list.append(tmpRecord)

                    if 'Proj' in dict_[idx][0]:
                        # 检查是否是通配符 *
                        if dict_[idx][0][1] == ['*']:
                            # 选择所有表的所有字段
                            SelIndexList = []
                            for table_idx in range(len(current_field)):
                                for field_idx in range(len(current_field[table_idx])):
                                    SelIndexList.append((table_idx, field_idx))
                        else:
                            SelIndexList = []
                            for i in range(len(dict_[idx][0][1])):
                                TableIndex, FieldIndex, FieldType, isTrue = GetFilterParam(tableName_Order, current_field,
                                                                                           dict_[idx][0][1][i])
                                if not isTrue:
                                    return [], [], False
                                SelIndexList.append((TableIndex, FieldIndex))
                        tmp_List = current_list[:]
                        current_list = []
                        # print SelIndexList,current_field
                        for tmpRecord in tmp_List:
                            # print tmpRecord
                            if len(current_field) == 1:
                                tmp = []
                                for x in list(map(lambda x: x[1], SelIndexList)):
                                    tmp.append(tmpRecord[x])
                                current_list.append(tmp)
                            else:
                                tmp = []
                                for x in SelIndexList:
                                    tmp.append(tmpRecord[x[0]][x[1]])
                                current_list.append(tmp)

                        outPutField = []
                        for xi in SelIndexList:
                            # 处理表名
                            table_name = tableName_Order[xi[0]]
                            if isinstance(table_name, bytes):
                                table_name = table_name.decode('utf-8')
                            table_name = table_name.strip()

                            # 处理字段名
                            field_name = current_field[xi[0]][xi[1]][0]
                            if isinstance(field_name, bytes):
                                field_name = field_name.decode('utf-8')
                            field_name = field_name.strip()

                            outPutField.append(table_name + '.' + field_name)
                        return outPutField, current_list, True
                idx -= 1

        outPutField, current_list, isRight = excute_tree()

        if isRight:
            print(outPutField)
            for record in current_list:
                print(record)
        else:
            print('WRONG SQL INPUT!')
    else:
        print('there is no query plan tree for the execution')


# --------------------------------
# Author: Shuting Guo shutingnjupt@gmail.com
# to construct a logical query plan tree
# output:
#       global_logical_tree
# ---------------------------------
def construct_logical_tree():
    # 直接使用 common_db.global_syn_tree
    if common_db.global_syn_tree is None:
        print('there is no data in the syntax tree in the construct_logical_tree')
        return

    sel_list, from_list, where_list = extract_sfw_data()
    sel_list = [i for i in sel_list if i != ',']

    # 处理 * 通配符
    if '*' in sel_list:
        sel_list = ['*']

    from_list = [i for i in from_list if i != ',']
    where_list = tuple(where_list)

    from_node = construct_from_node(from_list)
    where_node = construct_where_node(from_node, where_list)
    common_db.global_logical_tree = construct_select_node(where_node, sel_list)


# --------------------------------
# Author: 但芸妍
# 新增：执行 CREATE TABLE
# ---------------------------------
def execute_create_table(schema_obj):
    """执行 CREATE TABLE 语句"""
    tree = common_db.global_syn_tree
    if tree is None or tree.value != 'CreateStmt':
        print("不是 CREATE TABLE 语句")
        return False

    # 获取表名（第1个子节点）
    table_name_node = tree.children[0]
    if isinstance(table_name_node, bytes):
        table_name = table_name_node.decode('utf-8')
    else:
        table_name = str(table_name_node)
    table_name = table_name.strip()
    table_name_bytes = table_name.encode('utf-8')

    # 获取字段定义列表（第2个子节点）
    field_list_node = tree.children[1]

    # 检查表是否已存在
    if schema_obj.find_table(table_name_bytes):
        print(f"表 '{table_name}' 已存在")
        return False

    # 递归解析字段定义列表
    field_list = []
    _parse_field_list(field_list_node, field_list)

    # 创建表
    storage = storage_db.Storage(table_name_bytes, field_list=field_list)
    schema_obj.appendTable(table_name_bytes, field_list)
    del storage

    print(f"表 '{table_name}' 创建成功，共 {len(field_list)} 个字段")
    return True


def _parse_field_list(node, field_list):
    """
    递归解析 FieldDefList 节点
    树结构：FieldDefList → [FieldDef, FieldDefList] 或 [FieldDef]
    """
    if node.value != 'FieldDefList':
        return

    # 第一个子节点是 FieldDef
    first_child = node.children[0]
    _parse_field_def(first_child, field_list)

    # 如果有第二个子节点（剩余的 FieldDefList），递归处理
    if len(node.children) > 1:
        second_child = node.children[1]
        _parse_field_list(second_child, field_list)


def _parse_field_def(node, field_list):
    """解析单个 FieldDef 节点"""
    if node.value != 'FieldDef':
        return

    # 获取字段名
    fname_node = node.children[0]
    if isinstance(fname_node, bytes):
        fname = fname_node.decode('utf-8')
    else:
        fname = str(fname_node)
    fname = fname.strip()

    # 获取类型定义
    ftype_node = node.children[1]
    _parse_type_def(ftype_node, fname, field_list)


def _parse_type_def(node, fname, field_list):
    """解析 TypeDef 节点"""
    if node.value != 'TypeDef':
        return

    # 获取类型名
    type_name_node = node.children[0]
    if isinstance(type_name_node, bytes):
        type_name = type_name_node.decode('utf-8')
    else:
        type_name = str(type_name_node)
    type_name = type_name.strip().lower()

    # 修改原因：类型系统扩展到 9 种，与 main_db._exec_create_table 保持同步
    if type_name == 'char':
        ftype = 0
        flen = int(node.children[1]) if len(node.children) > 1 else 10
    elif type_name in ('varchar', 'varstr'):
        ftype = 1
        flen = int(node.children[1]) if len(node.children) > 1 else 255
    elif type_name in ('int', 'integer'):
        ftype, flen = 2, 4
    elif type_name in ('float', 'real'):
        ftype, flen = 4, 8
    elif type_name == 'bit':
        ftype = 5
        flen = int(node.children[1]) if len(node.children) > 1 else 8
    elif type_name in ('bit varying', 'bitvaring'):
        ftype = 6
        flen = int(node.children[1]) if len(node.children) > 1 else 64
    elif type_name == 'date':
        ftype, flen = 7, 10
    elif type_name == 'time':
        ftype, flen = 8, 8
    else:
        print(f"不支持的字段类型: {type_name}")
        return

    field_list.append((fname, ftype, flen))


# --------------------------------
# Author: 但芸妍
# 新增：执行 INSERT INTO
# ---------------------------------
def execute_insert(schema_obj):
    """执行 INSERT INTO 语句"""
    tree = common_db.global_syn_tree
    if tree is None or tree.value != 'InsertStmt':
        print("不是 INSERT INTO 语句")
        return False

    # 获取表名（第1个子节点）
    table_name_node = tree.children[0]
    if isinstance(table_name_node, bytes):
        table_name = table_name_node.decode('utf-8')
    else:
        table_name = str(table_name_node)
    table_name = table_name.strip()

    # 获取值列表（第2个子节点）
    value_list_node = tree.children[1]

    # 递归解析值列表
    values = []
    _extract_values(value_list_node, values)

    # 检查表是否存在
    if not schema_obj.find_table(table_name.encode('utf-8')):
        print(f"表 '{table_name}' 不存在")
        return False

    # 插入数据
    try:
        storage = storage_db.Storage(table_name)
        if storage.insert_record(values):
            print(f"插入成功: {values}")
            del storage
            return True
        else:
            print(f"插入失败: {values}")
            del storage
            return False
    except Exception as e:
        print(f"插入错误: {e}")
        return False


def _extract_values(node, values):
    """递归解析 ValueList 节点"""
    if node.value != 'ValueList':
        return

    # 第一个子节点是 CONSTANT 值
    first_child = node.children[0]
    if isinstance(first_child, bytes):
        val = first_child.decode('utf-8')
    else:
        val = str(first_child)
    val = val.strip()
    # 去掉字符串的引号
    if val.startswith("'") and val.endswith("'"):
        val = val[1:-1]
    values.append(val)

    # 如果有第二个子节点（剩余的 ValueList），递归处理
    if len(node.children) > 1:
        second_child = node.children[1]
        _extract_values(second_child, values)


# --------------------------------
# Author: 但芸妍
# 新增：执行 DELETE FROM（删除表中所有数据）
# ---------------------------------
def execute_delete(schema_obj):
    """执行 DELETE FROM 语句（删除表中所有数据）"""
    tree = common_db.global_syn_tree
    if tree is None or tree.value != 'DeleteStmt':
        print("不是 DELETE FROM 语句")
        return False

    # 获取表名
    table_name_node = tree.children[0]
    if isinstance(table_name_node, bytes):
        table_name = table_name_node.decode('utf-8')
    else:
        table_name = str(table_name_node)
    table_name = table_name.strip()
    table_name_bytes = table_name.encode('utf-8')

    # 检查表是否存在
    if not schema_obj.find_table(table_name_bytes):
        print(f"表 '{table_name}' 不存在")
        return False

    # 获取字段信息
    original_field_list = schema_obj.headObj.tableFields.get(table_name_bytes, [])

    if not original_field_list:
        print(f"表 '{table_name}' 没有字段定义")
        return False

    # 转换字段名：bytes → 字符串，并去掉空格
    field_list = []
    for fname, ftype, flen in original_field_list:
        if isinstance(fname, bytes):
            fname = fname.decode('utf-8').strip()
        field_list.append((fname, ftype, flen))

    # 删除原数据文件
    storage_db.Storage.remove_table_file(table_name)

    # 重新创建空的表结构（使用转换后的 field_list）
    storage = storage_db.Storage(table_name_bytes, field_list=field_list)
    del storage

    print(f"表 '{table_name}' 的所有数据已删除")
    return True


# --------------------------------
# Author: 但芸妍
# 新增：执行 UPDATE SET
# ---------------------------------
def execute_update(schema_obj):
    """执行 UPDATE SET 语句"""
    tree = common_db.global_syn_tree
    if tree is None or tree.value != 'UpdateStmt':
        print("不是 UPDATE SET 语句")
        return False

    # 获取表名
    table_name_node = tree.children[0]
    if isinstance(table_name_node, bytes):
        table_name = table_name_node.decode('utf-8')
    else:
        table_name = str(table_name_node)
    table_name = table_name.strip()
    table_name_bytes = table_name.encode('utf-8')

    # 检查表是否存在
    if not schema_obj.find_table(table_name_bytes):
        print(f"表 '{table_name}' 不存在")
        return False

    # 获取 AssignList 节点
    assign_node = tree.children[1]

    # 解析要更新的字段和值
    update_field = assign_node.children[0]
    update_value = assign_node.children[1]

    if isinstance(update_field, bytes):
        update_field = update_field.decode('utf-8')
    else:
        update_field = str(update_field)
    update_field = update_field.strip()

    if isinstance(update_value, bytes):
        update_value = update_value.decode('utf-8')
    else:
        update_value = str(update_value)
    update_value = update_value.strip()
    if update_value.startswith("'") and update_value.endswith("'"):
        update_value = update_value[1:-1]

    # 获取 Cond 节点
    cond_node = tree.children[2]

    # 解析条件字段和值
    cond_field = cond_node.children[0].children[0]
    cond_value = cond_node.children[2].children[0]

    if isinstance(cond_field, bytes):
        cond_field = cond_field.decode('utf-8')
    else:
        cond_field = str(cond_field)
    cond_field = cond_field.strip()

    if isinstance(cond_value, bytes):
        cond_value = cond_value.decode('utf-8')
    else:
        cond_value = str(cond_value)
    cond_value = cond_value.strip()
    if cond_value.startswith("'") and cond_value.endswith("'"):
        cond_value = cond_value[1:-1]

    # 执行更新
    storage = storage_db.Storage(table_name)
    success, result = storage.update_record_by_field(
        cond_field, cond_value, update_field, update_value
    )
    del storage

    if success:
        print(f"成功更新 {result} 条记录")
    else:
        print(result)
    return success


# --------------------------------
# Author: 但芸妍
# 新增：执行 DROP TABLE
# ---------------------------------
def execute_drop(schema_obj):
    """执行 DROP TABLE 语句"""
    tree = common_db.global_syn_tree
    if tree is None or tree.value != 'DropStmt':
        print("不是 DROP TABLE 语句")
        return False

    # 获取表名
    table_name_node = tree.children[0]
    if isinstance(table_name_node, bytes):
        table_name = table_name_node.decode('utf-8')
    else:
        table_name = str(table_name_node)
    table_name = table_name.strip()
    table_name_bytes = table_name.encode('utf-8')

    # 检查表是否存在
    if not schema_obj.find_table(table_name_bytes):
        print(f"表 '{table_name}' 不存在")
        return False

    # 删除表（包括模式和数据）
    if schema_obj.delete_table(table_name_bytes):
        print(f"表 '{table_name}' 已删除")
        return True
    else:
        print(f"删除表 '{table_name}' 失败")
        return False


# --------------------------------
# Author: 郑许博雅
# 新增：执行 CREATE INDEX
# ---------------------------------
def execute_create_index(schema_obj):
    """执行 CREATE INDEX 语句"""
    tree = common_db.global_syn_tree
    if tree is None or tree.value != 'CreateIdxStmt':
        print("不是 CREATE INDEX 语句")
        return False

    # 获取索引名（可选，第0个子节点）
    if len(tree.children) > 0:
        index_name_node = tree.children[0]
        if isinstance(index_name_node, bytes):
            index_name = index_name_node.decode('utf-8')
        else:
            index_name = str(index_name_node)
        index_name = index_name.strip()
    else:
        index_name = None

    # 获取表名（第1个子节点）
    if len(tree.children) > 1:
        table_name_node = tree.children[1]
        if isinstance(table_name_node, bytes):
            table_name = table_name_node.decode('utf-8')
        else:
            table_name = str(table_name_node)
        table_name = table_name.strip()
    else:
        print("CREATE INDEX 语句缺少表名")
        return False
    
    table_name_bytes = table_name.encode('utf-8')

    # 获取字段名（第2个子节点）
    if len(tree.children) > 2:
        field_name_node = tree.children[2]
        if isinstance(field_name_node, bytes):
            field_name = field_name_node.decode('utf-8')
        else:
            field_name = str(field_name_node)
        field_name = field_name.strip()
    else:
        print("CREATE INDEX 语句缺少字段名")
        return False

    # 检查表是否存在
    if not schema_obj.find_table(table_name_bytes):
        print(f"表 '{table_name}' 不存在")
        return False

    # 创建索引
    if schema_obj.create_index(table_name_bytes, index_name, field_name):
        print(f"索引 '{index_name}' 创建成功在表 '{table_name}' 的 '{field_name}' 字段上")
        return True
    else:
        print(f"创建索引失败")
        return False
    
# --------------------------------
# Author: 郑许博雅
# 新增：检查表是否有索引
# ---------------------------------
def has_index(table_name, field_name=None):
    """检查表是否有索引，如果指定字段名则检查该字段是否有索引"""
    import os
    from index_db import Index
    
    index_file = table_name + '.ind'
    if not os.path.exists(index_file):
        return False
    
    if field_name is None:
        return True
    
    # 检查索引是否建立在指定字段上
    try:
        idx = Index(table_name)
        # 简单判断：如果索引文件存在且有数据，假设索引有效
        # 实际可以读取索引元数据来判断索引字段
        return True
    except:
        return False
    
# --------------------------------
# Author: 郑许博雅
# 新增：执行范围查询
# ---------------------------------
def execute_range_search(schema_obj):
    """执行范围查询"""
    import os
    from index_db import Index
    import storage_db
    
    tree = common_db.global_syn_tree
    if tree is None or tree.value != 'RangeSearchStmt':
        print("不是 RANGE SEARCH 语句")
        return False
    
    # 解析语法树节点
    # 节点结构: [start_key, end_key, table_name, column_name]
    children = tree.children
    
    if len(children) < 4:
        print("范围查询语句格式错误")
        return False
    
    start_key_node = children[0]
    end_key_node = children[1]
    table_name_node = children[2]
    column_name_node = children[3]
    
    # 获取值
    if isinstance(start_key_node, common_db.Node):
        start_key = start_key_node.children[0] if start_key_node.children else str(start_key_node)
    else:
        start_key = str(start_key_node)
    
    if isinstance(end_key_node, common_db.Node):
        end_key = end_key_node.children[0] if end_key_node.children else str(end_key_node)
    else:
        end_key = str(end_key_node)
    
    if isinstance(table_name_node, common_db.Node):
        table_name = table_name_node.children[0] if table_name_node.children else str(table_name_node)
    else:
        table_name = str(table_name_node)
    
    if isinstance(column_name_node, common_db.Node):
        column_name = column_name_node.children[0] if column_name_node.children else str(column_name_node)
    else:
        column_name = str(column_name_node)
    
    # 去除引号（如果有）
    start_key = start_key.strip().strip("'").strip('"')
    end_key = end_key.strip().strip("'").strip('"')
    table_name = table_name.strip()
    column_name = column_name.strip()
    
    print(f"\n范围查询: {table_name}.{column_name} BETWEEN '{start_key}' AND '{end_key}'")
    print("-" * 60)
    
    # 检查表是否存在
    table_name_bytes = table_name.encode('utf-8')
    if not schema_obj.find_table(table_name_bytes):
        print(f"表 '{table_name}' 不存在")
        return False
    
    # 检查索引是否存在
    index_file = table_name + '.ind'
    if not os.path.exists(index_file):
        print(f"索引文件不存在，请先创建索引")
        print(f"提示: 使用选项 13 创建索引")
        return False
    
    try:
        # 使用索引进行范围查询
        idx = Index(table_name)
        results = idx.range_search(start_key, end_key)
        
        if not results:
            print(f"未找到 {column_name} 在 [{start_key}, {end_key}] 范围内的记录")
            return True
        
        print(f"\n找到 {len(results)} 条记录:")
        print("=" * 80)
        
        # 获取完整的记录数据
        storage = storage_db.Storage(table_name)
        field_list = storage.getFieldList()
        
        # 打印表头
        headers = ["序号", "键值"]
        for fname, _, _ in field_list:
            fname_str = fname.decode('utf-8').strip() if isinstance(fname, bytes) else str(fname).strip()
            headers.append(fname_str)
        
        # 计算列宽
        col_widths = [6, 12]
        for h in headers[2:]:
            col_widths.append(max(len(h), 15))
        
        # 打印表头
        header_line = ""
        for i, h in enumerate(headers):
            header_line += f"{h:<{col_widths[i]}} "
        print(header_line)
        print("-" * sum(col_widths) + "-" * (len(headers) * 2))
        
        # 打印记录
        for i, (key_bytes, blk, off) in enumerate(results):
            try:
                record = storage.read_record_by_position(blk, off)
                if record:
                    # 转换键值
                    key_str = key_bytes.decode('utf-8').strip() if isinstance(key_bytes, bytes) else str(key_bytes).strip()
                    
                    # 构建行
                    row = [str(i+1), key_str]
                    for val in record:
                        if isinstance(val, bytes):
                            val = val.decode('utf-8').strip()
                        row.append(str(val))
                    
                    # 打印行
                    line = ""
                    for j, val in enumerate(row):
                        line += f"{val:<{col_widths[j]}} "
                    print(line)
                    
            except Exception as e:
                print(f"读取记录 {i+1} 失败: {e}")
        
        print("=" * 80)
        del storage
        del idx
        return True
        
    except Exception as e:
        print(f"范围查询失败: {e}")
        import traceback
        traceback.print_exc()
        return False

'''
# the following is to test the code
from_list1=['a','b','c','d','e','f','g']
tree_from=construct_from_node(from_list1)
where_list1=[('x.c','=','y.c'),('z','=','w')]
tree_where=construct_where_node(tree_from,where_list1)
sel_list1=['f1','f2']
syn_tree=construct_select_node(tree_where,sel_list1)
print extract_sfw_data()
'''


