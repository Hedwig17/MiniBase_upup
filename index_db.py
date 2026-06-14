'''
index_db.py - B+树索引模块
# storage_db.py
# Author: Jingyu Han  hjymail@163.com
# modified by: 郑许博雅
================================
'''

import struct
import math
from storage_db import Storage
from common_db import BLOCK_SIZE

# The 0 block stores the meta information of the tree
'''
block_id|has_root|num_of_levels|root_node_ptr
# note: the root_node_ptr is a block id
# 快速定位根结点，并知道树有多深
'''
MAX_NUM_OF_KEYS=200#the number of keys in each block
#存储块大小是4096，每个键值占10字节，每个指针占4字节，假设每个叶子结点项包含一个键和一个指针，则每个项占14字节，4096/14约等于292，所以每个结点最多可以存储292个键值对（实际可能更少，因为还需要存储结点类型、键数量等元信息）。因此，n可以设置为200，以留出一些空间用于元信息和未来的扩展



# structure of leaf node
'''
block_id|node_type|number_of_keys|key_0|ptr_0|...|key_i|ptr_i|...|key_n|ptr_n|...free space...|last_ptr
note: for leaf node, ptr is a block id+entry id (8 bytes) except for the last one
#ptr即记录所在的数据块号(4)和块内偏移表下标(4)
'''
LEAF_NODE_TYPE=1
LEN_OF_LEAF_NODE=10+4+4  # key takes 10 bytes, block_id takes 4 bytes and offset takes 4 bytes


# structure of internal node
'''
block_id|node_type|number_of_keys|key_0|ptr_0|key_1|ptr_1|...|key_n|ptr_n|...free space...|last_ptr|
note: For internal node, ptr is just a block id( 4 bytes) 
'''
INTERNAL_NODE_TYPE=0
LEN_OF_INTERNAL_NODE=10+4


SPECIAL_INDEX_BLOCK_PTR=-1 # this is the last ptr for last leaf node when the next node is unknown



import os
import common_db
import ctypes

def test():
    my_dict={}
    my_dict.setdefault('one',80)
    my_dict.setdefault('two',90)
    my_dict.setdefault('aaa',90)
    print (my_dict.keys())
    print (my_dict.items())
    for my_each_key in sorted(my_dict):
        print ("the value of key ",my_each_key," is ",my_dict[my_each_key])

    my_list=[]
    my_tuple=(1,2)
    my_list.append(my_tuple)
    (a,b)=my_list[0]

    print (a,b)


    


class Index(object):
    

    #-----------------------------
    # 构造函数：初始化索引对象，打开或创建索引文件
    # input
    #       tablename : 表名（字符串）
    # 算法
    #       1. 判断 .ind 文件是否存在
    #       2. 若不存在：创建新文件，写入空元数据
    #       3. 若存在：打开文件，读取元数据到内存
    #--------------------------------
    def __init__(self,tablename):
        #！修改处
        self.tablename = tablename
        self.is_new_file = not os.path.exists(tablename+'.ind')
        
        if self.is_new_file:
            self.f_handle = open(tablename+'.ind', 'wb+')
            # 创建空的元数据块
            self.has_root = False
            self.num_of_levels = 0
            self.root_node_ptr = 0
            self._write_meta()  # 写入空元数据
        else:
            self.f_handle = open(tablename+'.ind', 'rb+')
            self._load_meta()  # 读取元数据
                # to view all the index entries
                # to be inserted here

    #---------------------------------
    # destructor of the class
    #-----------------------------------
    def __del__(self):
        print ("__del__ of ",Index.__name__)
        self.f_handle.close()
        self.open=False

#========================公开接口======================

    #-----------------------------
    # 批量创建索引（从数据文件读取所有记录，排序后构建 B+ 树）
    # input
    #       index_field : 要建立索引的字段名
    # output
    #       None
    # 算法
    #       1. 创建 Storage 对象，获取字段列表
    #       2. 遍历所有记录，提取 (键, 物理地址) 对
    #       3. 按键值排序
    #       4. 清空索引文件，逐条插入构建 B+ 树
    #--------------------------------
    def create_index(self, index_field):
        print('create_index begins to execute')
        
        # 获取数据
        store = Storage(self.tablename)
        field_list = store.getFieldList()
        field_idx = None
        for i, (fname_bytes, ftype, flen) in enumerate(field_list):
            fname = fname_bytes.decode('utf-8').strip()
            if fname == index_field:
                field_idx = i
                break
        
        if field_idx is None:
            print(f"错误：表中不存在字段 '{index_field}'")
            return
        
        # 收集键值对，注意：键需要是 10 字节的 bytes
        pairs = []
        for pos, record in zip(store.record_Position, store.record_list):
            key_raw = record[field_idx]
            
            # ========== 关键修复 ==========
            # key_raw 可能是 bytes 或 str
            if isinstance(key_raw, bytes):
                # 直接使用 bytes，不要再 encode
                key_bytes = key_raw
            elif isinstance(key_raw, str):
                key_bytes = key_raw.encode('utf-8')
            else:
                key_bytes = str(key_raw).encode('utf-8')
            
            # 补齐到 10 字节
            if len(key_bytes) > 10:
                key_bytes = key_bytes[:10]
            elif len(key_bytes) < 10:
                key_bytes = key_bytes.ljust(10, b' ')
            
            block_id, offset = pos
            pairs.append((key_bytes, block_id, offset))
            # 调试：打印前几条
            if len(pairs) <= 5:
                print(f"  键 {len(pairs)}: {key_bytes}")
        
        pairs.sort(key=lambda x: x[0])
            
        # 关闭当前索引文件
        self.f_handle.close()
        
        # 删除旧索引文件
        ind_file = self.tablename + '.ind'
        if os.path.exists(ind_file):
            os.remove(ind_file)
        
        # 重新初始化索引对象的状态
        self.f_handle = open(ind_file, 'wb+')
        self.is_new_file = True
        self.has_root = False
        self.num_of_levels = 0
        self.root_node_ptr = 0
        
        # 逐个插入
        for key_bytes, blk, off in pairs:
            self.insert_index_entry(key_bytes, blk, off)
        
        # 确保元数据正确写入
        self._write_meta()
        
        print(f"索引构建完成，共插入 {len(pairs)} 条记录")

    #-----------------------------
    # 精确查找索引键，返回所有匹配的记录位置
    # input
    #       field_value : 要查找的键值（str 或 bytes）
    # output
    #       list[tuple] : 每个元素为 (block_id, offset)
    # 算法
    #       1. 将 field_value 转为 10 字节 bytes
    #       2. 从根下降到目标叶子结点
    #       3. 在当前叶子及后续叶子中（通过 last_ptr 链表）查找匹配键
    #       4. 返回所有匹配的记录位置
    #--------------------------------
    def search(self, field_value):
        # 统一转换为 10 字节 bytes
        if isinstance(field_value, str):
            key_bytes = field_value.encode('utf-8')
        else:
            key_bytes = field_value
        
        key_bytes = key_bytes[:10].ljust(10, b' ')
        
        self._load_meta()
        if not self.has_root:
            return []
        
        leaf_ptr = self._find_leaf(key_bytes)
        if leaf_ptr < 0:
            return []
        
        results = []
        current_ptr = leaf_ptr
        
        while current_ptr != SPECIAL_INDEX_BLOCK_PTR and current_ptr > 0:
            buf = ctypes.create_string_buffer(BLOCK_SIZE)
            self.f_handle.seek(current_ptr * BLOCK_SIZE)
            self.f_handle.readinto(buf)
            
            _, node_type, num_keys = struct.unpack_from('!iii', buf, 0)
            if node_type != LEAF_NODE_TYPE:
                break
            
            found_any = False
            
            for i in range(num_keys):
                k_bytes, blk, off = struct.unpack_from(
                    '!10sii', buf, struct.calcsize('!iii') + i * LEN_OF_LEAF_NODE)
                
                # 直接比较 bytes，不需要 decode
                if k_bytes == key_bytes:
                    results.append((blk, off))
                    found_any = True
                elif k_bytes > key_bytes:
                    # 键已排序，后面不会再有匹配（但要考虑重复键可能跨叶子）
                    # 如果当前叶子找到了匹配，还需要检查下一个叶子
                    if not found_any:
                        return results
                    else:
                        break
            
            # 如果当前叶子最后一个键等于查找键，可能下一个叶子还有重复
            # 需要检查最后一个键
            if num_keys > 0:
                last_k_bytes, _, _ = struct.unpack_from(
                    '!10sii', buf, struct.calcsize('!iii') + (num_keys - 1) * LEN_OF_LEAF_NODE)
                if last_k_bytes == key_bytes:
                    current_ptr = struct.unpack_from('!i', buf, BLOCK_SIZE - 4)[0]
                else:
                    break
            else:
                break
        
        return results
    
    #-----------------------------
    # 范围查询，返回 [start_key, end_key] 内的所有索引条目
    # input
    #       start_key : 起始键（str 或 bytes）
    #       end_key   : 结束键（str 或 bytes）
    # output
    #       list[tuple] : 每个元素为 (key, block_id, offset)
    # 算法
    #       1. 将 start_key 和 end_key 转为 10 字节 bytes
    #       2. 找到包含 start_key 的叶子结点
    #       3. 通过叶子链表顺序遍历，收集范围内所有条目
    #-------------------------------- 
    def range_search(self, start_key, end_key):
        if isinstance(start_key, str):
            start_key = start_key.encode('utf-8')
        if isinstance(end_key, str):
            end_key = end_key.encode('utf-8')
    
        start_key = start_key[:10].ljust(10, b' ')
        end_key = end_key[:10].ljust(10, b' ')
    
        self._load_meta()
        if not self.has_root or start_key > end_key:
            return []
    
        leaf_ptr = self._find_leaf(start_key)
        if leaf_ptr < 0:
            return []

        results = []
        current_ptr = leaf_ptr

        while current_ptr != SPECIAL_INDEX_BLOCK_PTR and current_ptr > 0:
            buf = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
            self.f_handle.seek(current_ptr * common_db.BLOCK_SIZE)
            self.f_handle.readinto(buf)

            _, node_type, num_keys = struct.unpack_from('!iii', buf, 0)
            if node_type != LEAF_NODE_TYPE:
                break

            for i in range(num_keys):
                k_bytes, blk, off = struct.unpack_from(
                    '!10sii', buf, struct.calcsize('!iii') + i * LEN_OF_LEAF_NODE)
                
                if k_bytes > end_key:
                        return results
                if k_bytes >= start_key:
                        results.append((k_bytes, blk, off)) 

            # 通过叶子链表继续下一个叶子节点
            current_ptr = struct.unpack_from('!i', buf, common_db.BLOCK_SIZE - 4)[0]

        return results
    
    #-----------------------------
    # 删除指定的索引条目
    # input
    #       field_value : 索引键值
    #       block_id    : 数据块号
    #       offset      : 记录偏移
    # output
    #       bool : 删除成功返回 True，否则返回 False
    # 算法
    #       1. 从根下降到目标叶子结点，记录路径栈
    #       2. 在叶子结点中删除指定条目
    #       3. 若叶子结点下溢，进行重分配或合并
    # 修改记录
    #       TODO： 当前内部结点下溢为简化处理，待完善
    #--------------------------------
    def delete_index_entry(self, field_value, block_id, offset):
        """
        删除指定的索引条目 (field_value, block_id, offset)。
        包含叶子节点的下溢处理（重分配 / 合并）。
        成功返回 True，未找到返回 False。
        """
        self._load_meta()
        if not self.has_root:
            return False

        field_value = field_value[:10] if len(field_value) > 10 else field_value

        # ========== 从根下降到叶子，记录路径 ==========
        next_node_ptr = self.root_node_ptr
        level = 0
        path_stack = []  # [(parent_block_id, child_idx), ...]

        while level < self.num_of_levels - 1:
            buf = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
            self.f_handle.seek(next_node_ptr * common_db.BLOCK_SIZE)
            self.f_handle.readinto(buf)

            node_id, node_type, num_keys = struct.unpack_from('!iii', buf, 0)
            if node_type != INTERNAL_NODE_TYPE:
                return False

            key_list = []
            ptr_list = []
            for i in range(num_keys):
                k, p = struct.unpack_from('!10si', buf, struct.calcsize('!iii') + i * (10 + 4))
                key_list.append(k.decode().strip())
                ptr_list.append(p)

            last_ptr = struct.unpack_from('!i', buf, common_db.BLOCK_SIZE - 4)[0]
            ptr_list.append(last_ptr)

            next_node_ptr, child_idx = self.get_next_block_ptr(field_value, key_list, ptr_list)
            path_stack.append((node_id, child_idx))
            level += 1

        # ========== 到达叶子节点 ==========
        leaf_id = next_node_ptr
        buf = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
        self.f_handle.seek(leaf_id * common_db.BLOCK_SIZE)
        self.f_handle.readinto(buf)

        _, leaf_type, leaf_num_keys = struct.unpack_from('!iii', buf, 0)
        if leaf_type != LEAF_NODE_TYPE:
            return False

        # 读取叶子节点所有条目
        key_list = []
        ptr_list = []
        delete_pos = -1
        for i in range(leaf_num_keys):
            k_bytes, blk, off = struct.unpack_from(
                '!10sii', buf, struct.calcsize('!iii') + i * LEN_OF_LEAF_NODE)
            k_str = k_bytes.decode().strip()
            key_list.append(k_bytes)
            ptr_list.append((blk, off))
            if k_str == field_value and blk == block_id and off == offset:
                delete_pos = i

        if delete_pos == -1:
            return False  # 未找到

        # 执行删除
        del key_list[delete_pos]
        del ptr_list[delete_pos]
        leaf_num_keys -= 1

        # 写回叶子节点
        self._write_leaf_node(leaf_id, key_list, ptr_list)

        # ========== 检查并处理下溢 ==========
        MIN_KEYS = MAX_NUM_OF_KEYS // 2

        if leaf_num_keys < MIN_KEYS:
            if len(path_stack) == 0:
                # 根节点就是叶子节点
                if leaf_num_keys == 0:
                    self.has_root = False
                    self.num_of_levels = 0
                    self.root_node_ptr = 0
                    self._write_meta()
            else:
                self._handle_leaf_underflow(leaf_id, path_stack, key_list, ptr_list)

        return True
    
    # #-----------------------------
    # 向 B+ 树中插入一条索引记录
    # input
    #       field_value : 索引字段值（str 或 bytes）
    #       block_id    : 数据块号
    #       offset      : 记录在块内的偏移表下标
    # output
    #       None
    # 算法
    #       1. 将 field_value 统一转为 10 字节 bytes（空格补齐）
    #       2. 若树为空：创建根叶子结点，写入元数据
    #       3. 否则：从根下降到目标叶子结点，记录路径栈
    #       4. 若叶子未满：插入新条目并写回
    #       5. 若叶子已满：分裂叶子结点，通过路径栈向上插入父结点
    #--------------------------------
    def insert_index_entry(self,field_value,block_id,offset):
    
        # 统一转为 10 字节 bytes
        if isinstance(field_value, str):
            key_bytes = field_value.encode('utf-8')
        else:
            key_bytes = field_value
        if len(key_bytes) > 10:
            key_bytes = key_bytes[:10]
        elif len(key_bytes) < 10:
            key_bytes = key_bytes.ljust(10, b' ')

        #print(f'insert_index_entry called with field_value={field_value}, block_id={block_id}, offset={offset}')
        print(f'  key_bytes={repr(key_bytes)}')
        #print(f'  self.is_new_file={self.is_new_file}, self.has_root={getattr(self, "has_root", False)}')

        if len(key_bytes.strip()) > 0 and block_id > 0 and offset >= 0:# the following is to insert an index entry into the index file
            if self.is_new_file or not self.has_root:# there is no data in the index file
                # ========== 情况1：空索引文件，创建第一个叶子结点和元数据块 ==========
                # to prepare the data in the index node, which is stored in block 1 
                print("  -> entering empty file branch")
                first_index_block=ctypes.create_string_buffer(common_db.BLOCK_SIZE)

                #block_id|node_type|number_of_keys|key_0|ptr_0
                struct.pack_into('!iii10sii', first_index_block, 0,
                                 1,                     # 块号（实际未使用，仅占位）
                                 LEAF_NODE_TYPE,        # 结点类型
                                 1,                     # 键数量 = 1
                                 key_bytes,  # 键值（需转为bytes）
                                 block_id, offset)
                struct.pack_into('!i',first_index_block,common_db.BLOCK_SIZE-struct.calcsize('!i'),SPECIAL_INDEX_BLOCK_PTR)

                

                # to prepare the meta block node, which is stored in block 0
                self.meta_index_block=ctypes.create_string_buffer(common_db.BLOCK_SIZE)
                struct.pack_into('!i?ii', self.meta_index_block, 0,
                                 0,      # 块号（通常0）
                                 True,   # 有根结点
                                 1,      # 树的高度 = 1（只有叶子层）
                                 1)      # 根结点块号 = 1


                # record the meta information in the main memory data structures
                self.has_root=True
                self.number_of_levels=1
                self.root_node_ptr=1


                # the following is to write data to index file
                self.f_handle.seek(0)
                self.f_handle.write(self.meta_index_block)
                self.f_handle.write(first_index_block)
                self.f_handle.flush()
                self.is_new_file = False
                
                
             # ========== 情况2：索引文件非空，需要定位并插入 ==========   
            else:# there is data in the file
                # 重新读取元数据块（确保最新）
                #print("  -> entering normal insert branch")
                self.meta_index_block=ctypes.create_string_buffer(common_db.BLOCK_SIZE)
                self.f_handle.seek(0)
                self.meta_index_block=self.f_handle.read(common_db.BLOCK_SIZE)

                # 解析元数据
                temp_block_id,self.has_root,self.num_of_levels,self.root_node_ptr=struct.unpack_from('!i?ii',self.meta_index_block,0)
                if self.has_root==True and self.num_of_levels>0 and self.root_node_ptr>0:
                    
                    # 从根开始下降，找到目标叶子结点
                    temp_count=0
                    next_node_ptr=self.root_node_ptr
                    path_stack=[] # 用于记录下降路径上的结点信息，便于后续可能的分裂和更新

                     # 下降内部结点层（除最后一层叶子结点外）
                    while(temp_count<self.num_of_levels-1):# to search through the internal nodes
                        # 读取当前内部结点块
                        current_index_block=ctypes.create_string_buffer(common_db.BLOCK_SIZE)
                        read_pos=next_node_ptr*common_db.BLOCK_SIZE # the begining of the target block
                        
                        self.f_handle.seek(read_pos)
                        current_index_block=self.f_handle.read(common_db.BLOCK_SIZE)
                        # 解析结点类型和键个数
                        current_node_id,current_node_type,current_num_of_keys=struct.unpack_from('!iii',current_index_block,0)

                        if current_node_type!=INTERNAL_NODE_TYPE:
                            print ('the internal node type is wrong')
                            return

                        if current_num_of_keys <=0:
                            print ('the current_num_of_keys is wrong in internal node')
                            return

                        # 提取内部结点的所有键和对应指针
                        key_list=[]
                        ptr_list=[]
                        for i in range(current_num_of_keys):
                            # 每个内部结点项：键(10s) + 子块指针(4B)
                            current_key,current_ptr=struct.unpack_from('!10si',current_index_block,struct.calcsize('!iii')+i*(10+4))
                            key_list.append(current_key)
                            ptr_list.append(current_ptr)

                         # 最后一个指针（在块末尾）    
                        last_ptr,=struct.unpack_from('!i',current_index_block,common_db.BLOCK_SIZE-4)
                        ptr_list.append(last_ptr)
                        
                        # now it is to determine which path we should follow
                        ## 根据键值决定下一步的块号
                        next_node_ptr,child_idx= self.get_next_block_ptr(key_bytes, key_list, ptr_list)
                        temp_count+=1
                        path_stack.append( (current_node_id, child_idx) ) 
                        
                        
                    # now it is at the leaf node
                    # # 到达叶子结点，读取该叶子块
                    current_index_block=ctypes.create_string_buffer(common_db.BLOCK_SIZE)
                    read_pos=next_node_ptr*common_db.BLOCK_SIZE    # where the leaf node lies
                    self.f_handle.seek(read_pos)
                    
                    current_index_block = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
                    self.f_handle.readinto(current_index_block)  # 直接读入缓冲区
                    current_node_type,current_num_of_keys=struct.unpack_from('!ii',current_index_block,struct.calcsize('!i'))
                    
                    if current_node_type==LEAF_NODE_TYPE:# it is leaf node
                        if current_num_of_keys<MAX_NUM_OF_KEYS:# insert the value into the leaf node

                            # the following is to read index entry into main memory list
                            ## 叶子结点未满：读取现有键值对到内存列表
                            key_list=[]
                            ptr_list=[]
                            for i in range(current_num_of_keys):
                                 # 每个叶子项：键(10s) + 块号(4B) + 偏移(4B)
                                current_key,block_ptr,current_offset=struct.unpack_from('!10sii',current_index_block,struct.calcsize('!iii')+i*LEN_OF_LEAF_NODE)
                                key_list.append(current_key)
                                my_tuple=(block_ptr,current_offset)
                                ptr_list.append(my_tuple)
                              
                             # 插入新项
                             #原代码存在错误
                            new_ptr_tuple = (block_id, offset) 
                            self.insert_key_value_into_leaf_list(key_bytes, new_ptr_tuple ,key_list, ptr_list)

                            # 将更新后的列表写回缓冲区 
                            # the following is to write the new index entry list to buffer
                            for i in range(len(key_list)):
                                current_key=key_list[i]
                                (current_id,current_offset)=ptr_list[i]
                                struct.pack_into('!10sii',current_index_block,struct.calcsize('!iii')+i*LEN_OF_LEAF_NODE,current_key,current_id,current_offset)

                              
                            # change the nmber_of_keys
                            # 更新键数量
                            current_num_of_keys+=1
                            struct.pack_into('!i',current_index_block,8,current_num_of_keys)
                            

                            self.f_handle.seek(read_pos)
                            self.f_handle.write(current_index_block)
                            self.f_handle.flush()       
                            #print(f"After insert, leaf {next_node_ptr} has {current_num_of_keys} keys:")
                            keys_in_leaf = []
                            for i in range(current_num_of_keys):
                                k_bytes, _, _ = struct.unpack_from('!10sii', current_index_block, struct.calcsize('!iii') + i * LEN_OF_LEAF_NODE)
                                keys_in_leaf.append(k_bytes.decode().strip())
                            #print(f"  keys: {keys_in_leaf[:10]}...")  # 只打印前10个               
                       
                        else:
                            print("the leaf node is full, we should split")
                            new_block_id, up_key = self.split_leaf_node(current_index_block, next_node_ptr, key_bytes, block_id, offset)
                            # 确保 up_key 是 bytes
                            if isinstance(up_key, str):
                                up_key = up_key.encode('utf-8')
                            self.insert_into_parent(next_node_ptr, path_stack, up_key, new_block_id)

                                                   
                    else:
                        print ('wrong, it is should be a leaf node')
                    
                    
                else:
                    print ('the information in the index file is wrong')

#========================核心 B+ 树操作======================

    #-----------------------------
    # 从根下降到包含 key_bytes 的叶子结点
    # input
    #       key_bytes : 10 字节的 bytes 键
    # output
    #       int : 叶子结点块号，树空或出错返回 -1
    # 算法
    #       1. 读取元数据
    #       2. 从根开始，逐层下降
    #       3. 在内部结点中调用 get_next_block_ptr 确定下一步路径
    #       4. 到达叶子层后返回块号
    #--------------------------------
    def _find_leaf(self, key_bytes):
        """从根下降到包含 key_bytes 的叶子节点，key_bytes 是 10 字节 bytes"""
        self._load_meta()
        if not self.has_root or self.num_of_levels <= 0 or self.root_node_ptr <= 0:
            return -1
        
        next_node_ptr = self.root_node_ptr
        level = 0
        
        while level < self.num_of_levels - 1:
            buf = ctypes.create_string_buffer(BLOCK_SIZE)
            self.f_handle.seek(next_node_ptr * BLOCK_SIZE)
            self.f_handle.readinto(buf)
            
            node_id, node_type, num_keys = struct.unpack_from('!iii', buf, 0)
            if node_type != INTERNAL_NODE_TYPE:
                return -1
            
            key_list = []
            ptr_list = []
            for i in range(num_keys):
                k, p = struct.unpack_from('!10si', buf, struct.calcsize('!iii') + i * (10 + 4))
                key_list.append(k)      # 保持 bytes，不 decode
                ptr_list.append(p)
            
            last_ptr = struct.unpack_from('!i', buf, BLOCK_SIZE - 4)[0]
            ptr_list.append(last_ptr)
            
            next_node_ptr, _ = self.get_next_block_ptr(key_bytes, key_list, ptr_list)
            level += 1
        
        return next_node_ptr
    
    #-----------------------------
    # 递归向父结点插入 (new_key, new_right_ptr)
    # input
    #       current_node_id : 当前结点块号（分裂时的左子结点）
    #       path_stack      : 路径栈，元素为 (parent_block_id, child_idx)
    #       new_key         : 需要上浮的键（10 字节 bytes）
    #       new_right_ptr   : 新右子结点块号
    # output
    #       None
    # 算法
    #       1. 若栈为空：创建新根结点
    #       2. 否则弹出栈顶父结点信息
    #       3. 尝试向父结点插入新键和新指针
    #       4. 若父结点未满：写回磁盘
    #       5. 若父结点已满：分裂父结点，继续向上递归
    #--------------------------------
    def insert_into_parent(self, current_node_id,path_stack, new_key, new_right_ptr):
        """
        递归向父结点插入 (new_key, new_right_ptr)
        path_stack: 记录从根到当前结点的路径，每个元素为 (parent_block_id, child_idx)
        new_key: 需要上浮的键（bytes，10字节）
        new_right_ptr: 新右子结点的块号
        """
        if not path_stack:
            # 没有父结点，说明当前结点是根，需要创建新根
            self.create_new_root(current_node_id,new_key, new_right_ptr)
            return

        parent_block_id, child_idx = path_stack.pop()
        # 读取父结点
        parent_buf = ctypes.create_string_buffer(BLOCK_SIZE)
        self.f_handle.seek(parent_block_id * BLOCK_SIZE)
        self.f_handle.readinto(parent_buf)

        # 尝试插入
        self.insert_into_internal_node(parent_buf, new_key, new_right_ptr, child_idx)
        num_keys= struct.unpack_from('!i', parent_buf,struct.calcsize('!ii') )[0]
        if num_keys<MAX_NUM_OF_KEYS:
            # 未满，写回磁盘
            self.f_handle.seek(parent_block_id * BLOCK_SIZE)
            self.f_handle.write(parent_buf.raw)
            self.f_handle.flush()
            return
        else:
            # 父结点已满，需要分裂
            # 分裂内部结点，产生新的上浮键和右结点指针
            new_up_right_ptr,new_up_key= self.split_internal_node(parent_buf, parent_block_id)
            # 写回分裂后的两个内部结点（原结点和新结点）
            # （_split_internal_node 内部应负责写盘并返回上浮信息）
            # 然后继续向上一层插入
            self.insert_into_parent(parent_block_id, path_stack, new_up_key, new_up_right_ptr)

    #-----------------------------
    # 向内部结点缓冲区中插入新键和新指针（不检查容量）
    # input
    #       parent_buf : 内部结点缓冲区（bytearray）
    #       new_key    : 新键（10 字节 bytes）
    #       new_ptr    : 新指针（子块号）
    #       child_idx  : 插入位置（左指针索引）
    # output
    #       True（总是返回 True，调用者负责容量检查）
    # 算法
    #       1. 读取当前结点的所有键和指针
    #       2. 在 child_idx 位置插入新键
    #       3. 在 child_idx+1 位置插入新指针
    #       4. 重新打包缓冲区
    #--------------------------------
    def insert_into_internal_node(self,parent_buf, new_key, new_ptr, child_idx):
        node_type, num_keys = struct.unpack_from('!ii', parent_buf, 4)  # 跳过 block_id
        # 读取所有键和指针（除最后一个指针）
        keys = []
        ptrs = []
        base_off = struct.calcsize('!iii')
        for i in range(num_keys):
            key, ptr = struct.unpack_from('!10si', parent_buf, base_off + i * (10+4))
            keys.append(key)
            ptrs.append(ptr)
        # 读取最后一个指针
        last_ptr = struct.unpack_from('!i', parent_buf, BLOCK_SIZE - 4)[0]
        ptrs.append(last_ptr)
            
            # 插入新键和新指针
            # 新键插入到 keys[child_idx] 位置（因为 child_idx 是左指针索引，新键应放在该位置）
            # 新指针插入到 ptrs[child_idx+1] 位置
        keys.insert(child_idx, new_key)
        ptrs.insert(child_idx+1, new_ptr)
            
            # 更新 num_keys
        num_keys += 1
            # 重新打包到 parent_buf
            # 头部：block_id 保留原值（先读取原 block_id），node_type, num_keys
        block_id = struct.unpack_from('!i', parent_buf, 0)[0]
        struct.pack_into('!iii', parent_buf, 0, block_id, node_type, num_keys)
        for i in range(num_keys):
            struct.pack_into('!10si', parent_buf, base_off + i * (10+4), keys[i], ptrs[i])
            # 写入最后一个指针（现在 ptrs 长度 = num_keys+1, 最后一个元素是 ptrs[-1]）
        struct.pack_into('!i', parent_buf, BLOCK_SIZE - 4, ptrs[-1])
    
    #-----------------------------
    # 分裂叶子结点
    # input
    #       current_index_block : 原叶子结点缓冲区（bytearray）
    #       next_node_ptr       : 原叶子结点块号
    #       key_bytes           : 待插入的新键（10 字节 bytes）
    #       block_id, offset    : 新记录的物理位置
    # output
    #       tuple : (new_block_id, up_key)
    # 算法
    #       1. 读取原结点所有键值对到内存列表
    #       2. 插入新键值对（保持有序）
    #       3. 计算分裂点：split = ceil((MAX_NUM_OF_KEYS+1)/2)
    #       4. 前 split 个保留在原结点，后 (len-split) 个移到新结点
    #       5. 调整叶子链表指针
    #       6. 写回原结点和新结点
    #       7. 返回新块号和上浮键
    #--------------------------------
    def split_leaf_node(self, current_index_block, next_node_ptr,key_bytes, block_id, offset):
        # 获取当前结点中的键数量
        current_num_of_keys = struct.unpack_from('!i', current_index_block, struct.calcsize('!ii'))[0]

        key_list = []
        ptr_list = []
        for i in range(current_num_of_keys):
            offset_in_block = struct.calcsize('!iii') + i * LEN_OF_LEAF_NODE
            current_key, data_blk, data_off = struct.unpack_from('!10sii', current_index_block, offset_in_block)
            key_list.append(current_key)
            ptr_list.append((data_blk, data_off))

        new_ptr = (block_id, offset)
        self.insert_key_value_into_leaf_list(key_bytes, new_ptr, key_list, ptr_list)

        split = math.ceil((MAX_NUM_OF_KEYS + 1) / 2)   # 左结点保留的数量

        new_block_id = self.get_next_block_id()

        # 更新原结点缓冲区
        original_buf = ctypes.create_string_buffer(BLOCK_SIZE)
        # 写入原结点头部：block_id, node_type, number_of_keys = split
        struct.pack_into('!iii', original_buf, 0,
                        next_node_ptr,
                        LEAF_NODE_TYPE,
                        split)
        for i in range(split):
            key = key_list[i]
            data_blk, data_off = ptr_list[i]
            off = struct.calcsize('!iii') + i * LEN_OF_LEAF_NODE
            struct.pack_into('!10sii', original_buf, off, key, data_blk, data_off)

        struct.pack_into('!i', original_buf, BLOCK_SIZE - 4, new_block_id)

        # 新结点缓冲区
        new_buf = ctypes.create_string_buffer(BLOCK_SIZE)
        new_num_keys = len(key_list) - split
        struct.pack_into('!iii', new_buf, 0,
                        new_block_id,
                        LEAF_NODE_TYPE,
                        new_num_keys)
        for i in range(split, len(key_list)):
            key = key_list[i]
            data_blk, data_off = ptr_list[i]
            off = struct.calcsize('!iii') + (i - split) * LEN_OF_LEAF_NODE
            struct.pack_into('!10sii', new_buf, off, key, data_blk, data_off)

        old_last_ptr = struct.unpack_from('!i', current_index_block, BLOCK_SIZE - 4)[0]
        struct.pack_into('!i', new_buf, BLOCK_SIZE - 4, old_last_ptr)

        # 写回磁盘
        self.f_handle.seek(next_node_ptr * BLOCK_SIZE)
        self.f_handle.write(original_buf.raw)
        self.f_handle.seek(new_block_id * BLOCK_SIZE)
        self.f_handle.write(new_buf.raw)
        self.f_handle.flush()

        # 返回新块号和上浮的键（供父结点插入使用）
        up_key = key_list[split]
        if isinstance(up_key, str):
            up_key = up_key.encode('utf-8')
        return new_block_id, up_key

     #-----------------------------
    # 分裂内部结点（参照 PDF 第 115 页）
    # input
    #       current_index_block : 原内部结点缓冲区（bytearray，已满）
    #       current_block_id    : 原内部结点块号
    # output
    #       tuple : (new_block_id, up_key)
    # 算法
    #       1. 读取所有键和指针（此时已满 MAX_NUM_OF_KEYS+1 个键）
    #       2. left_keys = MAX_NUM_OF_KEYS // 2（左结点保留的键数）
    #       3. 上浮键 = keys[left_keys]
    #       4. 左结点：keys[0:left_keys], ptrs[0:left_keys+1]
    #       5. 右结点：keys[left_keys+1:], ptrs[left_keys+1:]
    #       6. 写回原块和新块
    #       7. 返回新块号和上浮键
    #--------------------------------
    def split_internal_node(self, current_index_block, current_block_id):
        # 获取当前结点中的键数量
        current_num_of_keys = struct.unpack_from('!i', current_index_block, struct.calcsize('!ii'))[0]

        key_list = []
        ptr_list = []
        for i in range(current_num_of_keys):
            offset_in_block = struct.calcsize('!iii') + i * LEN_OF_INTERNAL_NODE
            current_key, data_blk= struct.unpack_from('!10si', current_index_block, offset_in_block)
            key_list.append(current_key)
            ptr_list.append(data_blk)

        left_keys = math.ceil((MAX_NUM_OF_KEYS+1 ) / 2)   # 左结点保留的数量

        new_block_id = self.get_next_block_id()

        # 更新原结点缓冲区
        original_buf = ctypes.create_string_buffer(BLOCK_SIZE)
        # 写入原结点头部：block_id, node_type, number_of_keys = left_keys
        struct.pack_into('!iii', original_buf, 0,
                        current_block_id,
                        INTERNAL_NODE_TYPE,
                        left_keys)
        for i in range(left_keys):
            key = key_list[i]
            data_blk = ptr_list[i]
            off = struct.calcsize('!iii') + i * LEN_OF_INTERNAL_NODE
            struct.pack_into('!10si', original_buf, off, key, data_blk)

        struct.pack_into('!i', original_buf, BLOCK_SIZE - 4, new_block_id)

        # 新结点缓冲区
        new_buf = ctypes.create_string_buffer(BLOCK_SIZE)
        new_num_keys = len(key_list) - left_keys-1
        struct.pack_into('!iii', new_buf, 0,
                        new_block_id,
                        INTERNAL_NODE_TYPE,
                        new_num_keys)
        for i in range(left_keys+1, len(key_list)):
            key = key_list[i]
            data_blk= ptr_list[i]
            off = struct.calcsize('!iii') + (i - left_keys-1) * LEN_OF_INTERNAL_NODE
            struct.pack_into('!10si', new_buf, off, key, data_blk)

        old_last_ptr = struct.unpack_from('!i', current_index_block, BLOCK_SIZE - 4)[0]
        struct.pack_into('!i', new_buf, BLOCK_SIZE - 4, old_last_ptr)

        # 写回磁盘
        self.f_handle.seek(current_block_id * BLOCK_SIZE)
        self.f_handle.write(original_buf.raw)
        self.f_handle.seek(new_block_id * BLOCK_SIZE)
        self.f_handle.write(new_buf.raw)
        self.f_handle.flush()

        # 返回新块号和上浮的键（供父结点插入使用）
        return new_block_id, key_list[left_keys]

     #-----------------------------
    # 创建新根结点（当原根分裂时调用）
    # input
    #       current_node_id : 左子结点块号
    #       new_key         : 分隔键（10 字节 bytes）
    #       new_right_ptr   : 右子结点块号
    # output
    #       None
    # 算法
    #       1. 分配新块号
    #       2. 创建内部结点，包含一个键和两个指针
    #       3. 更新元数据（根块号、树高+1）
    #--------------------------------  
    def create_new_root(self,current_node_id,new_key, new_right_ptr):
        if isinstance(new_key, str):
            new_key = new_key.encode('utf-8')
        if len(new_key) > 10:
            new_key = new_key[:10]
        elif len(new_key) < 10:
            new_key = new_key.ljust(10, b' ')
        new_buf = ctypes.create_string_buffer(BLOCK_SIZE)
        new_block_id = self.get_next_block_id()
        struct.pack_into('!iii', new_buf, 0,
                        new_block_id,
                        INTERNAL_NODE_TYPE,
                        1)
        off = struct.calcsize('!iii') 
        struct.pack_into('!10si', new_buf, off, new_key,current_node_id)
        struct.pack_into('!i',new_buf,common_db.BLOCK_SIZE-4,new_right_ptr)
        self.f_handle.seek(new_block_id * BLOCK_SIZE)
        self.f_handle.write(new_buf.raw)
        self.f_handle.flush()
        # 更新元数据：新根块号，树高度+1
        self.root_node_ptr = new_block_id
        self.num_of_levels += 1
        self.has_root = True
        # 将元数据写回块0
        self.f_handle.seek(0)
        meta_buf = ctypes.create_string_buffer(BLOCK_SIZE)
        struct.pack_into('!i?ii', meta_buf, 0, 0, True, self.num_of_levels, self.root_node_ptr)
        self.f_handle.write(meta_buf)
        self.f_handle.flush()

    #-----------------------------
    # 将叶子结点数据写回磁盘，保留原有的 last_ptr
    # input
    #       block_id : 叶子结点块号
    #       key_list : 键列表（bytes 列表）
    #       ptr_list : 指针列表，元素为 (block_id, offset)
    # output
    #       None
    # 算法
    #       1. 读取原结点的 last_ptr
    #       2. 重新打包头部和键值对
    #       3. 将原 last_ptr 写回
    #       4. 写回磁盘
    #--------------------------------
    def _write_leaf_node(self, block_id, key_list, ptr_list):
        buf = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
        num_keys = len(key_list)

        struct.pack_into('!iii', buf, 0, block_id, LEAF_NODE_TYPE, num_keys)
        for i in range(num_keys):
            k, (blk, off) = key_list[i], ptr_list[i]
            struct.pack_into('!10sii', buf, struct.calcsize('!iii') + i * LEN_OF_LEAF_NODE,
                            k, blk, off)

        # 保留原来的 last_ptr
        old_buf = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
        self.f_handle.seek(block_id * common_db.BLOCK_SIZE)
        self.f_handle.readinto(old_buf)
        last_ptr = struct.unpack_from('!i', old_buf, common_db.BLOCK_SIZE - 4)[0]
        struct.pack_into('!i', buf, common_db.BLOCK_SIZE - 4, last_ptr)

        self.f_handle.seek(block_id * common_db.BLOCK_SIZE)
        self.f_handle.write(buf)
        self.f_handle.flush()

   #-----------------------------
    # 处理叶子结点下溢：先尝试重分配，不行则合并
    # input
    #       leaf_id     : 下溢的叶子结点块号
    #       path_stack  : 路径栈
    #       key_list    : 当前叶子结点的键列表
    #       ptr_list    : 当前叶子结点的指针列表
    # output
    #       None
    # 算法
    #       1. 检查左右兄弟是否有富余键
    #       2. 若有：从兄弟借一个键值对，更新父结点分隔键
    #       3. 若无：与左兄弟或右兄弟合并
    # 修改记录
    #       2024-06-11: 内部结点下溢暂未完整实现
    #-------------------------------- 
    def _handle_leaf_underflow(self, leaf_id, path_stack, key_list, ptr_list):
        """处理叶子节点下溢：先尝试重分配，不行则合并"""
        MIN_KEYS = MAX_NUM_OF_KEYS // 2
        parent_id, child_idx = path_stack[-1]

        # 读取父节点
        parent_buf = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
        self.f_handle.seek(parent_id * common_db.BLOCK_SIZE)
        self.f_handle.readinto(parent_buf)
        _, _, parent_num = struct.unpack_from('!iii', parent_buf, 0)

        # 读取父节点所有指针
        parent_ptrs = []
        for i in range(parent_num):
            _, p = struct.unpack_from('!10si', parent_buf, struct.calcsize('!iii') + i * (10 + 4))
            parent_ptrs.append(p)
        last_ptr = struct.unpack_from('!i', parent_buf, common_db.BLOCK_SIZE - 4)[0]
        parent_ptrs.append(last_ptr)

        left_sibling_id = parent_ptrs[child_idx - 1] if child_idx > 0 else None
        right_sibling_id = parent_ptrs[child_idx + 1] if child_idx < len(parent_ptrs) - 1 else None

        # 尝试从左兄弟借
        if left_sibling_id is not None:
            left_buf = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
            self.f_handle.seek(left_sibling_id * common_db.BLOCK_SIZE)
            self.f_handle.readinto(left_buf)
            _, _, left_num = struct.unpack_from('!iii', left_buf, 0)
            if left_num > MIN_KEYS:
                self._redistribute_leaf(leaf_id, left_sibling_id, parent_id, child_idx - 1,
                                        key_list, ptr_list, from_left=True)
                return

        # 尝试从右兄弟借
        if right_sibling_id is not None:
            right_buf = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
            self.f_handle.seek(right_sibling_id * common_db.BLOCK_SIZE)
            self.f_handle.readinto(right_buf)
            _, _, right_num = struct.unpack_from('!iii', right_buf, 0)
            if right_num > MIN_KEYS:
                self._redistribute_leaf(leaf_id, right_sibling_id, parent_id, child_idx,
                                        key_list, ptr_list, from_left=False)
                return

        # 无法借，优先与左兄弟合并，否则与右兄弟合并
        if left_sibling_id is not None:
            self._merge_leaf(leaf_id, left_sibling_id, parent_id, child_idx - 1,
                            path_stack, key_list, ptr_list, merge_to_left=True)
        elif right_sibling_id is not None:
            self._merge_leaf(leaf_id, right_sibling_id, parent_id, child_idx,
                            path_stack, key_list, ptr_list, merge_to_left=False)

    #-----------------------------
    # 叶子结点重分配：从兄弟借一个键值对
    # input
    #       leaf_id, sibling_id : 当前结点和兄弟结点块号
    #       parent_id, sep_key_idx : 父结点块号和分隔键位置
    #       key_list, ptr_list  : 当前结点内容
    #       from_left           : True 从左兄弟借，False 从右兄弟借
    # output
    #       None
    #--------------------------------
    def _redistribute_leaf(self, leaf_id, sibling_id, parent_id, sep_key_idx,
                        key_list, ptr_list, from_left=True):
        """叶子节点重分配：从兄弟借一个键值对，并更新父节点分隔键"""
        sib_buf = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
        self.f_handle.seek(sibling_id * common_db.BLOCK_SIZE)
        self.f_handle.readinto(sib_buf)
        _, _, sib_num = struct.unpack_from('!iii', sib_buf, 0)

        sib_keys = []
        sib_ptrs = []
        for i in range(sib_num):
            k, b, o = struct.unpack_from('!10sii', sib_buf, struct.calcsize('!iii') + i * LEN_OF_LEAF_NODE)
            sib_keys.append(k)
            sib_ptrs.append((b, o))

        if from_left:
            # 从左兄弟末尾借一个，插到当前节点开头
            borrowed_key = sib_keys.pop()
            borrowed_ptr = sib_ptrs.pop()
            key_list.insert(0, borrowed_key)
            ptr_list.insert(0, borrowed_ptr)
            new_sep_key = sib_keys[-1]  # 左兄弟新的最后一个键
        else:
            # 从右兄弟开头借一个，插到当前节点末尾
            borrowed_key = sib_keys.pop(0)
            borrowed_ptr = sib_ptrs.pop(0)
            key_list.append(borrowed_key)
            ptr_list.append(borrowed_ptr)
            new_sep_key = sib_keys[0]  # 右兄弟新的第一个键

        # 写回兄弟和当前节点
        self._write_leaf_node(sibling_id, sib_keys, sib_ptrs)
        self._write_leaf_node(leaf_id, key_list, ptr_list)

        # 更新父节点中的分隔键
        parent_buf = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
        self.f_handle.seek(parent_id * common_db.BLOCK_SIZE)
        self.f_handle.readinto(parent_buf)
        struct.pack_into('!10s', parent_buf, struct.calcsize('!iii') + sep_key_idx * (10 + 4), new_sep_key)
        self.f_handle.seek(parent_id * common_db.BLOCK_SIZE)
        self.f_handle.write(parent_buf)
        self.f_handle.flush()


    #-----------------------------
    # 合并两个叶子结点
    # input
    #       leaf_id, sibling_id : 要合并的两个结点块号
    #       parent_id, sep_key_idx : 父结点块号和要删除的分隔键位置
    #       path_stack, key_list, ptr_list : 当前结点内容
    #       merge_to_left       : True 合并到左兄弟，False 合并到右兄弟
    # output
    #       None
    #--------------------------------
    def _merge_leaf(self, leaf_id, sibling_id, parent_id, sep_key_idx,
                    path_stack, key_list, ptr_list, merge_to_left=True):
        """合并叶子节点，更新链表指针，并在父节点中删除分隔键"""
        # 读取当前节点的 last_ptr
        leaf_buf = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
        self.f_handle.seek(leaf_id * common_db.BLOCK_SIZE)
        self.f_handle.readinto(leaf_buf)
        leaf_last_ptr = struct.unpack_from('!i', leaf_buf, common_db.BLOCK_SIZE - 4)[0]

        # 读取兄弟节点
        sib_buf = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
        self.f_handle.seek(sibling_id * common_db.BLOCK_SIZE)
        self.f_handle.readinto(sib_buf)
        _, _, sib_num = struct.unpack_from('!iii', sib_buf, 0)

        sib_keys = []
        sib_ptrs = []
        for i in range(sib_num):
            k, b, o = struct.unpack_from('!10sii', sib_buf, struct.calcsize('!iii') + i * LEN_OF_LEAF_NODE)
            sib_keys.append(k)
            sib_ptrs.append((b, o))

        if merge_to_left:
            # 左兄弟吸收当前节点
            merged_keys = sib_keys + key_list
            merged_ptrs = sib_ptrs + ptr_list
            merged_id = sibling_id
            deleted_id = leaf_id
            last_ptr = leaf_last_ptr  # 合并后指向当前节点的下一个
        else:
            # 当前节点吸收右兄弟
            merged_keys = key_list + sib_keys
            merged_ptrs = ptr_list + sib_ptrs
            merged_id = leaf_id
            deleted_id = sibling_id
            last_ptr = struct.unpack_from('!i', sib_buf, common_db.BLOCK_SIZE - 4)[0]

        # 写回合并后的节点
        self._write_leaf_node(merged_id, merged_keys, merged_ptrs)
        # 更新链表指针
        merged_buf = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
        self.f_handle.seek(merged_id * common_db.BLOCK_SIZE)
        self.f_handle.readinto(merged_buf)
        struct.pack_into('!i', merged_buf, common_db.BLOCK_SIZE - 4, last_ptr)
        self.f_handle.seek(merged_id * common_db.BLOCK_SIZE)
        self.f_handle.write(merged_buf)
        self.f_handle.flush()

        # 在父节点中删除分隔键和对应指针
        self._delete_from_internal(parent_id, sep_key_idx, path_stack[:-1])

    #-----------------------------
    # 从内部结点删除指定位置的键和右指针
    # input
    #       node_id     : 内部结点块号
    #       key_idx     : 要删除的键的索引
    #       path_stack  : 路径栈（用于向上处理下溢）
    # output
    #       None
    # 算法
    #       1. 读取内部结点所有键和指针
    #       2. 删除指定键和对应的右指针
    #       3. 写回磁盘
    #       4. 若结点下溢，向上处理（当前为简化版）
    #--------------------------------    
    def _delete_from_internal(self, node_id, key_idx, path_stack):
        """从内部节点删除指定位置的键和右指针，并检查父节点下溢"""
        buf = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
        self.f_handle.seek(node_id * common_db.BLOCK_SIZE)
        self.f_handle.readinto(buf)

        _, node_type, num_keys = struct.unpack_from('!iii', buf, 0)

        # 读取所有键和指针
        keys = []
        ptrs = []
        for i in range(num_keys):
            k, p = struct.unpack_from('!10si', buf, struct.calcsize('!iii') + i * (10 + 4))
            keys.append(k)
            ptrs.append(p)
        last_ptr = struct.unpack_from('!i', buf, common_db.BLOCK_SIZE - 4)[0]
        ptrs.append(last_ptr)

        # 删除 key_idx 位置的键和 ptr_idx = key_idx + 1 位置的指针
        del keys[key_idx]
        del ptrs[key_idx + 1]
        num_keys -= 1

        # 写回
        struct.pack_into('!iii', buf, 0, node_id, node_type, num_keys)
        for i in range(num_keys):
            struct.pack_into('!10si', buf, struct.calcsize('!iii') + i * (10 + 4),
                            keys[i], ptrs[i])
        struct.pack_into('!i', buf, common_db.BLOCK_SIZE - 4, ptrs[-1])

        self.f_handle.seek(node_id * common_db.BLOCK_SIZE)
        self.f_handle.write(buf)
        self.f_handle.flush()

        # 检查内部节点下溢
        MIN_KEYS = MAX_NUM_OF_KEYS // 2
        if num_keys < MIN_KEYS:
            if not path_stack:
                # 根节点
                if len(ptrs) == 1 and self.num_of_levels > 1:
                    # 根只剩一个指针，子节点提升为根，树高减1
                    self.root_node_ptr = ptrs[0]
                    self.num_of_levels -= 1
                    self._write_meta()
            else:
                # 非根内部节点下溢 —— 完整实现需要类似叶子的重分配/合并
                # 此处为简化版，实际生产环境建议补充内部节点的重分配与合并逻辑
                parent_id, child_idx = path_stack[-1]
                # TODO: 实现内部节点的 _handle_internal_underflow
                pass

    #-----------------------------
    # 读取指定磁盘块，返回可写的 bytearray
    # input
    #       block_id : 块号（0-based）
    # output
    #       bytearray : 长度为 BLOCK_SIZE
    #--------------------------------
    def _read_block(self, block_id):
        buf = bytearray(BLOCK_SIZE)
        self.f_handle.seek(block_id * BLOCK_SIZE)
        self.f_handle.readinto(buf)
        return buf

   #-----------------------------
    # 将缓冲区数据写入指定磁盘块
    # input
    #       block_id : 块号（0-based）
    #       buf      : 缓冲区（bytes 或 bytearray）
    # output
    #       None
    #-------------------------------- 
    def _write_block(self, block_id, buf):
        self.f_handle.seek(block_id * BLOCK_SIZE)
        self.f_handle.write(buf)
        self.f_handle.flush()

    #-----------------------------
    # 从磁盘加载元数据到内存
    # 元数据结构: block_id(4B) | has_root(1B) | num_of_levels(4B) | root_node_ptr(4B)
    #--------------------------------
    def _load_meta(self):
        self.f_handle.seek(0)
        meta_buf = self.f_handle.read(common_db.BLOCK_SIZE)
        if len(meta_buf) >= struct.calcsize('!i?ii'):
            _, self.has_root, self.num_of_levels, self.root_node_ptr = struct.unpack_from(
                '!i?ii', meta_buf, 0)
        else:
            self.has_root = False
            self.num_of_levels = 0
            self.root_node_ptr = 0

     #-----------------------------
    # 将内存中的元数据写回磁盘块 0
    #--------------------------------
    def _write_meta(self):
        meta_buf = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
        struct.pack_into('!i?ii', meta_buf, 0,
                        0, self.has_root, self.num_of_levels, self.root_node_ptr)
        self.f_handle.seek(0)
        self.f_handle.write(meta_buf)
        self.f_handle.flush()


    #-----------------------------
    # 获取下一个可用的磁盘块号
    # 算法：文件末尾块号 = 文件大小 // BLOCK_SIZE
    #--------------------------------
    def get_next_block_id(self):
        self.f_handle.seek(0, os.SEEK_END)
        file_size = self.f_handle.tell()
        new_block_id = file_size // common_db.BLOCK_SIZE 
        return new_block_id


    #-----------------------------
    # 在内部结点中根据查找键确定下一步的子结点
    # input
    #       current_value   : 查找键（bytes）
    #       index_key_list  : 当前内部结点的键列表（bytes 列表）
    #       index_ptr_list  : 当前内部结点的指针列表（块号列表）
    # output
    #       tuple : (next_block_id, child_idx)
    # 算法
    #       找到第一个大于 current_value 的键，返回其左指针
    #       若所有键都 ≤ current_value，返回最后一个指针
    #--------------------------------
    def get_next_block_ptr(self, current_value, index_key_list, index_ptr_list):
        if len(index_key_list) > 0:
            for i, key in enumerate(index_key_list):
                if current_value < key:
                    return index_ptr_list[i], i
            # 大于等于所有键，走最后一个指针
            return index_ptr_list[-1], len(index_key_list)  #

    
     #-----------------------------
    # 在内存中的有序列表中插入新键值对，保持升序
    # input
    #       insert_key : 新键（bytes）
    #       ptr_tuple  : 新指针 (block_id, offset)
    #       key_list   : 现有键列表（会被修改）
    #       ptr_list   : 现有指针列表（会被修改）
    # output
    #       None
    # 说明：允许重复键，新键插入在相同键之后
    #--------------------------------
    def insert_key_value_into_leaf_list(self, insert_key, ptr_tuple, key_list, ptr_list):
        if len(key_list) > 0:
            pos = -1
            for i in range(len(key_list)):
                current_key = key_list[i]
                if current_key == insert_key:
                    pos = i
                    break
                elif current_key > insert_key:
                    pos = i
                    break

            if pos == -1:  # 所有键都小于 insert_key，插在末尾
                pos = len(key_list)  # ← 修复：从 len-1 改为 len

            key_list.insert(pos, insert_key)
            ptr_list.insert(pos, ptr_tuple)
        else:
            key_list.append(insert_key)
            ptr_list.append(ptr_tuple)
    
    #-----------------------------
    # 调试用：打印所有叶子结点的键
    # 算法：找到最左叶子，通过 last_ptr 链表遍历所有叶子
    #--------------------------------
    def dump_all_leaves(self):
        self._load_meta()
        if not self.has_root:
            return
        # 找到最左叶子
        node = self.root_node_ptr
        while self.num_of_levels > 1:
            # 下降找最左叶子
            buf = self._read_block(node)
            _, _, num_keys = struct.unpack_from('!iii', buf, 0)
            # 第一个指针是最左子节点
            node = struct.unpack_from('!i', buf, struct.calcsize('!iii'))[0]
        # 遍历叶子链表
        while node != SPECIAL_INDEX_BLOCK_PTR:
            buf = self._read_block(node)
            _, _, num_keys = struct.unpack_from('!iii', buf, 0)
            keys = []
            for i in range(num_keys):
                k_bytes, _, _ = struct.unpack_from('!10sii', buf, struct.calcsize('!iii') + i * LEN_OF_LEAF_NODE)
                keys.append(k_bytes.decode().strip())
            print(f"leaf {node}: {keys}")
            node = struct.unpack_from('!i', buf, BLOCK_SIZE - 4)[0]

    
                    
'''
#TODO:
    实现多种索引：
        顺序文件 + 稀疏/稠密索引（PDF 第一部分）

        静态散列（哈希）（PDF 第四部分）

        可扩展散列或线性散列（PDF 动态散列）  

    对比性能：
        插入性能：记录每次插入的磁盘 I/O 次数（索引文件读写块数）和 CPU 时间。

        查询性能：对精确匹配和范围查询（B+ 树擅长范围，哈希不擅长），测量 I/O 次数。

        存储空间：索引文件最终大小。

''' 

 


if __name__ == '__main__':
    # 清理可能存在的旧索引文件
    import os
    if os.path.exists('test.ind'):
        os.remove('test.ind')

    idx = Index('test')
    
    # 插入 500 条记录，键为 "key_0" 到 "key_499"，数据位置随意（block_id=1, offset=i）
    for i in range(500):
        key = f"key_{i}"
        idx.insert_index_entry(key, 1, i)
    
    # 查询单个键
    result = idx.search("key_123")
    print(f"search 'key_123' -> {result}")   # 期望 [(1,123)]
    
    # 查询不存在的键
    result = idx.search("not_exist")
    print(f"search 'not_exist' -> {result}") # 期望 []
    
    # 范围查询
    results = idx.range_search("key_50", "key_59")
    print(f"range 'key_50' to 'key_59' -> {len(results)} items")
    for r in results[:5]:
        print(r)

    idx.dump_all_leaves()
    
    # 测试重复键插入（相同键不同位置）
    idx.insert_index_entry("dup_key", 2, 100)
    idx.insert_index_entry("dup_key", 2, 200)
    result = idx.search("dup_key")
    print(f"search duplicate 'dup_key' -> {result}")  # 期望两个位置
    

        
