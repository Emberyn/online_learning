from flask import Blueprint, flash, redirect, url_for, render_template, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import time
from db import get_db_connection
from datetime import datetime

student_bp = Blueprint('student', __name__)

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'ppt', 'pptx', 'mp4', 'zip', 'rar'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@student_bp.route('/course/<int:course_id>/enroll', methods=['POST'])
@login_required
def enroll_course(course_id):
    if current_user.role != 'student':
        flash('只有学生可以选课', 'warning')
        return redirect(url_for('main.course_detail', course_id=course_id))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM enrollments WHERE student_id = %s AND course_id = %s",
                           (current_user.id, course_id))
            if cursor.fetchone():
                flash('您已选修该课程', 'info')
            else:
                cursor.callproc('proc_enroll', (current_user.id, course_id))
                conn.commit()
                flash('选课成功！', 'success')
    except Exception as e:
        error_msg = e.args[1] if len(e.args) > 1 else str(e)
        flash(f'选课失败: {error_msg}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('main.dashboard'))

@student_bp.route('/assignment/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
def assignment_detail(assignment_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Get Assignment Details
            cursor.execute("""
                SELECT a.*, c.title as course_title, c.teacher_id
                FROM assignments a 
                JOIN courses c ON a.course_id = c.id 
                WHERE a.id = %s
            """, (assignment_id,))
            assignment = cursor.fetchone()

            if not assignment:
                flash('作业不存在', 'danger')
                return redirect(url_for('main.dashboard'))

            submission = None

            # 2. Check Enrollment / Permission
            if current_user.role == 'student':
                cursor.execute("SELECT * FROM enrollments WHERE student_id = %s AND course_id = %s",
                               (current_user.id, assignment['course_id']))
                if not cursor.fetchone():
                    flash('您未选修该课程，无法查看作业', 'warning')
                    return redirect(url_for('main.dashboard'))
                
                # Fetch existing submission
                cursor.execute("SELECT * FROM submissions WHERE assignment_id = %s AND student_id = %s",
                               (assignment_id, current_user.id))
                submission = cursor.fetchone()

            # 3. Handle Submission (POST) - Only for Students
            if request.method == 'POST' and current_user.role == 'student':
                # 【新增】检查是否超过截止时间
                if assignment['deadline'] and datetime.now() > assignment['deadline']:
                    flash('该作业已过截止时间，无法再提交或修改！', 'danger')
                    return redirect(url_for('student.assignment_detail', assignment_id=assignment_id))

                if 'file' not in request.files:
                    flash('没有文件', 'warning')
                else:
                    file = request.files['file']
                    if file.filename == '':
                        flash('未选择文件', 'warning')
                    elif file and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        # Unique filename: sub_STUDENTID_TIMESTAMP_FILENAME
                        filename = f"sub_{current_user.id}_{int(time.time())}_{filename}"
                        
                        if not os.path.exists(current_app.config['UPLOAD_FOLDER']):
                            os.makedirs(current_app.config['UPLOAD_FOLDER'])
                            
                        file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                        file_path = f"uploads/{filename}"
                        
                        if submission:
                            # Update existing
                            cursor.execute("UPDATE submissions SET content = %s, submitted_at = NOW() WHERE id = %s",
                                           (file_path, submission['id']))
                            flash('作业已更新', 'success')
                        else:
                            # Create new
                            cursor.execute("INSERT INTO submissions (assignment_id, student_id, content) VALUES (%s, %s, %s)",
                                           (assignment_id, current_user.id, file_path))
                            flash('作业提交成功', 'success')
                        
                        conn.commit()
                        return redirect(url_for('student.assignment_detail', assignment_id=assignment_id))
                    else:
                        flash('不支持的文件格式', 'danger')

            return render_template('assignment_detail.html', assignment=assignment, submission=submission)

    finally:
        conn.close()

@student_bp.route('/my_grades')
@login_required
def my_grades():
    if current_user.role != 'student':
        flash('只有学生可以查看成绩', 'warning')
        return redirect(url_for('main.index'))
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Get all submissions with grades
            cursor.execute("""
                SELECT s.*, a.title as assignment_title, c.title as course_title, a.id as assignment_id
                FROM submissions s
                JOIN assignments a ON s.assignment_id = a.id
                JOIN courses c ON a.course_id = c.id
                WHERE s.student_id = %s
                ORDER BY c.title, a.deadline
            """, (current_user.id,))
            grades = cursor.fetchall()
            
            # 2. Calculate Comprehensive Score for each course
            # Group by course
            course_stats = {}
            for grade in grades:
                c_title = grade['course_title']
                if c_title not in course_stats:
                    course_stats[c_title] = {'total_score': 0, 'count': 0, 'assignments': []}
                
                course_stats[c_title]['assignments'].append(grade)
                if grade['grade'] is not None:
                    course_stats[c_title]['total_score'] += grade['grade']
                    course_stats[c_title]['count'] += 1
            
            # Final structure for template
            final_report = []
            for c_title, data in course_stats.items():
                avg_score = 0
                if data['count'] > 0:
                    avg_score = round(data['total_score'] / data['count'], 2)
                
                final_report.append({
                    'course_title': c_title,
                    'avg_score': avg_score,
                    'assignments': data['assignments'],
                    'attendance': '暂无', # Placeholder
                    'final_exam': '暂无'  # Placeholder
                })
                
    finally:
        conn.close()
    return render_template('my_grades.html', report=final_report)
