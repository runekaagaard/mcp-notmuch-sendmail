"""Boot smoke test: the server module must import and register tools on any supported mcp SDK."""
import mcp_notmuch_sendmail.server as server


def test_server_boots_and_registers_tools():
    assert server.mcp is not None
    assert hasattr(server, "find_email_thread")
    assert hasattr(server, "view_email_thread")
    # conftest sets SENDMAIL_FROM_EMAIL, so the sending tools are registered too
    assert hasattr(server, "compose_new_email")
    assert hasattr(server, "send_email")
