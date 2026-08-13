-- Local Docker Compose 전용 계정입니다. 운영 RDS에서는 grants.sql의 placeholder를 바꿔 실행하세요.
CREATE USER IF NOT EXISTS 'collector_user'@'%' IDENTIFIED BY 'local-collector-password';
CREATE USER IF NOT EXISTS 'mcp_user'@'%' IDENTIFIED BY 'local-mcp-password';

GRANT INSERT ON crypto_db.coin_prices TO 'collector_user'@'%';
GRANT SELECT ON crypto_db.coin_prices TO 'mcp_user'@'%';
FLUSH PRIVILEGES;
