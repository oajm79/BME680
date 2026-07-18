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
