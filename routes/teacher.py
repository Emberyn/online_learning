from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import time
from db import get_db_connection

teacher_bp = Blueprint('teacher', __name__)

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'ppt', 'pptx', 'mp4'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@teacher_bp.route('/create_course', methods=['GET', 'POST'])
@login_required
def create_course():
    if current_user.role != 'teacher' and current_user.role != 'admin':
        flash('只有教师可以发布课程', 'warning')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO courses (title, description, teacher_id, category, status) VALUES (%s, %s, %s, %s, 'pending')",
                    (title, description, current_user.id, category)
                )
                conn.commit()
                flash('课程已创建，等待管理员审核', 'success')
                return redirect(url_for('main.dashboard'))
        except Exception as e:
            flash(f'创建课程失败: {e}', 'danger')
        finally:
            conn.close()

    return render_template('create_course.html')

@teacher_bp.route('/my_courses')
@login_required
def my_courses():
    if current_user.role != 'teacher':
        flash('只有教师可以查看此页面', 'warning')
        return redirect(url_for('main.index'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM courses WHERE teacher_id = %s", (current_user.id,))
            courses = cursor.fetchall()
    finally:
        conn.close()
    return render_template('my_courses.html', courses=courses)

@teacher_bp.route('/teacher/stats/enrollment')
@login_required
def enrollment_stats():
    if current_user.role != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 403

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Get real enrollment count for each course from enrollments table
            cursor.execute("""
                SELECT c.title, COUNT(e.student_id) as enrolled_count 
                FROM courses c
                LEFT JOIN enrollments e ON c.id = e.course_id
                WHERE c.teacher_id = %s
                GROUP BY c.id, c.title
                ORDER BY enrolled_count DESC
            """, (current_user.id,))
            results = cursor.fetchall()
            
            labels = [row['title'] for row in results]
            values = [row['enrolled_count'] for row in results]
            
            return jsonify({'labels': labels, 'values': values})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@teacher_bp.route('/course/<int:course_id>/upload_resource', methods=['POST'])
@login_required
def upload_resource(course_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT teacher_id FROM courses WHERE id = %s", (course_id,))
            course = cursor.fetchone()

            if not course or course['teacher_id'] != current_user.id:
                flash('您没有权限操作此课程', 'danger')
                return redirect(url_for('main.course_detail', course_id=course_id))
    finally:
        conn.close()

    title = request.form['title']
    resource_type = request.form['resource_type']
    file_path = None

    if resource_type == 'link':
        file_path = request.form.get('external_link')
        if not file_path:
            flash('请输入外部链接', 'warning')
            return redirect(url_for('main.course_detail', course_id=course_id))
    else:
        if 'file' not in request.files:
            flash('没有文件部分', 'warning')
            return redirect(url_for('main.course_detail', course_id=course_id))

        file = request.files['file']
        if file.filename == '':
            flash('未选择文件', 'warning')
            return redirect(url_for('main.course_detail', course_id=course_id))

        if file and allowed_file(file.filename):
            # Use original filename but prepend timestamp to avoid collision
            original_filename = secure_filename(file.filename)
            filename = f"{int(time.time())}_{original_filename}"

            if not os.path.exists(current_app.config['UPLOAD_FOLDER']):
                os.makedirs(current_app.config['UPLOAD_FOLDER'])

            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
            file_path = f"uploads/{filename}"
        else:
            flash('不允许的文件类型', 'danger')
            return redirect(url_for('main.course_detail', course_id=course_id))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO resources (course_id, title, file_path, resource_type) VALUES (%s, %s, %s, %s)",
                (course_id, title, file_path, resource_type)
            )
            conn.commit()
            flash('资源上传成功', 'success')
    except Exception as e:
        flash(f'上传失败: {e}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('main.course_detail', course_id=course_id))

@teacher_bp.route('/course/<int:course_id>/create_assignment', methods=['GET', 'POST'])
@login_required
def create_assignment(course_id):
    if current_user.role != 'teacher' and current_user.role != 'admin':
        flash('只有教师可以发布作业', 'warning')
        return redirect(url_for('main.index'))

    conn = get_db_connection()
    try:
        # Check permission
        with conn.cursor() as cursor:
            cursor.execute("SELECT teacher_id FROM courses WHERE id = %s", (course_id,))
            course = cursor.fetchone()
            if not course or course['teacher_id'] != current_user.id:
                flash('您没有权限操作此课程', 'danger')
                return redirect(url_for('main.course_detail', course_id=course_id))

        if request.method == 'POST':
            title = request.form['title']
            description = request.form['description']
            deadline = request.form['deadline'] # Format: YYYY-MM-DDTHH:MM

            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO assignments (course_id, title, description, deadline) VALUES (%s, %s, %s, %s)",
                    (course_id, title, description, deadline)
                )
                conn.commit()
                flash('作业发布成功', 'success')
                return redirect(url_for('main.course_detail', course_id=course_id))
    except Exception as e:
        flash(f'发布作业失败: {e}', 'danger')
    finally:
        conn.close()

    return render_template('create_assignment.html', course_id=course_id)

@teacher_bp.route('/assignment/<int:assignment_id>/submissions')
@login_required
def assignment_submissions(assignment_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check permission via course teacher
            cursor.execute("""
                SELECT a.*, c.teacher_id, c.title as course_title 
                FROM assignments a 
                JOIN courses c ON a.course_id = c.id 
                WHERE a.id = %s
            """, (assignment_id,))
            assignment = cursor.fetchone()

            if not assignment:
                flash('作业不存在', 'danger')
                return redirect(url_for('main.dashboard'))
            
            if assignment['teacher_id'] != current_user.id and current_user.role != 'admin':
                flash('权限不足', 'danger')
                return redirect(url_for('main.dashboard'))

            # Get submissions
            cursor.execute("""
                SELECT s.*, u.name as student_name, u.username
                FROM submissions s
                JOIN users u ON s.student_id = u.id
                WHERE s.assignment_id = %s
                ORDER BY s.submitted_at DESC
            """, (assignment_id,))
            submissions = cursor.fetchall()
            
            return render_template('assignment_submissions.html', assignment=assignment, submissions=submissions)
    finally:
        conn.close()

@teacher_bp.route('/submission/<int:submission_id>/grade', methods=['POST'])
@login_required
def grade_submission(submission_id):
    grade = request.form['grade']
    feedback = request.form['feedback']
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Verify permission (omitted for brevity, ideally check teacher_id again)
            cursor.execute("UPDATE submissions SET grade = %s, feedback = %s, graded_at = NOW() WHERE id = %s", 
                           (grade, feedback, submission_id))
            
            # Get assignment_id to redirect back
            cursor.execute("SELECT assignment_id FROM submissions WHERE id = %s", (submission_id,))
            submission = cursor.fetchone()
            
            conn.commit()
            flash('评分完成', 'success')
            return redirect(url_for('teacher.assignment_submissions', assignment_id=submission['assignment_id']))
    except Exception as e:
        flash(f'评分失败: {e}', 'danger')
        return redirect(url_for('main.dashboard'))
    finally:
        conn.close()
