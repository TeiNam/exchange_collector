# Exchange Rate Collector

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram_Bot-22.6-26A5E4?logo=telegram&logoColor=white)
![Matplotlib](https://img.shields.io/badge/Matplotlib-3.10-11557C)
![Pandas](https://img.shields.io/badge/Pandas-2.2-150458?logo=pandas&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg)

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/teinam)

환율 정보를 수집하고, 기술적 지표를 분석하여 매수 신호와 함께 텔레그램으로 알림을 보내는 자동화 시스템입니다.

## 주요 기능

### 📊 환율 데이터 수집 및 알림
- 한국수출입은행 API를 통한 USD/JPY 환율 수집
- MySQL 데이터베이스 저장
- 매일 오후 2:00(KST) 텔레그램 자동 알림 (평일, 공휴일 제외)
- 유니코드 스파크라인으로 7일간 추세 표시

### 📈 기술적 지표 분석 및 매수 신호
- 이동평균선 (MA5, MA20) 및 골든크로스/데드크로스 감지
- RSI (14일) 과매도/과매수 판별
- 볼린저 밴드 (20일, 2σ) 상단/하단 터치 감지
- N주 최저가 분석
- 매수 타이밍 감지 시 즉시 텔레그램 알림

### 📉 데이터 시각화
- 3개월간 환율 트렌드 그래프
- 통화별 그룹 레이아웃 (USD 환율+RSI, JPY 환율+RSI)
- MA, 볼린저 밴드, RSI 지표 포함

### 🤖 텔레그램 봇 명령어
| 명령어 | 설명 |
|--------|------|
| `/start` | 시작 메시지 |
| `/rate` | 금일 환율 조회 |
| `/help` | 명령어 안내 |

## 프로젝트 구조

```
exchange_collector/
├── configs/                  # 설정 모듈
│   ├── apis_setting.py       # 외부 API 설정
│   ├── mysql_setting.py      # MySQL 설정
│   └── telegram_setting.py   # 텔레그램 봇 설정
├── modules/                  # 핵심 모듈
│   ├── cleanup.py            # 파일 정리
│   ├── mysql_connector.py    # DB 연결
│   ├── scheduler.py          # 작업 스케줄러
│   ├── telegram_bot.py       # 텔레그램 봇 명령어 핸들러
│   └── telegram_sender.py    # 텔레그램 메시지 전송
├── utils/                    # 유틸리티
│   ├── buy_signal_analyzer.py       # 매수 신호 분석기
│   ├── exchange_rate_collector.py   # 환율 데이터 수집
│   ├── exchange_rate_notifier.py    # 환율 알림 처리
│   ├── exchange_rate_visualizer.py  # 환율 시각화 (그래프)
│   ├── holiday_checker.py           # 공휴일 체크
│   ├── html_message_formatter.py    # HTML 메시지 포맷
│   ├── indicator_calculator.py      # 기술적 지표 계산
│   ├── signal_message_formatter.py  # 매수 신호 메시지 포맷
│   └── sparkline_generator.py       # 스파크라인 생성
├── tests/                    # 테스트 (단위 + 속성 기반)
├── docker/                   # Docker 설정
│   ├── Dockerfile            # 멀티스테이지 빌드
│   ├── docker-compose.yml
│   └── mysql/init.sql
├── .github/workflows/        # CI/CD
│   └── docker-build.yml      # GitHub Actions 도커 빌드
└── main.py                   # 진입점
```

## 설치 및 실행

### 환경변수 설정 (.env)
```bash
# MySQL
MYSQL_HOST=localhost
MYSQL_USER=your-user
MYSQL_PASSWORD=your-password
MYSQL_DATABASE=your-database
MYSQL_PORT=3306

# 텔레그램
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
TELEGRAM_SEND_GRAPH=true

# API 키
EXCHANGE_RATE_API_KEY=한국수출입은행-api-key
HOLIDAY_API_KEY=공공데이터포털-api-key
```

### 로컬 실행
```bash
pip install -r requirements.txt
python main.py
```

### Docker 실행
```bash
cd docker
docker-compose up -d
```

### GitHub Actions
`main` 브랜치 푸시 시 `ghcr.io`에 도커 이미지 자동 빌드/푸시됩니다.

## 기술 스택

- Python 3.12
- MySQL 8.0
- python-telegram-bot
- pandas, matplotlib
- schedule
- Docker (멀티스테이지 빌드)

## 라이선스

MIT License
