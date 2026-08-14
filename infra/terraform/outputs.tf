output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "Public Subnet (MCP Server EC2)"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "Private Subnet (RDS)"
  value       = aws_subnet.private[*].id
}

output "mcp_security_group_id" {
  description = "mcp-sg. RDS 인바운드의 Source로 참조된다"
  value       = aws_security_group.mcp.id
}

output "rds_security_group_id" {
  description = "rds-sg"
  value       = aws_security_group.rds.id
}

output "ec2_public_ip" {
  description = "MCP Server 공인 IP. Vercel의 MCP_SERVER_URL은 http://<이 IP> 가 된다"
  value       = aws_eip.mcp.public_ip
}

output "ec2_ssh_command" {
  description = "SSH 접속 명령"
  value       = "ssh -i ~/.ssh/${var.ec2_key_name}.pem ubuntu@${aws_eip.mcp.public_ip}"
}

output "rds_endpoint" {
  description = "RDS 엔드포인트. VPC 내부(EC2)에서만 resolve/접속 가능하다"
  value       = aws_db_instance.main.address
}

output "rds_publicly_accessible" {
  description = "false 여야 한다 (과제 채점 항목)"
  value       = aws_db_instance.main.publicly_accessible
}

output "collector_database_url" {
  description = "collector_user용 DATABASE_URL 형태 (비밀번호는 직접 채울 것)"
  value       = "mysql+pymysql://collector_user:<PASSWORD>@${aws_db_instance.main.address}:3306/${var.db_name}"
}

output "mcp_database_url" {
  description = "mcp_user(read-only)용 DATABASE_URL 형태 (비밀번호는 직접 채울 것)"
  value       = "mysql+pymysql://mcp_user:<PASSWORD>@${aws_db_instance.main.address}:3306/${var.db_name}"
}
