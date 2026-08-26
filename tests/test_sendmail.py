import json
from pathlib import Path
from unittest.mock import patch

from mcp_notmuch_sendmail.sendmail import markdown_to_html, create_draft, compose, send


class TestMarkdownToHtml:
    def test_basic_markdown(self):
        html, images = markdown_to_html("**bold** and *italic*")
        assert "<strong>bold</strong>" in html
        assert "<em>italic</em>" in html

    def test_table_support(self):
        md = "| a | b |\n|---|---|\n| 1 | 2 |"
        html, _ = markdown_to_html(md)
        assert "<table>" in html
        assert "<td>1</td>" in html

    def test_strikethrough_support(self):
        html, _ = markdown_to_html("~~deleted~~")
        assert "<s>deleted</s>" in html or "<del>deleted</del>" in html

    def test_tasklist_support(self):
        html, _ = markdown_to_html("- [x] done\n- [ ] todo")
        assert 'type="checkbox"' in html

    def test_css_injection(self, tmp_path):
        css_file = tmp_path / "test.css"
        css_file.write_text("body { color: red; }")
        html, _ = markdown_to_html("hello", css_path=css_file)
        assert "color: red" in html

    def test_draft_template_used_with_metadata(self):
        html, _ = markdown_to_html("hello", metadata={"subject": "Test", "to": ["a@b.com"], "cc": [], "bcc": []})
        assert "Subject:" in html
        assert "Test" in html

    def test_sent_template_used_without_metadata(self):
        html, _ = markdown_to_html("hello")
        assert "<article>" in html

    def test_no_images_returns_empty_dict(self):
        _, images = markdown_to_html("just text")
        assert images == {}


class TestCreateDraft:
    def test_creates_draft_files(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path):
            metadata = {"subject": "Hi", "to": ["a@b.com"], "cc": [], "bcc": [], "thread_info": None}
            result = create_draft("# Hello", metadata)

            assert (tmp_path / "draft.md").read_text() == "# Hello"
            assert (tmp_path / "draft.json").exists()
            stored = json.loads((tmp_path / "draft.json").read_text())
            assert stored["subject"] == "Hi"
            assert (tmp_path / "draft.html").exists()
            assert "<h1>" in (tmp_path / "draft.html").read_text()


class TestCompose:
    def test_compose_returns_draft_paths(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path):
            result = compose("Subject", "body", ["to@example.com"])
            assert "draft.md" in result
            assert "draft.html" in result

    def test_compose_stores_metadata(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path):
            compose("Subj", "body", ["to@example.com"], cc=["cc@example.com"])
            metadata = json.loads((tmp_path / "draft.json").read_text())
            assert metadata["subject"] == "Subj"
            assert metadata["to"] == ["to@example.com"]
            assert metadata["cc"] == ["cc@example.com"]

    def test_compose_without_cc_bcc_defaults_to_empty(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path):
            compose("Subj", "body", ["to@example.com"])
            metadata = json.loads((tmp_path / "draft.json").read_text())
            assert metadata["cc"] == []
            assert metadata["bcc"] == []


class TestSend:
    def test_send_builds_correct_mime(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = None

            (tmp_path / "draft.md").write_text("Hello")
            metadata = {"subject": "Test", "to": ["to@example.com"], "cc": [], "bcc": [], "thread_info": None}
            (tmp_path / "draft.json").write_text(json.dumps(metadata))

            result = send()
            assert result == "Email sent successfully"

            call_args = mock_run.call_args
            assert call_args[0][0] == ["sendmail", "-t"]
            mime_text = call_args[1]["input"]
            assert "Subject: Test" in mime_text
            assert "To: to@example.com" in mime_text
            assert "From: test@example.com" in mime_text

    def test_send_includes_threading_headers(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = None

            (tmp_path / "draft.md").write_text("Reply body")
            metadata = {
                "subject": "Re: Test",
                "to": ["to@example.com"],
                "cc": [],
                "bcc": [],
                "thread_info": {
                    "message_id": "<msg123@example.com>",
                    "references": "<msg000@example.com>",
                },
            }
            (tmp_path / "draft.json").write_text(json.dumps(metadata))

            send()
            mime_text = mock_run.call_args[1]["input"]
            assert "In-Reply-To: <msg123@example.com>" in mime_text
            assert "<msg000@example.com> <msg123@example.com>" in mime_text

    def test_send_without_threading_has_no_reply_headers(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = None

            (tmp_path / "draft.md").write_text("Hello")
            metadata = {"subject": "Test", "to": ["a@b.com"], "cc": [], "bcc": [], "thread_info": None}
            (tmp_path / "draft.json").write_text(json.dumps(metadata))

            send()
            mime_text = mock_run.call_args[1]["input"]
            assert "In-Reply-To" not in mime_text
            assert "References" not in mime_text

    def test_send_includes_cc_header(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = None

            (tmp_path / "draft.md").write_text("Hello")
            metadata = {"subject": "Test", "to": ["a@b.com"], "cc": ["cc@example.com"], "bcc": [], "thread_info": None}
            (tmp_path / "draft.json").write_text(json.dumps(metadata))

            send()
            mime_text = mock_run.call_args[1]["input"]
            assert "Cc: cc@example.com" in mime_text

    def test_send_raises_without_draft(self, tmp_path):
        import pytest
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path):
            with pytest.raises(ValueError, match="No draft found"):
                send()
