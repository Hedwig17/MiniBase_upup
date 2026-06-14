# -----------------------------
# parser_db.py
# author: Jingyu Han   hjymail@163.com
# modified by:但芸妍
# -------------------------------
# the module is to construct a syntax tree for a "select from where" SQL clause
# the output is a syntax tree
# ----------------------------------------------------
import common_db

# the following two packages need to be installed by yourself
import ply.yacc as yacc
import ply.lex as lex

from lex_db import tokens

'''
    p_ 前缀告诉 PLY 这是一个语法规则函数
'''

# ---------------------------------
# Query  : SFW
#   SWF  : SELECT SelList FROM FromList WHERE Condition
# SelList: TCNAME COMMA SelList
# SelList: TCNAME
#
# FromList:TCNAME COMMA FromList
# FromList:TCNAME
# Condition: TCNAME EQX CONSTANT
# ---------------------------------


# ------------------------------
# check the syntax tree
# input:
#       syntax tree
# output:
#       true or falise
# -----------------------------
def check_syn_tree(syn_tree):
    if syn_tree:
        pass


# ============================================================
# Author: 但芸妍
# 新增：Statement 顶层规则（新增，支持多种语句）
# ============================================================

def p_statement_query(t):
    'Statement : Query'
    common_db.global_syn_tree = t[1]
    check_syn_tree(common_db.global_syn_tree)
    t[0] = t[1]

def p_statement_create(t):
    'Statement : CreateStmt'
    common_db.global_syn_tree = t[1]
    check_syn_tree(common_db.global_syn_tree)
    t[0] = t[1]

def p_statement_insert(t):
    'Statement : InsertStmt'
    common_db.global_syn_tree = t[1]
    check_syn_tree(common_db.global_syn_tree)
    t[0] = t[1]

def p_statement_delete(t):
    'Statement : DeleteStmt'
    common_db.global_syn_tree = t[1]
    check_syn_tree(common_db.global_syn_tree)
    t[0] = t[1]

def p_statement_update(t):
    'Statement : UpdateStmt'
    common_db.global_syn_tree = t[1]
    check_syn_tree(common_db.global_syn_tree)
    t[0] = t[1]

def p_statement_drop(t):
    'Statement : DropStmt'
    common_db.global_syn_tree = t[1]
    check_syn_tree(common_db.global_syn_tree)
    t[0] = t[1]

def p_statement_range(t):
    'Statement : RangeSearchStmt'
    common_db.global_syn_tree = t[1]
    check_syn_tree(common_db.global_syn_tree)
    t[0] = t[1]

# ------------------------------
# (1) construct the node for query expression
# (2) check the tree
# (3) view the data in the tree
# input:
#
# output:
#       the root node of syntax tree
# --------------------------------------
def p_expr_query(t):
    'Query : SFW'  # 1、文档字符串：定义语法规则（Select-From-Where）

    # t[0] 代表当前规则（Query），我们需要为它赋值
    # t[1] 代表规则右边的第一个符号，也就是 SFW 的值
    t[0] = common_db.Node('Query', [t[1]])
    common_db.global_syn_tree = t[0]
    check_syn_tree(common_db.global_syn_tree)
    common_db.show(common_db.global_syn_tree)

    return t


# ------------------------------
# (1) construct the node for WFW expression
# input:
#
# output:
#       the nodes
# --------------------------------------
def p_expr_swf(t):
    'SFW : SELECT SelList FROM FromList WHERE Cond'
    t[1] = common_db.Node('SELECT', None)
    t[3] = common_db.Node('FROM', None)
    t[5] = common_db.Node('WHERE', None)

    t[0] = common_db.Node('SFW', [t[1], t[2], t[3], t[4], t[5], t[6]])

    return t

# 修改：支持没有 WHERE 子句的查询
def p_expr_swf_no_where(t):
    'SFW : SELECT SelList FROM FromList'
    t[1] = common_db.Node('SELECT', None)
    t[3] = common_db.Node('FROM', None)

    t[0] = common_db.Node('SFW', [t[1], t[2], t[3], t[4]])

    return t

# ------------------------------
# construct the node for select list
# input:
#
# output:
#       the nodes
# --------------------------------------

'''
    多字段
'''
def p_expr_sellist_first(t):
    'SelList : TCNAME COMMA SelList'

    t[1] = common_db.Node('TCNAME', [t[1]])

    t[2] = common_db.Node(',', None)
    t[0] = common_db.Node('SelList', [t[1], t[2], t[3]])

    return t


# ------------------------------
# construct the node for select list expression
# input:
#
# output:
#       the nodes
# --------------------------------------
'''
    一个字段
'''
def p_expr_sellist_second(t):
    'SelList : TCNAME'

    t[1] = common_db.Node('TCNAME', [t[1]])
    t[0] = common_db.Node('SelList', [t[1]])

    return t

'''
    修改：支持 select *
'''
def p_expr_sellist_star(t):
    'SelList : STAR'
    t[1] = common_db.Node('STAR', [t[1]])
    t[0] = common_db.Node('SelList', [t[1]])
    return t

# ---------------------------
# construct the node for from expression
# input:
#
# output:
#       the nodes
# --------------------------------------
def p_expr_fromlist_first(t):
    'FromList : TCNAME COMMA FromList'
    t[1] = common_db.Node('TCNAME', [t[1]])
    t[2] = common_db.Node(',', None)
    t[0] = common_db.Node('FromList', [t[1], t[2], t[3]])
    return t


# ------------------------------
# (1) construct the node for from expression
# input:
#
# output:
#       the nodes
# --------------------------------------
def p_expr_fromlist_second(t):
    'FromList : TCNAME'
    t[1] = common_db.Node('TCNAME', [t[1]])
    t[0] = common_db.Node('FromList', [t[1]])
    return t


# ------------------------------
# construct the node for condition expression
# input:
#
# output:
#       the nodes
# --------------------------------------
def p_expr_condition(t):
    'Cond : TCNAME EQX CONSTANT'
    t[1] = common_db.Node('TCNAME', [t[1]])
    t[2] = common_db.Node('=', None)
    t[3] = common_db.Node('CONSTANT', [t[3]])

    t[0] = common_db.Node('Cond', [t[1], t[2], t[3]])

    return t


# ============================================================
# Author: 但芸妍
# 新增：CREATE TABLE
# create table students (s_id char(3), name varstr(10), age integer)
'''
    CreateStmt
    ├── 'courses'
    └── FieldDefList
         ├── FieldDef
         │    ├── 'c_id'
         │    └── TypeDef
         │         ├── 'char'
         │         └── '20'
         ...
'''
# ============================================================

def p_create_stmt(t):
    'CreateStmt : CREATE TABLE TCNAME LPAREN FieldDefList RPAREN'
    t[0] = common_db.Node('CreateStmt', [t[3], t[5]])

def p_field_def_list_one(t):
    'FieldDefList : FieldDef'
    t[0] = common_db.Node('FieldDefList', [t[1]])

def p_field_def_list_multi(t):
    'FieldDefList : FieldDef COMMA FieldDefList'
    t[0] = common_db.Node('FieldDefList', [t[1], t[3]])

def p_field_def(t):
    'FieldDef : TCNAME TypeDef'
    t[0] = common_db.Node('FieldDef', [t[1], t[2]])

def p_type_def_char(t):
    'TypeDef : CHAR LPAREN CONSTANT RPAREN'
    t[0] = common_db.Node('TypeDef', [t[1], t[3]])

def p_type_def_integer(t):
    'TypeDef : INTEGER'
    t[0] = common_db.Node('TypeDef', [t[1]])

# 修改原因：类型系统扩展到 9 种，新增 varchar / int / float / real / bit / bit varying / date / time
def p_type_def_varchar(t):
    'TypeDef : VARCHAR LPAREN CONSTANT RPAREN'
    t[0] = common_db.Node('TypeDef', [t[1], t[3]])

def p_type_def_int(t):
    'TypeDef : INT'
    t[0] = common_db.Node('TypeDef', [t[1]])

def p_type_def_float(t):
    'TypeDef : FLOAT'
    t[0] = common_db.Node('TypeDef', [t[1]])

def p_type_def_real(t):
    'TypeDef : REAL'
    t[0] = common_db.Node('TypeDef', [t[1]])

def p_type_def_bit(t):
    'TypeDef : BIT LPAREN CONSTANT RPAREN'
    t[0] = common_db.Node('TypeDef', [t[1], t[3]])

def p_type_def_bitvarying(t):
    'TypeDef : BIT VARBIT LPAREN CONSTANT RPAREN'
    t[0] = common_db.Node('TypeDef', [t[1], t[4]])

def p_type_def_date(t):
    'TypeDef : DATE'
    t[0] = common_db.Node('TypeDef', [t[1]])

def p_type_def_time(t):
    'TypeDef : TIME'
    t[0] = common_db.Node('TypeDef', [t[1]])

def p_statement_create_idx(t):
    'Statement : CreateIdxStmt'
    common_db.global_syn_tree = t[1]
    t[0] = t[1]


# ============================================================
# Author: 但芸妍
# 新增：INSERT INTO 语句
# ============================================================

def p_insert_stmt(t):
    'InsertStmt : INSERT INTO TCNAME VALUES LPAREN ValueList RPAREN'
    t[0] = common_db.Node('InsertStmt', [t[3], t[6]])

def p_value_list_one(t):
    'ValueList : CONSTANT'
    t[0] = common_db.Node('ValueList', [t[1]])

def p_value_list_multi(t):
    'ValueList : CONSTANT COMMA ValueList'
    t[0] = common_db.Node('ValueList', [t[1] , t[3]])


# ============================================================
# Author: 但芸妍
# 新增：DELETE FROM 语句
# ============================================================

def p_delete_stmt(t):
    'DeleteStmt : DELETE FROM TCNAME'
    t[0] = common_db.Node('DeleteStmt', [t[3]])


# ============================================================
# Author: 但芸妍
# 新增：UPDATE SET 语句
# ============================================================

def p_update_stmt(t):
    'UpdateStmt : UPDATE TCNAME SET AssignList WHERE Cond'
    t[0] = common_db.Node('UpdateStmt', [t[2], t[4], t[6]])

def p_assign_list_one(t):
    'AssignList : TCNAME EQX CONSTANT'
    t[0] = common_db.Node('AssignList', [t[1], t[3]])

def p_assign_list_multi(t):
    'AssignList : TCNAME EQX CONSTANT COMMA AssignList'
    t[0] = common_db.Node('AssignList', [t[1], t[3], t[5]])


# ============================================================
# Author: 但芸妍
# 新增：DROP TABLE 语句
# ============================================================

def p_drop_stmt(t):
    'DropStmt : DROP TABLE TCNAME'
    t[0] = common_db.Node('DropStmt', [t[3]])

# ============================================================
# Author: 郑许博雅
# 新增：CREATE INDEX 语句
# ============================================================

def p_create_idx_stmt(t):
    'CreateIdxStmt : CREATE INDEX TCNAME ON TCNAME LPAREN TCNAME RPAREN'
    # t[1]=CREATE, t[2]=INDEX, t[3]=索引名, t[4]=ON, t[5]=表名, t[6]=LPAREN, t[7]=字段名, t[8]=RPAREN
    index_name = t[3]   # 索引名
    table_name = t[5]   # 表名
    field_name = t[7]   # 字段名
    t[0] = common_db.Node('CreateIdxStmt', [index_name, table_name, field_name])


# ============================================================
# Author: 郑许博雅
# 新增：RANGE SEARCH 语句
# 语法：SELECT * FROM table_name WHERE column_name BETWEEN start_key AND end_key
# ============================================================

def p_range_search_stmt(t):
    '''RangeSearchStmt : SELECT STAR FROM TCNAME WHERE TCNAME BETWEEN CONSTANT AND CONSTANT'''
    # t[1]=SELECT, t[2]=STAR, t[3]=FROM, t[4]=table_name, t[5]=WHERE, 
    # t[6]=column_name, t[7]=BETWEEN, t[8]=start_key, t[9]=AND, t[10]=end_key
    table_name = t[4]
    column_name = t[6]
    start_key = t[8]
    end_key = t[10]
    t[0] = common_db.Node('RangeSearchStmt', [start_key, end_key, table_name, column_name])


# ------------------------------
# for error
# input:
#
# output:
#       the error messages
# --------------------------------------
def p_error(t):
    print('wrong at %s' % t.value)


# ------------------------------------------
# to set the global_parser handle in common_db.py
# 创建并设置一个全局的语法分析器对象，供整个程序使用
# ---------------------------------------------
def set_handle():
    if common_db.global_parser is not None:
        return  # 已经创建过了，直接返回

    common_db.global_parser = yacc.yacc(start='Statement', write_tables=0)
    if common_db.global_parser is None:
        print('wrong when yacc object is created')


# the following is to test
'''
# the following is to test
my_str="select f1,f2 from t1,t2 where f1=9"
my_parser=yacc.yacc(write_tables=0)# the tabl does not cache
my_parser.parse(my_str)

'''

# ------------------------------
# Author: 郑许博雅
# 调试函数：打印语法树结构
# ------------------------------
def debug_print_tree(node, indent=0):
    """递归打印语法树结构，用于调试"""
    if node is None:
        print("  " * indent + "None")
        return
    
    prefix = "  " * indent
    if isinstance(node, common_db.Node):
        print(f"{prefix}Node: {node.value}")
        if node.children:
            print(f"{prefix}  children: {len(node.children)}")
            for i, child in enumerate(node.children):
                print(f"{prefix}  child[{i}]:")
                debug_print_tree(child, indent + 2)
    else:
        print(f"{prefix}Leaf: {node} (type: {type(node).__name__})")


def test_parse(sql):
    """测试解析 SQL 语句并打印语法树"""
    print(f"\n{'='*60}")
    print(f"测试解析: {sql}")
    print(f"{'='*60}")
    
    # 设置词法分析器
    import lex_db
    if common_db.global_lexer is None:
        lex_db.set_lex_handle()
    
    # 设置语法分析器
    if common_db.global_parser is None:
        set_handle()
    
    # 执行解析
    try:
        common_db.global_lexer.input(sql)
        result = common_db.global_parser.parse(sql)
        
        if result is None:
            print("解析结果: None (解析失败)")
            return None
        
        print(f"解析结果类型: {type(result).__name__}")
        if isinstance(result, common_db.Node):
            print(f"根节点值: {result.value}")
            print(f"子节点数量: {len(result.children) if result.children else 0}")
            print("\n语法树结构:")
            debug_print_tree(result)
        else:
            print(f"解析结果: {result}")
        
        # 将结果存入全局变量
        common_db.global_syn_tree = result
        return result
    except Exception as e:
        print(f"解析异常: {e}")
        import traceback
        traceback.print_exc()
        return None
    
  

# ========== 调试代码（直接运行测试）==========
if __name__ == '__main__':
    import lex_db
    
    print("=" * 60)
    print("测试 CREATE INDEX 解析")
    print("=" * 60)
    
    # 初始化词法分析器
    lex_db.set_lex_handle()
    set_handle()
    
    # 测试语句
    sql = "create index idx_name on students (name)"
    print(f"SQL: {sql}\n")
    
    # 解析
    result = common_db.global_parser.parse(sql)
    
    if result is None:
        print("解析失败！")
    else:
        print(f"解析成功！")
        print(f"根节点: {result.value}")
        print(f"子节点数: {len(result.children) if result.children else 0}")
        
        for i, child in enumerate(result.children):
            print(f"  child[{i}]: {child.value if hasattr(child, 'value') else child}")
            if hasattr(child, 'children') and child.children:
                for j, gc in enumerate(child.children):
                    print(f"    [{i}][{j}]: {gc.value if hasattr(gc, 'value') else gc}")
    
    print("\n" + "=" * 60)
    print("测试 SELECT 解析")
    print("=" * 60)
    
    sql2 = "select * from students"
    print(f"SQL: {sql2}\n")
    
    result2 = common_db.global_parser.parse(sql2)
    
    if result2 is None:
        print("解析失败！")
    else:
        print(f"解析成功！")
        print(f"根节点: {result2.value}")
        print(f"子节点数: {len(result2.children) if result2.children else 0}")