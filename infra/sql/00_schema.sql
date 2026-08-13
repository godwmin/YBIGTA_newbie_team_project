-- ---------------------------------------------------------------------------
-- coin_prices 테이블 생성
--
-- 실행:
--   mysql -h <rds-endpoint> -u admin -p crypto_db < 00_schema.sql
--
-- 실행 순서: 00_schema.sql -> 01_db_users.sql -> 02_verify_readonly.sql
--   (계정에 권한을 주기 전에 테이블이 있어야 GRANT 확인이 깔끔하다)
--
-- 컬럼 정의는 2026-08-13 팀 합의안(팀원2 제안)을 그대로 따른다.
-- ---------------------------------------------------------------------------

CREATE DATABASE IF NOT EXISTS crypto_db
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE crypto_db;

CREATE TABLE IF NOT EXISTS coin_prices (
  id           INT            NOT NULL AUTO_INCREMENT,

  -- 예: 'KRW-BTC'
  symbol       VARCHAR(20)    NOT NULL,

  -- 현재가. BTC는 억 단위까지 가므로 DECIMAL(18,4).
  -- FLOAT를 쓰면 반올림 오차가 생겨 시세 데이터에는 부적절하다.
  price        DECIMAL(18, 4) NOT NULL,

  -- 전일대비 변동률. 업비트 signed_change_rate (0.0123 = +1.23%)
  change_rate  FLOAT          NULL,

  -- 수집 시각: Collector가 업비트 API를 호출한 시점
  collected_at DATETIME       NOT NULL,

  -- 저장 시각: DB에 INSERT된 시점
  created_at   DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (id),

  -- get_price_history(symbol, hours) 와 get_latest_price(symbol) 을
  -- 풀스캔 없이 처리하기 위한 복합 인덱스.
  -- 30분마다 5종목씩 쌓이므로 데이터가 계속 늘어난다.
  KEY idx_symbol_collected (symbol, collected_at),

  -- get_top_gainers(limit) 용
  KEY idx_collected (collected_at)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

-- 확인
SHOW CREATE TABLE coin_prices\G
SELECT COUNT(*) AS row_count FROM coin_prices;
