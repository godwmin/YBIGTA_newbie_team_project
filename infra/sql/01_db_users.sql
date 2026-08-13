-- ===========================================================================
-- DB 계정 분리 (RDS MySQL 8.0)
--
-- 실행 위치: EC2에서 RDS 마스터 계정으로 접속하여 실행한다.
--   mysql -h <rds-endpoint> -u admin -p crypto_db < 01_db_users.sql
--
-- RDS는 Private Subnet + Public Access OFF 이므로 이 SQL은 VPC 안(EC2)에서만
-- 실행할 수 있다. 로컬 노트북에서는 접속 자체가 되지 않는 것이 정상이다.
--
-- 계정 설계
--   admin          : 마스터. 스키마 변경과 계정 관리에만 사용. 앱은 절대 안 씀.
--   collector_user : 수집 프로그램용. SELECT / INSERT / UPDATE 만.
--   mcp_user       : MCP Server용. SELECT 만. (과제 보안 평가 항목)
--
-- 호스트 지정에 대하여
--   아래는 '%' 를 사용한다. 접속 출발지 제한은 MySQL의 host 컬럼이 아니라
--   Security Group(rds-sg 인바운드 3306 <- mcp-sg)이 담당하기 때문이다.
--   SG 방식은 EC2가 교체되어 사설 IP가 바뀌어도 규칙을 고칠 필요가 없다.
--   더 조이고 싶다면 파일 하단의 "VPC CIDR로 호스트 제한" 블록을 참고할 것.
-- ===========================================================================

-- 실행 전 확인: 대상 DB가 맞는지
SELECT DATABASE() AS current_db, VERSION() AS mysql_version;

-- ---------------------------------------------------------------------------
-- 1. 수집 계정 : 쓰기 가능, 단 DDL은 불가
-- ---------------------------------------------------------------------------
CREATE USER IF NOT EXISTS 'collector_user'@'%'
  IDENTIFIED BY '__COLLECTOR_DB_PASSWORD__';

GRANT SELECT, INSERT, UPDATE
  ON crypto_db.*
  TO 'collector_user'@'%';

-- DELETE / DROP / ALTER / CREATE 는 주지 않는다.
-- 수집 프로그램의 버그나 사고로 테이블이 날아가는 경로를 원천 차단한다.

-- ---------------------------------------------------------------------------
-- 2. MCP 계정 : 읽기 전용
-- ---------------------------------------------------------------------------
CREATE USER IF NOT EXISTS 'mcp_user'@'%'
  IDENTIFIED BY '__MCP_DB_PASSWORD__';

GRANT SELECT
  ON crypto_db.*
  TO 'mcp_user'@'%';

-- MCP Tool이 아무리 잘못 만들어져도, 혹은 LLM이 이상한 요청을 보내도
-- DB 권한 자체가 없으므로 INSERT/UPDATE/DELETE/DROP이 실행될 수 없다.
-- 애플리케이션 레벨 검증(입력 validation, Raw SQL Tool 금지)에 더해
-- DB 레벨에서 한 번 더 막는 이중 방어다.

-- ---------------------------------------------------------------------------
-- 3. 폭주 방지 : 계정별 리소스 상한
--    MCP는 Agent가 호출하므로 요청량이 예측하기 어렵다.
-- ---------------------------------------------------------------------------
ALTER USER 'mcp_user'@'%'
  WITH MAX_USER_CONNECTIONS 20
       MAX_QUERIES_PER_HOUR 20000;

ALTER USER 'collector_user'@'%'
  WITH MAX_USER_CONNECTIONS 5;

FLUSH PRIVILEGES;

-- ---------------------------------------------------------------------------
-- 4. 결과 확인 (이 출력을 캡처하면 계정 분리 증빙이 된다)
-- ---------------------------------------------------------------------------
SELECT user, host FROM mysql.user WHERE user IN ('admin', 'collector_user', 'mcp_user');

SHOW GRANTS FOR 'collector_user'@'%';
SHOW GRANTS FOR 'mcp_user'@'%';


-- ===========================================================================
-- (선택) VPC CIDR로 호스트까지 제한하고 싶을 때
--   VPC가 10.0.0.0/16 이라는 전제. 다른 CIDR을 쓰면 값을 바꿀 것.
--   '%' 계정을 먼저 지우고 아래를 실행한다.
-- ===========================================================================
-- DROP USER IF EXISTS 'collector_user'@'%';
-- DROP USER IF EXISTS 'mcp_user'@'%';
--
-- CREATE USER 'collector_user'@'10.0.%' IDENTIFIED BY '__COLLECTOR_DB_PASSWORD__';
-- GRANT SELECT, INSERT, UPDATE ON crypto_db.* TO 'collector_user'@'10.0.%';
--
-- CREATE USER 'mcp_user'@'10.0.%' IDENTIFIED BY '__MCP_DB_PASSWORD__';
-- GRANT SELECT ON crypto_db.* TO 'mcp_user'@'10.0.%';
--
-- FLUSH PRIVILEGES;
