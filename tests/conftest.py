import os, sys
from unittest.mock import MagicMock

os.environ.setdefault("NOTMUCH_DATABASE_PATH", "/tmp/test-notmuch-db")
os.environ.setdefault("NOTMUCH_REPLY_SEPARATORS", "on|wrote:|from:|sent:")
os.environ.setdefault("SENDMAIL_FROM_EMAIL", "test@example.com")

# Mock both notmuch and notmuch2 so tests work with either the original code
mock_notmuch = MagicMock()
sys.modules["notmuch"] = mock_notmuch
sys.modules["notmuch2"] = MagicMock()
