from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db_connection

auth_bp = Blueprint('auth', __name__)

class User(UserMixin):
    def __init__(self, id, username, role, name):
        self.id = id
        self.username = username
        self.role = role
        self.name = name

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                user_data = cursor.fetchone()
                
                if user_data:
                    password_check = False
                    if user_data['password'].startswith('scrypt:') or user_data['password'].startswith('pbkdf2:'):
                        password_check = check_password_hash(user_data['password'], password)
                    else:
                        password_check = (user_data['password'] == password)
                        
                    if password_check:
                        user = User(user_data['id'], user_data['username'], user_data['role'], user_data['name'])
                        login_user(user)
                        flash('登录成功！', 'success')
                        return redirect(url_for('main.dashboard'))
                    else:
                        flash('密码错误', 'danger')
                else:
                    flash('用户不存在', 'danger')
        except Exception as e:
            flash(f'登录出错: {e}', 'danger')
        finally:
            conn.close()
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        name = request.form['name']
        email = request.form['email']

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                if cursor.fetchone():
                    flash('用户名已存在', 'danger')
                else:
                    cursor.execute(
                        "INSERT INTO users (username, password, role, name, email) VALUES (%s, %s, %s, %s, %s)",
                        (username, hashed_password, role, name, email))
                    conn.commit()
                    flash('注册成功，请登录', 'success')
                    return redirect(url_for('auth.login'))
        except Exception as e:
            flash(f'注册出错: {e}', 'danger')
        finally:
            conn.close()
    return render_template('register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('您已退出登录', 'info')
    return redirect(url_for('main.index'))
