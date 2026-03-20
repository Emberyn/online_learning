# 导入Flask需要的工具
from flask import Blueprint, render_template, request, redirect, url_for, flash
# 导入登录相关：登录、登出、登录验证、用户模型
from flask_login import login_user, logout_user, login_required, UserMixin
# 密码加密、校验工具
from werkzeug.security import generate_password_hash, check_password_hash
# 数据库连接
from db import get_db_connection

# 创建【登录注册蓝图】，负责所有登录、注册、退出功能
auth_bp = Blueprint('auth', __name__)

# 自定义User类，给Flask-Login使用
# UserMixin 提供了登录必须的方法：is_authenticated、get_id()等
class User(UserMixin):
    def __init__(self, id, username, role, name):
        self.id = id          # 用户ID
        self.username = username  # 账号
        self.role = role      # 角色：admin/teacher/student
        self.name = name      # 真实姓名


# ------------------- 登录页面 -------------------
# 支持GET（打开页面）、POST（提交账号密码）
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # 如果是POST：用户提交了登录表单
    if request.method == 'POST':
        # 从表单获取账号、密码
        username = request.form['username']
        password = request.form['password']

        # 连接数据库
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 根据用户名查用户
                cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                user_data = cursor.fetchone()  # 取一条

                # 如果查到用户
                if user_data:
                    password_check = False

                    # 判断密码是加密存储，还是明文
                    if user_data['password'].startswith('scrypt:') or user_data['password'].startswith('pbkdf2:'):
                        # 加密密码：用工具校验
                        password_check = check_password_hash(user_data['password'], password)
                    else:
                        # 明文密码：直接对比
                        password_check = (user_data['password'] == password)

                    # 如果密码正确
                    if password_check:
                        # 构建User对象，给Flask-Login使用
                        user = User(user_data['id'], user_data['username'], user_data['role'], user_data['name'])
                        login_user(user)  # 执行登录
                        flash('登录成功！', 'success')
                        return redirect(url_for('main.dashboard'))  # 跳转到主页
                    else:
                        flash('密码错误', 'danger')
                else:
                    flash('用户不存在', 'danger')
        except Exception as e:
            flash(f'登录出错: {e}', 'danger')
        finally:
            conn.close()  # 无论如何都关闭数据库连接

    # GET请求：直接显示登录页面
    return render_template('login.html')



# ------------------- 注册页面 -------------------
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # 获取表单数据
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        name = request.form['name']
        email = request.form['email']

        # 密码加密（不存明文）
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 先查用户名是否被占用
                cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                if cursor.fetchone():
                    flash('用户名已存在', 'danger')
                else:
                    # 插入新用户到数据库
                    cursor.execute(
                        "INSERT INTO users (username, password, role, name, email) VALUES (%s, %s, %s, %s, %s)",
                        (username, hashed_password, role, name, email))
                    conn.commit()  # 提交保存
                    flash('注册成功，请登录', 'success')
                    return redirect(url_for('auth.login'))
        except Exception as e:
            flash(f'注册出错: {e}', 'danger')
        finally:
            conn.close()

    # GET：显示注册页面
    return render_template('register.html')

# ------------------- 退出登录 -------------------
@auth_bp.route('/logout')
@login_required  # 必须登录才能退出
def logout():
    logout_user()  # 清空登录状态
    flash('您已退出登录', 'info')
    return redirect(url_for('main.index'))