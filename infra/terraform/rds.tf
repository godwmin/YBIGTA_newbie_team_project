# ---------------------------------------------------------------------------
# RDS (MySQL)
#   - Private Subnet에만 배치 (db_subnet_group)
#   - publicly_accessible = false  <- 과제 필수 조건
#   - Security Group은 rds-sg 하나. 인바운드는 mcp-sg 3306뿐.
# ---------------------------------------------------------------------------

resource "aws_db_instance" "main" {
  identifier = "${var.project_name}-rds"

  engine         = "mysql"
  engine_version = var.db_engine_version
  instance_class = var.db_instance_class

  # 스토리지 오토스케일링은 쓰지 않는다 (예기치 않은 과금 방지)
  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_master_username
  password = var.db_master_password
  port     = 3306

  # --- 네트워크 격리 (과제 채점 항목) ---
  db_subnet_group_name   = aws_db_subnet_group.rds.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  multi_az               = false

  # --- 과제 종료 후 정리를 쉽게 하기 위한 설정 ---
  backup_retention_period = 0
  skip_final_snapshot     = true
  deletion_protection     = false
  apply_immediately       = true

  # 느린 쿼리 확인용 (MCP query timeout 튜닝 근거로 쓸 수 있음)
  enabled_cloudwatch_logs_exports = ["error", "slowquery"]

  tags = { Name = "${var.project_name}-rds" }
}
