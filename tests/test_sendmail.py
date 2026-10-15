import json
from pathlib import Path
from unittest.mock import patch

from mcp_notmuch_sendmail.sendmail import markdown_to_html, create_draft, compose, send, update_preview


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


def _draft_dir(root):
    """The single draft directory compose/create_draft made under root."""
    dirs = [p for p in root.iterdir() if p.is_dir() and p.name.startswith("draft-")]
    assert len(dirs) == 1, dirs
    return dirs[0]


def _write_draft(root, markdown, metadata):
    d = root / "draft-test"
    d.mkdir(parents=True)
    (d / "draft.md").write_text(markdown)
    (d / "draft.json").write_text(json.dumps(metadata))
    return d


class TestCreateDraft:
    def test_creates_draft_files_in_own_directory(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path):
            metadata = {"subject": "Hi", "to": ["a@b.com"], "cc": [], "bcc": [], "thread_info": None}
            create_draft("# Hello", metadata)
            d = _draft_dir(tmp_path)
            assert (d / "draft.md").read_text() == "# Hello"
            assert json.loads((d / "draft.json").read_text())["subject"] == "Hi"
            assert "<h1>" in (d / "draft.html").read_text()

    def test_each_draft_gets_its_own_directory(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path):
            metadata = {"subject": "Hi", "to": ["a@b.com"], "cc": [], "bcc": [], "thread_info": None}
            a = create_draft("one", metadata)["dir"]
            b = create_draft("two", metadata)["dir"]
            assert a != b
            assert (a / "draft.md").read_text() == "one" and (b / "draft.md").read_text() == "two"


class TestCompose:
    def test_compose_returns_draft_paths(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path):
            result = compose("Subject", "body", ["to@example.com"])
            d = _draft_dir(tmp_path)
            assert str(d / "draft.md") in result
            assert str(d / "draft.html") in result
            assert f'send_email("{d}")' in result

    def test_compose_stores_metadata(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path):
            compose("Subj", "body", ["to@example.com"], cc=["cc@example.com"])
            metadata = json.loads((_draft_dir(tmp_path) / "draft.json").read_text())
            assert metadata["subject"] == "Subj"
            assert metadata["to"] == ["to@example.com"]
            assert metadata["cc"] == ["cc@example.com"]

    def test_compose_without_cc_bcc_defaults_to_empty(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path):
            compose("Subj", "body", ["to@example.com"])
            metadata = json.loads((_draft_dir(tmp_path) / "draft.json").read_text())
            assert metadata["cc"] == []
            assert metadata["bcc"] == []

    def test_compose_from_body_file(self, tmp_path):
        drafts = tmp_path / "drafts"
        body = tmp_path / "drafts" / "notes.md"
        body.parent.mkdir()
        body.write_text("# From a file")
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", drafts):
            compose("Subj", None, ["to@example.com"], body_file=str(body))
            assert (_draft_dir(drafts) / "draft.md").read_text() == "# From a file"

    def test_body_file_outside_allowed_dirs_refused(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mcp_notmuch_sendmail.sendmail.SENDMAIL_ALLOWED_UPLOAD_DIRECTORIES", [])
        secret = tmp_path / "secret.md"
        secret.write_text("x")
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path / "drafts"):
            result = compose("Subj", None, ["to@example.com"], body_file=str(secret))
        assert result.startswith("Error:") and "refused" in result

    def test_body_requires_exactly_one_source(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path):
            assert compose("S", None, ["a@b.com"]).startswith("Error: Pass exactly one")
            assert compose("S", "text", ["a@b.com"], body_file="/x.md").startswith("Error: Pass exactly one")


class TestUpdatePreview:
    def test_rerenders_html_after_direct_edit(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path):
            compose("Subj", "old", ["a@b.com"])
            d = _draft_dir(tmp_path)
            (d / "draft.md").write_text("# edited")
            assert "edited" not in (d / "draft.html").read_text()
            result = update_preview(str(d / "draft.md"))
            assert result.startswith("Updated")
            assert "<h1>edited</h1>" in (d / "draft.html").read_text()

    def test_rejects_paths_outside_draft_dir(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path / "drafts"):
            assert update_preview(str(tmp_path)).startswith("Error: Not a draft")


class TestSend:
    def test_send_builds_correct_mime(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = None
            d = _write_draft(tmp_path, "Hello",
                             {"subject": "Test", "to": ["to@example.com"], "cc": [], "bcc": [], "thread_info": None})

            result = send(str(d))
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
            d = _write_draft(tmp_path, "Reply body", {
                "subject": "Re: Test", "to": ["to@example.com"], "cc": [], "bcc": [],
                "thread_info": {"message_id": "<msg123@example.com>", "references": "<msg000@example.com>"},
            })
            send(str(d))
            mime_text = mock_run.call_args[1]["input"]
            assert "In-Reply-To: <msg123@example.com>" in mime_text
            assert "<msg000@example.com> <msg123@example.com>" in mime_text

    def test_send_without_threading_has_no_reply_headers(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = None
            d = _write_draft(tmp_path, "Hello",
                             {"subject": "Test", "to": ["a@b.com"], "cc": [], "bcc": [], "thread_info": None})
            send(str(d))
            mime_text = mock_run.call_args[1]["input"]
            assert "In-Reply-To" not in mime_text
            assert "References" not in mime_text

    def test_send_includes_cc_header(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = None
            d = _write_draft(tmp_path, "Hello",
                             {"subject": "Test", "to": ["a@b.com"], "cc": ["cc@example.com"], "bcc": [],
                              "thread_info": None})
            send(str(d))
            assert "Cc: cc@example.com" in mock_run.call_args[1]["input"]

    def test_send_accepts_the_markdown_path_too(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = None
            d = _write_draft(tmp_path, "Hello",
                             {"subject": "Test", "to": ["a@b.com"], "cc": [], "bcc": [], "thread_info": None})
            assert send(str(d / "draft.md")) == "Email sent successfully"

    def test_send_errors_without_draft(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path):
            (tmp_path / "draft-empty").mkdir()
            assert send(str(tmp_path / "draft-empty")).startswith("Error: No draft found")
            assert send("/etc").startswith("Error: Not a draft")

    def test_a_draft_is_sent_once(self, tmp_path):
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = None
            d = _write_draft(tmp_path, "Hello",
                             {"subject": "Test", "to": ["a@b.com"], "cc": [], "bcc": [], "thread_info": None})
            assert send(str(d)) == "Email sent successfully"
            assert send(str(d)).startswith("Error:") and "already sent" in send(str(d))
            assert mock_run.call_count == 1


class TestInlineImageAllowlist:
    """Local images in markdown are only embedded from SENDMAIL_ALLOWED_UPLOAD_DIRECTORIES."""

    def _allow(self, monkeypatch, *dirs):
        monkeypatch.setattr("mcp_notmuch_sendmail.sendmail.SENDMAIL_ALLOWED_UPLOAD_DIRECTORIES",
                            [Path(d) for d in dirs])

    def test_allowed_image_is_embedded_as_cid(self, monkeypatch, tmp_path):
        self._allow(monkeypatch, tmp_path)
        img = tmp_path / "chart.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        html, images = markdown_to_html(f"![chart]({img})")
        assert "cid:" in html
        assert list(images.values()) == [img]

    def test_disabled_by_default(self, monkeypatch, tmp_path):
        self._allow(monkeypatch)  # empty allowlist = unset
        img = tmp_path / "chart.png"
        img.write_bytes(b"fake")
        try:
            markdown_to_html(f"![chart]({img})")
            assert False, "should have raised"
        except ValueError as e:
            assert "SENDMAIL_ALLOWED_UPLOAD_DIRECTORIES" in str(e)

    def test_image_outside_allowlist_is_refused(self, monkeypatch, tmp_path):
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        self._allow(monkeypatch, allowed)
        outside = tmp_path / "secret.png"
        outside.write_bytes(b"fake")
        try:
            markdown_to_html(f"![x]({outside})")
            assert False, "should have raised"
        except ValueError as e:
            assert "not inside" in str(e)

    def test_dotdot_cannot_escape_allowlist(self, monkeypatch, tmp_path):
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        self._allow(monkeypatch, allowed)
        outside = tmp_path / "secret.png"
        outside.write_bytes(b"fake")
        try:
            markdown_to_html(f"![x]({allowed}/../secret.png)")
            assert False, "should have raised"
        except ValueError as e:
            assert "not inside" in str(e)

    def test_relative_path_is_refused(self, monkeypatch, tmp_path):
        self._allow(monkeypatch, tmp_path)
        try:
            markdown_to_html("![x](chart.png)")
            assert False, "should have raised"
        except ValueError as e:
            assert "absolute" in str(e)

    def test_missing_image_is_an_error_not_silent(self, monkeypatch, tmp_path):
        self._allow(monkeypatch, tmp_path)
        try:
            markdown_to_html(f"![x]({tmp_path}/nope.png)")
            assert False, "should have raised"
        except ValueError as e:
            assert "not found" in str(e)

    def test_remote_and_data_uris_untouched(self, monkeypatch):
        self._allow(monkeypatch)  # even with embedding disabled
        html, images = markdown_to_html(
            "![a](https://example.com/a.png) ![b](data:image/png;base64,AAAA)")
        assert images == {}
        assert "https://example.com/a.png" in html

    def test_markdown_without_images_unaffected(self, monkeypatch):
        self._allow(monkeypatch)  # embedding disabled
        html, images = markdown_to_html("just **text**")
        assert images == {}

    def test_compose_returns_error_string_instead_of_raising(self, monkeypatch, tmp_path):
        self._allow(monkeypatch)  # disabled
        img = tmp_path / "x.png"
        img.write_bytes(b"fake")
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", tmp_path / "drafts"):
            result = compose("Subject", f"![x]({img})", ["a@b.com"])
        assert result.startswith("Error:")
        assert "SENDMAIL_ALLOWED_UPLOAD_DIRECTORIES" in result

    def test_send_embeds_image_as_inline_mime_part(self, monkeypatch, tmp_path):
        self._allow(monkeypatch, tmp_path)
        img = tmp_path / "dot.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        drafts = tmp_path / "drafts"
        with patch("mcp_notmuch_sendmail.sendmail.DRAFT_DIR", drafts):
            compose("Subject", f"![dot]({img})", ["a@b.com"])
            sent = {}

            def fake_run(cmd, input=None, **kwargs):
                sent["message"] = input

                class R:
                    returncode = 0
                return R()

            with patch("mcp_notmuch_sendmail.sendmail.subprocess.run", fake_run):
                result = send(str(_draft_dir(drafts)))
        assert result == "Email sent successfully"
        assert "Content-ID:" in sent["message"]
        assert "Content-Disposition: inline" in sent["message"]
        assert 'Content-Type: image/png' in sent["message"]
