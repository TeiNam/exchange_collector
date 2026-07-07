# docker/mysql/init.sql
CREATE DATABASE IF NOT EXISTS ${DB_NAME};
USE ${DB_NAME};

CREATE TABLE IF NOT EXISTS exchange_rates (
    id INT UNSIGNED AUTO_INCREMENT COMMENT '고유 식별자',
    cur_unit VARCHAR(10) NOT NULL COMMENT '통화 단위 (예: USD, JPY, KRW)',
    ttb DECIMAL(10,2) NOT NULL COMMENT '전신환 매입률 (송금 받을 때 적용되는 환율)',
    tts DECIMAL(10,2) NOT NULL COMMENT '전신환 매도률 (송금할 때 적용되는 환율)',
    deal_bas_r DECIMAL(10,2) NOT NULL COMMENT '매매기준율 (일반적인 환율)',
    bkpr DECIMAL(10,2) NOT NULL COMMENT '장부가격 (고시환율)',
    cur_nm VARCHAR(50) NOT NULL COMMENT '통화명 (예: 미국 달러, 일본 엔)',
    search_date DATE NOT NULL COMMENT '환률 기록 날짜',
    create_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '데이터 생성 시간',
    PRIMARY KEY (id, create_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
COMMENT='한국수출입은행 환율 정보 저장 테이블'
PARTITION BY RANGE COLUMNS(create_at) (
    PARTITION p202412 VALUES LESS THAN ('2025-01-01 00:00:00'),
    PARTITION p202501 VALUES LESS THAN ('2025-02-01 00:00:00'),
    PARTITION p202502 VALUES LESS THAN ('2025-03-01 00:00:00'),
    PARTITION p202503 VALUES LESS THAN ('2025-04-01 00:00:00'),
    PARTITION p202504 VALUES LESS THAN ('2025-05-01 00:00:00'),
    PARTITION p202505 VALUES LESS THAN ('2025-06-01 00:00:00'),
    PARTITION p202506 VALUES LESS THAN ('2025-07-01 00:00:00'),
    PARTITION p202507 VALUES LESS THAN ('2025-08-01 00:00:00'),
    PARTITION p202508 VALUES LESS THAN ('2025-09-01 00:00:00'),
    PARTITION p202509 VALUES LESS THAN ('2025-10-01 00:00:00'),
    PARTITION p202510 VALUES LESS THAN ('2025-11-01 00:00:00'),
    PARTITION p202511 VALUES LESS THAN ('2025-12-01 00:00:00'),
    PARTITION p202512 VALUES LESS THAN ('2026-01-01 00:00:00'),
    PARTITION p_max VALUES LESS THAN MAXVALUE
);

-- 매수 신호 분석 조회(WHERE cur_unit, search_date + 날짜별 최신행)용 복합 인덱스
-- 기존 DB에는 다음을 수동 적용:
--   CREATE INDEX idx_rates_cur_date ON exchange_rates (cur_unit, search_date, create_at);
CREATE INDEX idx_rates_cur_date ON exchange_rates (cur_unit, search_date, create_at);

-- KRX 금시장 일별매매정보 (금 99.99 현물, 원/g)
-- 하루 2종목(금 1kg / 미니금 100g)만 저장하므로 파티션 없이 단순 구성
-- 기존 DB에는 아래 CREATE TABLE 문을 그대로 수동 적용
CREATE TABLE IF NOT EXISTS gold_prices (
    id INT UNSIGNED AUTO_INCREMENT COMMENT '고유 식별자',
    isu_cd VARCHAR(12) NOT NULL COMMENT '종목코드 (예: 04020000 금 1kg)',
    isu_nm VARCHAR(50) NOT NULL COMMENT '종목명 (예: 금 99.99_1kg)',
    clsprc DECIMAL(12,2) NOT NULL COMMENT '종가 (원/g)',
    cmpprevdd_prc DECIMAL(12,2) NOT NULL COMMENT '전일 대비',
    fluc_rt DECIMAL(6,2) NOT NULL COMMENT '등락률 (%)',
    opnprc DECIMAL(12,2) NOT NULL COMMENT '시가',
    hgprc DECIMAL(12,2) NOT NULL COMMENT '고가',
    lwprc DECIMAL(12,2) NOT NULL COMMENT '저가',
    trdvol BIGINT UNSIGNED NOT NULL COMMENT '거래량 (g)',
    trdval BIGINT UNSIGNED NOT NULL COMMENT '거래대금 (원)',
    search_date DATE NOT NULL COMMENT '기준일자 (basDd)',
    create_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '데이터 생성 시간',
    PRIMARY KEY (id),
    UNIQUE KEY uq_gold_isu_date (isu_cd, search_date),
    KEY idx_gold_isu_date (isu_cd, search_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
COMMENT='KRX 금시장 일별매매정보 저장 테이블';