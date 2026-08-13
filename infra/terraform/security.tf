# ---------------------------------------------------------------------------
# Security Group
#
#   mcp-sg  : MCP Server + Collector EC2
#             인바운드는 80(Nginx)과 22(내 IP)만. 8000(MCP 내부 포트)은 열지 않는다.
#   rds-sg  : RDS
#             인바운드는 3306을 mcp-sg에서만. CIDR이 아니라 Source = mcp-sg.
# ---------------------------------------------------------------------------

resource "aws_security_group" "mcp" {
  name        = "mcp-sg"
  description = "MCP Server / Collector EC2. Only Nginx(80) and SSH(my ip) are exposed"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "mcp-sg" }
}

# Nginx 리버스 프록시. MCP 애플리케이션 포트(8000)는 여기에 없다.
resource "aws_vpc_security_group_ingress_rule" "mcp_http" {
  security_group_id = aws_security_group.mcp.id
  description       = "HTTP to Nginx reverse proxy"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "mcp_https" {
  security_group_id = aws_security_group.mcp.id
  description       = "HTTPS to Nginx reverse proxy (when TLS is enabled)"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

# SSH는 내 IP에서만. 0.0.0.0/0은 variables.tf의 validation이 막는다.
resource "aws_vpc_security_group_ingress_rule" "mcp_ssh" {
  security_group_id = aws_security_group.mcp.id
  description       = "SSH from my IP only"
  cidr_ipv4         = var.my_ip_cidr
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "mcp_all" {
  security_group_id = aws_security_group.mcp.id
  description       = "outbound all (docker pull, external API crawling)"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

# ------------------------------- RDS SG ------------------------------------

resource "aws_security_group" "rds" {
  name        = "rds-sg"
  description = "RDS MySQL. Allow 3306 from mcp-sg only"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "rds-sg" }
}

# 핵심: Source가 CIDR이 아니라 mcp-sg(Security Group)다.
# EC2가 교체되어 IP가 바뀌어도 규칙을 고칠 필요가 없고,
# mcp-sg에 속하지 않은 어떤 리소스도 DB에 접속할 수 없다.
resource "aws_vpc_security_group_ingress_rule" "rds_from_mcp" {
  security_group_id            = aws_security_group.rds.id
  description                  = "MySQL 3306 from mcp-sg only"
  referenced_security_group_id = aws_security_group.mcp.id
  from_port                    = 3306
  to_port                      = 3306
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "rds_all" {
  security_group_id = aws_security_group.rds.id
  description       = "outbound (default. no internet route from private subnet)"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
