# -------------------------------
# lex_db.py
# author: Jingyu Han hjymail@163.com
# modified by:但芸妍
# --------------------------------------------
# the module is responsible for
# (1) defining tokens used for parsing SQL statements
# (2) constructing a lex object
# -------------------------------

'''
t.value: select    *    from    students
           ↓       ↓     ↓         ↓
t.type:  SELECT   STAR  FROM     TCNAME
'''

'''
    PLY 会扫描当前模块中所有以 t_ 开头的函数，把它们自动注册为 token 匹配规则
'''

import ply.lex as lex
import common_db
import re  # 添加

# Author: 但芸妍
# 修改：实验2需要支持 * 通配符，添加 STAR token
# 修改：添加 INDEX, ON token 支持 CREATE INDEX 语句
# 修改：添加BETWEEN 支持范围查询语句
# 新增：添加新的token
tokens = ('SELECT', 'FROM', 'WHERE', 'AND', 'TCNAME', 'EQX', 'COMMA', 'CONSTANT', 'SPACE', 'STAR',
          'CREATE', 'TABLE', 'INSERT', 'INTO', 'VALUES', 'DELETE', 'UPDATE', 'SET', 'DROP',
          'LPAREN', 'RPAREN', 'INDEX', 'ON',
          'CHAR', 'VARCHAR', 'INT', 'INTEGER', 'FLOAT', 'REAL',
          'BIT', 'VARBIT', 'DATE', 'TIME',
          'BETWEEN')  

def t_CREATE(t):
    r'create'
    return t

def t_TABLE(t):
    r'table'
    return t

def t_INSERT(t):
    r'insert'
    return t

def t_INTO(t):
    r'into'
    return t

def t_VALUES(t):
    r'values'
    return t

def t_DELETE(t):
    r'delete'
    return t

def t_UPDATE(t):
    r'update'
    return t

def t_SET(t):
    r'set'
    return t

def t_DROP(t):
    r'drop'
    return t

def t_INDEX(t):
    r'index'
    return t

def t_ON(t):
    r'on'
    return t

def t_LPAREN(t):
    r'\('
    return t

def t_RPAREN(t):
    r'\)'
    return t

def t_CHAR(t):
    r'char'
    return t

def t_INTEGER(t):
    r'integer'
    return t

def t_VARCHAR(t):
    r'varchar'
    return t

def t_VARSTR(t):
    r'varstr'
    return t

def t_INT(t):
    r'int'
    return t

def t_FLOAT(t):
    r'float'
    return t

def t_REAL(t):
    r'real'
    return t

def t_BIT(t):
    r'bit'
    return t

def t_VARBIT(t):
    r'bit\s*varying'  # 匹配 "bit varying"（含空格）
    return t

def t_DATE(t):
    r'date'
    return t

def t_TIME(t):
    r'time'
    return t

# the following is to defining rules for each token
def t_SELECT(t):
    r'select'
    return t


def t_FROM(t):
    r'from'
    return t


def t_WHERE(t):
    r'where'
    return t

def t_AND(t):
    r'and'
    return t


def t_COMMA(t):
    r','
    return t


def t_EQX(t):
    r'[=]'
    return t

# 修改：新增 * 通配符的识别规则
def t_STAR(t):
    r'\*'
    return t

def t_CONSTANT(t):
    # r'\d+|\'\w+\''
    r"\d+|'[^']*'"  # 修改：匹配空格
    return t

def t_SPACE(t):
    r'\s+'
    pass

def t_BETWEEN(t):
    r'between'
    return t

def t_TCNAME(t):
    r'[A-Z_a-z]\w*'
    return t





# --------------------------
# to cope with the error
# ------------------------

def t_error(t):
    try:

        print('wrong')

    except lex.LexError:
        print('wrong')

    else:
        print('wrong')


# ------------------------------------------
# to set the global_lexer in common_db.py
# 创建并设置一个全局的词法分析器对象，供整个程序使用
# -------------------------------------------
def set_lex_handle():
    if common_db.global_lexer is not None:
        return

    common_db.global_lexer = lex.lex(reflags=re.IGNORECASE)  #在 lex.lex() 中添加 reflags=re.IGNORECASE 参数，PLY 就会自动忽略所有 token 规则中的大小写
    if common_db.global_lexer is None:
        print('wrong when the global_lex is created')


'''
def test():
    my_lexer=lex.lex()
    my_lexer.input("select f1,f2 from GOOD where f1='xx' and f2=5 ")
    while True:
        temp_tok=my_lexer.token()
        if temp_tok is None:
            break
        print temp_tok


test()
'''
