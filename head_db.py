#---------------------------------
# head_db.py
# author: Jingyu Han    hjymail@163.com
# modified by: 胡丹


#--------------------------------------
# the main memory structure of table schema
# 修改原因：新增 BufferBlock 类 + LRU 缓冲区管理器，为实验三 WAL 日志提供磁盘块缓存层
#------------------------------------
import struct
import time

class BufferBlock:
    """
    磁盘数据块 → 内存缓存块
    每个 BufferBlock 对应磁盘上唯一的一个 BLOCK_SIZE 大小的数据块，
    通过 pin_count 实现引用计数，通过 is_dirty 标记是否需要写回
    """
    def __init__(self, block_id):
        """
        功能：初始化一个缓存块，绑定磁盘块号
        输入参数：block_id: int，磁盘块编号（数据文件中块的序号，从 0 开始）
        """
        self.block_id = block_id            # 磁盘块号
        self.data = None                    # 块内二进制数据（从磁盘读取或待写入）
        self.is_dirty = False               # 脏位：True 表示块被修改过，淘汰时必须写回磁盘
        self.pin_count = 0                  # 钉住计数：>0 表示块正被上层使用，LRU 不可淘汰
        self.last_access_time = time.time() # 最近访问时间戳，LRU 淘汰时选择最早者

class Header(object):
    def __init__(self, nameList, fieldDict, inistored, inLen, off,
                 block_size=4096, max_blocks=10):
        """
        功能：初始化内存中的模式头对象，包含表名列表、字段字典和缓冲区池
        输入参数：nameList: list[(bytes,int,int)]，表名条目列表；
                 fieldDict: dict，{表名: [(字段名,类型,长度),...]}；
                 inistored: bool，all.sch 中是否已有表模式数据；
                 inLen: int，表数量；
                 off: int，body 区下一个可写偏移量；
                 block_size: int，磁盘块大小，默认 4096；
                 max_blocks: int，缓冲区最大块数，默认 10
        """
        self.isStored = inistored      # all.sch 是否存有表模式数据
        self.lenOfTableNum = inLen     # 当前表总数
        self.offsetOfBody = off        # body 区空闲起始偏移
        self.tableNames = nameList     # 表名条目列表
        self.tableFields = fieldDict   # 字段字典
        self.block_size = block_size        # 磁盘块大小
        self.max_buffer_blocks = max_blocks # 缓冲区容量上限
        self.buffer_pool = []               # 缓冲区池，存储 BufferBlock 对象列表

        print("isStore is ", self.isStored, " tableNum is ", self.lenOfTableNum,
              " offset is ", self.offsetOfBody)
        print(f"缓冲区初始化：块大小={self.block_size}B，最大块数={self.max_buffer_blocks}")

    #-----------------------------
    # destructor of the class
    # 析构时打印提示缓冲区写回由上层调用 flush_all_dirty_blocks() 显式控制
    #-------------------------------
    def __del__(self):
        print('del Header')


    #-----------------------------
    # display the schema of all the tables in the schema file
    #打印 all.sch 中所有表的模式信息，调试用
    #----------------------------------------------------------
    def showTables(self):
        if self.lenOfTableNum > 0:
            print("the length of tableNames is", len(self.tableNames))
            for i in range(len(self.tableNames)):
                print(self.tableNames[i])
                # tableFields 是以表名(bytes)为键的字典，不能用整数索引访问
                print(self.tableFields[self.tableNames[i][0]])

    #-----------------------------
    # 在缓冲区池中查找指定磁盘块号对应的缓存块
    #输入参数：block_id: int，磁盘块号
    # return: BufferBlock 或 None
    #----------------------------------------------------------
    def _find_block(self, block_id):
        for block in self.buffer_pool:
            if block.block_id == block_id:
                return block
        return None

    #-----------------------------
    # LRU 置换算法：选出最近最少使用的未钉住块，脏块先写回磁盘
    #当缓冲区满时，选择 pin_count=0 且 last_access_time 最小的块淘汰
    #若该块为脏块（is_dirty=True），先调用 write_block_to_disk 写回磁盘
    # 异常处理：所有块均被钉住时抛出 Exception
    # return: 被淘汰的 BufferBlock
    #----------------------------------------------------------
    def _lru_replace(self):
        candidate_blocks = [b for b in self.buffer_pool if b.pin_count == 0]
        if not candidate_blocks:
            raise Exception("缓冲区所有块都被钉住，无法置换！")

        # 选择 last_access_time 最小的块（最近最少使用）
        lru_block = min(candidate_blocks, key=lambda x: x.last_access_time)
        if lru_block.is_dirty:
            self.write_block_to_disk(lru_block)
        self.buffer_pool.remove(lru_block)
        return lru_block

    #-----------------------------
    # 从磁盘 .dat 文件读取指定块数据到内存缓存,从数据文件读取指定块号的二进制数据，构造新的 BufferBlock
    # 输入参数：block_id: int，要加载的磁盘块号
    # 返回值：BufferBlock，包含读取到的数据（或空数据）
    # 注意❗：当前硬编码数据文件名为 t1.dat，实验三需改为动态表名
    #----------------------------------------------------------
    def load_block_from_disk(self, block_id):
        print(f"加载磁盘块 {block_id} 到缓冲区")
        new_block = BufferBlock(block_id)

        # 修改原因：硬编码 t1.dat 作为数据文件，实验三阶段需改造为动态传入表名
        data_file = "t1.dat"
        try:
            with open(data_file, 'rb') as f:
                offset = block_id * self.block_size   # 计算块在文件中的字节偏移
                f.seek(offset)
                new_block.data = f.read(self.block_size)
            print(f"成功加载块 {block_id}，数据长度：{len(new_block.data)} 字节")
        except FileNotFoundError:
            print(f"数据文件 {data_file} 不存在，创建空数据块")
            new_block.data = b''

        return new_block

    #-----------------------------
    # 将内存中的脏块数据写回磁盘对应位置
    #输入参数：block: BufferBlock，要写回的缓存块
    #副作用：写入成功后重置 block.is_dirty = False
    #----------------------------------------------------------
    def write_block_to_disk(self, block):
        print(f"脏块 {block.block_id} 写回磁盘")

        data_file = "t1.dat"
        try:
            with open(data_file, 'rb+') as f:
                offset = block.block_id * self.block_size
                f.seek(offset)
                f.write(block.data)
            print(f"成功写回块 {block.block_id} 到磁盘")
        except FileNotFoundError:
            with open(data_file, 'wb') as f:
                f.seek(block.block_id * self.block_size)
                f.write(block.data)
            print(f"数据文件不存在，已创建并写入块 {block.block_id}")

        block.is_dirty = False   # 写回后清除脏位

    #-----------------------------
    # 获取指定磁盘块号的缓存块缓存命中则更新访问时间并钉住；
    #未命中则从磁盘加载，缓冲区满时触发 LRU 置换⭐
    # 输入参数：block_id: int，磁盘块号
    #返回值：BufferBlock，钉住计数已 +1 的缓存块
    #----------------------------------------------------------
    def get_block(self, block_id):
        block = self._find_block(block_id)

        if block:
            # 缓存命中：更新 LRU 时间戳，钉住块防止被淘汰
            print(f"缓存命中：块 {block_id}")
            block.last_access_time = time.time()
            block.pin_count += 1
            return block

        # 缓存未命中：从磁盘加载新块
        print(f"缓存未命中：块 {block_id}")
        new_block = self.load_block_from_disk(block_id)

        if len(self.buffer_pool) >= self.max_buffer_blocks:
            self._lru_replace()

        new_block.pin_count += 1
        self.buffer_pool.append(new_block)
        return new_block

    #-----------------------------
    # 释放数据块（解除钉住），减少 pin_count若 is_dirty=True 则标记脏位
    #输入参数：block_id: int；is_dirty: bool，本次使用是否修改了块数据
    #----------------------------------------------------------
    def release_block(self, block_id, is_dirty=False):
        block = self._find_block(block_id)
        if not block:
            return

        block.is_dirty = is_dirty
        if block.pin_count > 0:
            block.pin_count -= 1
        block.last_access_time = time.time()
        print(f"释放块 {block_id}，当前钉住数={block.pin_count}，脏位={block.is_dirty}")

    #-----------------------------
    # 将所有脏块强制写回磁盘（用于事务提交或程序正常退出时保证数据持久化）
    #----------------------------------------------------------
    def flush_all_dirty_blocks(self):
        for block in self.buffer_pool:
            if block.is_dirty:
                self.write_block_to_disk(block)
        print("所有脏块已刷新到磁盘")

    #-----------------------------
    # 打印缓冲区当前状态（调试用）
    #----------------------------------------------------------
    def show_buffer_status(self):
        print("\n===== 缓冲区状态 =====")
        print(f"总容量：{self.max_buffer_blocks}，已使用：{len(self.buffer_pool)}")
        for block in self.buffer_pool:
            print(f"块号：{block.block_id} | 钉住：{block.pin_count} | 脏块：{block.is_dirty}")
        print("======================\n")