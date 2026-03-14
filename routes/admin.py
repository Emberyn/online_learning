from flask import Blueprint, render_template, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from db import get_db_connection

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/courses')
@login_required
def admin_courses():
    if current_user.role != 'admin':
        flash('权限不足', 'danger')
        return redirect(url_for('main.index'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT c.*, u.name as teacher_name 
                FROM courses c 
                JOIN users u ON c.teacher_id = u.id 
                WHERE c.status = 'pending'
            """)
            pending_courses = cursor.fetchall()
    finally:
        conn.close()
    return render_template('admin_courses.html', courses=pending_courses)

@admin_bp.route('/admin/course/<int:course_id>/approve', methods=['POST'])
@login_required
def approve_course(course_id):
    if current_user.role != 'admin':
        flash('权限不足', 'danger')
        return redirect(url_for('admin.admin_courses'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE courses SET status = 'published' WHERE id = %s", (course_id,))
            conn.commit()
            flash('课程已审核通过', 'success')
    finally:
        conn.close()
    return redirect(url_for('admin.admin_courses'))

@admin_bp.route('/admin/stats/users')
@login_required
def user_stats():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT role, COUNT(*) as count FROM users GROUP BY role")
            results = cursor.fetchall()
            
            labels = [row['role'] for row in results]
            values = [row['count'] for row in results]
            
            return jsonify({'labels': labels, 'values': values})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@admin_bp.route('/admin/course/<int:course_id>/reject', methods=['POST'])
@login_required
def reject_course(course_id):
    if current_user.role != 'admin':
        flash('权限不足', 'danger')
        return redirect(url_for('admin.admin_courses'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE courses SET status = 'rejected' WHERE id = %s", (course_id,))
            conn.commit()
            flash('课程已拒绝', 'warning')
    finally:
        conn.close()
    return redirect(url_for('admin.admin_courses'))
