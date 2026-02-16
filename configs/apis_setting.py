# configs/apis_setting.py

import os
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트 디렉토리 찾기
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = os.path.join(BASE_DIR, '.env')

# .env 파일 로드
load_dotenv(dotenv_path=env_path)

# API 설정
HOLIDAY_API_CONFIG = {
    'api_key': os.getenv('HOLIDAY_API_KEY'),
    'base_url': 'http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo'
}

EXCHANGE_RATE_API_CONFIG = {
    'api_key': os.getenv('EXCHANGE_RATE_API_KEY'),
    'base_url': 'https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON'
}

# 필수 환경변수 확인
required_vars = ['HOLIDAY_API_KEY', 'EXCHANGE_RATE_API_KEY']
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# 디버깅을 위한 출력
print(f"Loading .env from: {env_path}")
print(f"Environment variables loaded: {list(os.environ.keys())}")