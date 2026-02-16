# configs/apis_setting.py

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# .env 파일이 있으면 로드 (로컬 개발용), 없으면 환경변수에서 직접 읽음 (도커)
env_path = Path(__file__).resolve().parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    logger.debug(f".env 파일 로드: {env_path}")

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
