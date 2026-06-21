# MiniBase_upup

这是一个基于 Python 实现的简易数据库系统原型，包含表模式管理、记录存储、SQL 解析、查询执行、索引与事务日志恢复等模块。

## 项目定位

该项目模拟了一个小型关系型数据库的核心流程，适合用于课程实验与源码学习。整体功能包括：

- 创建/删除表结构
- 插入/删除/更新记录
- 基于 SQL 的查询执行
- 简单的 B+ 树索引支持
- 范围查询能力
- 事务日志与异常恢复机制

---

## 目录结构说明

- `main_db.py`  
  主程序入口，提供交互式菜单，负责调用各个模块。

- `schema_db.py`  
  管理表结构元数据，负责 `all.sch` 的读写。

- `storage_db.py`  
  负责数据文件的存储与记录操作，支持 CRUD。

- `head_db.py`  
  负责模式头和缓冲区相关逻辑。

- `lex_db.py`  
  词法分析器，定义 SQL 关键字与 token。

- `parser_db.py`  
  语法分析器，用于构建 SQL 的语法树。

- `query_plan_db.py`  
  查询计划生成与执行逻辑。

- `index_db.py`  
  B+ 树索引实现，用于单字段索引和范围检索。

- `transaction_log.py`  
  事务日志、提交与恢复逻辑。

- `common_db.py`  
  公共常量、树节点结构和全局状态定义。

- `test_db.py`、`test_index_performance.py`  
  测试脚本。

---

## 运行方式

### 1. 安装依赖

该项目使用 PLY 进行词法与语法分析，需先安装：

```bash
pip install ply
```

### 2. 启动程序

```bash
python main_db.py
```

程序启动后会显示菜单，用户可以通过数字选择不同操作。

---

## 主菜单功能概览

程序中的菜单选项大致如下：

| 选项 | 功能 |
|---|---|
| 1 | 新建表并插入数据 |
| 2 | 删除表 |
| 3 | 查看表结构与表数据 |
| 4 | 删除所有表及数据 |
| 5 | 执行 SELECT 查询 |
| 6 | 按字段删除记录 |
| 7 | 按字段更新记录 |
| 8 | 执行 CREATE TABLE |
| 9 | 执行 INSERT INTO |
| 10 | 执行 DELETE FROM |
| 11 | 执行 UPDATE SET |
| 12 | 执行 DROP TABLE |
| 13 | 执行 CREATE INDEX |
| 14 | 执行 RANGE 查询 |
| . | 退出程序 |

---

## 支持的 SQL 示例

### 建表

```sql
CREATE TABLE students (
    sid INT,
    name CHAR(20),
    age INT
)
```

### 插入数据

```sql
INSERT INTO students VALUES ('001', 'Alice', 20)
```

### 查询数据

```sql
SELECT * FROM students
```

```sql
SELECT sid, name FROM students WHERE sid = 1
```

### 创建索引

```sql
CREATE INDEX idx_students_sid ON students sid
```

### 范围查询

```sql
RANGE FROM '001' TO '010' ON students (sid)
```

---

## 数据文件说明

程序运行时会生成一些文件：

- `all.sch`  
  表模式文件，保存所有表的结构信息。

- `*.dat`  
  各表的数据文件。

- `*.ind`  
  索引文件。

- `active.trx`、`commit.trx`、`before.img`、`after.img`  
  事务日志相关文件。

- `system.flag`  
  用于标记程序运行状态。

---

## 设计说明

项目整体上分为四层：

1. **用户交互层**  
   由 `main_db.py` 提供菜单和输入输出。

2. **SQL 层**  
   `lex_db.py` + `parser_db.py` 负责词法和语法分析。

3. **执行层**  
   `query_plan_db.py` 负责查询计划的构建与执行。

4. **存储层**  
   `schema_db.py`、`storage_db.py`、`index_db.py` 负责模式、数据和索引的持久化。

---

## 注意事项

- 本项目是一个课程型数据库实验实现，功能较完整，但仍可能存在边界情况或兼容性差异。
- 运行前建议先确认 Python 环境已安装 `ply`。
- 某些复杂查询和特殊类型处理可能需要结合具体测试案例进一步调试。

---

## 参考用途

适合用于：

- 数据库课程实验学习
- 小型关系型数据库原理验证
- Python 文件存储与缓冲区机制练习
- SQL 解析器与查询优化思路的学习
