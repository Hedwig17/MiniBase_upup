#----------------------------------------
# common_db.py
# author: Jingyu Han   hjymail@163.com
# modified by: 胡丹
#--------------------------------------------
# the module provides the constants, class, data structures which
# are used for all the program
#--------------------------------------------------
BLOCK_SIZE=4096  # 磁盘块固定大小（字节），所有 I/O 以块为单位进行

global_lexer=None    # PLY lex 对象，由 lex_db.set_lex_handle() 初始化
global_parser=None   # PLY yacc 对象，由 parser_db.set_handle() 初始化
global_syn_tree=None  # SELECT/CREATE/INSERT 语法树根节点，parser 归约完成后赋值
global_logical_tree=None  # 查询计划树根节点，query_plan_db.construct_logical_tree() 构建

#-----------------------------
# 树节点类 —— 用于存储语法树和查询计划树，支持多叉树递归遍历
#---------------------------------
class Node:
    def __init__(self, value, children, varList=None):
        """
        功能：构造一个树节点，value 为节点类型标识，children 为子节点列表，varList 为额外参数
        输入参数：value: str，节点类型（如 'Query' 'SFW' 'Proj' 'Filter' 'X'）；
                 children: list，子节点列表，可为 None；
                 varList: any，附加数据（Filter 存条件元组，Proj 存投影字段列表）
        """
        self.value = value
        self.var = varList
        # 修改原因：children 入参可能为 None（叶子节点），统一转为空列表避免遍历时报错
        if children:
            self.children = children
        else:
            self.children = []


#-------------------------
# 递归遍历并打印语法树 / 查询计划树的所有节点
#---------------------------
def show(node_obj):
    """
    功能：深度优先遍历树结构，逐层打印节点值和附加参数，用于调试查看语法树和计划树
    输入参数：node_obj: Node 或 str，树节点或叶子字符串
    """
    if isinstance(node_obj, Node):
        print(node_obj.value)
        if node_obj.var:
            print(node_obj.var)
        if node_obj.children:
            for i in range(len(node_obj.children)):
                show(node_obj.children[i])
    if isinstance(node_obj, str):
        print(node_obj)


