# 1. Base 이미지 선택 (파이썬 3.10)
FROM python:3.10-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. Collector 의존성 파일 복사 및 설치
COPY collector/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 4. Collector 소스 코드 복사
COPY collector/ ./collector/

# 5. 수집기 실행 명령
CMD ["python", "collector/main.py"]