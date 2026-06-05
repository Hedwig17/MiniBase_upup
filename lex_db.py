#-------------------------------
# lex_db.py
# author: Jingyu Han hjymail@163.com
# modified by: 胡丹
#--------------------------------------------
# the module is responsible for
#(1) defining tokens used for parsing SQL statements
#(2) constructing a lex object
#-------------------------------
import ply.lex as lex
import common_db

# 修改原因：增加 DDL/DML 语句所需 token，实验2 选做支持 CREATE TABLE / INSERT INTO / DELETE / UPDATE / DROP
tokens=('SELECT','FROM','WHERE','AND','TCNAME','EQX','COMMA','CONSTANT','SPACE','STAR',
        'CREATE','TABLE','INSERT','INTO','VALUES','DROP','DELETE','UPDATE','SET',
        'CHAR','INTEGER',
        'LPAREN','RPAREN','SEMICOLON')

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

def t_DROP(t):
    r'drop'
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

def t_CHAR(t):
    r'char'
    return t

def t_INTEGER(t):
    r'integer'
    return t

def t_TCNAME(t):
    r'[A-Z_a-z]\w*'
    return t

def t_COMMA(t):
    r','
    return t

def t_EQX(t):
    r'[=]'
    return t

# 修改原因：[^']* 匹配除单引号外的任意字符序列，解决 'database system' 含空格无法识别的问题
def t_CONSTANT(t):
    r"\d+|'[^']*'"
    return t

def t_STAR(t):
    r'\*'
    return t

def t_LPAREN(t):
    r'\('
    return t

def t_RPAREN(t):
    r'\)'
    return t

def t_SEMICOLON(t):
    r';'
    return t

def t_SPACE(t):
    r'\s+'
    pass

#--------------------------
# to cope with the error
#------------------------

def t_error(t):
    try:
        print ('wrong')
    except lex.LexError:
        print ('wrong')
    else:
        print ('wrong')


#------------------------------------------
# to set the global_lexer in common_db.py
#-------------------------------------------
def set_lex_handle():
    common_db.global_lexer=lex.lex()
    if common_db.global_lexer is None:
        print ('wrong when the global_lex is created')



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
