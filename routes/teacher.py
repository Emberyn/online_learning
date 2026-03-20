# 导入Flask核心模块：Blueprint(蓝图)、render_template(渲染HTML)、request(接收请求)
# flash(提示消息)、redirect(重定向)、url_for(反向路由)、current_app(应用配置)、jsonify(返回JSON)
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
# 导入Flask-Login模块：login_required(登录验证)、current_user(当前登录用户)
from flask_login import login_required, current_user
# 导入werkzeug工具：安全处理文件名（防止恶意文件名）
from werkzeug.utils import secure_filename
# 导入系统模块：文件路径、时间戳
import os
import time
# 导入自定义数据库连接函数
from db import get_db_connection

# 创建教师蓝图：名称为'teacher'，关联当前文件，负责教师端所有功能
teacher_bp = Blueprint('teacher', __name__)

# 允许上传的资源文件格式集合（限制类型，提升安全性）
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'ppt', 'pptx', 'mp4'}


# ==========================================
# 新增：删除课程资源记录
# ==========================================
@teacher_bp.route('/resource/<int:resource_id>/delete', methods=['POST'])
@login_required
def delete_resource(resource_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 获取资源信息，并校验当前用户是否为该课程的老师
            cursor.execute("""
                SELECT r.file_path, r.course_id, c.teacher_id 
                FROM resources r
                JOIN courses c ON r.course_id = c.id
                WHERE r.id = %s
            """, (resource_id,))
            resource = cursor.fetchone()

            if not resource or resource['teacher_id'] != current_user.id:
                flash('无权操作或资源不存在', 'danger')
                return redirect(url_for('main.dashboard'))

            # 从数据库中彻底删除该条记录
            cursor.execute("DELETE FROM resources WHERE id = %s", (resource_id,))
            conn.commit()

            # 如果物理文件凑巧还在（比如用户只是单纯想删记录），顺手清理掉物理文件释放空间
            if resource['file_path'] and resource['file_path'].startswith('uploads/'):
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], resource['file_path'].split('/')[-1])
                if os.path.exists(file_path):
                    os.remove(file_path)

            flash('资源记录已成功删除', 'success')
            return redirect(url_for('main.course_detail', course_id=resource['course_id']))
    except Exception as e:
        flash(f'删除失败: {e}', 'danger')
        return redirect(url_for('main.dashboard'))
    finally:
        conn.close()


# ==========================================
# 新增：删除无效的学生作业提交记录
# ==========================================
@teacher_bp.route('/submission/<int:submission_id>/delete', methods=['POST'])
@login_required
def delete_submission(submission_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 校验当前用户是否为该课程的老师
            cursor.execute("""
                SELECT s.assignment_id, c.teacher_id 
                FROM submissions s
                JOIN assignments a ON s.assignment_id = a.id
                JOIN courses c ON a.course_id = c.id
                WHERE s.id = %s
            """, (submission_id,))
            record = cursor.fetchone()

            if not record or record['teacher_id'] != current_user.id:
                flash('无权操作', 'danger')
                return redirect(url_for('main.dashboard'))

            # 从数据库中删除记录
            cursor.execute("DELETE FROM submissions WHERE id = %s", (submission_id,))
            conn.commit()
            flash('无效的作业记录已清理', 'success')
            return redirect(url_for('teacher.assignment_submissions', assignment_id=record['assignment_id']))
    except Exception as e:
        flash(f'删除失败: {e}', 'danger')
        return redirect(url_for('main.dashboard'))
    finally:
        conn.close()


# ==========================================
# 新增：教师端作业管理中心
# ==========================================
@teacher_bp.route('/teacher/assignments')
@login_required
def manage_assignments():
    # 权限校验
    if current_user.role != 'teacher':
        flash('只有教师可以访问此页面', 'warning')
        return redirect(url_for('main.index'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 核心查询：获取该教师的所有作业，并使用子查询统计提交情况
            cursor.execute("""
                SELECT 
                    a.id, a.title as assignment_title, a.deadline, a.created_at,
                    c.id as course_id, c.title as course_title,
                    -- 统计该作业的总提交份数
                    (SELECT COUNT(*) FROM submissions s WHERE s.assignment_id = a.id) as total_submissions,
                    -- 统计该作业中还没有打分（grade is null）的份数
                    (SELECT COUNT(*) FROM submissions s WHERE s.assignment_id = a.id AND s.grade IS NULL) as ungraded_count
                FROM assignments a
                JOIN courses c ON a.course_id = c.id
                WHERE c.teacher_id = %s
                ORDER BY a.created_at DESC
            """, (current_user.id,))
            assignments = cursor.fetchall()
    finally:
        conn.close()

    return render_template('teacher_assignments.html', assignments=assignments)


# -------------------------- 工具函数：校验文件格式 --------------------------
def allowed_file(filename):
    """
    校验上传文件是否为允许的格式
    :param filename: 上传的文件名
    :return: True=格式合法，False=格式不合法
    """
    # 条件1：文件名包含小数点（有后缀）；条件2：后缀在允许集合中（不区分大小写）
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# -------------------------- 创建课程 --------------------------
# 路由：/create_course (支持GET/POST)，必须登录
@teacher_bp.route('/create_course', methods=['GET', 'POST'])
@login_required
def create_course():
    # 权限校验：仅教师/管理员可创建课程
    if current_user.role != 'teacher' and current_user.role != 'admin':
        flash('只有教师可以发布课程', 'warning')
        return redirect(url_for('main.index'))

    # POST请求：用户提交课程创建表单
    if request.method == 'POST':
        # 从表单获取课程信息
        title = request.form['title']  # 课程名称
        description = request.form['description']  # 课程描述
        category = request.form['category']  # 课程分类

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 插入课程数据到数据库，状态默认设为"pending(待审核)"
                cursor.execute(
                    "INSERT INTO courses (title, description, teacher_id, category, status) VALUES (%s, %s, %s, %s, 'pending')",
                    (title, description, current_user.id, category)
                )
                conn.commit()  # 提交事务
                flash('课程已创建，等待管理员审核', 'success')
                return redirect(url_for('main.dashboard'))  # 跳转到教师仪表盘
        except Exception as e:
            # 捕获异常，提示错误
            flash(f'创建课程失败: {e}', 'danger')
        finally:
            # 无论是否报错，关闭数据库连接
            conn.close()

    # GET请求：渲染课程创建页面
    return render_template('create_course.html')


# -------------------------- 查看我的课程 --------------------------
# 路由：/my_courses (GET请求)，必须登录
@teacher_bp.route('/my_courses')
@login_required
def my_courses():
    # 权限校验：仅教师可访问
    if current_user.role != 'teacher':
        flash('只有教师可以查看此页面', 'warning')
        return redirect(url_for('main.index'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 查询当前教师创建的所有课程
            cursor.execute("SELECT * FROM courses WHERE teacher_id = %s", (current_user.id,))
            courses = cursor.fetchall()
    finally:
        conn.close()
    # 渲染我的课程页面，传递课程数据
    return render_template('my_courses.html', courses=courses)



# -------------------------- 课程选课人数统计 --------------------------
# 路由：/teacher/stats/enrollment (GET请求)，必须登录，返回JSON数据
@teacher_bp.route('/teacher/stats/enrollment')
@login_required
def enrollment_stats():
    # 权限校验：仅教师可访问，非教师返回403未授权（JSON格式）
    if current_user.role != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 403

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 联表查询：统计每门课程的选课人数（LEFT JOIN保证无选课的课程也显示）
            cursor.execute("""
                SELECT c.title, COUNT(e.student_id) as enrolled_count 
                FROM courses c
                LEFT JOIN enrollments e ON c.id = e.course_id  # 课程表关联选课表
                WHERE c.teacher_id = %s                        # 筛选当前教师的课程
                GROUP BY c.id, c.title                         # 按课程分组
                ORDER BY enrolled_count DESC                   # 按选课人数降序
            """, (current_user.id,))
            results = cursor.fetchall()

            # 提取统计数据：课程名称列表 + 选课人数列表（供前端图表渲染）
            labels = [row['title'] for row in results]
            values = [row['enrolled_count'] for row in results]

            # 返回JSON格式数据
            return jsonify({'labels': labels, 'values': values})
    except Exception as e:
        # 捕获异常，返回500服务器错误（JSON格式）
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@teacher_bp.route('/course/<int:course_id>/upload_resource', methods=['POST'])
@login_required
def upload_resource(course_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 【修改点】：多查一个 status 字段
            cursor.execute("SELECT teacher_id, status FROM courses WHERE id = %s", (course_id,))
            course = cursor.fetchone()

            if not course or course['teacher_id'] != current_user.id:
                flash('您没有权限操作此课程', 'danger')
                return redirect(url_for('main.course_detail', course_id=course_id))

            # 【新增】：如果课程被拒绝，直接拦截拦截请求
            if course['status'] == 'rejected':
                flash('操作失败：该课程已被管理员拒绝，无法继续上传资源。', 'warning')
                return redirect(url_for('main.course_detail', course_id=course_id))
    finally:
        conn.close()

    # 第二步：处理资源上传（链接/文件）
    title = request.form['title']  # 资源名称
    resource_type = request.form['resource_type']  # 资源类型：link(链接)/file(文件)
    file_path = None  # 资源存储路径

    # 资源类型为链接
    if resource_type == 'link':
        file_path = request.form.get('external_link')  # 获取外部链接
        if not file_path:
            flash('请输入外部链接', 'warning')
            return redirect(url_for('main.course_detail', course_id=course_id))
    # 资源类型为文件
    else:
        # 校验：请求中是否包含文件
        if 'file' not in request.files:
            flash('没有文件部分', 'warning')
            return redirect(url_for('main.course_detail', course_id=course_id))

        file = request.files['file']
        # 校验：是否选择了文件（文件名不为空）
        if file.filename == '':
            flash('未选择文件', 'warning')
            return redirect(url_for('main.course_detail', course_id=course_id))

        # 校验：文件格式是否合法
        if file and allowed_file(file.filename):
            # 放弃 secure_filename，手动过滤斜杠，完美保留中文文件名
            original_filename = file.filename.replace('/', '').replace('\\', '')
            # 生成唯一文件名：时间戳_原文件名（避免文件重名覆盖）
            filename = f"{int(time.time())}_{original_filename}"

            # 确保上传文件夹存在（不存在则创建）
            if not os.path.exists(current_app.config['UPLOAD_FOLDER']):
                os.makedirs(current_app.config['UPLOAD_FOLDER'])

            # 保存文件到上传文件夹
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
            # 记录文件相对路径（供后续下载）
            file_path = f"uploads/{filename}"
        else:
            flash('不允许的文件类型', 'danger')
            return redirect(url_for('main.course_detail', course_id=course_id))

    # 第三步：将资源信息存入数据库
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO resources (course_id, title, file_path, resource_type) VALUES (%s, %s, %s, %s)",
                (course_id, title, file_path, resource_type)
            )
            conn.commit()  # 提交事务
            flash('资源上传成功', 'success')
    except Exception as e:
        flash(f'上传失败: {e}', 'danger')
    finally:
        conn.close()

    # 上传完成后返回课程详情页
    return redirect(url_for('main.course_detail', course_id=course_id))


@teacher_bp.route('/course/<int:course_id>/create_assignment', methods=['GET', 'POST'])
@login_required
def create_assignment(course_id):
    if current_user.role != 'teacher' and current_user.role != 'admin':
        flash('只有教师可以发布作业', 'warning')
        return redirect(url_for('main.index'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 【修改点】：多查一个 status 字段
            cursor.execute("SELECT teacher_id, status FROM courses WHERE id = %s", (course_id,))
            course = cursor.fetchone()

            if not course or course['teacher_id'] != current_user.id:
                flash('您没有权限操作此课程', 'danger')
                return redirect(url_for('main.course_detail', course_id=course_id))

            # 【新增】：如果课程被拒绝，拦截请求
            if course['status'] == 'rejected':
                flash('操作失败：该课程已被管理员拒绝，无法发布新作业。', 'warning')
                return redirect(url_for('main.course_detail', course_id=course_id))

        # 第二步：处理作业创建表单（POST请求）
        if request.method == 'POST':
            title = request.form['title']  # 作业名称
            description = request.form['description']  # 作业描述
            deadline = request.form['deadline']  # 截止时间（格式：YYYY-MM-DDTHH:MM）

            with conn.cursor() as cursor:
                # 插入作业数据到数据库
                cursor.execute(
                    "INSERT INTO assignments (course_id, title, description, deadline) VALUES (%s, %s, %s, %s)",
                    (course_id, title, description, deadline)
                )
                conn.commit()  # 提交事务
                flash('作业发布成功', 'success')
                return redirect(url_for('main.course_detail', course_id=course_id))
    except Exception as e:
        flash(f'发布作业失败: {e}', 'danger')
    finally:
        conn.close()

    # GET请求：渲染作业创建页面，传递课程ID
    return render_template('create_assignment.html', course_id=course_id)


# -------------------------- 查看作业提交列表 --------------------------
# 路由：/assignment/作业ID/submissions (GET请求)，必须登录
@teacher_bp.route('/assignment/<int:assignment_id>/submissions')
@login_required
def assignment_submissions(assignment_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 第一步：查询作业信息 + 校验权限
            cursor.execute("""
                SELECT a.*, c.teacher_id, c.title as course_title 
                FROM assignments a 
                JOIN courses c ON a.course_id = c.id 
                WHERE a.id = %s
            """, (assignment_id,))
            assignment = cursor.fetchone()

            # 作业不存在：提示并返回仪表盘
            if not assignment:
                flash('作业不存在', 'danger')
                return redirect(url_for('main.dashboard'))

            # 权限校验：仅授课教师/管理员可查看提交列表
            if assignment['teacher_id'] != current_user.id and current_user.role != 'admin':
                flash('权限不足', 'danger')
                return redirect(url_for('main.dashboard'))

            # 第二步：查询该作业的所有提交记录（关联学生表获取姓名/账号）
            cursor.execute("""
                SELECT s.*, u.name as student_name, u.username
                FROM submissions s
                JOIN users u ON s.student_id = u.id  # 关联用户表
                WHERE s.assignment_id = %s
                ORDER BY s.submitted_at DESC        # 按提交时间降序
            """, (assignment_id,))
            submissions = cursor.fetchall()

            # 渲染作业提交列表页面
            return render_template('assignment_submissions.html', assignment=assignment, submissions=submissions)
    finally:
        conn.close()


# -------------------------- 作业评分 --------------------------
# 路由：/submission/提交ID/grade (仅POST请求)，必须登录
@teacher_bp.route('/submission/<int:submission_id>/grade', methods=['POST'])
@login_required
def grade_submission(submission_id):
    # 从表单获取评分和评语
    grade = request.form['grade']  # 分数
    feedback = request.form['feedback']  # 评语

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 更新提交记录的评分、评语、评分时间
            cursor.execute("UPDATE submissions SET grade = %s, feedback = %s, graded_at = NOW() WHERE id = %s",
                           (grade, feedback, submission_id))

            # 查询该提交对应的作业ID（用于评分后跳转）
            cursor.execute("SELECT assignment_id FROM submissions WHERE id = %s", (submission_id,))
            submission = cursor.fetchone()

            conn.commit()  # 提交事务
            flash('评分完成', 'success')
            # 跳转到该作业的提交列表页
            return redirect(url_for('teacher.assignment_submissions', assignment_id=submission['assignment_id']))
    except Exception as e:
        flash(f'评分失败: {e}', 'danger')
        return redirect(url_for('main.dashboard'))
    finally:
        conn.close()