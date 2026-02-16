# docker/Dockerfile
# === 빌드 스테이지: C 확장 패키지 컴파일 ===
FROM python:3.12.8-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# === 런타임 스테이지: 최소 이미지 ===
FROM python:3.12.8-slim

WORKDIR /app

# 런타임에 필요한 라이브러리만 설치 (빌드 도구 제외)
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    tzdata \
    fonts-nanum \
    && rm -rf /var/lib/apt/lists/*

# 타임존 설정
ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 빌드 스테이지에서 설치된 패키지 복사
COPY --from=builder /install /usr/local

# 애플리케이션 코드 복사
COPY . .

# 그래프 저장 디렉토리 생성 및 matplotlib 폰트 캐시 재생성
RUN mkdir -p graph_files \
    && python -c "import matplotlib.font_manager; matplotlib.font_manager._load_fontmanager(try_read_cache=False)"

CMD ["python", "main.py"]
