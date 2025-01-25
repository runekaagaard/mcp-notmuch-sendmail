from pathlib import Path
from typing import List, Optional
from mcp.server.fastmcp import FastMCP

from core import SENDMAIL_EMAIL_SIGNATURE_HTML, log
from notmuchlib import find_threads, view_thread
from sendmail import compose, send

mcp = FastMCP("Notmuch Email Client")

SIGNATURE_NOTE = ". NEVER add the signature, it will be automatically added!" if SENDMAIL_EMAIL_SIGNATURE_HTML else ""

@mcp.tool(description="Find email threads in the notmuch database")
@log
def find_email_thread(notmuch_search_query: str) -> str:
    return find_threads(notmuch_search_query)

@mcp.tool(description="View all messages for an email thread")
def view_email_thread(thread_id: str) -> str:
    return view_thread(thread_id)

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

if __name__ == "__main__":
    mcp.run()
