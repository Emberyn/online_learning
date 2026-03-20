# 导入Flask核心模块：Blueprint(蓝图)、flash(提示消息)、redirect(重定向)、url_for(反向路由)
# render_template(渲染HTML)、request(接收请求数据)、current_app(当前应用配置)
from flask import Blueprint, flash, redirect, url_for, render_template, request, current_app
# 导入Flask-Login模块：login_required(登录验证)、current_user(当前登录用户对象)
from flask_login import login_required, current_user
# 导入werkzeug工具：安全处理文件名（防止恶意文件名）
from werkzeug.utils import secure_filename
# 导入系统模块：文件路径处理、时间戳
import os
import time
# 导入自定义数据库连接函数
from db import get_db_connection
# 导入日期时间模块：处理截止时间校验
from datetime import datetime

# 创建学生蓝图：名称为'student'，关联当前文件，负责学生选课、作业提交、成绩查看等功能
student_bp = Blueprint('student', __name__)

# 允许上传的文件格式集合（限制文件类型，提升安全性）
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'ppt', 'pptx', 'mp4', 'zip', 'rar'}


# ==========================================
# 新增：学生选课中心 (带左侧边栏)
# ==========================================
@student_bp.route('/student/courses')
@login_required
def course_center():
    if current_user.role != 'student':
        flash('只有学生可以访问选课中心', 'warning')
        return redirect(url_for('main.index'))

    # 1. 尝试获取网址栏中的 category 参数
    category_filter = request.args.get('category')

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 2. 如果存在分类参数，SQL 增加 WHERE c.category = %s 条件
            if category_filter:
                cursor.execute("""
                    SELECT c.*, u.name as teacher_name, 
                           CASE WHEN e.student_id IS NOT NULL THEN 1 ELSE 0 END as is_enrolled
                    FROM courses c
                    JOIN users u ON c.teacher_id = u.id
                    LEFT JOIN enrollments e ON c.id = e.course_id AND e.student_id = %s
                    WHERE c.status = 'published' AND c.category = %s
                """, (current_user.id, category_filter))
            # 3. 如果没有分类参数，则查询全部已发布课程
            else:
                cursor.execute("""
                    SELECT c.*, u.name as teacher_name, 
                           CASE WHEN e.student_id IS NOT NULL THEN 1 ELSE 0 END as is_enrolled
                    FROM courses c
                    JOIN users u ON c.teacher_id = u.id
                    LEFT JOIN enrollments e ON c.id = e.course_id AND e.student_id = %s
                    WHERE c.status = 'published'
                """, (current_user.id,))

            courses = cursor.fetchall()
    finally:
        conn.close()

    # 注意这里多传了一个 current_category 参数给前端
    return render_template('student_courses.html', courses=courses, current_category=category_filter)


# ==========================================
# 新增：学生任务中心 (我的作业)
# ==========================================
@student_bp.route('/student/assignments')
@login_required
def my_assignments():
    if current_user.role != 'student':
        flash('只有学生可以访问作业中心', 'warning')
        return redirect(url_for('main.index'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 查询当前学生已选课程的所有作业，以及提交状态
            cursor.execute("""
                SELECT a.*, c.title as course_title, 
                       s.id as submission_id, s.grade, s.submitted_at
                FROM assignments a
                JOIN courses c ON a.course_id = c.id
                JOIN enrollments e ON c.id = e.course_id
                LEFT JOIN submissions s ON a.id = s.assignment_id AND s.student_id = %s
                WHERE e.student_id = %s
                ORDER BY a.deadline ASC
            """, (current_user.id, current_user.id))
            assignments = cursor.fetchall()

            # 在后端计算作业状态，方便前端展示
            now = datetime.now()
            for task in assignments:
                if task['submission_id']:
                    task['status'] = 'graded' if task['grade'] is not None else 'submitted'
                else:
                    task['status'] = 'overdue' if task['deadline'] and now > task['deadline'] else 'pending'

    finally:
        conn.close()
    return render_template('student_assignments.html', assignments=assignments)


# -------------------------- 工具函数：校验文件格式 --------------------------
def allowed_file(filename):
    """
    校验上传文件是否为允许的格式
    :param filename: 上传的文件名
    :return: True=格式合法，False=格式不合法
    """
    # 条件1：文件名包含小数点（有后缀）；条件2：后缀在允许的集合中（不区分大小写）
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# -------------------------- 学生选课功能 --------------------------
# 路由：/course/课程ID/enroll (仅POST请求)，必须登录
@student_bp.route('/course/<int:course_id>/enroll', methods=['POST'])
@login_required
def enroll_course(course_id):
    # 权限校验：仅学生角色可选课
    if current_user.role != 'student':
        flash('只有学生可以选课', 'warning')
        return redirect(url_for('main.course_detail', course_id=course_id))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 先校验：是否已选过该课程（避免重复选课）
            cursor.execute("SELECT * FROM enrollments WHERE student_id = %s AND course_id = %s",
                           (current_user.id, course_id))
            if cursor.fetchone():
                flash('您已选修该课程', 'info')
            else:
                # 调用数据库存储过程proc_enroll完成选课（存储过程封装了复杂的选课逻辑）
                cursor.callproc('proc_enroll', (current_user.id, course_id))
                conn.commit()  # 提交事务
                flash('选课成功！', 'success')
    except Exception as e:
        # 捕获异常：提取具体错误信息（兼容不同异常格式）
        error_msg = e.args[1] if len(e.args) > 1 else str(e)
        flash(f'选课失败: {error_msg}', 'danger')
    finally:
        # 无论是否报错，关闭数据库连接
        conn.close()
    # 选课完成后跳转到学生仪表盘
    return redirect(url_for('main.dashboard'))


# -------------------------- 作业详情&提交功能 --------------------------
# 路由：/assignment/作业ID (支持GET/POST)，必须登录
@student_bp.route('/assignment/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
def assignment_detail(assignment_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 查询作业基本信息（关联课程表获取课程名称、授课老师ID）
            cursor.execute("""
                SELECT a.*, c.title as course_title, c.teacher_id
                FROM assignments a 
                JOIN courses c ON a.course_id = c.id 
                WHERE a.id = %s
            """, (assignment_id,))
            assignment = cursor.fetchone()

            # 作业不存在：提示并返回仪表盘
            if not assignment:
                flash('作业不存在', 'danger')
                return redirect(url_for('main.dashboard'))

            # 初始化提交记录变量
            submission = None

            # 2. 权限校验：学生需先选该课程才能查看作业
            if current_user.role == 'student':
                cursor.execute("SELECT * FROM enrollments WHERE student_id = %s AND course_id = %s",
                               (current_user.id, assignment['course_id']))
                if not cursor.fetchone():
                    flash('您未选修该课程，无法查看作业', 'warning')
                    return redirect(url_for('main.dashboard'))

                # 查询该学生是否已提交过该作业（用于回显提交记录）
                cursor.execute("SELECT * FROM submissions WHERE assignment_id = %s AND student_id = %s",
                               (assignment_id, current_user.id))
                submission = cursor.fetchone()

            # 3. 处理作业提交（仅POST请求 + 学生角色）
            if request.method == 'POST' and current_user.role == 'student':
                # 校验：作业是否超过截止时间
                if assignment['deadline'] and datetime.now() > assignment['deadline']:
                    flash('该作业已过截止时间，无法再提交或修改！', 'danger')
                    return redirect(url_for('student.assignment_detail', assignment_id=assignment_id))

                # 校验：请求中是否包含文件
                if 'file' not in request.files:
                    flash('没有文件', 'warning')
                else:
                    file = request.files['file']
                    # 校验：是否选择了文件（文件名不为空）
                    if file.filename == '':
                        flash('未选择文件', 'warning')
                    # 校验：文件格式是否合法
                    elif file and allowed_file(file.filename):
                        # 放弃 secure_filename，手动过滤斜杠以防路径穿越，从而完美保留中文文件名
                        safe_filename = file.filename.replace('/', '').replace('\\', '')
                        # 生成唯一文件名：sub_学生ID_时间戳_原文件名（避免文件重名覆盖）
                        filename = f"sub_{current_user.id}_{int(time.time())}_{safe_filename}"

                        # 确保上传文件夹存在（不存在则创建）
                        if not os.path.exists(current_app.config['UPLOAD_FOLDER']):
                            os.makedirs(current_app.config['UPLOAD_FOLDER'])

                        # 保存文件到上传文件夹
                        file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                        # 记录文件存储路径（相对路径，便于后续下载）
                        file_path = f"uploads/{filename}"

                        # 有历史提交记录：更新提交（覆盖原有文件）
                        if submission:
                            cursor.execute("UPDATE submissions SET content = %s, submitted_at = NOW() WHERE id = %s",
                                           (file_path, submission['id']))
                            flash('作业已更新', 'success')
                        # 无历史提交记录：新增提交
                        else:
                            cursor.execute(
                                "INSERT INTO submissions (assignment_id, student_id, content) VALUES (%s, %s, %s)",
                                (assignment_id, current_user.id, file_path))
                            flash('作业提交成功', 'success')

                        conn.commit()  # 提交事务（保存作业）

                        # ==========================================
                        # 新增：自动计算并更新学习进度
                        # ==========================================
                        try:
                            # 1. 获取该课程的总作业数
                            cursor.execute("SELECT COUNT(*) as total FROM assignments WHERE course_id = %s", (assignment['course_id'],))
                            total_tasks = cursor.fetchone()['total']
                            
                            # 2. 获取该学生目前已提交的不重复作业数
                            cursor.execute("""
                                SELECT COUNT(DISTINCT s.assignment_id) as sub_count 
                                FROM submissions s 
                                JOIN assignments a ON s.assignment_id = a.id 
                                WHERE s.student_id = %s AND a.course_id = %s
                            """, (current_user.id, assignment['course_id']))
                            submitted_tasks = cursor.fetchone()['sub_count']
                            
                            # 3. 计算进度百分比 (保留两位小数)
                            if total_tasks > 0:
                                new_progress = round((submitted_tasks / total_tasks) * 100, 2)
                            else:
                                new_progress = 0.00
                                
                            # 4. 更新数据库中的选课进度字段
                            cursor.execute("UPDATE enrollments SET progress = %s WHERE student_id = %s AND course_id = %s",
                                           (new_progress, current_user.id, assignment['course_id']))
                            conn.commit()  # 提交事务（保存进度）
                        except Exception as e:
                            print(f"自动更新进度时发生异常: {e}")
                        # ==========================================

                        # 提交后刷新作业详情页
                        return redirect(url_for('student.assignment_detail', assignment_id=assignment_id))
                    else:
                        # 文件格式不合法
                        flash('不支持的文件格式', 'danger')

            # 渲染作业详情页，传递作业信息、提交记录
            return render_template('assignment_detail.html', assignment=assignment, submission=submission)

    finally:
        conn.close()


# -------------------------- 学生成绩查看功能 --------------------------
# 路由：/my_grades (GET请求)，必须登录
@student_bp.route('/my_grades')
@login_required
def my_grades():
    # 权限校验：仅学生角色可查看成绩
    if current_user.role != 'student':
        flash('只有学生可以查看成绩', 'warning')
        return redirect(url_for('main.index'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 查询该学生所有带成绩的作业提交记录
            cursor.execute("""
                SELECT s.*, a.title as assignment_title, c.title as course_title, a.id as assignment_id
                FROM submissions s
                JOIN assignments a ON s.assignment_id = a.id  # 关联作业表
                JOIN courses c ON a.course_id = c.id          # 关联课程表
                WHERE s.student_id = %s
                ORDER BY c.title, a.deadline  # 按课程名称、作业截止时间排序
            """, (current_user.id,))
            grades = cursor.fetchall()

            # 2. 按课程分组，计算每门课程的平均成绩
            # 初始化课程统计字典：key=课程名称，value=统计数据
            course_stats = {}
            for grade in grades:
                c_title = grade['course_title']
                # 课程首次出现：初始化统计数据
                if c_title not in course_stats:
                    course_stats[c_title] = {'total_score': 0, 'count': 0, 'assignments': []}

                # 追加该课程的作业记录
                course_stats[c_title]['assignments'].append(grade)
                # 仅统计有成绩的作业（grade不为空）
                if grade['grade'] is not None:
                    course_stats[c_title]['total_score'] += grade['grade']
                    course_stats[c_title]['count'] += 1

            # 3. 构建最终成绩报表（供模板渲染）
            final_report = []
            for c_title, data in course_stats.items():
                avg_score = 0
                # 计算平均成绩（避免除以0）
                if data['count'] > 0:
                    avg_score = round(data['total_score'] / data['count'], 2)

                # 组装单门课程的成绩数据
                final_report.append({
                    'course_title': c_title,  # 课程名称
                    'avg_score': avg_score,  # 平均成绩（保留2位小数）
                    'assignments': data['assignments'],  # 该课程所有作业记录
                    'attendance': '暂无',  # 考勤成绩（占位符）
                    'final_exam': '暂无'  # 期末成绩（占位符）
                })

    finally:
        conn.close()
    # 渲染成绩页面，传递成绩报表数据
    return render_template('my_grades.html', report=final_report)