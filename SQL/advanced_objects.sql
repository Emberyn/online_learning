USE online_learning_db;

-- ==========================================
-- 1. 创建视图：课程列表 (整合教师姓名)
-- 用于首页展示，避免复杂的联表查询
-- ==========================================
DROP VIEW IF EXISTS v_course_list;

CREATE VIEW v_course_list AS
SELECT
    c.*,
    u.name AS teacher_name
FROM courses c
JOIN users u ON c.teacher_id = u.id
WHERE c.status = 'published';

-- ==========================================
-- 2. 存储过程：安全选课 (带事务与容量校验)
-- ==========================================
DELIMITER $$

-- 先删除已存在的同名存储过程
DROP PROCEDURE IF EXISTS proc_enroll$$

CREATE PROCEDURE proc_enroll(
    IN p_student_id INT,  -- 选课学生ID
    IN p_course_id INT    -- 课程ID
)
BEGIN
    DECLARE v_capacity INT;
    DECLARE v_enrolled INT;
    DECLARE v_status VARCHAR(20);

    -- 异常处理机制：遇到错误自动回滚
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    -- 开启事务
    START TRANSACTION;

    -- 检查课程状态、容量和已选人数，并加行级排他锁(FOR UPDATE)，防止并发超卖
    SELECT max_capacity, enrolled_count, status
    INTO v_capacity, v_enrolled, v_status
    FROM courses
    WHERE id = p_course_id
    FOR UPDATE;

    -- 业务逻辑校验
    IF v_status != 'published' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '该课程未发布，无法选课';
    ELSEIF v_enrolled >= v_capacity THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '课程名额已满';
    ELSE
        -- 1. 插入选课记录
        INSERT INTO enrollments (student_id, course_id, progress)
        VALUES (p_student_id, p_course_id, 0.00);

        -- 2. 更新课程已选人数
        UPDATE courses
        SET enrolled_count = enrolled_count + 1
        WHERE id = p_course_id;

        -- 提交事务
        COMMIT;
    END IF;
END$$

DELIMITER ;