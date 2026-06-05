#-----------------------------
# parser_db.py
# author: Jingyu Han   hjymail@163.com
# modified by:
#-------------------------------
# the module is to construct a syntax tree for a "select from where" SQL clause
# the output is a syntax tree
#----------------------------------------------------
import common_db

# the following two packages need to be installed by yourself
import ply.yacc as yacc 
import ply.lex as lex



from lex_db import tokens



#---------------------------------
# Query  : SFW
#   SWF  : SELECT SelList FROM FromList WHERE Condition
# SelList: TCNAME COMMA SelList
# SelList: TCNAME
#
# FromList:TCNAME COMMA FromList
# FromList:TCNAME
# Condition: TCNAME EQX CONSTANT
#---------------------------------



#------------------------------
# check the syntax tree
# input:
#       syntax tree
# output:
#       true or falise
#-----------------------------
def check_syn_tree(syn_tree):
    """
    功能：校验三种 SQL 语句（SELECT / CREATE TABLE / INSERT INTO）的语法树结构合法性。
    输入参数：syn_tree: common_db.Node，归约完成后的语法树根节点。
    返回值：bool，结构合法返回 True，否则返回 False。
    """
    if syn_tree is None:
        print('语法树为空，解析未生成任何节点')
        return False

    root_val = syn_tree.value

    # ── SELECT 语句校验 ──
    if root_val == 'Query':
        if not syn_tree.children or len(syn_tree.children) != 1:
            print('Query 节点应有且仅有一个 SFW 子节点')
            return False
        sfw_node = syn_tree.children[0]
        if sfw_node.value != 'SFW':
            print('Query 的子节点应为 SFW，实际为:', sfw_node.value)
            return False
        sfw_children = sfw_node.children
        if len(sfw_children) not in (4, 6):
            print('SFW 子节点数异常，期望 4 或 6，实际:', len(sfw_children))
            return False
        if sfw_children[0].value != 'SELECT' or sfw_children[2].value != 'FROM':
            print('SFW 前几个子节点应为 SELECT / FROM')
            return False
        if sfw_children[1].value != 'SelList' or sfw_children[3].value != 'FromList':
            print('SFW 应有 SelList 和 FromList')
            return False
        if not sfw_children[1].children or not sfw_children[3].children:
            print('SelList / FromList 不能为空')
            return False
        if len(sfw_children) == 6:
            if sfw_children[4].value != 'WHERE' or sfw_children[5].value != 'Cond':
                print('WHERE/Cond 节点类型错误')
                return False
            cond = sfw_children[5]
            if not cond.children or len(cond.children) != 3:
                print('Cond 子节点数应为 3')
                return False
        return True

    # ── CREATE TABLE 语句校验 ──
    if root_val == 'CreateStmt':
        if not syn_tree.children or len(syn_tree.children) < 2:
            print('CreateStmt 应至少有表名和字段列表两个子节点')
            return False
        # 子节点：[表名, FieldDefList]
        if syn_tree.children[1].value != 'FieldDefList':
            print('CreateStmt 第 2 个子节点应为 FieldDefList')
            return False
        if not syn_tree.children[1].children:
            print('FieldDefList 不能为空，至少需要一个字段')
            return False
        return True

    # ── INSERT INTO 语句校验 ──
    if root_val == 'InsertStmt':
        if not syn_tree.children or len(syn_tree.children) < 2:
            print('InsertStmt 应至少有表名和值列表两个子节点')
            return False
        if syn_tree.children[1].value != 'ValueList':
            print('InsertStmt 第 2 个子节点应为 ValueList')
            return False
        if not syn_tree.children[1].children:
            print('ValueList 不能为空')
            return False
        return True

    # 未知语句类型
    print('语法树根节点类型未知:', root_val)
    return False



# ============================================================
# 顶层规则 —— Statement 是多语句类型的入口（PLY 以首个产生式的左部为起始符号）
# 实验中所有 SQL 都归约到 Statement 节点，根节点类型即语句类型
# ============================================================

def p_statement_query(t):
    'Statement : Query'
    common_db.global_syn_tree = t[1]
    check_syn_tree(common_db.global_syn_tree)
    common_db.show(common_db.global_syn_tree)
    t[0] = t[1]

def p_statement_create(t):
    'Statement : CreateStmt'
    common_db.global_syn_tree = t[1]
    check_syn_tree(common_db.global_syn_tree)
    common_db.show(common_db.global_syn_tree)
    t[0] = t[1]

def p_statement_insert(t):
    'Statement : InsertStmt'
    common_db.global_syn_tree = t[1]
    check_syn_tree(common_db.global_syn_tree)
    common_db.show(common_db.global_syn_tree)
    t[0] = t[1]


#------------------------------
#(1) construct the node for query expression
#(2) check the tree
#(3) view the data in the tree
# input:
#       
# output:
#       the root node of syntax tree
#--------------------------------------      
def p_expr_query(t):
    'Query : SFW'
    
    t[0]=common_db.Node('Query',[t[1]])
    common_db.global_syn_tree=t[0]
    check_syn_tree(common_db.global_syn_tree)
    common_db.show(common_db.global_syn_tree)
    
    return t

#------------------------------
#(1) construct the node for WFW expression
# input:
#       
# output:
#       the nodes
#--------------------------------------   
def p_expr_swf(t):
    'SFW : SELECT SelList FROM FromList WHERE Cond'
    t[1]=common_db.Node('SELECT',None)
    t[3]=common_db.Node('FROM',None)
    t[5]=common_db.Node('WHERE',None)

    t[0]=common_db.Node('SFW',[t[1],t[2],t[3],t[4],t[5],t[6]])


    return t

# 实验2 ：支持 select * from students 无形如 where 的查询
def p_expr_swf_no_where(t):
    'SFW : SELECT SelList FROM FromList'
    t[1]=common_db.Node('SELECT',None)
    t[3]=common_db.Node('FROM',None)

    t[0]=common_db.Node('SFW',[t[1],t[2],t[3],t[4]])


    return t

#------------------------------
#construct the node for select list
# input:
#       
# output:
#       the nodes
#--------------------------------------   

# 实验2 ：支持 select * 通配符语法
def p_expr_sellist_star(t):
    'SelList : STAR'
    t[1]=common_db.Node('STAR',[t[1]])
    t[0]=common_db.Node('SelList',[t[1]])

    return t

def p_expr_sellist_first(t):
    'SelList : TCNAME COMMA SelList'
    
    
    t[1]=common_db.Node('TCNAME',[t[1]])
    
    t[2]=common_db.Node(',',None)
    t[0]=common_db.Node('SelList',[t[1],t[2],t[3]])
    
    return t

#------------------------------
#construct the node for select list expression
# input:
#       
# output:
#       the nodes
#--------------------------------------   
def p_expr_sellist_second(t):
    'SelList : TCNAME'
   
    t[1]=common_db.Node('TCNAME',[t[1]])
    t[0]=common_db.Node('SelList',[t[1]])
    
    return t


#---------------------------
#construct the node for from expression
# input:
#       
# output:
#       the nodes
#--------------------------------------   
def p_expr_fromlist_first(t):
    'FromList : TCNAME COMMA FromList'
    t[1]=common_db.Node('TCNAME',[t[1]])
    t[2]=common_db.Node(',',None)
    t[0]=common_db.Node('FromList',[t[1],t[2],t[3]])
    
    return t


#------------------------------
#(1) construct the node for from expression
# input:
#       
# output:
#       the nodes
#--------------------------------------           
def p_expr_fromlist_second(t):
    'FromList : TCNAME'
    t[1]=common_db.Node('TCNAME',[t[1]])
    t[0]=common_db.Node('FromList',[t[1]])    
    return t
        
#------------------------------
#construct the node for condition expression
# input:
#       
# output:
#       the nodes
#--------------------------------------   
def p_expr_condition(t):
    'Cond : TCNAME EQX CONSTANT'
    t[1]=common_db.Node('TCNAME',[t[1]])
    t[2]=common_db.Node('=',None)
    t[3]=common_db.Node('CONSTANT',[t[3]])
    
    t[0]=common_db.Node('Cond',[t[1],t[2],t[3]])
    
    return t 


# ============================================================
# 实验2 选做：CREATE TABLE 语法规则
# CREATE TABLE 表名 (字段名 类型(长度), ...)
# ============================================================

def p_create_stmt(t):
    '''CreateStmt : CREATE TABLE TCNAME LPAREN FieldDefList RPAREN'''
    t[0] = common_db.Node('CreateStmt', [t[3], t[5]])


def p_field_def_list_one(t):
    '''FieldDefList : FieldDef'''
    t[0] = common_db.Node('FieldDefList', [t[1]])


def p_field_def_list_multi(t):
    '''FieldDefList : FieldDef COMMA FieldDefList'''
    t[0] = common_db.Node('FieldDefList', [t[1]] + t[3].children)


def p_field_def(t):
    '''FieldDef : TCNAME TypeDef'''
    t[0] = common_db.Node('FieldDef', [t[1], t[2]])


def p_type_def_char(t):
    '''TypeDef : CHAR LPAREN CONSTANT RPAREN'''
    t[0] = common_db.Node('TypeDef', [t[1], t[3]])


def p_type_def_integer(t):
    '''TypeDef : INTEGER'''
    t[0] = common_db.Node('TypeDef', [t[1]])


# ============================================================
# 实验2 选做：INSERT INTO 语法规则
# INSERT INTO 表名 VALUES(值1, 值2, ...)
# ============================================================

def p_insert_stmt(t):
    '''InsertStmt : INSERT INTO TCNAME VALUES LPAREN ValueList RPAREN'''
    t[0] = common_db.Node('InsertStmt', [t[3], t[6]])


def p_value_list_one(t):
    '''ValueList : CONSTANT'''
    t[0] = common_db.Node('ValueList', [t[1]])


def p_value_list_multi(t):
    '''ValueList : CONSTANT COMMA ValueList'''
    t[0] = common_db.Node('ValueList', [t[1]] + t[3].children)


#------------------------------
# for error
# input:
#       
# output:
#       the error messages
#--------------------------------------   
def p_error(t):
    print ('wrong at %s'% t.value)


#------------------------------------------
# to set the global_parser handle in common_db.py
#---------------------------------------------    
def set_handle():    
    common_db.global_parser=yacc.yacc(write_tables=0)
    if common_db.global_parser is None:
        print ('wrong when yacc object is created')

        
    
# the following is to test
'''
# the following is to test
my_str="select f1,f2 from t1,t2 where f1=9"
my_parser=yacc.yacc(write_tables=0)# the tabl does not cache
my_parser.parse(my_str)
'''

