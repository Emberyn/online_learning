# 导入Flask核心模块：Blueprint(蓝图)、render_template(渲染HTML)、flash(提示消息)、redirect(重定向)
# url_for(反向路由)、request(接收请求数据)、send_from_directory(文件下载)、current_app(当前应用配置)
from flask import Blueprint, render_template, flash, redirect, url_for, request, send_from_directory, current_app
# 导入Flask-Login模块：login_required(登录验证)、current_user(当前登录用户对象)
from flask_login import login_required, current_user
# 导入自定义数据库连接函数
from db import get_db_connection
# 导入系统模块：处理文件路径
import os

# 创建主蓝图：名称为'main'，关联当前文件，负责首页、仪表盘、课程详情等核心功能
main_bp = Blueprint('main', __name__)


# ==========================================
# 新增：全局模板工具函数
# ==========================================
@main_bp.app_context_processor
def inject_utilities():
    def file_exists(filename):
        """检查文件在服务器硬盘上是否真实存在"""
        if not filename:
            return False
        # 拼接出文件的绝对路径
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        return os.path.exists(file_path)

    # 这样一来，所有的 HTML 模板里都可以直接调用 file_exists() 函数了
    return dict(file_exists=file_exists)


# -------------------------- 网站首页 --------------------------
# 路由：根路径 / (GET请求)，所有用户均可访问
@main_bp.route('/')
def index():
    # 初始化数据库连接和课程列表
    conn = get_db_connection()
    courses = []
    try:
        with conn.cursor() as cursor:
            # SQL查询：从视图v_course_list获取所有课程数据（视图是预定义的查询结果集）
            sql = "SELECT * FROM v_course_list"
            cursor.execute(sql)
            # 获取所有课程数据，返回列表+字典格式
            courses = cursor.fetchall()
    except Exception as e:
        # 捕获异常，打印错误信息（方便调试）
        print(f"Error fetching courses: {e}")
    finally:
        # 无论是否报错，最终关闭数据库连接
        conn.close()
    # 渲染首页模板，传递课程数据给HTML
    return render_template('index.html', courses=courses)


# -------------------------- 用户专属传送门 (原仪表盘) --------------------------
@main_bp.route('/dashboard')
@login_required
def dashboard():
    # 1. 管理员：点击自己名字，直接跳转到“课程审核”
    if current_user.role == 'admin':
        return redirect(url_for('admin.admin_courses'))

    # 2. 教师：点击自己名字，直接跳转到“我的课程”
    elif current_user.role == 'teacher':
        return redirect(url_for('teacher.my_courses'))

    # 3. 学生：展示自己已选的课程（我们把原来学生的仪表盘改名叫“我的课程”）
    else:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 联表查询：学生已选课程 + 学习进度
                cursor.execute("""
                    SELECT c.*, u.name as teacher_name, e.progress
                    FROM enrollments e
                    JOIN courses c ON e.course_id = c.id
                    JOIN users u ON c.teacher_id = u.id
                    WHERE e.student_id = %s
                """, (current_user.id,))
                enrolled_courses = cursor.fetchall()
            # 这里依然渲染 student_dashboard.html，但我们在前端把它的标题改成了“我的课程”
            return render_template('student_dashboard.html', courses=enrolled_courses)
        finally:
            conn.close()


# -------------------------- 课程详情页 --------------------------
# 路由：/course/课程ID (GET请求)，<int:course_id>接收整数类型的课程ID
@main_bp.route('/course/<int:course_id>')
def course_detail(course_id):
    conn = get_db_connection()
    # 初始化变量：课程信息、是否选课、课程资源、作业、评论
    course = None
    is_enrolled = False
    resources = []
    try:
        with conn.cursor() as cursor:
            # 1. 查询课程基本信息 + 授课老师姓名
            cursor.execute("""
                SELECT c.*, u.name as teacher_name 
                FROM courses c 
                JOIN users u ON c.teacher_id = u.id 
                WHERE c.id = %s
            """, (course_id,))
            course = cursor.fetchone()

            # 课程不存在：提示并返回首页
            if not course:
                flash('课程不存在', 'danger')
                return redirect(url_for('main.index'))

            # 2. 已登录学生：检查是否选过该课程
            if current_user.is_authenticated:
                if current_user.role == 'student':
                    cursor.execute("SELECT * FROM enrollments WHERE student_id = %s AND course_id = %s",
                                   (current_user.id, course_id))
                    # 查到选课记录则标记为已选课
                    if cursor.fetchone():
                        is_enrolled = True

            # 3. 查询课程资源（如课件、视频等）
            cursor.execute("SELECT * FROM resources WHERE course_id = %s", (course_id,))
            resources = cursor.fetchall()

            # 4. 查询课程作业（按截止时间排序）
            cursor.execute("SELECT * FROM assignments WHERE course_id = %s ORDER BY deadline", (course_id,))
            assignments = cursor.fetchall()

            # 5. 查询课程评论（按发布时间倒序）
            cursor.execute("""
                SELECT c.*, u.username, u.name as user_name, u.role
                FROM comments c
                JOIN users u ON c.user_id = u.id  # 关联用户表，获取评论者信息
                WHERE c.course_id = %s
                ORDER BY c.created_at DESC
            """, (course_id,))
            comments = cursor.fetchall()

    finally:
        conn.close()

    # 渲染课程详情页，传递所有相关数据
    return render_template('course_detail.html',
                           course=course,
                           is_enrolled=is_enrolled,
                           resources=resources,
                           assignments=assignments,
                           comments=comments)


# -------------------------- 发布课程评论 --------------------------
@main_bp.route('/course/<int:course_id>/comment', methods=['POST'])
@login_required
def post_comment(course_id):
    # 从表单获取评论内容和评分
    content = request.form.get('content')
    # 新增：获取评分，默认给 5 分
    rating = request.form.get('rating', 5) 

    if not content:
        flash('评论内容不能为空', 'warning')
        return redirect(url_for('main.course_detail', course_id=course_id))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM courses WHERE id = %s", (course_id,))
            if not cursor.fetchone():
                flash('课程不存在', 'danger')
                return redirect(url_for('main.index'))

            # 修改：将 rating 一并存入数据库
            cursor.execute(
                "INSERT INTO comments (course_id, user_id, content, rating) VALUES (%s, %s, %s, %s)",
                (course_id, current_user.id, content, int(rating))
            )
            conn.commit()
            flash('评价发表成功', 'success')
    except Exception as e:
        flash(f'评价失败: {e}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('main.course_detail', course_id=course_id))


# -------------------------- 课程资源下载 --------------------------
@main_bp.route('/download/<path:filename>')
@login_required
def download_file(filename):
    try:
        # 默认下载名与物理文件名相同
        download_name = filename

        # 规则 1：处理学生作业 (格式: sub_学生ID_时间戳_真实文件名)
        if filename.startswith('sub_'):
            parts = filename.split('_', 3)  # 按下划线切分3次
            if len(parts) == 4:
                download_name = parts[3]  # 拿到最后一部分（完美还原真实文件名）

        # 规则 2：处理教师资源 (格式: 时间戳_真实文件名)
        elif '_' in filename:
            parts = filename.split('_', 1)  # 教师的文件只切1次
            # 确保下划线前面是纯数字（时间戳），防止误伤原本就带有下划线的文件名
            if len(parts) == 2 and parts[0].isdigit():
                download_name = parts[1]

        # 从配置的上传文件夹中下载文件
        return send_from_directory(
            current_app.config['UPLOAD_FOLDER'],
            filename,
            as_attachment=True,
            download_name=download_name  # 告诉浏览器下载时用这个干净的名字
        )
    except Exception as e:
        flash(f'文件下载失败: {e}', 'danger')
        return redirect(url_for('main.index'))
    


# ==========================================
# 新增：个人信息修改页面 (全角色通用)
# ==========================================
@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # 获取表单提交的新姓名和新邮箱
        new_name = request.form.get('name')
        new_email = request.form.get('email')
        
        if not new_name:
            flash('真实姓名不能为空', 'warning')
            return redirect(url_for('main.profile'))
            
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 更新数据库中的用户信息
                cursor.execute("UPDATE users SET name = %s, email = %s WHERE id = %s", 
                               (new_name, new_email, current_user.id))
                conn.commit()
                
                # 同步更新当前登录在系统内存中的名字，这样右上角的欢迎语会立刻变化
                current_user.name = new_name 
                flash('个人资料更新成功！', 'success')
        except Exception as e:
            flash(f'更新失败: {e}', 'danger')
        finally:
            conn.close()
            
        return redirect(url_for('main.profile'))
        
    # GET请求：从数据库加载最新的用户信息用于页面回显
    conn = get_db_connection()
    user_data = None
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE id = %s", (current_user.id,))
            user_data = cursor.fetchone()
    finally:
        conn.close()
        
    return render_template('profile.html', user_info=user_data)