from flask import Blueprint, render_template, flash, redirect, url_for, request, send_from_directory, current_app
from flask_login import login_required, current_user
from db import get_db_connection
import os

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    conn = get_db_connection()
    courses = []
    try:
        with conn.cursor() as cursor:
            sql = "SELECT * FROM v_course_list"
            cursor.execute(sql)
            courses = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching courses: {e}")
    finally:
        conn.close()
    return render_template('index.html', courses=courses)

@main_bp.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    try:
        if current_user.role == 'admin':
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as count FROM courses WHERE status = 'pending'")
                pending_count = cursor.fetchone()['count']
                cursor.execute("SELECT COUNT(*) as count FROM users")
                user_count = cursor.fetchone()['count']
            return render_template('admin_dashboard.html', pending_count=pending_count, user_count=user_count)

        elif current_user.role == 'teacher':
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as count FROM courses WHERE teacher_id = %s", (current_user.id,))
                course_count = cursor.fetchone()['count']
            return render_template('teacher_dashboard.html', course_count=course_count)

        else:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT c.*, u.name as teacher_name, e.progress
                    FROM enrollments e
                    JOIN courses c ON e.course_id = c.id
                    JOIN users u ON c.teacher_id = u.id
                    WHERE e.student_id = %s
                """, (current_user.id,))
                enrolled_courses = cursor.fetchall()
            return render_template('student_dashboard.html', courses=enrolled_courses)
    finally:
        conn.close()

@main_bp.route('/course/<int:course_id>')
def course_detail(course_id):
    conn = get_db_connection()
    course = None
    is_enrolled = False
    resources = []
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT c.*, u.name as teacher_name 
                FROM courses c 
                JOIN users u ON c.teacher_id = u.id 
                WHERE c.id = %s
            """, (course_id,))
            course = cursor.fetchone()

            if not course:
                flash('课程不存在', 'danger')
                return redirect(url_for('main.index'))

            if current_user.is_authenticated:
                if current_user.role == 'student':
                    cursor.execute("SELECT * FROM enrollments WHERE student_id = %s AND course_id = %s",
                                   (current_user.id, course_id))
                    if cursor.fetchone():
                        is_enrolled = True

            cursor.execute("SELECT * FROM resources WHERE course_id = %s", (course_id,))
            resources = cursor.fetchall()

            cursor.execute("SELECT * FROM assignments WHERE course_id = %s ORDER BY deadline", (course_id,))
            assignments = cursor.fetchall()

            # Fetch comments
            cursor.execute("""
                SELECT c.*, u.username, u.name as user_name, u.role
                FROM comments c
                JOIN users u ON c.user_id = u.id
                WHERE c.course_id = %s
                ORDER BY c.created_at DESC
            """, (course_id,))
            comments = cursor.fetchall()

    finally:
        conn.close()

    return render_template('course_detail.html', course=course, is_enrolled=is_enrolled, resources=resources, assignments=assignments, comments=comments)

@main_bp.route('/course/<int:course_id>/comment', methods=['POST'])
@login_required
def post_comment(course_id):
    content = request.form['content']
    if not content:
        flash('评论内容不能为空', 'warning')
        return redirect(url_for('main.course_detail', course_id=course_id))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check if course exists
            cursor.execute("SELECT id FROM courses WHERE id = %s", (course_id,))
            if not cursor.fetchone():
                flash('课程不存在', 'danger')
                return redirect(url_for('main.index'))
                
            cursor.execute("INSERT INTO comments (course_id, user_id, content) VALUES (%s, %s, %s)",
                           (course_id, current_user.id, content))
            conn.commit()
            flash('评论发表成功', 'success')
    except Exception as e:
        flash(f'评论失败: {e}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('main.course_detail', course_id=course_id))

@main_bp.route('/download/<path:filename>')
@login_required
def download_file(filename):
    # uploads/1710345678_realname.pdf -> realname.pdf
    try:
        # Check if file exists in upload folder
        return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename, as_attachment=True, download_name=filename.split('_', 1)[1] if '_' in filename else filename)
    except Exception as e:
        flash(f'文件下载失败: {e}', 'danger')
        return redirect(url_for('main.index'))
