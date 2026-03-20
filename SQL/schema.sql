-- 创建数据库（如果不存在）
create database if not exists online_learning_db character set utf8mb4 collate utf8mb4_unicode_ci;

use online_learning_db;

-- 用户表
create table if not exists users (
    id int auto_increment primary key,
    username varchar(50) not null unique comment '用户名',
    password varchar(255) not null comment '密码哈希',
    role enum('admin', 'teacher', 'student') not null comment '角色',
    name varchar(100) not null comment '真实姓名',
    email varchar(100) comment '邮箱',
    created_at timestamp default current_timestamp comment '注册时间'
) engine=innodb default charset=utf8mb4;

-- 课程表
create table if not exists courses (
    id int auto_increment primary key,
    title varchar(200) not null comment '课程名称',
    description text comment '课程简介',
    objectives text comment '课程目标',
    content text comment '课程内容',
    outline text comment '课程大纲',
    teacher_id int not null comment '授课教师ID',
    category varchar(100) comment '课程分类',

    -- 【新增下面两行】
    max_capacity int default 100 comment '最大选课人数',
    enrolled_count int default 0 comment '已选人数',

    status enum('pending', 'published', 'rejected') default 'pending' comment '课程状态：待审核，已发布，已拒绝',
    created_at timestamp default current_timestamp comment '创建时间',
    foreign key (teacher_id) references users(id) on delete cascade
) engine=innodb default charset=utf8mb4;

-- 选课表（包含学习进度）
create table if not exists enrollments (
    id int auto_increment primary key,
    student_id int not null comment '学生ID',
    course_id int not null comment '课程ID',
    progress decimal(5, 2) default 0.00 comment '学习进度百分比',
    enrolled_at timestamp default current_timestamp comment '选课时间',
    unique key unique_enrollment (student_id, course_id),
    foreign key (student_id) references users(id) on delete cascade,
    foreign key (course_id) references courses(id) on delete cascade
) engine=innodb default charset=utf8mb4;

-- 教学资源表
create table if not exists resources (
    id int auto_increment primary key,
    course_id int not null comment '课程ID',
    title varchar(200) not null comment '资源标题',
    file_path varchar(500) comment '文件路径或链接',
    resource_type enum('video', 'document', 'link') not null comment '资源类型',
    uploaded_at timestamp default current_timestamp comment '上传时间',
    foreign key (course_id) references courses(id) on delete cascade
) engine=innodb default charset=utf8mb4;

-- 作业表
create table if not exists assignments (
    id int auto_increment primary key,
    course_id int not null comment '课程ID',
    title varchar(200) not null comment '作业标题',
    description text comment '作业描述',
    deadline datetime comment '截止时间',
    created_at timestamp default current_timestamp comment '发布时间',
    foreign key (course_id) references courses(id) on delete cascade
) engine=innodb default charset=utf8mb4;

-- 作业提交与成绩表
create table if not exists submissions (
    id int auto_increment primary key,
    assignment_id int not null comment '作业ID',
    student_id int not null comment '学生ID',
    content text comment '提交内容或文件路径',
    grade decimal(5, 2) comment '成绩',
    feedback text comment '教师评语',
    submitted_at timestamp default current_timestamp comment '提交时间',
    graded_at timestamp comment '评分时间',
    foreign key (assignment_id) references assignments(id) on delete cascade,
    foreign key (student_id) references users(id) on delete cascade
) engine=innodb default charset=utf8mb4;

-- 插入默认管理员账户 (密码: 123456)
-- 注意：实际生产环境中密码应存储哈希值，这里为了演示简单直接存明文或弱哈希，建议后续代码中使用 werkzeug.security
insert into users (username, password, role, name, email)
select 'admin', '123456', 'admin', '系统管理员', 'admin@example.com'
where not exists (select 1 from users where username = 'admin');


-- 创建评论表
CREATE TABLE IF NOT EXISTS comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    course_id INT NOT NULL COMMENT '所属课程ID',
    user_id INT NOT NULL COMMENT '评论者ID',
    content TEXT NOT NULL COMMENT '评论内容',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '评论时间',
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;