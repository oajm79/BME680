"""Tests for the TelegramNotifier hysteresis state machine."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bme680_monitor.telegram_notifier import TelegramNotifier


def make_notifier(confirmation_readings=3):
    # No token/chat_id -> enabled=False, so no network calls are ever attempted.
    return TelegramNotifier(enabled=True, confirmation_readings=confirmation_readings)


class TestStateTransitionHysteresis:
    """Test suite for _check_state_transition, which prevents alert flapping."""

    def test_no_transition_while_state_unchanged(self):
        notifier = make_notifier()
        assert notifier._check_state_transition("air_quality_poor", False) is None

    def test_requires_confirmation_readings_before_confirming_entry(self):
        notifier = make_notifier(confirmation_readings=3)

        assert notifier._check_state_transition("air_quality_poor", True) is None
        assert notifier._check_state_transition("air_quality_poor", True) is None
        assert notifier._check_state_transition("air_quality_poor", True) == "entered"

    def test_single_bad_reading_does_not_trigger_alert(self):
        """A single flaky reading shouldn't be enough to alert - that's the whole point."""
        notifier = make_notifier(confirmation_readings=5)

        assert notifier._check_state_transition("air_quality_poor", True) is None
        assert notifier._alert_states["air_quality_poor"] is False

    def test_flapping_reading_resets_pending_count(self):
        """A reading that flips back to normal mid-confirmation resets the counter."""
        notifier = make_notifier(confirmation_readings=3)

        assert notifier._check_state_transition("air_quality_poor", True) is None
        assert notifier._check_state_transition("air_quality_poor", True) is None
        # Flaps back to good before confirmation completes
        assert notifier._check_state_transition("air_quality_poor", False) is None

        # Needs 3 fresh consecutive "bad" readings again, not just 1 more
        assert notifier._check_state_transition("air_quality_poor", True) is None
        assert notifier._check_state_transition("air_quality_poor", True) is None
        assert notifier._check_state_transition("air_quality_poor", True) == "entered"

    def test_exit_transition_after_confirmed_entry(self):
        notifier = make_notifier(confirmation_readings=2)

        notifier._check_state_transition("air_quality_poor", True)
        assert notifier._check_state_transition("air_quality_poor", True) == "entered"

        assert notifier._check_state_transition("air_quality_poor", False) is None
        assert notifier._check_state_transition("air_quality_poor", False) == "exited"

    def test_independent_state_keys_do_not_interfere(self):
        notifier = make_notifier(confirmation_readings=2)

        notifier._check_state_transition("temperature_high", True)
        assert notifier._check_state_transition("temperature_high", True) == "entered"

        # A different state key starts fresh
        assert notifier._check_state_transition("humidity_high", True) is None

    def test_time_based_debounce_blocks_until_elapsed(self):
        from unittest.mock import patch

        notifier = TelegramNotifier(enabled=True, confirmation_readings=2, debounce_seconds=60.0)
        with patch("bme680_monitor.telegram_notifier.time.monotonic") as mock_mono:
            mock_mono.return_value = 1000.0
            assert notifier._check_state_transition("air_quality_poor", True) is None

            # 2nd reading after only 10s (< 60s debounce) -> still blocked
            mock_mono.return_value = 1010.0
            assert notifier._check_state_transition("air_quality_poor", True) is None

            # Reading after 65s (>= 60s debounce and >= 2 readings) -> confirmed
            mock_mono.return_value = 1065.0
            assert notifier._check_state_transition("air_quality_poor", True) == "entered"


class TestHumidityAndTemperatureHysteresis:
    """Test suite for humidity and temperature hysteresis to prevent threshold flapping."""

    def test_humidity_low_hysteresis_prevents_flapping(self):
        from unittest.mock import MagicMock

        notifier = TelegramNotifier(
            bot_token="test_token",
            chat_id="12345",
            enabled=True,
            confirmation_readings=2,
            debounce_seconds=0.0,
        )
        notifier.send_message = MagicMock(return_value=True)

        # 1. Enter low state (threshold = 30.0%, hysteresis = 2.0%)
        # Reading 1: 29.5% (< 30.0%) -> pending
        assert notifier.check_humidity_transition(29.5, high_threshold=70.0, low_threshold=30.0, hysteresis=2.0) is False
        assert notifier._alert_states["humidity_low"] is False

        # Reading 2: 29.5% -> confirmed entry
        assert notifier.check_humidity_transition(29.5, high_threshold=70.0, low_threshold=30.0, hysteresis=2.0) is True
        assert notifier._alert_states["humidity_low"] is True
        assert notifier.send_message.call_count == 1
        assert "dropped below" in notifier.send_message.call_args[0][0]

        # 2. Hover around threshold: 29.8, 30.0, 30.5, 31.0, 31.8 (< 30 + 2 = 32.0%)
        # None of these should trigger an exit or alert
        for h in [29.8, 30.0, 30.2, 30.9, 31.5, 31.9]:
            assert notifier.check_humidity_transition(h, high_threshold=70.0, low_threshold=30.0, hysteresis=2.0) is False
            assert notifier._alert_states["humidity_low"] is True
        assert notifier.send_message.call_count == 1  # Still only the initial alert

        # 3. Sustained crossing above band (>= 32.0%)
        # Reading 1: 32.5% -> pending exit
        assert notifier.check_humidity_transition(32.5, high_threshold=70.0, low_threshold=30.0, hysteresis=2.0) is False
        assert notifier._alert_states["humidity_low"] is True

        # Reading 2: 32.5% -> confirmed exit
        assert notifier.check_humidity_transition(32.5, high_threshold=70.0, low_threshold=30.0, hysteresis=2.0) is True
        assert notifier._alert_states["humidity_low"] is False
        assert notifier.send_message.call_count == 2
        assert "returned to normal" in notifier.send_message.call_args[0][0]

        # 4. Reading at 30.5% (above 30% low threshold) does not re-enter
        assert notifier.check_humidity_transition(30.5, high_threshold=70.0, low_threshold=30.0, hysteresis=2.0) is False
        assert notifier._alert_states["humidity_low"] is False
        assert notifier.send_message.call_count == 2

    def test_humidity_high_hysteresis_prevents_flapping(self):
        from unittest.mock import MagicMock

        notifier = TelegramNotifier(
            bot_token="test_token",
            chat_id="12345",
            enabled=True,
            confirmation_readings=2,
            debounce_seconds=0.0,
        )
        notifier.send_message = MagicMock(return_value=True)

        # 1. Enter high state (threshold = 70.0%, hysteresis = 2.0%)
        assert notifier.check_humidity_transition(70.5, high_threshold=70.0, low_threshold=30.0, hysteresis=2.0) is False
        assert notifier.check_humidity_transition(70.5, high_threshold=70.0, low_threshold=30.0, hysteresis=2.0) is True
        assert notifier._alert_states["humidity_high"] is True
        assert notifier.send_message.call_count == 1
        assert "exceeded" in notifier.send_message.call_args[0][0]

        # 2. Hover around threshold: 69.8, 70.0, 69.2, 68.5 (> 70 - 2 = 68.0%)
        for h in [69.8, 70.0, 69.2, 68.5]:
            assert notifier.check_humidity_transition(h, high_threshold=70.0, low_threshold=30.0, hysteresis=2.0) is False
            assert notifier._alert_states["humidity_high"] is True
        assert notifier.send_message.call_count == 1

        # 3. Sustained crossing below band (<= 68.0%)
        assert notifier.check_humidity_transition(67.5, high_threshold=70.0, low_threshold=30.0, hysteresis=2.0) is False
        assert notifier.check_humidity_transition(67.5, high_threshold=70.0, low_threshold=30.0, hysteresis=2.0) is True
        assert notifier._alert_states["humidity_high"] is False
        assert notifier.send_message.call_count == 2
        assert "returned to normal" in notifier.send_message.call_args[0][0]

    def test_temperature_hysteresis_prevents_flapping(self):
        from unittest.mock import MagicMock

        notifier = TelegramNotifier(
            bot_token="test_token",
            chat_id="12345",
            enabled=True,
            confirmation_readings=2,
            debounce_seconds=0.0,
        )
        notifier.send_message = MagicMock(return_value=True)

        # 1. Enter high temperature (threshold = 30.0°C, hysteresis = 0.5°C)
        assert notifier.check_temperature_transition(30.2, high_threshold=30.0, low_threshold=15.0, hysteresis=0.5) is False
        assert notifier.check_temperature_transition(30.2, high_threshold=30.0, low_threshold=15.0, hysteresis=0.5) is True
        assert notifier._alert_states["temperature_high"] is True
        assert notifier.send_message.call_count == 1
        assert "exceeded" in notifier.send_message.call_args[0][0]

        # 2. Hover around threshold: 29.8, 29.6 (> 30.0 - 0.5 = 29.5°C)
        for t in [29.9, 30.0, 29.7, 29.6]:
            assert notifier.check_temperature_transition(t, high_threshold=30.0, low_threshold=15.0, hysteresis=0.5) is False
            assert notifier._alert_states["temperature_high"] is True
        assert notifier.send_message.call_count == 1

        # 3. Sustained crossing below band (<= 29.5°C)
        assert notifier.check_temperature_transition(29.4, high_threshold=30.0, low_threshold=15.0, hysteresis=0.5) is False
        assert notifier.check_temperature_transition(29.4, high_threshold=30.0, low_threshold=15.0, hysteresis=0.5) is True
        assert notifier._alert_states["temperature_high"] is False
        assert notifier.send_message.call_count == 2
        assert "returned to normal" in notifier.send_message.call_args[0][0]


class TestOpenClawIntegration:
    """Test suite for OpenClaw dispatch and fallback."""

    def test_openclaw_client_instantiation_when_enabled(self):
        from unittest.mock import patch
        with patch("bme680_monitor.telegram_notifier.OpenClawClient") as mock_client_cls:
            notifier = TelegramNotifier(
                bot_token="fake_token",
                chat_id="123456",
                thread_id="789",
                use_openclaw=True,
                openclaw_account="infra",
                enabled=True,
            )
            mock_client_cls.assert_called_once_with(
                target="123456",
                thread_id="789",
                channel="telegram",
                account="infra",
            )
            assert notifier.use_openclaw is True
            assert notifier._openclaw is not None

    def test_openclaw_not_instantiated_when_disabled(self):
        from unittest.mock import patch
        with patch("bme680_monitor.telegram_notifier.OpenClawClient") as mock_client_cls:
            notifier = TelegramNotifier(
                bot_token="fake_token",
                chat_id="123456",
                use_openclaw=False,
                enabled=True,
            )
            mock_client_cls.assert_not_called()
            assert notifier._openclaw is None

    def test_send_message_dispatches_via_openclaw_success(self):
        from unittest.mock import MagicMock, patch
        notifier = TelegramNotifier(
            bot_token="fake_token",
            chat_id="123456",
            use_openclaw=True,
            enabled=True,
        )
        notifier._openclaw = MagicMock()
        notifier._openclaw.send_message.return_value = True

        with patch("shared_services.telegram.TelegramNotifier.send_message") as mock_base_send:
            result = notifier.send_message("Test message", force=True)
            assert result is True
            notifier._openclaw.send_message.assert_called_once_with(text="Test message")
            mock_base_send.assert_not_called()

    def test_send_message_falls_back_when_openclaw_fails(self):
        from unittest.mock import MagicMock, patch
        notifier = TelegramNotifier(
            bot_token="fake_token",
            chat_id="123456",
            use_openclaw=True,
            enabled=True,
        )
        notifier._openclaw = MagicMock()
        notifier._openclaw.send_message.return_value = False

        with patch("shared_services.telegram.TelegramNotifier.send_message") as mock_base_send:
            mock_base_send.return_value = True
            result = notifier.send_message("Test message", force=True)
            assert result is True
            notifier._openclaw.send_message.assert_called_once_with(text="Test message")
            mock_base_send.assert_called_once_with("Test message", parse_mode="HTML", disable_notification=False)

    def test_send_message_falls_back_when_openclaw_raises(self):
        from unittest.mock import MagicMock, patch
        notifier = TelegramNotifier(
            bot_token="fake_token",
            chat_id="123456",
            use_openclaw=True,
            enabled=True,
        )
        notifier._openclaw = MagicMock()
        notifier._openclaw.send_message.side_effect = RuntimeError("OpenClaw CLI crash")

        with patch("shared_services.telegram.TelegramNotifier.send_message") as mock_base_send:
            mock_base_send.return_value = True
            result = notifier.send_message("Test message", force=True)
            assert result is True
            notifier._openclaw.send_message.assert_called_once_with(text="Test message")
            mock_base_send.assert_called_once_with("Test message", parse_mode="HTML", disable_notification=False)

    def test_alert_state_persistence_across_instances(self, tmp_path):
        state_file = tmp_path / ".alert_state.json"
        n1 = TelegramNotifier(enabled=False, confirmation_readings=1, state_file=state_file)
        # Transition to bad state
        assert n1._check_state_transition("air_quality_poor", True) == "entered"
        assert state_file.exists()

        # New instance pointing to same file should load the state and not re-trigger "entered"
        n2 = TelegramNotifier(enabled=False, confirmation_readings=1, state_file=state_file)
        assert n2._alert_states["air_quality_poor"] is True
        assert n2._check_state_transition("air_quality_poor", True) is None

