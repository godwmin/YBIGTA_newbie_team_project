# ---------------------------------------------------------------------------
# EC2 : MCP Server(Docker) + Collector(cron)
#   - Public Subnet 배치 (과제 명세)
#   - 인바운드는 mcp-sg가 통제. 8000번은 인터넷에 열리지 않는다.
#   - user_data로 docker / nginx / cron 까지 부팅 시 자동 설치
# ---------------------------------------------------------------------------

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  # 24.04는 hvm-ssd / hvm-ssd-gp3 두 경로가 섞여 있어 와일드카드로 둘 다 잡는다
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd*/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "mcp" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.ec2_instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.mcp.id]
  key_name               = var.ec2_key_name

  associate_public_ip_address = true

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  # IMDSv2 강제 (SSRF로 인스턴스 자격증명이 유출되는 것을 막는다)
  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  user_data                   = file("${path.module}/../ec2/bootstrap.sh")
  user_data_replace_on_change = false

  tags = { Name = "${var.project_name}-mcp-ec2" }
}

# 재부팅해도 주소가 바뀌지 않도록 고정 IP.
# 과제 종료 후 반드시 release 할 것 (미사용 EIP는 과금된다).
resource "aws_eip" "mcp" {
  instance = aws_instance.mcp.id
  domain   = "vpc"

  tags = { Name = "${var.project_name}-mcp-eip" }
}
