# Exchange Rate Collector

환율 정보를 수집하고 시각화하여 Slack으로 알림을 보내는 자동화 시스템입니다.

## 프로젝트 구조

```
exchange_collector/
├── configs/                # 설정 관련 모듈
│   ├── apis_setting.py    # API 설정
│   ├── mysql_setting.py   # MySQL 데이터베이스 설정
│   └── slack_setting.py   # Slack 봇 설정
├── docker/                 # Docker 관련 파일
│   └── setup_db.py        # 데이터베이스 초기 설정
├── graph_files/           # 생성된 그래프 파일 저장
├── modules/               # 핵심 기능 모듈
│   ├── cleanup.py        # 파일 정리 모듈
│   ├── mysql_connector.py # 데이터베이스 연결 모듈
│   ├── scheduler.py      # 작업 스케줄러
│   └── slack_sender.py   # Slack 메시지 전송 모듈
├── utils/                 # 유틸리티 모듈
│   ├── exchange_rate_collector.py  # 환율 데이터 수집
│   ├── exchange_rate_notifier.py   # 환율 알림 처리
│   ├── exchange_rate_visualizer.py # 환율 데이터 시각화
│   └── holiday_checker.py          # 공휴일 체크
└── main.py               # 애플리케이션 진입점
```

## 주요 기능

1. **환율 데이터 수집**
   - 한국수출입은행 API를 통한 환율 정보 수집
   - 수집된 데이터 MySQL 데이터베이스 저장

2. **데이터 시각화**
   - 수집된 환율 데이터를 그래프로 시각화
   - 3개월간의 환율 트렌드 표시

3. **Slack 알림**
   - 일일 환율 정보 Slack 채널로 전송
   - 환율 트렌드 그래프 자동 첨부

4. **자동화**
   - 정해진 스케줄에 따라 자동 실행
   - 공휴일 체크 및 처리

## 설치 및 설정

1. 환경 설정
   ```bash
   # .env 파일 생성
   SLACK_BOT_TOKEN=xoxb-your-bot-token
   SLACK_CHANNEL_ID=your-channel-id
   DB_HOST=localhost
   DB_USER=your-db-user
   DB_PASSWORD=your-db-password
   DB_NAME=your-db-name
   EXCHANGE_RATE_API_KEY=한국수출입은행 api
   HOLIDAY_API_KEY=공공천문데이터 api
   ```

2. 의존성 설치
   ```bash
   pip install -r requirements.txt
   ```

3. 데이터베이스 설정
   ```bash
   python docker/mysql/init.sql
   ```

## 실행 방법

1. 직접 실행
   ```bash
   python main.py
   ```

2. 스케줄러 실행
   ```bash
   python -m modules.scheduler
   ```

## 개발 요구사항

- Python 3.8+
- MySQL 5.7+
- 필요한 Python 패키지:
  - requests
  - pandas
  - matplotlib
  - python-dotenv
  - mysql-connector-python
  - slack_sdk

## 설정 파일

1. **APIs 설정** (configs/apis_setting.py)
   - 한국수출입은행 API 설정
   - API 키 및 엔드포인트 관리

2. **MySQL 설정** (configs/mysql_setting.py)
   - 데이터베이스 연결 설정
   - 테이블 스키마 관리

3. **Slack 설정** (configs/slack_setting.py)
   - Slack 봇 토큰 관리
   - 채널 ID 설정

## 주의사항

1. 환율 데이터는 평일에만 수집됩니다 (공휴일 제외)
2. 그래프 파일은 3일 후 자동으로 삭제됩니다
3. 환경 변수 설정이 올바르게 되어 있는지 확인하세요
4. Slack 봇이 해당 채널에 초대되어 있어야 합니다

## 라이선스

MIT License