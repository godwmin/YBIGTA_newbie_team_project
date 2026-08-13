-- RDS 관리자 계정으로 실행하세요.
-- 아래 CHANGE_ME 값은 실행 직전에만 안전한 비밀번호로 교체하고,
-- 실제 비밀번호가 들어간 SQL은 Git에 커밋하지 마세요.

CREATE USER IF NOT EXISTS 'collector_user'@'%'
    IDENTIFIED BY 'CHANGE_ME_COLLECTOR_PASSWORD';
CREATE USER IF NOT EXISTS 'mcp_user'@'%'
    IDENTIFIED BY 'CHANGE_ME_MCP_PASSWORD';

REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'collector_user'@'%';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'mcp_user'@'%';

-- Collector는 수집 데이터 추가만 가능합니다.
GRANT INSERT ON crypto_db.coin_prices TO 'collector_user'@'%';

-- MCP Server는 조회만 가능하고 INSERT/UPDATE/DELETE는 할 수 없습니다.
GRANT SELECT ON crypto_db.coin_prices TO 'mcp_user'@'%';

FLUSH PRIVILEGES;

-- 권한 확인
SHOW GRANTS FOR 'collector_user'@'%';
SHOW GRANTS FOR 'mcp_user'@'%';
