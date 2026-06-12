#-----------------------------------------------
# schema_db.py
# author: Jingyu Han   hjymail@163.com
# modified by: Ning wang, Yidan Xu, 胡丹
#-----------------------------------------------
# to process the schema data, which is stored in all.sch
# all.sch are divied into three parts,namely metaHead, tableNameHead and body
# metaHead|tableNameHead|body
#-------------------------------------------


import ctypes
import os
import struct
import head_db # it is main memory structure for the table schema

# 修改原因：类型系统从 4 种扩展到 9 种，支持基本 SQL 数据类型
FIELD_TYPE_NAME_MAP = {
    0: 'char',        # 定长字符串
    1: 'varchar',     # 变长字符串
    2: 'int',         # 整数
    3: 'bool',        # 布尔
    4: 'float',       # 浮点数
    5: 'bit',         # 定长位串
    6: 'bit varying', # 变长位串
    7: 'date',        # 日期 YYYY-MM-DD
    8: 'time'         # 时间 HH:MM:SS
}

#the following is metaHead structure,which is 12 bytes
"""
isStored    # whether there is data in the all.sch
tableNum    # how many tables
offset      # where the free area begins for body.
"""
META_HEAD_SIZE=12                                           #the First part in the schema file


#the following is the structure of tableNameHead
"""
tablename|numofFeilds|beginOffsetInBody|....|tablename|numofFeilds|beginOffsetInBody|
10 bytes |4 bytes    |4 bytes
"""
MAX_TABLE_NAME_LEN=10                                       # the maximum length of table name
MAX_TABLE_NUM=100                                           # the maximum number of tables in the all.sch
TABLE_NAME_ENTRY_LEN=MAX_TABLE_NAME_LEN+4+4                 # the length of one table name entry
TABLE_NAME_HEAD_SIZE=MAX_TABLE_NUM*TABLE_NAME_ENTRY_LEN     # the SECOND part in the schema file



# the following is for body, which stores the field information of each table and the field information is as follows
"""
field_name   # it is a string
field_type   # it is an integer, 0->str,1->varstr,2->int,3->bool
field_length # it is an integer
"""
MAX_FIELD_NAME_LEN=10                                       # the maximum length of field name
MAX_FIELD_LEN=10+4+4                                         #  the maximum length of one field
MAX_NUM_OF_FIELD_PER_TABLE=5                                # the maximum number of fields in one table
FIELD_ENTRY_SIZE_PER_TABLE=MAX_FIELD_LEN*MAX_NUM_OF_FIELD_PER_TABLE #单张表的字段总占用空间
MAX_FIELD_SECTION_SIZE=FIELD_ENTRY_SIZE_PER_TABLE*MAX_TABLE_NUM #the THIRD part in the schema file



BODY_BEGIN_INDEX=META_HEAD_SIZE+TABLE_NAME_HEAD_SIZE            # Intitially, where the field name, type and length are stored


# -----------------------------
# the table name is padded if its lenght is smaller than MAX_TABLE_NAME_WHEN
#将表名补齐到 MAX_TABLE_NAME_LEN(10) 字节，不足左侧补空格，保证 all.sch 中定长存储
# 输入参数：tableName: str/bytes，原始表名    
# 返回值：bytes，补齐空格后的 10 字节表名  
# -------------------------------
def fillTableName(tableName):
    tableName = tableName.strip()
    if isinstance(tableName, str):
        tableName = tableName.encode('utf-8')
    if len(tableName.strip()) < MAX_TABLE_NAME_LEN:
        # 左侧补空格到 10 字节
        tableName = (' ' * (MAX_TABLE_NAME_LEN - len(tableName.strip()))).encode('utf-8') + tableName.strip()
    return tableName


def _to_display_text(value):
    """
    功能描述：将 bytes 或其他类型统一转换为适合打印显示的字符串
    输入参数：value: any，待显示的数据
    返回值：str，转换后的文本
    """
    if isinstance(value, bytes):
        return value.decode('utf-8').strip()
    return str(value).strip()


def _print_aligned_table(headers, rows):
    """
    功能描述：按列宽对齐打印表格，提升模式和列表输出的可读性
    输入参数：headers: list[str]，表头列表；rows: list[list[str]]，表格数据行
    返回值：None，无返回值
    异常处理：无；空数据时仅打印表头和分隔线
    """
    normalized_rows = [[_to_display_text(item) for item in row] for row in rows]
    widths = [len(_to_display_text(header)) for header in headers]
    for row in normalized_rows:
        for idx in range(len(row)):
            widths[idx] = max(widths[idx], len(row[idx]))

    header_line = ' | '.join(_to_display_text(headers[idx]).ljust(widths[idx]) for idx in range(len(headers)))
    separator_line = '-+-'.join('-' * widths[idx] for idx in range(len(widths)))
    print(header_line)
    print(separator_line)
    for row in normalized_rows:
        print(' | '.join(row[idx].ljust(widths[idx]) for idx in range(len(row))))


class Schema(object):
    """
    模式管理器 —— 负责 all.sch 文件的读写，维护系统中所有表的元数据
    元数据包括：表名列表（tableNameHead 区）、各表字段定义（body 区）
    """

    fileName = 'all.sch'   # 模式文件名（全局唯一）
    count = 0               # 实例计数，确保 Schema 单例

    @staticmethod
    def how_many():
        """
        功能：返回 Schema 实例数量，保证程序中只有一个 Schema 对象
        """
        return Schema.count


    def viewTableNames(self):
        """
        功能：列出 all.sch 中所有已注册的表名，以对齐表格形式输出
        """
        print('viewtablenames begin to execute')
        # 修改原因：按对齐表格打印所有表名，便于在输入 all 时统一查看系统中的表列表
        table_rows = []
        for index, table_info in enumerate(self.headObj.tableNames, start=1):
            table_rows.append([str(index), _to_display_text(table_info[0])])
        if len(table_rows) == 0:
            print('there is no table in the schema file.')
        else:
            _print_aligned_table(['No.', 'Table Name'], table_rows)
        print ('execute Done!')

    #------------------------
    # to show the schema of given table 
    #按对齐表格显示指定表的字段结构（字段名、类型、长度）
    # 输入参数：table_name: bytes/str，表名
    #返回值：list，字段三元组列表 [(字段名,类型,长度),...]
    #------------------------------
    def viewTableStructure(self, table_name):
        print('the structure of table {0} is as follows:'.format(_to_display_text(table_name)))
        '''
        tmp=[]
        for i in range(len(self.headObj.tableNames)):
            if self.headObj.tableNames[i][0] == table_name:
                tmp = [j.strip() for j in self.headObj.tableFields[i]]
                print '|'.join(tmp)
                return tmp
        '''
        # 修改原因：按字段名、类型、长度三列对齐输出表结构，避免原始字节串打印难以阅读
        field_list = self.headObj.tableFields.get(table_name.strip(), [])
        if len(field_list) == 0:
            print('the table structure is empty.')
            return []

        field_rows = []
        for field_name, field_type, field_length in field_list:
            field_rows.append([
                _to_display_text(field_name),
                FIELD_TYPE_NAME_MAP.get(int(field_type), str(field_type)),
                str(field_length)
            ])
        _print_aligned_table(['Field Name', 'Field Type', 'Field Length'], field_rows)
        return field_list

    # ------------------------------------------------
    # constructor of the class
    #打开/创建 all.sch 模式文件，读取所有表元数据到内存 Header 对象
    #若 all.sch 不存在则自动创建并初始化空的 metaHead
    # ------------------------------------------------
    def __init__(self):
        print('__init__ of Schema')

        print ('schema fileName is ' + Schema.fileName)
        if not os.path.exists(Schema.fileName):
            # 修改原因：支持删除 all.sch 后重新启动程序时自动重建空的 schema 文件
            open(Schema.fileName, 'wb').close()
        # Schema 类的内存对象
        self.fileObj = open(Schema.fileName, 'rb+')  # in binary format

        # read all data from schema file读取
        bufLen = META_HEAD_SIZE + TABLE_NAME_HEAD_SIZE + MAX_FIELD_SECTION_SIZE  # the length of metahead, table name entries and fieldName sections
        buf = ctypes.create_string_buffer(bufLen)
        buf = self.fileObj.read(bufLen)

        #the following is to print the content of the buffer打印
        buf.strip()
        if len(buf) == 0:  # for the first time, there is nothing in the schema file
            self.body_begin_index = BODY_BEGIN_INDEX
            buf = struct.pack('!?ii', False, 0, self.body_begin_index)  # is_stored, tablenum,offset

            self.fileObj.seek(0)
            self.fileObj.write(buf)
            self.fileObj.flush()

            # the following is to create a main memory structure for the schema

            tableNameList = []
            fieldNameList = {}  # it is a dictionary
            nameList = []
            fieldsList = {}
            # Schema 类的内存对象；head_db.Header：已经写好的内存结构类
            self.headObj = head_db.Header(nameList, fieldsList,False, 0, self.body_begin_index)

            print ('metaHead of schema has been written to all.sch and the Header ojbect created')

        else:  # there is something in the schema file

            print("\n" + "=" * 50)
            print("  元数据头（metaHead）解析")
            print("=" * 50)
            # in the following ? denotes bool type and  i denotes int type
            isStored, tempTableNum, tempOffset = struct.unpack_from('!?ii', buf, 0)

            print("  isStored = {0}  |  tableNum = {1}  |  body offset = {2}".format(
                isStored, tempTableNum, tempOffset))
            print("-" * 50)

            Schema.body_begin_index = tempOffset
            nameList = []
            fieldsList = {}

            if isStored == False:  # only the meta head exists, but there is no table information in the schema file
                self.headObj = head_db.Header(nameList, fieldsList, False, 0, BODY_BEGIN_INDEX)
                print("  (无表模式数据)")

            else:  # there is information of some tables

                print("  表列表解析（共 {0} 张表）".format(tempTableNum))
                print("-" * 50)

                # the following is to fetch the tableNameHead from the buffer
                for i in range(tempTableNum):
                    # fetch the table name in tableNameHead
                    tempName, = struct.unpack_from('!10s', buf,
                                                   META_HEAD_SIZE + i * TABLE_NAME_ENTRY_LEN)
                    # fetch the number of fields in the table in tableNameHead
                    tempNum, = struct.unpack_from('!i', buf, META_HEAD_SIZE + i * TABLE_NAME_ENTRY_LEN + 10)
                    # fetch the offset where field names are stored in the body
                    tempPos, = struct.unpack_from('!i', buf,
                                                  META_HEAD_SIZE + i * TABLE_NAME_ENTRY_LEN
                                                  + 10 + struct.calcsize('i'))

                    # 显示时 strip 去掉定长存储的补位空格
                    print("  [{0}] 表名: {1}  |  字段数: {2}  |  body偏移: {3}".format(
                        i + 1, tempName.strip().decode('utf-8'), tempNum, tempPos))

                    tempNameMix = (tempName.strip(), tempNum, tempPos)
                    nameList.append(tempNameMix)  # It is a triple

                    # the following is to fetch field information from body section
                    if tempNum > 0:
                        fields = []
                        print("        字段名         类型  长度")
                        print("        " + "-" * 28)
                        for j in range(tempNum):
                            tempFieldName, tempFieldType, tempFieldLength = struct.unpack_from(
                                '!10sii', buf, tempPos + j * MAX_FIELD_LEN)
                            # 类型码 → 可读类型名
                            type_label = FIELD_TYPE_NAME_MAP.get(tempFieldType, str(tempFieldType))
                            print("        {0:12s}  {1:4s}  {2:4d}".format(
                                tempFieldName.strip().decode('utf-8'), type_label, tempFieldLength))
                            tempFieldTuple = (tempFieldName, tempFieldType, tempFieldLength)
                            fields.append(tempFieldTuple)

                        fieldsList[tempName.strip()] = fields
                    print()  # 表间空行

                print("=" * 50)
                print("  Header 内存对象构造完成")
                print("=" * 50)

                # the main memory structure for schema is constructed
                self.headObj = head_db.Header(nameList, fieldsList, True, tempTableNum, tempOffset)

    # ----------------------------
    # destructor of the class
    #析构时刷新 metaHead 到磁盘并关闭 all.sch，防止未落盘的元数据丢失
    # ----------------------------
    def __del__(self):
        print ("__del__ of class Schema begins to execute")
        # 修改原因：复用统一的元数据落盘逻辑，保证关闭对象前 schema 元信息已写回磁盘
        if hasattr(self, 'fileObj') and self.fileObj and (not self.fileObj.closed):
            self.flush_meta_head()
            self.fileObj.close()

    def flush_meta_head(self):
        """
        功能描述：将 all.sch 的元数据头信息立即写回磁盘，保证表数量和 body 偏移量实时持久化
        输入参数：无
        返回值：bool，写回成功返回 True
        异常处理：无；调用前默认文件句柄已正常打开
        """
        # 修改原因：创建表后若程序未正常析构，原实现不会立刻写回元数据，可能导致重启后表丢失
        buf = ctypes.create_string_buffer(12)
        struct.pack_into('!?ii', buf, 0, self.headObj.isStored, self.headObj.lenOfTableNum, self.headObj.offsetOfBody)
        self.fileObj.seek(0)
        self.fileObj.write(buf)
        self.fileObj.flush()
        return True

    def _rewrite_schema_file(self):
        """
        功能描述：依据当前内存中的表结构信息重写 all.sch，保证删除表后磁盘元数据与字段区一致
        输入参数：无
        返回值：bool，重写成功返回 True
        异常处理：无；当无表存在时写回空的 metaHead
        """
        # 修改原因：原删除逻辑在 Python 3 下使用旧式 map/zip，且磁盘重写不完整，容易造成 all.sch 不一致
        normalized_table_names = []
        current_offset = BODY_BEGIN_INDEX
        buf_len = META_HEAD_SIZE + TABLE_NAME_HEAD_SIZE + MAX_FIELD_SECTION_SIZE
        buf = ctypes.create_string_buffer(buf_len)

        for table_name, _, _ in self.headObj.tableNames:
            normalized_name = table_name.strip()
            field_list = self.headObj.tableFields.get(normalized_name, [])
            field_num = len(field_list)
            normalized_table_names.append((normalized_name, field_num, current_offset))
            current_offset += field_num * MAX_FIELD_LEN

        for idx in range(len(normalized_table_names)):
            table_name, field_num, table_offset = normalized_table_names[idx]
            struct.pack_into('!10sii', buf, META_HEAD_SIZE + idx * TABLE_NAME_ENTRY_LEN,
                             fillTableName(table_name), field_num, table_offset)
            field_list = self.headObj.tableFields.get(table_name, [])
            for field_index in range(len(field_list)):
                field_name, field_type, field_length = field_list[field_index]
                packed_field_name = fillTableName(field_name)
                struct.pack_into('!10sii', buf, table_offset + field_index * MAX_FIELD_LEN,
                                 packed_field_name, int(field_type), int(field_length))

        self.headObj.tableNames = normalized_table_names
        self.headObj.lenOfTableNum = len(normalized_table_names)
        self.headObj.isStored = self.headObj.lenOfTableNum > 0
        self.headObj.offsetOfBody = current_offset if self.headObj.isStored else BODY_BEGIN_INDEX

        struct.pack_into('!?ii', buf, 0, self.headObj.isStored, self.headObj.lenOfTableNum, self.headObj.offsetOfBody)
        self.fileObj.seek(0)
        self.fileObj.truncate(0)
        self.fileObj.write(buf.raw)
        self.fileObj.flush()
        return True

    def delete_table(self, table_name):
        """
        功能描述：删除指定表在 all.sch 中的模式信息，并同步更新表数量与偏移量元数据
        输入参数：table_name: bytes/str，要删除的表名
        返回值：bool，删除成功返回 True，表不存在返回 False
        异常处理：无；调用方负责处理删除失败提示
        """
        # 修改原因：新增统一的表删除接口，负责删除模式信息并重建磁盘中的 schema 文件
        normalized_table_name = table_name.strip()
        if isinstance(normalized_table_name, str):
            normalized_table_name = normalized_table_name.encode('utf-8')

        if not self.find_table(normalized_table_name):
            print('Cannot find the table!')
            return False

        self.headObj.tableNames = [item for item in self.headObj.tableNames if item[0].strip() != normalized_table_name]
        if normalized_table_name in self.headObj.tableFields:
            del self.headObj.tableFields[normalized_table_name]
        # 修改原因：删除模式信息的同时清理对应的 .dat 数据文件，避免残留孤儿文件
        import storage_db as _sd
        _sd.Storage.remove_table_file(normalized_table_name)
        return self._rewrite_schema_file()

    # --------------------------
    # delete all the contents in the schema file
    #清空 all.sch 中所有表名和字段定义，将 isStored 置 False，表数量归零
    # ----------------------------------------
    def deleteAll(self):
        self.headObj.tableFields={}
        self.headObj.tableNames=[]
        self.fileObj.seek(0)
        self.fileObj.truncate(0)
        self.headObj.isStored = False
        self.headObj.lenOfTableNum = 0
        self.headObj.offsetOfBody = self.body_begin_index
        self.fileObj.flush()
        print ("all.sch file has been truncated")

    def reset_schema_file(self):
        """
        功能描述：重置当前 all.sch 的内容并立即重建一个空的 schema 文件，供“删除所有表”流程调用
        输入参数：无
        返回值：bool，重建成功返回 True
        异常处理：无；若旧文件不存在则直接创建新文件
        """
        # 修改原因：Windows 下已打开文件可能无法立刻 os.remove，这里改为清空并重建空 schema 文件，避免文件锁异常
        if self.fileObj and (not self.fileObj.closed):
            self.fileObj.close()
        open(Schema.fileName, 'wb').close()
        self.fileObj = open(Schema.fileName, 'rb+')
        self.body_begin_index = BODY_BEGIN_INDEX
        self.headObj = head_db.Header([], {}, False, 0, self.body_begin_index)
        self.flush_meta_head()
        return True

    # -----------------------------
    # insert a table schema to the schema file模式存入
    #向 all.sch 追加一张新表的模式信息——先写字段定义到 body 区，再写表名条目到 tableNameHead 区，
    #最后更新内存 Header 并立即调用 flush_meta_head() 刷盘
    #输入参数：tableName: str/bytes，表名；fieldList: list[(str,int,int)]，字段三元组列表
    # -------------------------------
    def appendTable(self, tableName, fieldList):
        """
        功能：向 all.sch 追加新表模式——先写字段到 body 区，再写表名条目到 tableNameHead，
              最后更新内存 Header 并立即 flush_meta_head() 刷盘。
        输入参数：tableName: str/bytes，表名；fieldList: list[(str,int,int)]，字段三元组。
        """
        print("appendTable begins to execute")
        tableName = tableName.strip()

        if len(tableName) == 0:
            print('表名为空，创建失败')
            return False
        elif len(tableName) > MAX_TABLE_NAME_LEN:
            print('表名 "{0}" 长度 {1} 超过上限 {2}，创建失败'.format(
                tableName.decode('utf-8') if isinstance(tableName, bytes) else tableName,
                len(tableName), MAX_TABLE_NAME_LEN))
            return False
        elif len(fieldList) == 0:
            print('字段列表为空，创建失败')
            return False
        # 修改原因：防止重复建表导致 all.sch 中出现同名表条目（如手动建表 + SQL 建表分别调用）
        elif self.find_table(tableName):
            print('table {0} already exists, cannot create again'.format(
                tableName.decode('utf-8') if isinstance(tableName, bytes) else tableName))
            return False
        else:

            fieldNum = len(fieldList)

            print ("the following is to write the fields to body in all.sch")
            #Python 标准库 ctypes，专门用来创建固定长度的字节缓冲区,创建一个预分配大小的、可写的二进制内存块
            fieldBuff = ctypes.create_string_buffer(MAX_FIELD_LEN * len(fieldList))
            beginIndex = 0
            for i in range(len(fieldList)):
                #Python的序列解包（Tuple Unpacking）:只要 fieldList[i] 是一个长度为 3 的可迭代对象（比如三元组、列表），就可以直接把它的三个元素分别赋值给三个变量
                (fieldName,fieldType,fieldLength)=fieldList[i]
                # 先处理字段名

                if len(fieldName.strip()) < MAX_FIELD_NAME_LEN:
                    if isinstance(fieldName, str):
                        fieldName = fieldName.encode('utf-8')
                    # 先 strip 去空格再填，避免 Storage 已填充的定长字段名被重复填充
                    fieldName = fieldName.strip()
                    filledFieldName = (' ' * (MAX_FIELD_NAME_LEN - len(fieldName))).encode('utf-8') + fieldName
                
                if isinstance(filledFieldName,str):
                    filledFieldName=filledFieldName.encode('utf-8')
                #struct.pack_into 二进制打包写入缓冲区 ; !10sii → 大端序 + 10字节字符串 + 两个4字节整数:字段名(10b)、类型(4b)、长度(4b)
                struct.pack_into('!10sii', fieldBuff, beginIndex, filledFieldName,int(fieldType),int(fieldLength))
                #准备写下一个字段:循环内的偏移量累加
                beginIndex = beginIndex + MAX_FIELD_LEN
            #self.headObj 是内存表头对象;offsetOfBody：body 区下一个可写入的起始位置
            #获取当前body区的写入位置（下一个可写字段的起始地址）
            writePos = self.headObj.offsetOfBody

            #文件指针跳转 + 写入缓冲区 + 刷新磁盘
            self.fileObj.seek(writePos)
            self.fileObj.write(fieldBuff)
            self.fileObj.flush()

            # self.headObj.offsetOfBody=self.headObj.offsetBody+fieldNum*MAX_FIELD_LEN

            print ("the following is to write table name entry to tableNameHead in all.sch")
            
            filledTableName = fillTableName(tableName)
            if isinstance(filledTableName, str):
                filledTableName = filledTableName.encode('utf-8')
            #打包表名(10b)、字段数(4b)、body偏移(4b)
            nameBuf = struct.pack('!10sii', filledTableName, fieldNum, self.headObj.offsetOfBody)

            #将文件指针跳转到指定字节位置:metaHead长度 + 当前表数量 × 单张表名占用长度
            self.fileObj.seek(META_HEAD_SIZE + self.headObj.lenOfTableNum * TABLE_NAME_ENTRY_LEN)
            #内存快速查询用，不用读磁盘就能知道表的结构:清理空格后的表名,这张表有多少个字段,字段数据在磁盘 body 区的起始位置
            nameContent = (tableName.strip(), fieldNum, self.headObj.offsetOfBody)

            self.fileObj.write(nameBuf)
            self.fileObj.flush()

            #磁盘写完了，必须同步更新内存，否则下次操作会读旧数据！
            print ("to modify the header structure in main memory")
            self.headObj.isStored = True
            self.headObj.lenOfTableNum += 1
            self.headObj.offsetOfBody += fieldNum * MAX_FIELD_LEN #新的可写位置 = 原位置 + 本次字段数 ×18 字节
            self.headObj.tableNames.append(nameContent)
            # fieldTuple = tuple(fieldList)
            self.headObj.tableFields[tableName.strip()]=fieldList
            # 修改原因：表创建成功后立即同步 metaHead，修复程序重启后表模式可能丢失的问题
            self.flush_meta_head()
            return True

    # -------------------------------
    # to determine whether the table named table_name exist, depending on the main memory structures
    # 判断指定表名是否已在 all.sch 中注册
    #输入参数：table_name: bytes/str，待查找的表名
    #返回值：bool，存在返回 True
    # -------------------------------------------------------
    def find_table(self, table_name):
        Tables = map(lambda x: x[0], self.headObj.tableNames)
        if table_name in Tables:
            return True
        else:
            return False
    # ----------------------------------------------
    # to write the main memory information into the schema file
    # 将内存 Header 中所有表名和字段信息完整序列化写回 all.sch 文件
    #遍历 tableNames 和 tableFields，按定长格式逐一打包到缓冲区后整体写入磁盘       
    # ------------------------------------------------   

    def WriteBuff(self):
        bufLen = META_HEAD_SIZE + TABLE_NAME_HEAD_SIZE + MAX_FIELD_SECTION_SIZE
        buf = ctypes.create_string_buffer(bufLen)
        struct.pack_into('!?ii', buf, 0, self.headObj.isStored, self.headObj.lenOfTableNum, self.headObj.offsetOfBody)
        #isStored, tempTableNum, tempOffset = struct.unpack_from('!?ii', buf,0)  # link:https://docs.python.org/2/library/struct.html
        #print isStored,tempTableNum,tempOffset
        for idx in range(len(self.headObj.tableNames)):
            tmp_tableName = self.headObj.tableNames[idx][0]
            if len(tmp_tableName)<10:
                tmp_tableName = ' ' * (10 - len(tmp_tableName.strip())) + tmp_tableName

            # write (tablename,numberoffields,offsetinbody) to buffer
            struct.pack_into('!10sii', buf, META_HEAD_SIZE + idx * TABLE_NAME_ENTRY_LEN, tmp_tableName,
                             self.headObj.tableNames[idx][1],self.headObj.tableNames[idx][2])

            # write the field information of each table into the buffer
            for idj in range(self.headObj.tableNames[idx][1]):
                (tempFieldName,tempFieldType,tempFieldLength)=self.headObj.tableFields[idx][idj]                
                struct.pack_into('!10sii',buf,self.headObj.tableNames[idx][2]+idj*MAX_FIELD_LEN,
                                tempFieldName,tempFieldType,tempFieldLength)
        self.fileObj.seek(0)
        self.fileObj.write(buf)
        self.fileObj.flush()

    # ----------------------------------------------
    # to delete the schema of a table from the schema file
    # 删除指定表的模式信息（旧接口，兼容原有调用）内部转发到 delete_table()
    # input
    #       table_name: the table to be deleted
    # output
    #       True or False
    # ------------------------------------------------
    def delete_table_schema(self, table_name):
        # 修改原因：保留旧接口名称以兼容原有调用，内部统一转发到新的 delete_table 实现
        return self.delete_table(table_name)

    def get_table_name_list(self):
        """
        功能：返回 all.sch 中所有已注册表名的可迭代对象
        返回值：iterator，每次迭代返回一个 bytes 类型的表名
        """
        return map(lambda x: x[0], self.headObj.tableNames)
