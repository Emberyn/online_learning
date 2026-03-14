import pymysql
import os

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456',  # 请根据实际情况修改
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# 数据库名称
DB_NAME = 'online_learning_db'

def init_db():
    # 连接 MySQL 服务器（不指定数据库，因为可能还没创建）
    conn = pymysql.connect(
        host=DB_CONFIG['host'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        charset=DB_CONFIG['charset']
    )
    
    try:
        with conn.cursor() as cursor:
            # 读取 SQL 文件
            with open('schema.sql', 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # 分割 SQL 语句（简单的按分号分割，处理存储过程可能需要更复杂的逻辑，但这里只用于建表）
            # 注意：如果 SQL 文件中有复杂的存储过程定义，简单的 split(';') 可能会出错
            # 这里我们手动执行建库和切库操作，然后逐个执行建表语句
            
            # 1. 创建数据库
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print(f"数据库 '{DB_NAME}' 检查/创建完成。")
            
            # 2. 切换到该数据库
            cursor.execute(f"USE {DB_NAME}")
            
            # 3. 执行建表语句
            # 为了避免 split(';') 的问题，我们直接运行建表部分的语句
            # 这里简单处理：读取文件，移除注释，按分号分割
            statements = sql_content.split(';')
            
            for statement in statements:
                statement = statement.strip()
                if statement and not statement.upper().startswith('CREATE DATABASE') and not statement.upper().startswith('USE'):
                    try:
                        cursor.execute(statement)
                        print(f"执行成功: {statement[:50]}...")
                    except Exception as e:
                        print(f"执行失败: {statement[:50]}... \n错误: {e}")
                        
        conn.commit()
        print("数据库初始化完成！")
        
    except Exception as e:
        print(f"初始化过程中发生错误: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    init_db()
