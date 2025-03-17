# 업무 자동화 및 알림 시스템

환율 정보를 수집하고 시각화하여 Slack으로 알림을 보내고, 평일 아침에 업무일지 작성 알림을 제공하며, 업무일지 댓글을 수집하고 저장하는 자동화 시스템입니다.

## 프로젝트 구조

```
exchange_collector/
├── configs/                # 설정 관련 모듈
│   ├── apis_setting.py    # API 설정
│   ├── mysql_setting.py   # MySQL 데이터베이스 설정
│   └── slack_setting.py   # Slack 봇 설정
├── docker/                 # Docker 관련 파일
│   ├── mysql/             # MySQL 관련 파일
│   │   ├── init.sql       # 데이터베이스 초기 설정
│   │   └── slack_comments.sql # 댓글 테이블 설정
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
│   ├── holiday_checker.py          # 공휴일 체크
│   ├── slack_comment_collector.py  # Slack 댓글 수집 모듈
│   └── work_journal_notifier.py    # 업무일지 작성 알림
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
   - 일일 환율 정보 Slack 채널로 전송 (11:05 KST)
   - 환율 트렌드 그래프 자동 첨부
   - 평일 아침 업무일지 작성 알림 전송 (09:00 KST)

4. **댓글 수집 및 저장**
   - 업무일지 메시지에 달린 댓글 수집 및 저장
   - 댓글 내용, 작성자, 시간 등 데이터베이스에 기록

5. **자동화**
   - 정해진 스케줄에 따라 자동 실행
   - 공휴일 및 주말 체크 및 처리 (평일에만 알림 전송)

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

3. 데이터베이스 테이블 설정
   ```bash
   # 환율 테이블 설정
   python docker/mysql/init.sql
   
   # 댓글 테이블 설정
   python docker/mysql/slack_comments.sql
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
  - schedule
  - pytz

## 설정 파일

1. **APIs 설정** (configs/apis_setting.py)
   - 한국수출입은행 API 설정
   - 공휴일 API 설정
   - API 키 및 엔드포인트 관리

2. **MySQL 설정** (configs/mysql_setting.py)
   - 데이터베이스 연결 설정
   - 테이블 스키마 관리

3. **Slack 설정** (configs/slack_setting.py)
   - Slack 봇 토큰 관리
   - 채널 ID 설정

## 주의사항

1. 환율 알림과 업무일지 알림은 평일에만 전송됩니다 (공휴일 및 주말 제외)
2. 업무일지 메시지에 달린 댓글만 수집 및 저장됩니다 (환율 메시지의 댓글은 수집하지 않음)
3. 그래프 파일은 3일 후 자동으로 삭제됩니다
4. 환경 변수 설정이 올바르게 되어 있는지 확인하세요
5. Slack 봇이 해당 채널에 초대되어 있어야 합니다
6. 봇이 스레드 메시지(댓글)를 읽을 수 있는 권한이 필요합니다

## 라이선스

MIT License