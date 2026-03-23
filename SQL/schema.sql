-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS online_learning_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE online_learning_db;

-- 1. 用户表
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    password VARCHAR(255) NOT NULL COMMENT '密码哈希(当前测试环境为明文)',
    role ENUM('admin', 'teacher', 'student') NOT NULL COMMENT '角色',
    name VARCHAR(100) NOT NULL COMMENT '真实姓名',
    email VARCHAR(100) COMMENT '邮箱',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. 课程表 (包含拒绝原因字段)
CREATE TABLE IF NOT EXISTS courses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL COMMENT '课程名称',
    description TEXT COMMENT '课程简介',
    objectives TEXT COMMENT '课程目标',
    content TEXT COMMENT '课程内容',
    outline TEXT COMMENT '课程大纲',
    teacher_id INT NOT NULL COMMENT '授课教师ID',
    category VARCHAR(100) COMMENT '课程分类',
    max_capacity INT DEFAULT 100 COMMENT '最大选课人数',
    enrolled_count INT DEFAULT 0 COMMENT '已选人数',
    status ENUM('pending', 'published', 'rejected') DEFAULT 'pending' COMMENT '状态',
    reject_reason TEXT COMMENT '审核未通过原因',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. 选课表
CREATE TABLE IF NOT EXISTS enrollments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL COMMENT '学生ID',
    course_id INT NOT NULL COMMENT '课程ID',
    progress DECIMAL(5, 2) DEFAULT 0.00 COMMENT '学习进度百分比',
    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '选课时间',
    UNIQUE KEY unique_enrollment (student_id, course_id),
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. 教学资源表
CREATE TABLE IF NOT EXISTS resources (
    id INT AUTO_INCREMENT PRIMARY KEY,
    course_id INT NOT NULL COMMENT '课程ID',
    title VARCHAR(200) NOT NULL COMMENT '资源标题',
    file_path VARCHAR(500) COMMENT '文件路径或链接',
    resource_type ENUM('video', 'document', 'link') NOT NULL COMMENT '资源类型',
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. 作业表
CREATE TABLE IF NOT EXISTS assignments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    course_id INT NOT NULL COMMENT '课程ID',
    title VARCHAR(200) NOT NULL COMMENT '作业标题',
    description TEXT COMMENT '作业描述',
    deadline DATETIME COMMENT '截止时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '发布时间',
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. 作业提交与成绩表
CREATE TABLE IF NOT EXISTS submissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    assignment_id INT NOT NULL COMMENT '作业ID',
    student_id INT NOT NULL COMMENT '学生ID',
    content TEXT COMMENT '提交内容或文件路径',
    grade DECIMAL(5, 2) COMMENT '成绩',
    feedback TEXT COMMENT '教师评语',
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '提交时间',
    graded_at TIMESTAMP COMMENT '评分时间',
    FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. 评论表 (包含防重复评价约束)
CREATE TABLE IF NOT EXISTS comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    course_id INT NOT NULL COMMENT '所属课程ID',
    user_id INT NOT NULL COMMENT '评论者ID',
    content TEXT NOT NULL COMMENT '评论内容',
    rating INT DEFAULT 5 COMMENT '评分1-5星',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '评论时间',
    UNIQUE KEY unique_user_course_comment (course_id, user_id),
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 8. 学习计划表
CREATE TABLE IF NOT EXISTS study_plans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL COMMENT '学生ID',
    course_id INT COMMENT '关联课程ID（可选）',
    task_content VARCHAR(255) NOT NULL COMMENT '计划内容',
    is_completed BOOLEAN DEFAULT FALSE COMMENT '是否已完成',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 9. 插入默认管理员账户 (密码纯明文)
INSERT INTO users (username, password, role, name, email)
SELECT 'admin', '123456', 'admin', '刘建国', 'admin_liu@qq.com'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin');