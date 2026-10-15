from datetime import datetime
from unittest.mock import MagicMock, patch

import mcp_notmuch_sendmail.notmuchlib as nm_lib


def _make_fake_message(from_addr, date_ts, mime_raw):
    """Create a fake notmuch message object.

    Works with both old (notmuch) and new (notmuch2) APIs by supporting
    both method signatures the code may call."""
    import tempfile
    from pathlib import Path

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".eml")
    if isinstance(mime_raw, str):
        mime_raw = mime_raw.encode()
    tmp.write(mime_raw)
    tmp.close()

    msg = MagicMock()
    # Old API: get_header(name); New API (notmuch2): header(name)
    msg.get_header.return_value = from_addr
    msg.header.return_value = from_addr
    type(msg).date = property(lambda self: date_ts)
    msg.get_date.return_value = date_ts
    type(msg).path = property(lambda self: Path(tmp.name))
    return msg


def _build_mime(html_content):
    """Build a raw MIME multipart/alternative email for testing."""
    boundary = "===============boundary============="
    part = (
        f"--{boundary}\r\n"
        f"Content-Type: text/html; charset=\"utf-8\"\r\n\r\n"
        f"{html_content}"
    )
    body = part + f"\r\n--{boundary}--\r\n"
    return (
        "MIME-Version: 1.0\r\n"
        "Content-Type: multipart/alternative; boundary=\"===============boundary=============\"\r\n\r\n"
        f"{body}"
    )


def test_fmt_timestamp_formats_date():
    assert nm_lib.fmt_timestamp(1706140800) == "2024-01-25"


def test_fmt_timestamp_various_dates():
    ts = datetime(2030, 6, 15).timestamp()
    assert nm_lib.fmt_timestamp(ts) == "2030-06-15"


def test_message_to_text_converts_html():
    mime = _build_mime("<p>Hello <b>world</b></p>")
    msg = _make_fake_message("alice@example.com", 1706140800, mime)

    text = nm_lib.message_to_text(msg)
    assert "FROM: alice@example.com" in text
    assert "DATE: 2024-01-25" in text
    assert "Hello world" in text


def test_message_to_text_strips_html_tags():
    mime = _build_mime("<h1>Title</h1><p>Body text.</p>")
    msg = _make_fake_message("sender@test.com", 1706140800, mime)

    text = nm_lib.message_to_text(msg)
    assert "<h1>" not in text
    assert "</p>" not in text


def test_message_to_text_trims_reply_at_separator():
    mime = _build_mime(
        "<p>Hello there</p>\n<p>On Monday someone wrote:</p>\n<p>quoted stuff</p>"
    )
    msg = _make_fake_message("sender@test.com", 1706140800, mime)

    text = nm_lib.message_to_text(msg)
    assert "Hello there" in text
    assert "On Monday someone wrote:" not in text


def test_message_to_text_empty_parts():
    mime = (
        "MIME-Version: 1.0\r\n"
        "Content-Type: multipart/alternative; boundary=\"===============boundary=============\"\r\n\r\n"
        "--===============boundary=============--\r\n"
    )
    msg = _make_fake_message("empty@test.com", 1706140800, mime)

    text = nm_lib.message_to_text(msg)
    assert "FROM: empty@test.com" in text
    assert "DATE: 2024-01-25" in text


def test_message_to_text_multiple_parts():
    mime_raw = (
        "MIME-Version: 1.0\r\n"
        "Content-Type: multipart/alternative; boundary=\"===============boundary=============\"\r\n\r\n"
        "--===============boundary=============\r\n"
        "Content-Type: text/html; charset=\"utf-8\"\r\n\r\n"
        "<p>Part one</p>\r\n"
        "--===============boundary=============\r\n"
        "Content-Type: text/plain; charset=\"utf-8\"\r\n\r\n"
        "Part two\r\n"
        "--===============boundary=============--\r\n"
    )
    msg = _make_fake_message("multi@test.com", 1706140800, mime_raw)

    text = nm_lib.message_to_text(msg)
    assert "Part one" in text or "Part two" in text


def test_fetch_new_emails_returns_unset_when_no_script():
    with patch.object(nm_lib, "NOTMUCH_SYNC_SCRIPT", None):
        result = nm_lib.fetch_new_emails()
        assert "not set" in result


def test_fetch_new_emails_returns_error_for_missing_script(tmp_path, monkeypatch):
    import os, importlib

    monkeypatch.setenv("NOTMUCH_SYNC_SCRIPT", str(tmp_path / "nonexistent.sh"))
    importlib.reload(nm_lib)

    result = nm_lib.fetch_new_emails()
    assert "Script not found" in result


def test_fetch_new_emails_runs_script(tmp_path, monkeypatch):
    import os, importlib

    script = tmp_path / "sync.sh"
    script.write_text("#!/bin/sh\necho synced\n")
    script.chmod(0o755)

    monkeypatch.setenv("NOTMUCH_SYNC_SCRIPT", str(script))
    importlib.reload(nm_lib)

    result = nm_lib.fetch_new_emails()
    assert "synced" in result


def test_find_threads_returns_formatted_output():
    """Test that find_threads returns properly formatted thread info."""
    # Determine which API is available (old vs new notmuch bindings)
    if hasattr(nm_lib, 'notmuch2'):
        mock_thread = MagicMock()
        mock_thread.threadid = "abc123"
        mock_thread.last = 1706140800
        mock_thread.subject = "Test Subject That Is Very Long For Testing Purposes"
        mock_thread.authors = "Alice <alice@test.com>, Bob <bob@test.com>"

        mock_db_instance = MagicMock()
        mock_db_instance.threads.return_value = iter([mock_thread])

        with patch.object(nm_lib.notmuch2, "Database", return_value=mock_db_instance):
            result = nm_lib.find_threads("tag:inbox")
    else:
        # Old API using notmuch module directly
        mock_thread = MagicMock()
        mock_thread.get_thread_id.return_value = "abc123"
        mock_thread.get_newest_date.return_value = 1706140800
        mock_thread.get_subject.return_value = "Test Subject That Is Very Long For Testing Purposes"
        mock_thread.get_authors.return_value = "Alice <alice@test.com>, Bob <bob@test.com>"

        mock_query_class = MagicMock()
        mock_db_instance = MagicMock()
        mock_db_instance.__enter__.return_value = mock_db_instance
        mock_db_instance.__exit__.return_value = False

        with patch.object(nm_lib, "Database", return_value=mock_db_instance), \
             patch.object(nm_lib, "Query") as mock_query_class:
            mock_query_instance = MagicMock()
            mock_query_instance.search_threads.return_value = iter([mock_thread])
            mock_query_class.return_value = mock_query_instance

            result = nm_lib.find_threads("tag:inbox")

    assert "abc123" in result
    assert "2024-01-25" in result


def test_view_thread_joins_messages():
    """Test that view_thread joins multiple messages with separator."""
    import tempfile, pathlib

    mock_msg = MagicMock()
    mock_msg.header.return_value = "alice@test.com"
    type(mock_msg).date = property(lambda self: 1706140800)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".eml")
    tmp.write(b"MIME-Version: 1.0\r\nContent-Type: text/plain\r\n\r\nHello\r\n")
    tmp.close()
    type(mock_msg).path = property(lambda self: pathlib.Path(tmp.name))

    if hasattr(nm_lib, 'notmuch2'):
        mock_db_instance = MagicMock()
        mock_db_instance.messages.return_value = iter([mock_msg, mock_msg])

        with patch.object(nm_lib.notmuch2, "Database", return_value=mock_db_instance):
            result = nm_lib.view_thread("thread123")
    else:
        # Old API using Query pattern
        mock_query_class = MagicMock()
        mock_query_instance = MagicMock()
        mock_query_instance.search_messages.return_value = iter([mock_msg, mock_msg])
        mock_query_class.return_value = mock_query_instance

        with patch.object(nm_lib, "Database") as mock_db_class, \
             patch.object(nm_lib, "Query", mock_query_class):
            result = nm_lib.view_thread("thread123")

    assert "- - -" in result


def test_get_thread_info_returns_dict():
    """Test that get_thread_info returns a dict with expected keys."""
    mock_msg = MagicMock()
    mock_msg.header.side_effect = lambda name: {
        "Message-ID": "<msg@example.com>",
        "References": "<ref@example.com>",
        "In-Reply-To": "<irt@example.com>",
        "Subject": "Test Subject",
        "From": "alice@test.com",
        "Reply-To": "reply@test.com",
    }.get(name, "")

    if hasattr(nm_lib, 'notmuch2'):
        mock_db_instance = MagicMock()
        mock_db_instance.messages.return_value = iter([mock_msg])

        with patch.object(nm_lib.notmuch2, "Database", return_value=mock_db_instance):
            result = nm_lib.get_thread_info("thread123")
    else:
        # Old API using Query pattern
        mock_query_class = MagicMock()
        mock_query_instance = MagicMock()
        mock_query_instance.search_messages.return_value = iter([mock_msg])
        mock_query_class.return_value = mock_query_instance

        with patch.object(nm_lib, "Database") as mock_db_class, \
             patch.object(nm_lib, "Query", mock_query_class):
            result = nm_lib.get_thread_info("thread123")

    assert "message_id" in result
    assert result["subject"] == "Test Subject"


# Images and attachments in received mail

def _build_mixed_mime(html, image_bytes, filename, content_type="image/png", inline=False):
    import base64
    b = "===============mixed============="
    disposition = f'inline; filename="{filename}"' if inline else f'attachment; filename="{filename}"'
    return (
        "MIME-Version: 1.0\r\n"
        f'Content-Type: multipart/mixed; boundary="{b}"\r\n\r\n'
        f"--{b}\r\nContent-Type: text/html; charset=\"utf-8\"\r\n\r\n{html}\r\n"
        f"--{b}\r\nContent-Type: {content_type}; name=\"{filename}\"\r\n"
        f"Content-Disposition: {disposition}\r\nContent-Transfer-Encoding: base64\r\n"
        f"Content-ID: <{filename}>\r\n\r\n{base64.b64encode(image_bytes).decode()}\r\n"
        f"--{b}--\r\n"
    )


PNG = b"\x89PNG\r\n\x1a\nfake"


def test_thread_view_lists_images_and_attachments():
    msg = _make_fake_message("a@b.c", 1706140800, _build_mixed_mime("<p>see attached</p>", PNG, "chart.png"))
    text = nm_lib.message_to_text(msg)
    assert "see attached" in text
    assert "[image: chart.png]" in text
    msg = _make_fake_message("a@b.c", 1706140800,
                             _build_mixed_mime("<p>x</p>", b"%PDF", "report.pdf", content_type="application/pdf"))
    assert "[attachment: report.pdf]" in nm_lib.message_to_text(msg)


def test_get_image_returns_bytes_and_subtype():
    msg = _make_fake_message("a@b.c", 1706140800, _build_mixed_mime("<p>x</p>", PNG, "chart.png", inline=True))
    db = MagicMock()
    db.messages.return_value = iter([msg])
    with patch.object(nm_lib.notmuch2, "Database", return_value=db):
        error, data, subtype = nm_lib.get_image("t1", "chart.png")
    assert error is None and data == PNG and subtype == "png"


def test_get_image_unknown_name_is_an_error():
    msg = _make_fake_message("a@b.c", 1706140800, _build_mixed_mime("<p>x</p>", PNG, "chart.png"))
    db = MagicMock()
    db.messages.return_value = iter([msg])
    with patch.object(nm_lib.notmuch2, "Database", return_value=db):
        error, data, _ = nm_lib.get_image("t1", "nope.png")
    assert data is None and "No image named nope.png" in error


def test_get_image_refuses_non_image_parts():
    msg = _make_fake_message("a@b.c", 1706140800,
                             _build_mixed_mime("<p>x</p>", b"%PDF", "report.pdf", content_type="application/pdf"))
    db = MagicMock()
    db.messages.return_value = iter([msg])
    with patch.object(nm_lib.notmuch2, "Database", return_value=db):
        error, data, _ = nm_lib.get_image("t1", "report.pdf")
    assert data is None and error
