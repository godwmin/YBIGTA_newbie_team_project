variable "project_name" {
  description = "리소스 이름 접두사"
  type        = string
  default     = "ybigta-agent"
}

variable "region" {
  description = "AWS 리전"
  type        = string
  default     = "ap-northeast-2"
}

variable "azs" {
  description = "사용할 가용영역 2개 (RDS Subnet Group은 최소 2개 AZ를 요구함)"
  type        = list(string)
  default     = ["ap-northeast-2a", "ap-northeast-2c"]
}

variable "vpc_cidr" {
  description = "VPC CIDR"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "Public Subnet CIDR (MCP Server / Collector EC2가 위치)"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "Private Subnet CIDR (RDS만 위치. IGW 라우트 없음)"
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24"]
}

variable "my_ip_cidr" {
  description = "SSH(22)를 허용할 내 공인 IP. 예: 1.2.3.4/32 — 절대 0.0.0.0/0 금지"
  type        = string

  validation {
    condition     = var.my_ip_cidr != "0.0.0.0/0"
    error_message = "SSH를 0.0.0.0/0으로 열 수 없습니다. 본인 IP/32를 지정하세요."
  }
}

variable "ec2_key_name" {
  description = "EC2에 붙일 기존 EC2 Key Pair 이름"
  type        = string
}

variable "ec2_instance_type" {
  description = "MCP Server + Collector용 인스턴스 타입"
  type        = string
  default     = "t3.micro"
}

variable "db_engine_version" {
  description = "RDS MySQL 엔진 버전"
  type        = string
  default     = "8.0"
}

variable "db_instance_class" {
  description = "RDS 인스턴스 클래스"
  type        = string
  default     = "db.t3.micro"
}

variable "db_name" {
  description = "초기 생성할 데이터베이스 이름"
  type        = string
  default     = "crypto_db"
}

variable "db_master_username" {
  description = "RDS 마스터 계정 (애플리케이션이 직접 쓰지 않음. 계정 분리용 관리자)"
  type        = string
  default     = "admin"
}

variable "db_master_password" {
  description = "RDS 마스터 비밀번호. terraform.tfvars 또는 TF_VAR_db_master_password 환경변수로 주입"
  type        = string
  sensitive   = true
}
