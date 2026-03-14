-- ======================================================
-- 数据库高级对象：视图、触发器、存储过程
-- 功能说明：为在线学习系统实现课程列表视图、选课人数自动更新、带容量检查的选课存储过程
-- 适用数据库：MySQL 5.7+ / 8.0+
-- ======================================================

-- 切换到目标数据库（确保后续操作在正确的数据库中执行）
USE online_learning_db;

-- ------------------------------------------------------------------------------
-- 1. 创建视图（v_course_list）：供首页调用，整合课程与教师姓名
-- 视图作用：封装课程表和用户表的关联查询，简化前端/应用层获取已发布课程列表的逻辑
-- 优势：无需重复编写JOIN语句，视图数据实时同步底层表，便于维护
-- ------------------------------------------------------------------------------
-- 先删除已存在的同名视图（避免创建时报错）
DROP VIEW IF EXISTS v_course_list;
-- 创建视图
CREATE VIEW v_course_list AS
-- 查询课程表所有字段 + 关联的教师姓名
SELECT
    c.*,          -- 课程表（courses）的所有字段
    u.name as teacher_name  -- 关联用户表（users）的教师真实姓名，并别名化
FROM courses c
-- 内连接用户表：通过课程表的teacher_id关联用户表的id，筛选出授课教师信息
JOIN users u ON c.teacher_id = u.id
-- 只显示状态为"已发布"的课程（过滤待审核/已拒绝的课程，符合首页展示逻辑）
WHERE c.status = 'published';

-- ------------------------------------------------------------------------------
-- 2. 创建触发器（trg_enroll_course）：选课自动增加课程已选人数
-- 触发器作用：当学生选课后，自动更新对应课程的enrolled_count字段，保证数据一致性
-- 触发时机：在enrollments表插入数据之后（AFTER INSERT）
-- 触发范围：每插入一行数据就执行一次（FOR EACH ROW）
-- ------------------------------------------------------------------------------
-- 修改语句结束符为$$（避免触发器内部的;被MySQL误认为语句结束）
DELIMITER $$
-- 先删除已存在的同名触发器
DROP TRIGGER IF EXISTS trg_enroll_course$$
-- 创建触发器，命名规则：trg_触发动作_关联表
CREATE TRIGGER trg_enroll_course
-- 触发时机：在enrollments表插入数据之后
AFTER INSERT ON enrollments
-- 行级触发器：每插入一条选课记录就执行一次
FOR EACH ROW
BEGIN
    -- 核心逻辑：更新课程表的已选人数
    -- NEW.course_id 代表刚插入到enrollments表中的课程ID（触发器的内置变量）
    UPDATE courses
    SET enrolled_count = enrolled_count + 1  -- 已选人数+1
    WHERE id = NEW.course_id;                -- 匹配对应的课程
END$$
-- 恢复MySQL默认的语句结束符为;
DELIMITER ;

-- ------------------------------------------------------------------------------
-- 3. 创建存储过程（proc_enroll）：带事务和容量检查的选课逻辑
-- 存储过程作用：封装完整的选课业务逻辑，包含：
--   1. 事务控制（保证操作原子性）
--   2. 课程容量检查（防止超员）
--   3. 行级锁（避免并发选课导致超员）
--   4. 异常处理（出错时回滚事务）
-- 参数说明：
--   IN p_student_id INT：输入参数，学生ID
--   IN p_course_id INT：输入参数，课程ID
-- ------------------------------------------------------------------------------
DELIMITER $$
-- 先删除已存在的同名存储过程
DROP PROCEDURE IF EXISTS proc_enroll$$
-- 创建存储过程，命名规则：proc_业务动作
CREATE PROCEDURE proc_enroll(
    IN p_student_id INT,  -- 输入参数：要选课的学生ID
    IN p_course_id INT    -- 输入参数：要选的课程ID
)
BEGIN
    -- 声明局部变量，用于存储课程容量和当前已选人数
    DECLARE v_capacity INT;    -- 课程最大容量
    DECLARE v_enrolled INT;    -- 课程当前已选人数

    -- 异常处理机制：当存储过程执行过程中发生任何SQL异常时
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;              -- 回滚当前事务（撤销所有未提交的操作）
        RESIGNAL;              -- 重新抛出异常，让调用方感知错误
    END;

    -- 开启事务：后续操作要么全部成功，要么全部失败
    START TRANSACTION;

    -- 查询课程的容量和当前已选人数，并加行级排他锁（FOR UPDATE）
    -- FOR UPDATE：锁定查询到的课程行，防止并发选课导致超员（直到事务提交/回滚才释放锁）
    SELECT max_capacity, enrolled_count
    INTO v_capacity, v_enrolled  -- 将查询结果赋值给局部变量
    FROM courses
    WHERE id = p_course_id
    FOR UPDATE;

    -- 容量检查：判断当前已选人数是否达到最大容量
    IF v_enrolled >= v_capacity THEN
        -- 抛出自定义异常：课程已满，终止执行
        -- SQLSTATE '45000'：自定义异常码（非标准错误码）
        -- MESSAGE_TEXT：异常提示信息
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '课程已满！';
    ELSE
        -- 容量充足：执行选课操作，插入选课记录
        INSERT INTO enrollments (student_id, course_id)
        VALUES (p_student_id, p_course_id);
    END IF;

    -- 提交事务：所有操作执行成功，持久化数据
    COMMIT;
END$$
-- 恢复默认语句结束符
DELIMITER ;