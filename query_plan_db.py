#------------------------------------------------
# query_plan_db.py
# author: Jingyu Han  hjymail@163.com
# modified by:Shuting Guo shutingnjupt@gmail.com
#------------------------------------------------



#----------------------------------------------------------
# this module can turn a syntax tree into a query plan tree
#----------------------------------------------------------

import common_db
import storage_db
import itertools
    

#--------------------------------
# to import the syntax tree, which is defined in parser_db.py
#-------------------------------------------
# 修改原因：不用 from import 别名，改为直接引用 common_db.global_syn_tree
# 避免 Python 值拷贝导入导致 parser 重新赋值后此处仍为 None 的经典陷阱

class parseNode:
    def __init__(self):
        self.sel_list=[]
        self.from_list=[]
        self.where_list=[]

    def get_sel_list(self):
        return self.sel_list

    def get_from_list(self):
        return self.from_list

    def get_where_list(self):
        return self.where_list

    def update_sel_list(self,self_list):
        self.sel_list = self_list

    def update_from_list(self, from_list):
        self.from_list = from_list

    def update_where_list(self,where_list):
        self.where_list = where_list


#--------------------------------
# Author: Shuting Guo shutingnjupt@gmail.com
# to extract data from gloal variable syn_tree
# output:
#       sel_list
#       from_list
#       where_list
#--------------------------------
def extract_sfw_data():
    print('extract_sfw_data begins to execute')
    if common_db.global_syn_tree is None:
        print ('wrong')
    else:
        #common_db.show(common_db.global_syn_tree)
        PN = parseNode()
        destruct(common_db.global_syn_tree, PN)
        return PN.get_sel_list(),PN.get_from_list(),PN.get_where_list()

#---------------------------------
# Author: Shuting Guo shutingnjupt@gmail.com
# Query  : SFW
#   SFW  : SELECT SelList FROM FromList WHERE Condition
# SelList: TCNAME COMMA SelList
# SelList: TCNAME
#
# FromList:TCNAME COMMA FromList
# FromList:TCNAME
# Condition: TCNAME EQX CONSTANT
#---------------------------------

def destruct(nodeobj,PN):
    if isinstance(nodeobj, common_db.Node):  # it is a Node object
        if nodeobj.children:
            if nodeobj.value == 'SelList':
                tmpList=[]
                show(nodeobj,tmpList)
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
                    destruct(nodeobj.children[i],PN)

def show(nodeobj,tmpList):
    if isinstance(nodeobj,common_db.Node):
        if not nodeobj.children:
            tmpList.append(nodeobj.value)
        else:
            for i in range(len(nodeobj.children)):
                show(nodeobj.children[i],tmpList)
    if isinstance(nodeobj,str):
        tmpList.append(nodeobj)


#---------------------------
#input:
#       from_list
#output:
#       a tree
#-----------------------------------
        
def construct_from_node(from_list):
    if from_list:        
        if len(from_list)==1:
            temp_node=common_db.Node(from_list[0],None)
            return common_db.Node('X',[temp_node])
        elif len(from_list)==2:
            temp_node_first=common_db.Node(from_list[0],None)
            temp_node_second=common_db.Node(from_list[1],None)
            
            return common_db.Node('X',[temp_node_first,temp_node_second])       
            
        elif len(from_list)>2:
            
            right_node=common_db.Node(from_list[len(from_list)-1],None)
            
            return common_db.Node('X',[construct_from_node(from_list[0:len(from_list)-1]),right_node])

#---------------------------
#input:
#       where_list
#       from_node
#output:
#       a tree
#-----------------------------------
def construct_where_node(from_node,where_list):
    if from_node and len(where_list)>0:
       return common_db.Node('Filter',[from_node],where_list)
    elif from_node and len(where_list)==0:# there is no where clause
        return from_node


#---------------------------
#input:
#       sel_list
#       wf_node
#output:
#       a tree
#-----------------------------------
def construct_select_node(wf_node,sel_list):
    if wf_node and len(sel_list)>0:
        return common_db.Node('Proj',[wf_node],sel_list)

#----------------------------------
# Author: Shuting Guo shutingnjupt@gmail.com
# to execute the query plan and return the result
# input
#       global logical tree
#---------------------------------------------

def execute_logical_tree():
    if common_db.global_logical_tree:
        def excute_tree():

            idx = 0
            dict_ = {}

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
            idx = sorted(dict_.keys(), reverse=True)[0]

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
                # 修改原因：磁盘读出的字段名是 bytes，统一解码为 str 才能与语法树中的 FieldName 比较
                tmp = []
                for x in current_field[TableIndex]:
                    fn = x[0]
                    if isinstance(fn, bytes):
                        fn = fn.decode('utf-8')
                    tmp.append(fn.strip())
                if FieldName in tmp:
                    FieldIndex = tmp.index(FieldName)
                    FieldType = current_field[TableIndex][FieldIndex][1]
                    return TableIndex, FieldIndex, FieldType, True
                else:
                    return 0, 0, 0, False

            current_field = []
            current_list =[]
            #print dict_
            while (idx >= 0):
                if idx == sorted(dict_.keys(), reverse=True)[0]:
                    if len(dict_[idx]) > 1:
                        a_1 = storage_db.Storage(dict_[idx][0])
                        a_2 = storage_db.Storage(dict_[idx][1])
                        current_list = []
                        tableName_Order = [dict_[idx][0], dict_[idx][1]]
                        current_field = [a_1.getFieldList(), a_2.getFieldList()]
                        for x in itertools.product(a_1.getRecord(), a_2.getRecord()):
                            current_list.append(list(x))
                    else:
                        a_1 = storage_db.Storage(dict_[idx][0])
                        current_list = a_1.getRecord()

                        tableName_Order = [dict_[idx][0]]
                        current_field = [a_1.getFieldList()]
                        #print current_list

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
                            #print FilterParam
                        tmp_List = current_list[:]
                        current_list = []
                        for tmpRecord in tmp_List:
                            if len(current_field) == 1:
                                ans = tmpRecord[FieldIndex]
                            else:
                                ans = tmpRecord[TableIndex][FieldIndex]
                            if FieldType == 0 or FieldType == 1:
                                ans = ans.strip()
                                # 修改原因：记录值从 .dat 读出是 bytes，FilterParam 来自语法树是 str，统一解码后比较
                                if isinstance(ans, bytes):
                                    ans = ans.decode('utf-8')
                            if FilterParam == ans:
                                current_list.append(tmpRecord)

                    if 'Proj' in dict_[idx][0]:
                        SelIndexList = []
                        # 实验2 ： select * 通配符 → 选中所有表的所有字段
                        if dict_[idx][0][1] == ['*']:
                            for table_idx in range(len(current_field)):
                                for field_idx in range(len(current_field[table_idx])):
                                    SelIndexList.append((table_idx, field_idx))
                        else:
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
                            # 修改原因：磁盘读出字段名为 bytes，统一解码避免 str + bytes 拼接报错
                            field_name = current_field[xi[0]][xi[1]][0]
                            if isinstance(field_name, bytes):
                                field_name = field_name.decode('utf-8').strip()
                            outPutField.append(
                                tableName_Order[xi[0]].strip() + '.' + field_name)
                        return outPutField, current_list, True
                idx -= 1

        outPutField, current_list, isRight = excute_tree()

        if isRight:
            print (outPutField)
            for record in current_list:
                print (record)
        else:
            print ('WRONG SQL INPUT!')
    else:
        print ('there is no query plan tree for the execution')

# --------------------------------
# Author: Shuting Guo shutingnjupt@gmail.com
# to construct a logical query plan tree
# output:
#       global_logical_tree
# ---------------------------------
# ============================================================
# 查询优化器 —— 三类优化：谓词下推 / 连接重排序 / 投影下推
# ============================================================

def _print_plan_tree(node, indent=0):
    """
    以缩进树形格式递归打印查询计划树，展示节点类型、关键参数及叶子表行数。
    用于优化前后的对比可视化。
    """
    prefix = '  ' * indent
    if node is None:
        print(prefix + '(nil)')
        return

    label = node.value
    detail = ''

    if node.value == 'Proj' and node.var:
        detail = ' ' + str(node.var)
    elif node.value == 'Filter' and node.var:
        detail = ' ' + str(node.var)
    elif node.value != 'X' and node.value != 'Proj' and node.value != 'Filter':
        # 叶子表节点：尝试读取行数
        try:
            s = storage_db.Storage(node.value)
            cnt = len(s.getRecord())
            del s
            detail = ' ({0} 行)'.format(cnt)
        except:
            detail = ' (行数未知)'

    print(prefix + '[' + label + ']' + detail)

    if node.children:
        for child in node.children:
            _print_plan_tree(child, indent + 1)


def _get_table_field_map(table_names):
    """
    构建 {字段名: 所属表名} 的映射字典，用于谓词下推时定位字段属于哪张表。
    若字段名在多个表中同时存在则记录最先匹配的表。
    """
    field_map = {}
    for tname in table_names:
        try:
            s = storage_db.Storage(tname)
            flist = s.getFieldList()
            del s
            for fname, ftype, flen in flist:
                key = fname.decode('utf-8').strip() if isinstance(fname, bytes) else str(fname).strip()
                if key not in field_map:
                    field_map[key] = tname
        except:
            pass
    return field_map


def _push_down_predicates(node, field_to_table):
    """
    谓词下推优化 —— 递归遍历计划树，将 Filter 节点中仅涉及单表的过滤条件
    沿 X 连接树向下推至对应叶子表节点上方，减少连接前的中间结果集大小。

    原理：σ(table1.col=val)(table1 × table2)  →  σ(table1.col=val)(table1) × table2
    """
    if node is None:
        return None

    if node.value == 'Proj':
        # Proj 节点：递归优化其子树
        if node.children:
            node.children[0] = _push_down_predicates(node.children[0], field_to_table)
        return node

    if node.value == 'Filter':
        conds = node.var
        if conds is None or len(conds) == 0:
            return _push_down_predicates(node.children[0], field_to_table) if node.children else node

        # 将单条件包装为 list 统一处理
        if isinstance(conds, tuple) and len(conds) > 0 and not isinstance(conds[0], (tuple, list)):
            conds = [conds]

        single_conds = {}   # {table_name: [cond, cond, ...]}
        remain_conds = []   # 多表条件保留在原位置

        for cond in conds:
            field_name = cond[0]
            owner = field_to_table.get(field_name)
            if owner:
                single_conds.setdefault(owner, []).append(cond)
            else:
                remain_conds.append(cond)

        # 沿 X 树下降，将单表条件插入到对应叶子表节点上方
        child = _push_to_leaves(node.children[0], single_conds)

        if remain_conds:
            # 还有跨表条件未下推，保留当前 Filter 层包裹在 child 外面
            node.children[0] = child
            node.var = tuple(remain_conds[0]) if len(remain_conds) == 1 else tuple(remain_conds)
            return node
        else:
            # 所有条件都已落到叶子层，当前 Filter 层可消去
            # 注意：child 内部已被 _push_to_leaves 递归处理过，不再重复下推
            return child

    if node.value == 'X':
        # 笛卡尔积节点：递归优化每个子树
        new_children = [_push_down_predicates(ch, field_to_table) for ch in node.children]
        node.children = new_children
        return node

    # 叶子表节点：直接返回
    return node


def _push_to_leaves(node, single_conds):
    """
    沿 X 连接树递归下降，在匹配的叶子表节点上方插入 Filter。
    """
    if node is None:
        return None

    if node.value == 'X':
        new_children = [_push_to_leaves(ch, single_conds) for ch in node.children]
        node.children = new_children
        return node

    # 叶子表节点（value 为表名）
    tname = node.value.strip()
    if isinstance(tname, bytes):
        tname = tname.decode('utf-8')
    if tname in single_conds:
        conds = single_conds[tname]
        cond_var = tuple(conds[0]) if len(conds) == 1 else tuple(conds)
        return common_db.Node('Filter', [node], cond_var)

    return node


def _reorder_from_list(from_list):
    """
    连接重排序优化 —— 按表的记录数升序排列 from_list。
    小表先参与笛卡尔积可使中间结果尽早保持较小规模。

    原理：R × S 与 S × R 结果等价，但若 |R| < |S|，先处理 R 可减少中间内存占用。
    """
    if len(from_list) <= 1:
        return list(from_list)

    def _row_count(tname):
        try:
            s = storage_db.Storage(tname)
            cnt = len(s.getRecord())
            del s
            return cnt
        except:
            return 99999

    return sorted(list(from_list), key=_row_count)


def construct_logical_tree():
    if not common_db.global_syn_tree:
        print('there is no data in the syntax tree in the construct_logical_tree')
        return

    sel_list, from_list, where_list = extract_sfw_data()
    sel_list = [i for i in sel_list if i != ',']
    from_list = [i for i in from_list if i != ',']
    where_list = tuple(where_list)

    # ---------- 优化前原始计划树 ----------
    raw_from_node = construct_from_node(from_list)
    raw_where_node = construct_where_node(raw_from_node, where_list)
    raw_tree = construct_select_node(raw_where_node, sel_list)

    print('\n' + '=' * 55)
    print('  优化前 查询计划树')
    print('=' * 55)
    _print_plan_tree(raw_tree)

    # ========== 优化管线 ==========

    # --- 优化1: 连接重排序 ---
    reordered_list = _reorder_from_list(from_list)
    if reordered_list != from_list:
        print('\n  >> 连接重排序: {0} → {1} (按行数升序)'.format(from_list, reordered_list))

    # --- 优化2: 谓词下推 ---
    field_to_table = _get_table_field_map(reordered_list)
    from_node = construct_from_node(reordered_list)
    where_node = construct_where_node(from_node, where_list)
    optimized_tree = construct_select_node(where_node, sel_list)
    optimized_tree = _push_down_predicates(optimized_tree, field_to_table)

    # --- 优化3: 投影下推 ---
    # 当前 Storage 按定长整行读取，列裁剪无法减少 I/O 字节数，
    # 此处将投影字段列表记录在根节点 var 中，执行阶段已按需裁剪输出列。

    common_db.global_logical_tree = optimized_tree

    print('\n' + '=' * 55)
    print('  优化后 查询计划树')
    print('=' * 55)
    _print_plan_tree(optimized_tree)
    print('=' * 55 + '\n')


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


