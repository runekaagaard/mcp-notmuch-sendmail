from pathlib import Path
from typing import List, Optional
try:
    from mcp.server.mcpserver import MCPServer
except ModuleNotFoundError:
    from mcp.server import FastMCP as MCPServer

from mcp_notmuch_sendmail.core import SENDMAIL_FROM_EMAIL, SENDMAIL_EMAIL_SIGNATURE_HTML, DRAFT_DIR, log
from mcp_notmuch_sendmail.notmuchlib import find_threads, view_thread, fetch_new_emails, NOTMUCH_SYNC_SCRIPT
from mcp_notmuch_sendmail.sendmail import compose, send

mcp = MCPServer("Notmuch Email Client")

SIGNATURE_NOTE = ". NEVER write an email signature, it will be automatically added after your content!" if SENDMAIL_EMAIL_SIGNATURE_HTML else ""

@mcp.tool(description="Find email threads in the notmuch database. "
                      "Returns tab-separated list with thread_id, date, subject, authors. "
                      "Use max_threads to control how many results are returned (default: 25).")
@log
def find_email_thread(notmuch_search_query: str, max_threads: int = 25) -> str:
    return find_threads(notmuch_search_query, max_threads)

@mcp.tool(description="View all messages for an email thread")
def view_email_thread(thread_id: str) -> str:
    return view_thread(thread_id)

if SENDMAIL_FROM_EMAIL:
    @mcp.tool(description=f"Compose a new email draft from markdown{SIGNATURE_NOTE}")
    @log
    def compose_new_email(subject: str, body_as_markdown: str, to: List[str], cc: Optional[List[str]] = None,
                          bcc: Optional[List[str]] = None) -> str:
        return compose(subject, body_as_markdown, to, cc, bcc, thread_id=None)

    @mcp.tool(description=f"Compose a reply to an existing email thread{SIGNATURE_NOTE}")
    @log
    def compose_email_reply(thread_id: str, subject: str, body_as_markdown: str, to: List[str],
                            cc: Optional[List[str]] = None, bcc: Optional[List[str]] = None) -> str:
        return compose(subject, body_as_markdown, to, cc, bcc, thread_id)

    @mcp.tool(description="Sends the composed email draft")
    @log
    def send_email() -> str:
        return send()

if NOTMUCH_SYNC_SCRIPT is not None:

    @mcp.tool(description="Sync emails by running the configured script")
    @log
    def sync_emails() -> str:
        return fetch_new_emails()

def main():
    """Main entry point for the mcp-notmuch-sendmail package."""
    import argparse
    parser = argparse.ArgumentParser(description="MCP Notmuch Sendmail Server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default="stdio",
                        help="Transport type (default: stdio). streamable-http is the recommended HTTP "
                             "transport, sse is supported for legacy clients.")
    parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP transports (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port for HTTP transports (default: 8000)")
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port)

if __name__ == "__main__":
    main()
