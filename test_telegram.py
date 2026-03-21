#!/usr/bin/env python
"""Quick test script for Telegram notifications."""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from bme680_monitor import Config, TelegramNotifier

def main():
    # Load config (this also loads .env file)
    config_path = Path(__file__).parent / "config" / "config.yaml"
    config = Config(str(config_path))

    bot_token = config.telegram_bot_token
    chat_id = config.telegram_chat_id

    print("Telegram Configuration:")
    print(f"  Bot Token: {bot_token[:20]}...{bot_token[-5:]}" if bot_token else "  Bot Token: NOT SET")
    print(f"  Chat ID: {chat_id}" if chat_id else "  Chat ID: NOT SET")
    print(f"  Enabled in config: {config.telegram_enabled}")

    if not bot_token or not chat_id:
        print("\nError: Missing credentials!")
        print("Create a .env file with TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        sys.exit(1)

    # Create notifier (force enabled for testing)
    telegram = TelegramNotifier(
        bot_token=bot_token,
        chat_id=chat_id,
        enabled=True  # Force enabled for test
    )

    print("\nSending test message...")
    success = telegram.test_connection()

    if success:
        print("Test message sent successfully! Check your Telegram.")
    else:
        print("Failed to send test message. Check your bot token and chat ID.")

if __name__ == "__main__":
    main()
