import os
import pymysql
import pymysql.cursors
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', '123456'),  # 如果环境变量没配置，默认回退到 123456
    'database': os.getenv('DB_NAME', 'online_learning_db'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db_connection():
    return pymysql.connect(**DB_CONFIG)