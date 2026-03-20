# 导入Flask核心模块：Blueprint(蓝图)、render_template(渲染HTML)、flash(提示消息)、redirect(重定向)、url_for(反向路由)、jsonify(返回JSON)
from flask import Blueprint, render_template, flash, redirect, url_for, jsonify
# 导入Flask-Login模块：login_required(登录验证装饰器)、current_user(当前登录用户对象)
from flask_login import login_required, current_user
# 导入自定义的数据库连接函数
from db import get_db_connection

# 创建管理员蓝图：名称为'admin'，关联当前文件，用于管理后台相关功能
admin_bp = Blueprint('admin', __name__)



# ==========================================
# 新增：用户管理路由
# ==========================================
@admin_bp.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != 'admin':
        flash('权限不足', 'danger')
        return redirect(url_for('main.index'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 查询所有用户的信息，按注册时间倒序排列
            cursor.execute("""
                SELECT id, username, name, email, role, created_at 
                FROM users 
                ORDER BY created_at DESC
            """)
            users = cursor.fetchall()
    finally:
        conn.close()
    return render_template('admin_users.html', users=users)


@admin_bp.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        flash('权限不足', 'danger')
        return redirect(url_for('main.index'))

    # 防止管理员误删自己
    if current_user.id == user_id:
        flash('安全限制：您不能删除自己的账号！', 'danger')
        return redirect(url_for('admin.admin_users'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()
            flash('用户已成功删除', 'success')
    finally:
        conn.close()
    return redirect(url_for('admin.admin_users'))


# ==========================================
# 新增：详细数据统计路由
# ==========================================
@admin_bp.route('/admin/statistics')
@login_required
def admin_statistics():
    if current_user.role != 'admin':
        flash('权限不足', 'danger')
        return redirect(url_for('main.index'))

    conn = get_db_connection()
    stats = {}
    try:
        with conn.cursor() as cursor:
            # 1. 统计平台总课程数
            cursor.execute("SELECT COUNT(*) as count FROM courses")
            stats['total_courses'] = cursor.fetchone()['count']

            # 2. 统计平台总选课人次
            cursor.execute("SELECT COUNT(*) as count FROM enrollments")
            stats['total_enrollments'] = cursor.fetchone()['count']

            # 3. 统计各状态的课程分布 (待审核、已发布、已拒绝)
            cursor.execute("SELECT status, COUNT(*) as count FROM courses GROUP BY status")
            stats['course_status'] = cursor.fetchall()

            # 4. 统计资源总数
            cursor.execute("SELECT COUNT(*) as count FROM resources")
            stats['total_resources'] = cursor.fetchone()['count']
    finally:
        conn.close()
    return render_template('admin_stats.html', stats=stats)


# -------------------------- 管理员课程审核页面 --------------------------
# 路由：/admin/courses (GET请求)
@admin_bp.route('/admin/courses')
@login_required  # 必须登录才能访问该页面
def admin_courses():
    # 权限校验：仅管理员角色可访问，非管理员则提示并跳转到首页
    if current_user.role != 'admin':
        flash('权限不足', 'danger')  # 弹出危险级别提示消息
        return redirect(url_for('main.index'))  # 重定向到main蓝图的index视图

    # 获取数据库连接
    conn = get_db_connection()
    try:
        # 使用游标执行SQL：自动关闭游标（with上下文管理器）
        with conn.cursor() as cursor:
            # SQL联表查询：查询待审核课程（status=pending），关联用户表获取授课老师姓名
            cursor.execute("""
                SELECT c.*, u.name as teacher_name 
                FROM courses c 
                JOIN users u ON c.teacher_id = u.id  # 课程表teacher_id关联用户表id
                WHERE c.status = 'pending'
            """)
            # 获取所有查询结果（多个课程数据），返回列表+字典格式
            pending_courses = cursor.fetchall()
    finally:
        # 无论是否报错，最终都关闭数据库连接（避免连接泄露）
        conn.close()
    # 渲染管理员课程审核页面，传递待审核课程数据给HTML模板
    return render_template('admin_courses.html', courses=pending_courses)


# -------------------------- 审核通过课程 --------------------------
# 路由：/admin/course/课程ID/approve (仅POST请求)，<int:course_id>接收整数类型的课程ID
@admin_bp.route('/admin/course/<int:course_id>/approve', methods=['POST'])
@login_required  # 必须登录
def approve_course(course_id):
    # 权限校验：仅管理员可操作
    if current_user.role != 'admin':
        flash('权限不足', 'danger')
        return redirect(url_for('admin.admin_courses'))  # 重定向回课程审核页

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # SQL更新：将指定课程的状态改为已发布(published)
            cursor.execute("UPDATE courses SET status = 'published' WHERE id = %s", (course_id,))
            conn.commit()  # 提交事务（UPDATE/INSERT/DELETE必须提交才生效）
            flash('课程已审核通过', 'success')  # 弹出成功提示
    finally:
        conn.close()
    # 操作完成后重定向回课程审核列表页
    return redirect(url_for('admin.admin_courses'))


# -------------------------- 获取用户角色统计数据 --------------------------
# 路由：/admin/stats/users (GET请求)，返回JSON格式的统计数据
@admin_bp.route('/admin/stats/users')
@login_required
def user_stats():
    # 权限校验：非管理员返回403未授权错误（JSON格式）
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403  # 403是HTTP状态码：禁止访问

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # SQL分组统计：按角色(role)分组，统计每个角色的用户数量
            cursor.execute("SELECT role, COUNT(*) as count FROM users GROUP BY role")
            results = cursor.fetchall()  # 获取所有统计结果

            # 提取统计数据：角色名称列表 + 对应数量列表
            labels = [row['role'] for row in results]  # 如：['admin', 'teacher', 'student']
            values = [row['count'] for row in results]  # 如：[1, 5, 20]

            # 返回JSON格式数据（供前端图表渲染）
            return jsonify({'labels': labels, 'values': values})
    except Exception as e:
        # 捕获异常，返回500服务器错误（JSON格式）
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# -------------------------- 拒绝课程审核 --------------------------
# 路由：/admin/course/课程ID/reject (仅POST请求)
@admin_bp.route('/admin/course/<int:course_id>/reject', methods=['POST'])
@login_required
def reject_course(course_id):
    # 权限校验：仅管理员可操作
    if current_user.role != 'admin':
        flash('权限不足', 'danger')
        return redirect(url_for('admin.admin_courses'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # SQL更新：将指定课程的状态改为已拒绝(rejected)
            cursor.execute("UPDATE courses SET status = 'rejected' WHERE id = %s", (course_id,))
            conn.commit()  # 提交事务
            flash('课程已拒绝', 'warning')  # 弹出警告级别提示
    finally:
        conn.close()
    # 重定向回课程审核列表页
    return redirect(url_for('admin.admin_courses'))