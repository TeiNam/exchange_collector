CREATE TABLE IF NOT EXISTS slack_comments (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    parent_message_id VARCHAR(100) NOT NULL COMMENT '원본 메시지 ID',
    comment_message_id VARCHAR(100) NOT NULL COMMENT '댓글 메시지 ID',
    user_id VARCHAR(50) NOT NULL COMMENT '댓글 작성자 ID',
    user_name VARCHAR(100) COMMENT '댓글 작성자 이름',
    content TEXT NOT NULL COMMENT '댓글 내용',
    comment_timestamp DATETIME NOT NULL COMMENT '댓글 작성 시간',
    is_edited BOOLEAN DEFAULT FALSE COMMENT '댓글 수정 여부',
    edit_count INT DEFAULT 0 COMMENT '수정 횟수',
    previous_content TEXT NULL COMMENT '이전 댓글 내용',
    message_type VARCHAR(50) DEFAULT 'unknown' COMMENT '원본 메시지 유형 (exchange_rate, work_journal)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '데이터베이스 저장 시간',
    updated_at TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '마지막 업데이트 시간',    
    INDEX slack_comments_parent_message_IDX (parent_message_id),
    INDEX slack_comments_comment_message_IDX (comment_message_id),
    INDEX slack_comments_user_IDX (user_id),
    INDEX slack_comments_timestamp_IDX (comment_timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;