## 部署

### 环境配置

1. 下载安装Python 3.10+
2. 运行
```bash
$ pip install -r requirements.txt
```

### 配置数据库

1. (假设使用`litecli`):
```
(none)> .open instance/zvms.db
instance/zvms.db> source zvms.sql
```
2. 如果要从`ZVMS 2.0`中导入数据的话, 
    1. 复制2.0的`zvms.db`至根目录
    2. 检查数据库中有没有同一班中重名的情况, 如果有, 改掉
    3. 如果旧数据库里有系统和义管会, 把`zvms.sql`的最后两行去掉
    4. 运行`migrate.py`
3. 如果要从头开始导入数据的话,
    1. 准备两份csv文件, `classes.csv`和`users.csv`, 格式分别为:
    ```csv
    ID, 班级名
    202209, 高一九班
    ```
    和
    ```csv
    ID, 用户名, 班级
    20220901, 张三, 202209
    ```
    2. 运行`import.py`
    3. `import.py`还有许多功能, 具体内容可以通过`$ python import.py -h`获取
   
## 运行

```bash
$ python run.py [-p PORT]
```