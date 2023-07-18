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
instance/zvms.db> source sql.sql
```
2. 如果要从`ZVMS 2.0`中导入数据的话, 
    1. 复制2.0的`zvms.db`至根目录
    2. 检查数据库中有没有同一班中重名的情况, 如果有, 改掉
    3. 运行`migrate.py`
   
## 运行

```bash
$ python run.py [-p PORT]
```