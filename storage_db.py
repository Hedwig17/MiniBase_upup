# -----------------------------------------------------------------------
# storage_db.py
# Author: Jingyu Han  hjymail@163.com
# modified by: 胡丹，马焱涵
# -----------------------------------------------------------------------
# the module is to store tables in files
# Each table is stored in a separate file with the suffix ".dat".
# For example, the table named moviestar is stored in file moviestar.dat 
# -----------------------------------------------------------------------

# struct of file is as follows, each block is 4096
# ---------------------------------------------------
# block_0|block_1|...|block_n
# ----------------------------------------------------------------
from common_db import BLOCK_SIZE

# structure of block_0, which stores the meta information and field information
# ---------------------------------------------------------------------------------
# block_id                                # 0
# number_of_dat_blocks                    # at first it is 0 because there is no data in the table
# number_of_fields or number_of_records   # the total number of fields for the table
# -----------------------------------------------------------------------------------------


# the data type is as follows
# ----------------------------------------------------------
# 0->char, 1->varchar, 2->int, 3->bool, 4->float,
# 5->bit, 6->bit varying, 7->date, 8->time
# ---------------------------------------------------------------


# structure of data block, whose block id begins with 1
# ----------------------------------------
# block_id       
# number of records
# record_0_offset         # it is a pointer to the data of record
# record_1_offset
# ...
# record_n_offset
# ....
# free space
# ...
# record_n
# ...
# record_1
# record_0
# -------------------------------------------

# structre of one record
# -----------------------------
# pointer                     #offset of table schema in block id 0
# length of record            # including record head and record content
# time stamp of last update  # for example,1999-08-22
# field_0_value
# field_1_value
# ...
# field_n_value
# -------------------------

# 【M】导入事务模块
from transaction_log import *

import struct
import os
import ctypes
import re  # 修改原因：date/time 格式校验需要正则

STORAGE_DEBUG_OUTPUT = False


def _to_display_text(value):
    """
    功能描述：将 bytes、bool 或其他类型统一转换为便于表格显示的字符串
    输入参数：value: any，待显示的数据
    返回值：str，转换后的文本
    """
    if isinstance(value, bytes):
        return value.decode('utf-8').strip()
    if isinstance(value, bool):
        return 'True' if value else 'False'
    return str(value).strip()


def _print_aligned_table(headers, rows):
    """
    功能描述：按列宽对齐打印数据表格，提升查看记录时的可读性
    输入参数：headers: list[str]，表头列表；rows: list[list[str]]，数据行列表
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


def print_aligned_table(headers, rows):
    """
    功能描述：对外提供统一的对齐表格打印接口，供主流程和查询功能复用
    输入参数：headers: list[str]，表头列表；rows: list[list[str]]，数据行列表
    返回值：None，无返回值
    """
    # 修改原因：选项 5 查询结果也需要表格化显示，复用存储模块已有格式输出能力
    _print_aligned_table(headers, rows)


def _debug_print(*args):
    """
    功能描述：统一控制存储模块的调试输出，默认关闭，避免内部日志干扰用户交互结果
    输入参数：*args: tuple，传递给 print 的调试内容
    返回值：None，无返回值
    """
    if STORAGE_DEBUG_OUTPUT:
        print(*args)


# --------------------------------------------
# the class can store table data into files
# functions include insert, delete and update
# --------------------------------------------

class Storage(object):

    def _normalize_field_name(self, field_name):
        """
        功能描述：将字段名统一转换为便于比较的纯文本形式
        输入参数：field_name: bytes/str，字段名
        返回值：str，去除空白后的字段名文本
        """
        if isinstance(field_name, bytes):
            return field_name.decode('utf-8').strip()
        return str(field_name).strip()

    def _convert_value_by_field_type(self, field_type, raw_value):
        """
        功能描述：将用户输入转为可比较的 Python 值（委托到 _validate，传大长度跳过长度检查）。
        输入参数：field_type: int，字段类型编号；raw_value: str，用户输入的原始值。
        返回值：tuple[bool, any]，成功时返回 (True, 值)，失败时返回 (False, None)。
        """
        ok, result = self._validate_value_for_field(field_type, 99999, raw_value)
        return (True, result) if ok else (False, None)

    def _record_to_insert_values(self, record):
        """
        功能描述：将内存中的记录元组转换为可复用 insert_record 的字符串列表
        输入参数：record: tuple，单条记录
        返回值：list[str]，适用于 insert_record 的字段值列表
        """
        insert_values = []
        for value in record:
            if isinstance(value, bool):
                insert_values.append('True' if value else 'False')
            elif isinstance(value, bytes):
                insert_values.append(value.decode('utf-8').strip())
            else:
                insert_values.append(str(value).strip())
        return insert_values

    def _normalize_record_value_for_compare(self, field_type, field_value):
        """
        功能描述：将记录中的字段值转换为适合比较的标准形式，避免 bytes 与 str 直接比较失败
        输入参数：field_type: int，字段类型编号；field_value: any，记录中的字段值
        返回值：any，标准化后的可比较值
        """
        # 修改原因：新类型（float/bit/date/time）存储为字符串，比较前需统一转成对应 Python 类型
        if field_type in [0, 1, 5, 6, 7, 8]:  # 字符串类：char/varchar/bit/bit varying/date/time
            if isinstance(field_value, bytes):
                return field_value.decode('utf-8').strip()
            return str(field_value).strip()
        if field_type == 4:  # float
            if isinstance(field_value, bytes):
                field_value = field_value.decode('utf-8').strip()
            return float(field_value)
        return field_value  # int(2) / bool(3) 已由 Storage 读取时转换过

    def _validate_value_for_field(self, field_type, field_length, raw_value):
        """
        功能描述：校验并转换待写入字段的新值，确保其类型和长度符合字段定义
        输入参数：field_type: int，字段类型编号；field_length: int，字段长度限制；raw_value: str，用户输入的新值
        返回值：tuple[bool, any/str]，成功时返回 True 和转换后的值，失败时返回 False 和错误信息
        异常处理：无；长度超限或类型不匹配时返回明确错误
        """
        text_value = str(raw_value).strip()
        if field_type in [0, 1]:
            if len(text_value) > field_length:
                return False, 'new value length exceeds the field length.'
            return True, text_value
        if field_type == 2:
            try:
                return True, int(text_value)
            except ValueError:
                return False, 'value type does not match the field type.'
        if field_type == 3:
            normalized_value = text_value.lower()
            if normalized_value in ['true', '1', 'yes', 'y']:
                return True, True
            if normalized_value in ['false', '0', 'no', 'n']:
                return True, False
            return False, 'boolean value must be true/false/1/0/yes/no.'
        # 修改原因：类型系统扩展到 9 种，新增 float / bit / bit varying / date / time
        if field_type == 4:  # float / real
            try:
                return True, float(text_value)
            except ValueError:
                return False, 'value must be a floating-point number.'
        if field_type in [5, 6]:  # bit(n) / bit varying(n)
            if not re.match(r'^[01]+$', text_value):
                return False, 'bit value must consist of only 0 and 1.'
            if len(text_value) > field_length:
                return False, 'bit length {0} exceeds maximum {1}.'.format(
                    len(text_value), field_length)
            return True, text_value
        if field_type == 7:  # date YYYY-MM-DD
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', text_value):
                return False, 'date must be in YYYY-MM-DD format.'
            return True, text_value
        if field_type == 8:  # time HH:MM:SS
            if not re.match(r'^\d{2}:\d{2}:\d{2}$', text_value):
                return False, 'time must be in HH:MM:SS format.'
            return True, text_value
        return False, 'unsupported field type.'

    def _rebuild_storage_records(self, remaining_records):
        """
        功能描述：依据保留记录重建当前表的数据文件内容
        输入参数：remaining_records: list[tuple]，删除后需要保留的记录列表
        返回值：bool，重建成功返回 True
        异常处理：无；默认当前对象文件句柄有效且字段结构已存在内存中
        """
        # 修改原因：按条件删除记录后需要稳定重写 .dat 文件，避免直接在原二进制块中原地删改过于复杂
        self.f_handle.seek(0)
        self.f_handle.truncate(0)

        self.dir_buf = ctypes.create_string_buffer(BLOCK_SIZE)
        self.block_id = 0
        self.data_block_num = 0
        self.record_list = []
        self.record_Position = []

        begin_index = 0
        struct.pack_into('!iii', self.dir_buf, begin_index, 0, 0, int(self.num_of_fields))
        begin_index += struct.calcsize('!iii')
        for field_name, field_type, field_length in self.field_name_list:
            packed_field_name = field_name
            if isinstance(packed_field_name, str):
                packed_field_name = packed_field_name.encode('utf-8')
            struct.pack_into('!10sii', self.dir_buf, begin_index, packed_field_name, int(field_type), int(field_length))
            begin_index += struct.calcsize('!10sii')
        self.f_handle.seek(0)
        self.f_handle.write(self.dir_buf)
        self.f_handle.flush()

        for record in remaining_records:
            insert_values = self._record_to_insert_values(record)
            # 【M】修改，添加is_recovery=True参数，因为该操作属于内部操作不能生成事务日志
            if not self.insert_record(insert_values, is_recovery=True):
                return False
        return True

    def _find_free_slot(self):
        """
        功能：扫描所有数据块的偏移量表，查找第一个空闲槽位（偏移值 = -1）。
              这是教材"空闲空间链表"方法的简化版——用 -1 标记逻辑删除，
              插入时复用这些槽位，无需滑动记录或重建整个文件。
        返回值：tuple(block_id, record_index) 或 None。
        """
        for block_id in range(1, self.data_block_num + 1):
            self.f_handle.seek(BLOCK_SIZE * block_id)
            block_buf = self.f_handle.read(BLOCK_SIZE)
            _, num_records = struct.unpack_from('!ii', block_buf, 0)
            for i in range(num_records):
                off = struct.unpack_from('!i', block_buf,
                                         struct.calcsize('!ii') + i * struct.calcsize('!i'))[0]
                if off == -1:
                    return (block_id, i)
        return None

    def _read_positive_int(self, prompt_text):
        """
        功能描述：读取并校验正整数输入，用于字段数量和字段长度等场景
        输入参数：prompt_text: str，输入提示语
        返回值：int，校验通过的正整数
        异常处理：无；输入非法时循环提示重新输入
        """
        while True:
            # 修改原因：统一处理数值校验，避免直接 int() 转换导致程序崩溃
            input_value = input(prompt_text).strip()
            if input_value.isdigit() and int(input_value) > 0:
                return int(input_value)
            print('input must be a positive integer.')

    def _read_field_type(self, prompt_text):
        """
        功能描述：读取字段类型，限制为 0-8（char/varchar/int/bool/float/bit/bit varying/date/time）。
        输入参数：prompt_text: str，输入提示语。
        返回值：int，字段类型编号（0-8）。
        """
        while True:
            input_value = input(prompt_text).strip()
            if input_value in [str(i) for i in range(9)]:
                return int(input_value)
            print('field type must be one of 0, 1, 2 or 3.')

    def _read_field_name(self, field_index):
        """
        功能描述：读取字段名并保证非空且不超过 10 个字符，适配当前定长字段结构
        输入参数：field_index: int，当前字段序号，仅用于提示信息
        返回值：str，符合长度要求的字段名
        异常处理：无；输入非法时循环提示重新输入
        """
        while True:
            # 修改原因：字段名会写入固定 10 字节区域，提前限制长度可避免后续写入异常
            field_name = input("please input the name of field " + str(field_index) + " :").strip()
            if len(field_name) == 0:
                print('field name cannot be empty.')
                continue
            if len(field_name) > 10:
                print('field name length cannot exceed 10 characters.')
                continue
            return field_name

    # ------------------------------
    # 1.初始化表数据文件，自动创建 / 打开 .dat 文件constructor of the class
    #  输入参数：tablename: str/bytes，表名；field_list: list[(str,int,int)]，可选，SQL 建表时传入的字段定义
    #       tablename
    # -------------------------------------
    def __init__(self, tablename, field_list=None):
        # print "__init__ of ",Storage.__name__,"begins to execute"
        tablename = tablename.strip()
        # 修改原因：query_plan_db 传入 str 表名，统一转为 bytes 避免 str+bytes 拼接报错
        if isinstance(tablename, str):
            tablename = tablename.encode('utf-8')
        # 【M】新增，保证self.table_name永远是bytes，后面日志模块就能直接使用
        self.table_name = tablename

        self.record_list = []
        self.record_Position = []
        #tablename.dat是否存在
        if not os.path.exists(tablename + '.dat'.encode('utf-8')):  # the file corresponding to the table does not exist
            _debug_print('table file '.encode('utf-8') + tablename + '.dat does not exists'.encode('utf-8'))
            self.f_handle = open(tablename + '.dat'.encode('utf-8'), 'wb+')
            self.f_handle.close()
            self.open = False
            _debug_print(tablename + '.dat has been created'.encode('utf-8'))

        #打开文件
        self.f_handle = open(tablename + '.dat'.encode('utf-8'), 'rb+')
        _debug_print('table file '.encode('utf-8') + tablename + '.dat has been opened'.encode('utf-8'))
        self.open = True

        #读取第0块的内容到内存中，分析出表结构信息
        self.dir_buf = ctypes.create_string_buffer(BLOCK_SIZE)
        self.f_handle.seek(0)
        self.dir_buf = self.f_handle.read(BLOCK_SIZE)

        self.dir_buf.strip()
        my_len = len(self.dir_buf)
        self.field_name_list = []
        beginIndex = 0

        if my_len == 0:  # 刚创建的 .dat 文件是空的，block_0 尚无内容
            # 修改原因：SQL 建表时传入 field_list 则直接写入，不走交互式询问
            if field_list is not None:
                self.num_of_fields = len(field_list)
                self.dir_buf = ctypes.create_string_buffer(BLOCK_SIZE)# 分配 4096 字节内存缓冲区
                self.block_id = 0 # 当前块号 = 0
                self.data_block_num = 0  # 数据块计数，新建表时还没有数据块
                # ═══ block_0 头部：写入 3 个 4 字节整数 ═══
                struct.pack_into('!iii', self.dir_buf, beginIndex, 0, 0,
                                 int(self.num_of_fields))
                #  !iii  = 大端序 + 三个 int(各 4B)
                #  第 1 个 0 = block_id（当前块编号，恒为 0）
                #  第 2 个 0 = data_block_num（新建表尚无数据块）
                #  第 3 个   = num_of_fields（本表的字段总数）
                #  写入位置：缓冲区第 0 字节（beginIndex=0）
                #  占用字节：4 + 4 + 4 = 12 字节
                beginIndex = beginIndex + struct.calcsize('!iii')
                #  beginIndex 从 0 → 12，接下来从第 12 字节开始写字段信息

                # ═══ block_0 字段区：逐字段写入 (字段名 10B + 类型 4B + 长度 4B) ═══
                for i in range(int(self.num_of_fields)):
                    fname, ftype, flen = field_list[i]
                    # 左侧补充空格使字段名凑足 10 字节，如 'c_id' → '      c_id'
                    padded_field_name = ' ' * (10 - len(fname.strip())) + fname.strip()
                    # 同时维护内存中的字段列表，后续查询、插入都依赖这个数据结构
                    temp_tuple = (padded_field_name, int(ftype), int(flen))
                    self.field_name_list.append(temp_tuple)
                    if isinstance(padded_field_name, str):
                        padded_field_name = padded_field_name.encode('utf-8')
                    struct.pack_into('!10sii', self.dir_buf, beginIndex, padded_field_name, int(ftype),
                                     int(flen))
                    beginIndex = beginIndex + struct.calcsize('!10sii')
                # ═══ 将拼装好的 block_0 内容真正写入磁盘 ═══
                # 文件指针跳转到文件开头（第 0 字节）
                self.f_handle.seek(0)
                # 把整个 4096 字节的缓冲区一次性写入磁盘
                self.f_handle.write(self.dir_buf)
                self.f_handle.flush()
                print('block_0 已写入磁盘（{0} 个字段）'.format(self.num_of_fields))

            else:
                if isinstance(tablename, bytes):
                    self.num_of_fields = self._read_positive_int(
                        "please input the number of fields in table " + tablename.decode('utf-8') + ":")
                else:
                    self.num_of_fields = self._read_positive_int(
                        "please input the number of fields in table " + tablename + ":")
                # 创建缓冲区块
                self.dir_buf = ctypes.create_string_buffer(BLOCK_SIZE)
                self.block_id = 0
                self.data_block_num = 0
                struct.pack_into('!iii', self.dir_buf, beginIndex, 0, 0,
                                 int(self.num_of_fields))

                beginIndex = beginIndex + struct.calcsize('!iii')

                for i in range(int(self.num_of_fields)):
                    field_name = self._read_field_name(i)
                    padded_field_name = ' ' * (10 - len(field_name.strip())) + field_name
                    field_type = self._read_field_type(
                        "please input the type of field"
                        "(0:char 1:varchar 2:int 3:bool 4:float"
                        " 5:bit 6:bitvarying 7:date 8:time) " + str(i) + " :")
                    # 修改原因：有固定长度的类型自动设定，不询问用户
                    if int(field_type) == 2:     # int
                        field_length = 4
                    elif int(field_type) == 3:   # bool
                        field_length = 1
                    elif int(field_type) == 4:   # float
                        field_length = 8
                    elif int(field_type) == 7:   # date
                        field_length = 10
                    elif int(field_type) == 8:   # time
                        field_length = 8
                    else:
                        field_length = self._read_positive_int("please input the length of field " + str(i) + " :")
                    temp_tuple = (padded_field_name, int(field_type), int(field_length))
                    self.field_name_list.append(temp_tuple)
                    if isinstance(padded_field_name, str):
                        padded_field_name = padded_field_name.encode('utf-8')
                    struct.pack_into('!10sii', self.dir_buf, beginIndex, padded_field_name, int(field_type),
                                     int(field_length))
                    beginIndex = beginIndex + struct.calcsize('!10sii')
                # 写回第0块
                self.f_handle.seek(0)
                self.f_handle.write(self.dir_buf)
                self.f_handle.flush()
                print('block_0 已写入磁盘（{0} 个字段）'.format(self.num_of_fields))

        else:  # there is something in the file

            self.block_id, self.data_block_num, self.num_of_fields = struct.unpack_from('!iii', self.dir_buf, 0)

            _debug_print('number of fields is ', self.num_of_fields)
            _debug_print('data_block_num', self.data_block_num)
            beginIndex = struct.calcsize('!iii')

            # the followins is to read field name, field type and field length into main memory structures
            for i in range(self.num_of_fields):
                field_name, field_type, field_length = struct.unpack_from('!10sii', self.dir_buf,
                                                                          beginIndex + i * struct.calcsize(
                                                                              '!10sii'))  # i means no memory alignment

                temp_tuple = (field_name, field_type, field_length)
                self.field_name_list.append(temp_tuple)
                _debug_print("the " + str(i) + "th field information (field name,field type,field length) is ", temp_tuple)
        # print self.field_name_list
        record_head_len = struct.calcsize('!ii10s')
        record_content_len = sum(map(lambda x: x[2], self.field_name_list))
        # print record_content_len

        Flag = 1
        while Flag <= self.data_block_num:
            self.f_handle.seek(BLOCK_SIZE * Flag)
            self.active_data_buf = self.f_handle.read(BLOCK_SIZE)
            self.block_id, self.Number_of_Records = struct.unpack_from('!ii', self.active_data_buf, 0)
            _debug_print('Block_ID=%s,   Contains %s data' % (self.block_id, self.Number_of_Records))
            # There exists record
            if self.Number_of_Records > 0:
                for i in range(self.Number_of_Records):
                    offset = \
                        struct.unpack_from('!i', self.active_data_buf,
                                           struct.calcsize('!ii') + i * struct.calcsize('!i'))[
                            0]
                    # 修改原因：空闲槽标记 offset=-1 表示逻辑删除，跳过不加载到内存
                    if offset == -1:
                        continue
                    self.record_Position.append((Flag, i))
                    record = struct.unpack_from('!' + str(record_content_len) + 's', self.active_data_buf,
                                                offset + record_head_len)[0]
                    tmp = 0
                    tmpList = []
                    for field in self.field_name_list:
                        t = record[tmp:tmp + field[2]].strip()
                        tmp = tmp + field[2]
                        # 修改原因：类型系统扩展，float 也需从字符串转回数值
                        if field[1] == 2:       # int
                            t = int(t)
                        if field[1] == 3:       # bool
                            t = bool(t)
                        if field[1] == 4:       # float
                            t = float(t)
                        tmpList.append(t)
                    self.record_list.append(tuple(tmpList))
            Flag += 1

    # ------------------------------
    # 3. 返回表中所有已缓存的记录列表（内存中的 record_list，不含重新读取磁盘）return the record list of the table
    # input:
    # 返回值：list[tuple]，每条记录为一个字段值元组      
    # -------------------------------------
    def getRecord(self):
        return self.record_list


# 【M】修改函数参数，用于区分正常插入和恢复插入
    def insert_record(self, insert_record,  is_recovery=False):
        """
        功能：向表中插入一行数据先逐字段校验类型（str/int/bool）和长度限制，
              再将记录格式化为定长二进制串写入 .dat 文件对应数据块
        输入参数：insert_record: list[str]，用户输入的字段值列表（已去空白）
        返回值：bool，校验通过且写入成功返回 True
        算法：记录从块末尾向前生长，偏移量表从块头部向后生长，两者相向增长
        """

        # example: ['xuyidan','23','123456']

        # step 1 : to check the insert_record is True or False

        tmpRecord = []
        for idx in range(len(self.field_name_list)):
            insert_record[idx] = insert_record[idx].strip()
            if self.field_name_list[idx][1] in [0, 1, 5, 6, 7, 8]:  # 字符串类
                if len(insert_record[idx]) > self.field_name_list[idx][2]:
                    return False
                tmpRecord.append(insert_record[idx])
            if self.field_name_list[idx][1] == 2:  # int
                try:
                    tmpRecord.append(int(insert_record[idx]))
                except:
                    return False
            if self.field_name_list[idx][1] == 3:  # bool
                try:
                    tmpRecord.append(bool(insert_record[idx]))
                except:
                    return False
            # 修改原因：类型系统扩展到 9 种，新增 float
            if self.field_name_list[idx][1] == 4:  # float
                try:
                    tmpRecord.append(float(insert_record[idx]))
                except:
                    return False
            insert_record[idx] = ' ' * (self.field_name_list[idx][2] - len(insert_record[idx])) + insert_record[idx]

        # step2: Add tmpRecord to record_list ; change insert_record into inputstr
        inputstr = ''.join(insert_record)

        # Step3: To calculate MaxNum in each Data Blocks
        record_content_len = len(inputstr)
        record_head_len = struct.calcsize('!ii10s')
        record_len = record_head_len + record_content_len
        MAX_RECORD_NUM = (BLOCK_SIZE - struct.calcsize('!i') - struct.calcsize('!ii')) / (
                record_len + struct.calcsize('!i'))

        # Step4: 先扫描空闲槽位（偏移 = -1），复用已删记录的位置，再决定是否追加
        free_slot = self._find_free_slot()
        reuse_slot = free_slot is not None

        if reuse_slot:
            # 复用空闲槽位：无需修改块首部记录数和 data_block_num
            print('  >> 复用空闲槽位: block={0}, slot={1}'.format(
                free_slot[0], free_slot[1]))
            last_Position = free_slot
        else:
            # 无空闲槽位，按堆文件方式追加到末尾
            if not len(self.record_Position):
                self.data_block_num += 1
                self.record_Position.append((1, 0))
            else:
                prev = self.record_Position[-1]
                if prev[1] == MAX_RECORD_NUM - 1:
                    self.record_Position.append((prev[0] + 1, 0))
                    self.data_block_num += 1
                else:
                    self.record_Position.append((prev[0], prev[1] + 1))
            last_Position = self.record_Position[-1]

        self.record_list.append(tuple(tmpRecord))

        # 【M】新增，先记后写规则（WAL）
        txn_id = None

        if not is_recovery:

            txn_id = generate_txn_id()

            begin_transaction(txn_id)

            write_before_image(txn_id, "INSERT", self.table_name)

            write_after_image(txn_id, "INSERT", self.table_name, tmpRecord)

            commit_transaction(txn_id)
            # 模拟提交后、写入数据库前崩溃
            # os._exit(0)

        # Step5: Write new record into file xxx.dat
        offset_table_pos = (struct.calcsize('!ii') +
                           last_Position[1] * struct.calcsize('!i'))
        beginIndex = BLOCK_SIZE - (last_Position[1] + 1) * record_len

        if reuse_slot:
            # 复用槽位：只更新偏移表项 + 重写记录数据，不改块首部
            self.f_handle.seek(BLOCK_SIZE * last_Position[0] + offset_table_pos)
            self.buf = ctypes.create_string_buffer(struct.calcsize('!i'))
            struct.pack_into('!i', self.buf, 0, beginIndex)
            self.f_handle.write(self.buf)
            self.f_handle.flush()
        else:
            # 追加模式：更新 data_block_num + 块首部记录数 + 偏移表项
            self.f_handle.seek(0)
            self.buf = ctypes.create_string_buffer(struct.calcsize('!ii'))
            struct.pack_into('!ii', self.buf, 0, 0, self.data_block_num)
            self.f_handle.write(self.buf)
            self.f_handle.flush()

            self.f_handle.seek(BLOCK_SIZE * last_Position[0])
            self.buf = ctypes.create_string_buffer(struct.calcsize('!ii'))
            struct.pack_into('!ii', self.buf, 0, last_Position[0], last_Position[1] + 1)
            self.f_handle.write(self.buf)
            self.f_handle.flush()

            self.f_handle.seek(BLOCK_SIZE * last_Position[0] + offset_table_pos)
            self.buf = ctypes.create_string_buffer(struct.calcsize('!i'))
            struct.pack_into('!i', self.buf, 0, beginIndex)
            self.f_handle.write(self.buf)
            self.f_handle.flush()

        # 写入记录数据（两种模式都需要）
        record_schema_address = struct.calcsize('!iii')
        update_time = '2016-11-16'
        self.f_handle.seek(BLOCK_SIZE * last_Position[0] + beginIndex)
        self.buf = ctypes.create_string_buffer(record_len)
        struct.pack_into('!ii10s', self.buf, 0, record_schema_address, record_content_len, update_time.encode('utf-8'))
        struct.pack_into('!' + str(record_content_len) + 's', self.buf, record_head_len, inputstr.encode('utf-8'))
        self.f_handle.write(self.buf.raw)
        self.f_handle.flush()

        return True

    # ------------------------------
    # 5.显示表结构 + 所有数据show the data structure and its data
    # -------------------------------------

    def show_table_data(self):
        # 修改原因：按对齐表格显示记录，并在空表时给出明确提示
        header_list = [_to_display_text(field_info[0]) for field_info in self.field_name_list]
        if len(self.record_list) == 0:
            print('该表暂无数据')
            return

        record_rows = []
        for record in self.record_list:
            record_rows.append([_to_display_text(field_value) for field_value in record])
        _print_aligned_table(header_list, record_rows)

    def delete_record_by_field(self, field_name, field_value):
        """
        功能描述：按指定字段和值删除记录。在偏移量表中标记 -1（逻辑删除），
                  插入时通过 _find_free_slot 复用这些槽位，无需滑动记录或重写整个文件。
        输入参数：field_name: str/bytes，条件字段名；field_value: str，匹配值。
        返回值：tuple[bool, int/str]。
        """
        normalized_field_name = self._normalize_field_name(field_name)
        field_name_list = [self._normalize_field_name(field_info[0]) for field_info in self.field_name_list]
        if normalized_field_name not in field_name_list:
            return False, 'field does not exist.'

        field_index = field_name_list.index(normalized_field_name)
        field_type = self.field_name_list[field_index][1]
        is_valid, converted_field_value = self._convert_value_by_field_type(field_type, field_value)
        if not is_valid:
            return False, 'value type does not match the field type.'

        # 第一遍扫描：找到所有匹配记录的 (内存索引, block_id, record_index)
        deleted_entries = []
        for idx, record in enumerate(self.record_list):
            current_value = self._normalize_record_value_for_compare(field_type, record[field_index])
            if current_value == converted_field_value:
                block_id, rec_idx = self.record_Position[idx]
                deleted_entries.append((idx, block_id, rec_idx))

        if len(deleted_entries) == 0:
            return True, 0

        # 从后往前处理，避免索引错位
        for mem_idx, block_id, rec_idx in sorted(deleted_entries, reverse=True):
            # 在偏移量表中写入 -1，标记该槽位为空闲
            offset_entry_pos = (BLOCK_SIZE * block_id +
                               struct.calcsize('!ii') +
                               rec_idx * struct.calcsize('!i'))
            self.f_handle.seek(offset_entry_pos)
            self.buf = ctypes.create_string_buffer(struct.calcsize('!i'))
            struct.pack_into('!i', self.buf, 0, -1)
            self.f_handle.write(self.buf)
            self.f_handle.flush()

            # 从内存列表中移除
            del self.record_list[mem_idx]
            del self.record_Position[mem_idx]

        return True, len(deleted_entries)

    # 【M】增加参数is_recovery
    def update_record_by_field(self, condition_field_name, condition_field_value, target_field_name, new_field_value, is_recovery=False):
        """
        功能描述：按条件字段匹配记录，并更新目标字段为新值，返回更新条数
        输入参数：condition_field_name: str/bytes，条件字段名；condition_field_value: str，条件匹配值；target_field_name: str/bytes，要更新的字段名；new_field_value: str，新值
        返回值：tuple[bool, int/str]，成功时返回 True 和更新条数，失败时返回 False 和错误信息
        """
        # 修改原因：补全选项 7 的底层更新能力，支持按条件匹配后更新指定字段并持久化写回
        normalized_condition_field = self._normalize_field_name(condition_field_name)
        normalized_target_field = self._normalize_field_name(target_field_name)
        field_name_list = [self._normalize_field_name(field_info[0]) for field_info in self.field_name_list]

        if normalized_condition_field not in field_name_list:
            return False, 'condition field does not exist.'
        if normalized_target_field not in field_name_list:
            return False, 'target field does not exist.'

        condition_field_index = field_name_list.index(normalized_condition_field)
        target_field_index = field_name_list.index(normalized_target_field)

        condition_field_type = self.field_name_list[condition_field_index][1]
        target_field_type = self.field_name_list[target_field_index][1]
        target_field_length = self.field_name_list[target_field_index][2]

        is_valid_condition, converted_condition_value = self._convert_value_by_field_type(
            condition_field_type, condition_field_value)
        if not is_valid_condition:
            return False, 'condition value type does not match the field type.'

        is_valid_new_value, converted_new_value = self._validate_value_for_field(
            target_field_type, target_field_length, new_field_value)
        if not is_valid_new_value:
            return False, converted_new_value

        updated_records = []
        updated_count = 0

        txn_id = None
        # 【M】恢复阶段不生成新事务
        if not is_recovery:
            txn_id = generate_txn_id()
            begin_transaction(txn_id)

        for record in self.record_list:
            current_record = list(record)
            current_condition_value = self._normalize_record_value_for_compare(
                condition_field_type, current_record[condition_field_index])
            if current_condition_value == converted_condition_value:
                # 【M】写前像
                if not is_recovery:
                    write_before_image(txn_id, "UPDATE", self.table_name, list(record))

                current_record[target_field_index] = converted_new_value
                # 【M】写后像
                if not is_recovery:
                    write_after_image(txn_id, "UPDATE", self.table_name, current_record)

                updated_count += 1
            updated_records.append(tuple(current_record))

        if updated_count == 0:
            # 【M】避免残留事务
            if not is_recovery:
                remove_active_transaction(txn_id)
            return True, 0

        # 【M】先提交
        if not is_recovery:
            print("UPDATE提交事务:", txn_id)
            commit_transaction(txn_id)
            # 模拟崩溃点：CTL已提交，但DB还没写完
            os._exit(0)
            # 提交后写入db
            if not self._rebuild_storage_records(updated_records):
                return False, 'failed to rebuild the data file after update.'
        
        if not is_recovery:
            remove_active_transaction(txn_id)

        return True, updated_count

    # --------------------------------
    # 6.关闭表文件并从磁盘删除对应的 .dat 数据文件（彻底清除数据）to delete  the data file
    #输入参数：tableName: bytes/str，表名
    # output
    #       True or False
    # -----------------------------------
    def delete_table_data(self, tableName):
        # step 1: identify whether the file is still open
        if self.open == True:
            self.f_handle.close()
            self.open = False

        # step 2: remove the file from os   
        tableName.strip()
        if os.path.exists(tableName + '.dat'.encode('utf-8')):
            os.remove(tableName + '.dat'.encode('utf-8'))

        return True

    @staticmethod
    def remove_table_file(table_name):
        """
        功能描述：按表名直接删除对应的 .dat 数据文件，供删表流程调用
        输入参数：table_name: bytes/str，要删除的表名
        返回值：bool，删除成功或文件本就不存在时返回 True
        异常处理：无；文件不存在时按删除成功处理
        """
        # 修改原因：删除表时不应为了删文件而重新构造 Storage 对象，避免误创建新的空 .dat 文件
        normalized_name = table_name.strip()
        if isinstance(normalized_name, str):
            normalized_name = normalized_name.encode('utf-8')
        data_file_name = normalized_name + '.dat'.encode('utf-8')
        if os.path.exists(data_file_name):
            os.remove(data_file_name)
        return True

    @staticmethod
    def remove_all_data_files():
        """
        功能描述：删除当前目录下所有 .dat 数据文件，供“删除所有表和数据”流程调用
        输入参数：无
        返回值：int，实际删除的 .dat 文件数量
        异常处理：无；没有 .dat 文件时返回 0
        """
        # 修改原因：选项 4 需要一次性清空全部数据文件，直接按扩展名扫描比逐表构造对象更安全
        removed_count = 0
        for file_name in os.listdir('.'):
            if file_name.lower().endswith('.dat') and os.path.isfile(file_name):
                os.remove(file_name)
                removed_count += 1
        return removed_count

    # ------------------------------
    # 2. 获取表的字段结构（模式信息），返回字段名、类型、长度的列表get the list of field information, each element of which is (field name, field type, field length)
    # input:
    #  返回值：list[(bytes/int, int, int)]，每个元素为 (字段名, 类型码, 长度)      
    # -------------------------------------

    def getFieldList(self):
        return self.field_name_list

    def __del__(self):
        """
        功能：析构时更新 block_0 的 data_block_num 并 flush+close 文件，防止元数据未落盘
        """

        if self.open == True:
            self.f_handle.seek(0)
            self.buf = ctypes.create_string_buffer(struct.calcsize('!ii'))
            struct.pack_into('!ii', self.buf, 0, 0, self.data_block_num)
            self.f_handle.write(self.buf)
            self.f_handle.flush()
            self.f_handle.close()

    # --------------------------------
    # Author: 郑许博雅
    # 新增：根据位置读取记录
    # ---------------------------------
    def read_record_by_position(self, block_id, slot_id):
        """根据块号和槽位读取记录"""
        import struct
        try:
            self.f_handle.seek(block_id * BLOCK_SIZE)
            block_buf = self.f_handle.read(BLOCK_SIZE)
            
            # 解析偏移表，获取记录起始位置
            offset = struct.unpack_from('!i', block_buf, struct.calcsize('!ii') + slot_id * 4)[0]
            
            # 读取记录
            record_head_len = struct.calcsize('!ii10s')
            record_content_len = struct.unpack_from('!i', block_buf, offset + 4)[0]
            record_data = struct.unpack_from(f'!{record_content_len}s', block_buf, offset + record_head_len)[0]
            
            # 解析记录字段
            tmp = 0
            record = []
            for field in self.field_name_list:
                t = record_data[tmp:tmp + field[2]].strip()
                tmp += field[2]
                if field[1] == 2:
                    t = int(t)
                if field[1] == 3:
                    t = bool(t)
                record.append(t)
            return tuple(record)
        except Exception as e:
            print(f"读取记录失败: {e}")
            return None
        
#该函数用于测试索引效果，不包含事务回滚
    def insert_record_simple(self, insert_record):
        """
        简化版插入方法，用于测试索引性能
        不涉及事务、不涉及空闲槽位复用
        """
        # step 1: 校验字段
        tmpRecord = []
        formatted_values = []
        
        for idx in range(len(self.field_name_list)):
            val = insert_record[idx].strip()
            field_type = self.field_name_list[idx][1]
            field_len = self.field_name_list[idx][2]
            
            if field_type in [0, 1, 5, 6, 7, 8]:  # 字符串类
                if len(val) > field_len:
                    print(f"字段 {idx} 长度超限: {len(val)} > {field_len}")
                    return False
                tmpRecord.append(val)
                formatted_values.append(val.ljust(field_len, ' '))
                
            elif field_type == 2:  # int
                try:
                    int_val = int(val)
                    tmpRecord.append(int_val)
                    str_val = str(int_val)
                    if len(str_val) > field_len:
                        return False
                    formatted_values.append(str_val.rjust(field_len, ' '))
                except:
                    return False
                    
            elif field_type == 3:  # bool
                try:
                    bool_val = val.lower() in ('true', '1', 'yes', 't')
                    tmpRecord.append(bool_val)
                    formatted_values.append('1' if bool_val else '0')
                except:
                    return False
                    
            elif field_type == 4:  # float
                try:
                    float_val = float(val)
                    tmpRecord.append(float_val)
                    str_val = f"{float_val:.2f}"
                    if len(str_val) > field_len:
                        str_val = str_val[:field_len]
                    formatted_values.append(str_val.rjust(field_len, ' '))
                except:
                    return False
        
        # step 2: 组装记录
        inputstr = ''.join(formatted_values)
        record_content_len = len(inputstr)
        record_head_len = struct.calcsize('!ii10s')
        record_len = record_head_len + record_content_len
        
        # step 3: 计算每块最大记录数
        MAX_RECORD_NUM = (BLOCK_SIZE - struct.calcsize('!i') - struct.calcsize('!ii')) // (record_len + struct.calcsize('!i'))
        
        if MAX_RECORD_NUM <= 0:
            MAX_RECORD_NUM = 1
        
        # step 4: 计算插入位置
        if not len(self.record_Position):
            self.data_block_num += 1
            self.record_Position.append((1, 0))
        else:
            last = self.record_Position[-1]
            if last[1] >= MAX_RECORD_NUM - 1:
                self.record_Position.append((last[0] + 1, 0))
                self.data_block_num += 1
            else:
                self.record_Position.append((last[0], last[1] + 1))
        
        last_Position = self.record_Position[-1]
        self.record_list.append(tuple(tmpRecord))
        
        # step 5: 写入磁盘
        # 更新 data_block_num 到块0
        self.f_handle.seek(0)
        buf = ctypes.create_string_buffer(struct.calcsize('!ii'))
        struct.pack_into('!ii', buf, 0, 0, self.data_block_num)
        self.f_handle.write(buf)
        self.f_handle.flush()
        
        # 更新数据块头部的记录数
        self.f_handle.seek(BLOCK_SIZE * last_Position[0])
        buf = ctypes.create_string_buffer(struct.calcsize('!ii'))
        struct.pack_into('!ii', buf, 0, last_Position[0], last_Position[1] + 1)
        self.f_handle.write(buf)
        self.f_handle.flush()
        
        # 写入偏移表
        offset_pos = struct.calcsize('!ii') + last_Position[1] * struct.calcsize('!i')
        beginIndex = BLOCK_SIZE - (last_Position[1] + 1) * record_len
        
        self.f_handle.seek(BLOCK_SIZE * last_Position[0] + offset_pos)
        buf = ctypes.create_string_buffer(struct.calcsize('!i'))
        struct.pack_into('!i', buf, 0, beginIndex)
        self.f_handle.write(buf)
        self.f_handle.flush()
        
        # 写入记录数据
        record_schema_address = struct.calcsize('!iii')
        update_time = '2016-11-16'
        
        self.f_handle.seek(BLOCK_SIZE * last_Position[0] + beginIndex)
        buf = ctypes.create_string_buffer(record_len)
        struct.pack_into('!ii10s', buf, 0, record_schema_address, record_content_len, update_time.encode('utf-8'))
        struct.pack_into('!' + str(record_content_len) + 's', buf, record_head_len, inputstr.encode('utf-8'))
        self.f_handle.write(buf.raw)
        self.f_handle.flush()
        
        return True