-- ===========================================================================
-- mcp_user가 정말로 read-only인지 증명하는 검증 스크립트
--
-- 실행 (반드시 mcp_user로 접속할 것. admin으로 실행하면 의미가 없다):
--   mysql -h <rds-endpoint> -u mcp_user -p crypto_db < 02_verify_readonly.sql
--
-- 기대 결과
--   1) SELECT      -> 성공
--   2) INSERT      -> ERROR 1142 (42000): INSERT command denied to user 'mcp_user'...
--   3) UPDATE      -> ERROR 1142
--   4) DELETE      -> ERROR 1142
--   5) DROP TABLE  -> ERROR 1142
--
-- 이 에러 화면이 곧 "DB Read-only 권한 적용" 채점 항목의 증빙이다.
-- 캡처해서 aws/security_group.png 옆에 함께 두면 좋다.
--
-- 주의: mysql 클라이언트는 에러가 나면 기본적으로 즉시 중단한다.
--       모든 케이스를 한 화면에서 보려면 --force 옵션을 붙일 것.
--         mysql --force -h <endpoint> -u mcp_user -p crypto_db < 02_verify_readonly.sql
-- ===========================================================================

SELECT CURRENT_USER() AS connected_as;
SHOW GRANTS FOR CURRENT_USER();

-- 1) 읽기: 성공해야 한다
SELECT '--- 1. SELECT (성공 기대) ---' AS step;
SHOW TABLES;

-- 2) 쓰기: 전부 ERROR 1142로 거부되어야 한다.
--    테이블 이름은 실제 스키마(팀원1 담당)에 맞게 바꿔서 실행할 것.
SELECT '--- 2. INSERT (거부 기대) ---' AS step;
INSERT INTO market_prices (symbol, price) VALUES ('HACK', 0);

SELECT '--- 3. UPDATE (거부 기대) ---' AS step;
UPDATE market_prices SET price = 0;

SELECT '--- 4. DELETE (거부 기대) ---' AS step;
DELETE FROM market_prices;

SELECT '--- 5. DROP (거부 기대) ---' AS step;
DROP TABLE market_prices;
