"""
매수 신호 분석 통합 단위 테스트

exchange_rate_notifier.py의 main() 함수에서 매수 신호 분석이
올바르게 통합되었는지 검증한다.

- main() 실행 시 매수 신호 분석이 호출되는지 확인
- 분석 오류 시 기존 알림 정상 동작 확인
- 신호 미감지 시 매수 신호 메시지 미전송 확인

Requirements: 5.3, 5.4, 5.5, 6.1, 6.2
"""

import os
import pytest
from unittest.mock import patch, MagicMock, call

# apis_setting 모듈이 import 시점에 환경변수를 검증하므로, 테스트 전에 설정
os.environ.setdefault("HOLIDAY_API_KEY", "test_key")
os.environ.setdefault("EXCHANGE_RATE_API_KEY", "test_key")

# main() 내부에서 사용하는 모든 의존성의 패치 경로
NOTIFIER_MODULE = "utils.exchange_rate_notifier"


@pytest.fixture
def mock_dependencies():
    """
    main() 함수의 모든 외부 의존성을 Mock으로 대체한다.
    각 Mock 객체를 딕셔너리로 반환하여 테스트에서 접근 가능하게 한다.
    """
    with (
        patch(f"{NOTIFIER_MODULE}.get_credentials") as mock_get_creds,
        patch(f"{NOTIFIER_MODULE}.TelegramSender") as mock_telegram_cls,
        patch(f"{NOTIFIER_MODULE}.MySQLConnector") as mock_db_cls,
        patch(f"{NOTIFIER_MODULE}.ExchangeRateCollector") as mock_collector_cls,
        patch(f"{NOTIFIER_MODULE}.get_exchange_rates") as mock_get_rates,
        patch(f"{NOTIFIER_MODULE}.get_weekly_rates") as mock_get_weekly,
        patch(f"{NOTIFIER_MODULE}.SparklineGenerator") as mock_sparkline_cls,
        patch(f"{NOTIFIER_MODULE}.HTMLMessageFormatter") as mock_formatter_cls,
        patch(f"{NOTIFIER_MODULE}.is_send_graph_enabled") as mock_graph_enabled,
        patch(f"{NOTIFIER_MODULE}.BuySignalAnalyzer") as mock_analyzer_cls,
        patch(f"{NOTIFIER_MODULE}.SignalMessageFormatter") as mock_signal_fmt_cls,
    ):
        # 텔레그램 설정
        mock_get_creds.return_value = {"chat_id": "test_chat_id"}
        mock_telegram = MagicMock()
        mock_telegram.send_message.return_value = True
        mock_telegram_cls.return_value = mock_telegram

        # DB 커넥터
        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db

        # 환율 수집기
        mock_collector = MagicMock()
        mock_collector_cls.return_value = mock_collector

        # 환율 데이터 조회 (오늘/어제)
        mock_get_rates.return_value = {
            "USD": {"deal_bas_r": 1400.0, "bkpr": 1390.0},
            "JPY(100)": {"deal_bas_r": 950.0, "bkpr": 945.0},
        }

        # 주간 환율 데이터 (스파크라인용)
        mock_get_weekly.return_value = [1400.0, 1405.0, 1410.0]

        # 스파크라인 생성
        mock_sparkline_cls.generate.return_value = "▁▂▃"

        # HTML 메시지 포맷터
        mock_html_formatter = MagicMock()
        mock_html_formatter.format_message.return_value = "<b>환율 알림</b>"
        mock_formatter_cls.return_value = mock_html_formatter

        # 그래프 전송 비활성화 (기본)
        mock_graph_enabled.return_value = False

        # BuySignalAnalyzer
        mock_analyzer = MagicMock()
        mock_analyzer_cls.return_value = mock_analyzer

        # SignalMessageFormatter
        mock_signal_formatter = MagicMock()
        mock_signal_fmt_cls.return_value = mock_signal_formatter

        yield {
            "telegram": mock_telegram,
            "telegram_cls": mock_telegram_cls,
            "db": mock_db,
            "db_cls": mock_db_cls,
            "collector": mock_collector,
            "get_rates": mock_get_rates,
            "get_weekly": mock_get_weekly,
            "html_formatter": mock_html_formatter,
            "graph_enabled": mock_graph_enabled,
            "analyzer": mock_analyzer,
            "analyzer_cls": mock_analyzer_cls,
            "signal_formatter": mock_signal_formatter,
            "signal_formatter_cls": mock_signal_fmt_cls,
        }


class TestBuySignalAnalysisInvocation:
    """main() 실행 시 매수 신호 분석이 호출되는지 확인 (Requirements 6.1)"""

    def test_buy_signal_analyzer_is_called_after_notification(self, mock_dependencies):
        """기존 환율 알림 전송 후 BuySignalAnalyzer.analyze()가 호출된다"""
        from utils.exchange_rate_notifier import main

        mock_analyzer = mock_dependencies["analyzer"]
        mock_analyzer.analyze.return_value = []

        main()

        # BuySignalAnalyzer가 DB 커넥터로 초기화되었는지 확인
        mock_dependencies["analyzer_cls"].assert_called_once_with(
            mock_dependencies["db"]
        )
        # analyze()가 호출되었는지 확인
        mock_analyzer.analyze.assert_called_once()

    def test_analyzer_receives_today_rates(self, mock_dependencies):
        """analyze()에 오늘의 환율 데이터(deal_bas_r)가 전달된다"""
        from utils.exchange_rate_notifier import main

        mock_analyzer = mock_dependencies["analyzer"]
        mock_analyzer.analyze.return_value = []

        main()

        # analyze()에 전달된 인자 확인: {currency: deal_bas_r} 형태
        call_args = mock_analyzer.analyze.call_args[0][0]
        assert call_args == {"USD": 1400.0, "JPY(100)": 950.0}


class TestBuySignalMessageSending:
    """매수 신호 감지 시 메시지 전송 확인 (Requirements 5.3)"""

    def test_signal_message_sent_when_signals_detected(self, mock_dependencies):
        """매수 신호가 감지되면 포맷된 메시지를 텔레그램으로 전송한다"""
        from utils.exchange_rate_notifier import main

        # 신호가 존재하는 경우
        mock_signal = MagicMock()
        mock_dependencies["analyzer"].analyze.return_value = [mock_signal]
        mock_dependencies["signal_formatter"].format_signals.return_value = (
            "<b>매수 신호</b>"
        )

        main()

        # SignalMessageFormatter.format_signals()가 호출되었는지 확인
        mock_dependencies["signal_formatter"].format_signals.assert_called_once_with(
            [mock_signal]
        )
        # 텔레그램으로 매수 신호 메시지가 전송되었는지 확인
        telegram_calls = mock_dependencies["telegram"].send_message.call_args_list
        # 기존 환율 알림 + 매수 신호 메시지 = 최소 2회 호출
        signal_call = telegram_calls[-1]
        assert signal_call == call("<b>매수 신호</b>", parse_mode="HTML")


class TestNoSignalNoMessage:
    """신호 미감지 시 매수 신호 메시지 미전송 확인 (Requirements 5.4)"""

    def test_no_signal_message_when_no_signals(self, mock_dependencies):
        """매수 신호가 없으면 매수 신호 메시지를 전송하지 않는다"""
        from utils.exchange_rate_notifier import main

        # 신호 없음
        mock_dependencies["analyzer"].analyze.return_value = []

        main()

        # SignalMessageFormatter가 호출되지 않아야 한다
        mock_dependencies["signal_formatter"].format_signals.assert_not_called()
        # 텔레그램 전송은 기존 환율 알림 1회만 호출
        assert mock_dependencies["telegram"].send_message.call_count == 1


class TestAnalysisErrorIsolation:
    """분석 오류 시 기존 알림 정상 동작 확인 (Requirements 5.5, 6.2)"""

    def test_analyzer_exception_does_not_affect_existing_notification(
        self, mock_dependencies
    ):
        """BuySignalAnalyzer.analyze()에서 예외 발생 시 기존 환율 알림은 정상 전송된다"""
        from utils.exchange_rate_notifier import main

        # 분석 중 예외 발생
        mock_dependencies["analyzer"].analyze.side_effect = RuntimeError(
            "DB 연결 실패"
        )

        # main()이 예외 없이 정상 종료되어야 한다
        main()

        # 기존 환율 알림 메시지는 정상 전송되었는지 확인
        mock_dependencies["telegram"].send_message.assert_called()
        first_call = mock_dependencies["telegram"].send_message.call_args_list[0]
        assert first_call == call("<b>환율 알림</b>", parse_mode="HTML")

    def test_analyzer_init_exception_does_not_affect_notification(
        self, mock_dependencies
    ):
        """BuySignalAnalyzer 초기화 중 예외 발생 시에도 기존 알림은 정상 동작한다"""
        from utils.exchange_rate_notifier import main

        # 초기화 시 예외 발생
        mock_dependencies["analyzer_cls"].side_effect = RuntimeError(
            "초기화 실패"
        )

        main()

        # 기존 환율 알림은 정상 전송
        mock_dependencies["telegram"].send_message.assert_called()
        first_call = mock_dependencies["telegram"].send_message.call_args_list[0]
        assert first_call == call("<b>환율 알림</b>", parse_mode="HTML")

    def test_signal_formatter_exception_does_not_affect_notification(
        self, mock_dependencies
    ):
        """SignalMessageFormatter에서 예외 발생 시에도 기존 알림은 정상 동작한다"""
        from utils.exchange_rate_notifier import main

        mock_signal = MagicMock()
        mock_dependencies["analyzer"].analyze.return_value = [mock_signal]
        # 포맷터에서 예외 발생
        mock_dependencies["signal_formatter"].format_signals.side_effect = (
            ValueError("포맷 오류")
        )

        main()

        # 기존 환율 알림은 정상 전송
        first_call = mock_dependencies["telegram"].send_message.call_args_list[0]
        assert first_call == call("<b>환율 알림</b>", parse_mode="HTML")

    def test_signal_send_failure_does_not_affect_notification(
        self, mock_dependencies
    ):
        """매수 신호 메시지 전송 실패 시에도 기존 알림은 이미 전송된 상태이다"""
        from utils.exchange_rate_notifier import main

        mock_signal = MagicMock()
        mock_dependencies["analyzer"].analyze.return_value = [mock_signal]
        mock_dependencies["signal_formatter"].format_signals.return_value = (
            "<b>매수 신호</b>"
        )

        # 첫 번째 호출(기존 알림)은 성공, 두 번째 호출(매수 신호)은 실패
        mock_dependencies["telegram"].send_message.side_effect = [
            True,
            False,
        ]

        # main()이 예외 없이 정상 종료
        main()

        # 두 번 호출되었는지 확인 (기존 알림 + 매수 신호)
        assert mock_dependencies["telegram"].send_message.call_count == 2
