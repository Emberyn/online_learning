-- ======================================================
-- 在线学习系统 - 完整系统测试数据脚本
-- 用于期末答辩演示，涵盖所有表的数据流转
-- ======================================================

USE online_learning_db;

-- ------------------------------------------------------
-- 0. 清理旧数据（防止重复运行报错，按外键依赖顺序删除）
-- 注意：这里不删除 admin，因为 schema.sql 可能已经创建了默认 admin
-- ------------------------------------------------------
DELETE FROM submissions;
DELETE FROM assignments;
DELETE FROM resources;
DELETE FROM enrollments;
DELETE FROM courses;
DELETE FROM users WHERE role != 'admin';

-- ------------------------------------------------------
-- 1. 插入测试用户 (2个老师, 3个学生)
-- 密码均使用明文 '123456' 方便测试登录
-- ------------------------------------------------------
INSERT INTO users (id, username, password, role, name, email) VALUES
(2, 'teacher1', '123456', 'teacher', '张教授', 't1@test.com'),
(3, 'teacher2', '123456', 'teacher', '王老师', 't2@test.com'),
(4, 'student1', '123456', 'student', '李同学', 's1@test.com'),
(5, 'student2', '123456', 'student', '赵同学', 's2@test.com'),
(6, 'student3', '123456', 'student', '陈同学', 's3@test.com');

-- ------------------------------------------------------
-- 2. 插入测试课程 (涵盖不同的状态：已发布 和 待审核)
-- ------------------------------------------------------
-- 课程1：容量设为 2，并且已经有 1 人选了，方便测试“名额已满”逻辑
INSERT INTO courses (id, title, description, objectives, content, outline, teacher_id, category, status, max_capacity, enrolled_count) VALUES
(1, '数据库高级设计', '学习触发器、存储过程与视图的实战应用', '掌握数据库高级特性开发', '第一章：视图...第二章：触发器...', '1. 视图 2. 触发器 3. 存储过程', 2, '计算机与IT', 'published', 2, 1),
(2, 'Python Web实战', '基于Flask框架开发在线系统', '能够独立完成B/S架构系统开发', 'Flask路由、模板、数据库连接', '1. Flask基础 2. PyMySQL集成', 2, '计算机与IT', 'published', 50, 0),
(3, '高等数学基础', '微积分与线性代数入门', '掌握极限与导数计算', '极限、导数、积分应用', '1. 极限计算 2. 导数基础', 3, '理学与工学', 'pending', 60, 0);

-- ------------------------------------------------------
-- 3. 插入测试选课记录 (验证学习进度)
-- 李同学(id=4) 已经选了《数据库高级设计》(id=1)
-- ------------------------------------------------------
INSERT INTO enrollments (student_id, course_id, progress) VALUES
(4, 1, 35.50);

-- ------------------------------------------------------
-- 4. 插入教学资源 (丰富课程详情页)
-- ------------------------------------------------------
INSERT INTO resources (course_id, title, file_path, resource_type) VALUES
(1, '数据库E-R图设计规范指导', 'uploads/er_guide.pdf', 'document'),
(1, '触发器实战演示录屏', 'uploads/trigger_demo.mp4', 'video'),
(2, 'Flask中文官方文档', 'uploads/flask_docs.pdf', 'document');

-- ------------------------------------------------------
-- 5. 插入作业表
-- ------------------------------------------------------
INSERT INTO assignments (id, course_id, title, description, deadline) VALUES
(1, 1, '编写选课存储过程', '请提交带有事务控制的选课存储过程SQL代码，要求能处理并发问题。', '2026-06-30 23:59:59'),
(2, 2, '完成用户登录模块', '使用Flask-Login实现用户鉴权，区分学生和教师角色。', '2026-06-15 23:59:59');

-- ------------------------------------------------------
-- 6. 插入作业提交与成绩表 (展示师生互动闭环)
-- ------------------------------------------------------
INSERT INTO submissions (assignment_id, student_id, content, grade, feedback) VALUES
(1, 4, 'DELIMITER $$ CREATE PROCEDURE proc_enroll... (已提交完整代码)', 95.00, '思路清晰，事务处理得很完美！');



---------------------------------------------------------------------
