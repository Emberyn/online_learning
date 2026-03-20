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


# -------------------------- 个性化仪表盘 --------------------------
# 路由：/dashboard (GET请求)，必须登录才能访问
@main_bp.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    try:
        # 1. 管理员角色：显示待审核课程数、总用户数
        if current_user.role == 'admin':
            with conn.cursor() as cursor:
                # 查询待审核课程数量（status=pending）
                cursor.execute("SELECT COUNT(*) as count FROM courses WHERE status = 'pending'")
                pending_count = cursor.fetchone()['count']
                # 查询总用户数量
                cursor.execute("SELECT COUNT(*) as count FROM users")
                user_count = cursor.fetchone()['count']
            # 渲染管理员仪表盘，传递统计数据
            return render_template('admin_dashboard.html', pending_count=pending_count, user_count=user_count)

        # 2. 教师角色：显示自己创建的课程数
        elif current_user.role == 'teacher':
            with conn.cursor() as cursor:
                # 根据教师ID查询课程数量
                cursor.execute("SELECT COUNT(*) as count FROM courses WHERE teacher_id = %s", (current_user.id,))
                course_count = cursor.fetchone()['count']
            # 渲染教师仪表盘
            return render_template('teacher_dashboard.html', course_count=course_count)

        # 3. 学生角色：显示已选课程及学习进度
        else:
            with conn.cursor() as cursor:
                # 联表查询：学生已选课程 + 课程信息 + 授课老师 + 学习进度
                cursor.execute("""
                    SELECT c.*, u.name as teacher_name, e.progress
                    FROM enrollments e  # 选课表
                    JOIN courses c ON e.course_id = c.id  # 关联课程表
                    JOIN users u ON c.teacher_id = u.id   # 关联用户表（获取老师姓名）
                    WHERE e.student_id = %s  # 筛选当前学生的选课记录
                """, (current_user.id,))
                enrolled_courses = cursor.fetchall()
            # 渲染学生仪表盘，传递已选课程数据
            return render_template('student_dashboard.html', courses=enrolled_courses)
    finally:
        # 关闭数据库连接
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
# 路由：/course/课程ID/comment (仅POST请求)，必须登录
@main_bp.route('/course/<int:course_id>/comment', methods=['POST'])
@login_required
def post_comment(course_id):
    # 从表单获取评论内容
    content = request.form['content']
    # 校验：评论内容不能为空
    if not content:
        flash('评论内容不能为空', 'warning')
        # 返回到课程详情页
        return redirect(url_for('main.course_detail', course_id=course_id))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 先校验课程是否存在
            cursor.execute("SELECT id FROM courses WHERE id = %s", (course_id,))
            if not cursor.fetchone():
                flash('课程不存在', 'danger')
                return redirect(url_for('main.index'))

            # 插入评论数据到数据库
            cursor.execute("INSERT INTO comments (course_id, user_id, content) VALUES (%s, %s, %s)",
                           (course_id, current_user.id, content))
            conn.commit()  # 提交事务（INSERT必须提交）
            flash('评论发表成功', 'success')
    except Exception as e:
        # 捕获异常，提示错误
        flash(f'评论失败: {e}', 'danger')
    finally:
        conn.close()

    # 评论提交后返回课程详情页
    return redirect(url_for('main.course_detail', course_id=course_id))


# -------------------------- 课程资源下载 --------------------------
# 路由：/download/文件路径 (GET请求)，必须登录
@main_bp.route('/download/<path:filename>')
@login_required
def download_file(filename):
    try:
        # 处理文件名：截取真实文件名（如uploads/1710345678_realname.pdf → realname.pdf）
        # 规则：如果文件名包含下划线，取第二个部分；否则用原文件名
        download_name = filename.split('_', 1)[1] if '_' in filename else filename
        # 从配置的上传文件夹中下载文件，as_attachment=True表示强制下载（而非预览）
        return send_from_directory(
            current_app.config['UPLOAD_FOLDER'],  # 上传文件夹路径（app.py中配置）
            filename,  # 服务器端的文件名
            as_attachment=True,  # 强制下载
            download_name=download_name  # 客户端显示的文件名
        )
    except Exception as e:
        # 下载失败：提示错误并返回首页
        flash(f'文件下载失败: {e}', 'danger')
        return redirect(url_for('main.index'))