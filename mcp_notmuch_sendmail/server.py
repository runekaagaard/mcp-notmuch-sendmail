from pathlib import Path
from typing import List, Optional
from functools import wraps
from mcp.server.fastmcp import FastMCP

from mcp_notmuch_sendmail.core import SENDMAIL_EMAIL_SIGNATURE_HTML, DRAFT_DIR, log
from mcp_notmuch_sendmail.notmuchlib import find_threads, view_thread, view_threads, fetch_new_emails, read_attachment_from_thread, NOTMUCH_SYNC_SCRIPT
from mcp_notmuch_sendmail.sendmail import compose, send

def safe_json_output(func):
    """Decorator that ensures function output is always JSON-safe by cleaning any problematic Unicode."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            # Clean the result to ensure it's JSON-serializable
            if isinstance(result, str):
                cleaned = result.encode('utf-8', errors='ignore').decode('utf-8')
                # Truncate very long responses to prevent timeouts
                if len(cleaned) > 100000:  # 100KB limit
                    cleaned = cleaned[:100000] + "\n\n[Response truncated - too large]"
                return cleaned
            else:
                # For non-string results, convert to string first then clean
                return str(result).encode('utf-8', errors='ignore').decode('utf-8')
        except Exception as e:
            # If the function itself fails, return a safe error message
            error_msg = f"Error in {func.__name__}: {str(e)}"
            return error_msg.encode('utf-8', errors='ignore').decode('utf-8')

    return wrapper

mcp = FastMCP("Notmuch Email Client")

SIGNATURE_NOTE = ". NEVER write an email signature, it will be automatically added after your content!" if SENDMAIL_EMAIL_SIGNATURE_HTML else ""

@mcp.tool(description="Find email threads in the notmuch database. Has a 50 thread limit")
@safe_json_output
@log
def find_email_thread(notmuch_search_query: str) -> str:
    return find_threads(notmuch_search_query)

@mcp.tool(description="View all messages for an email thread")
@safe_json_output
def view_email_thread(thread_id: str) -> str:
    return view_thread(thread_id)

@mcp.tool(description="View all messages for multiple email threads with clear separation and thread ID display")
@safe_json_output
def view_email_threads(thread_ids: List[str]) -> str:
    return view_threads(thread_ids)

@mcp.tool(description=f"Compose a new email draft from markdown{SIGNATURE_NOTE}")
@safe_json_output
@log
def compose_new_email(subject: str, body_as_markdown: str, to: List[str], cc: Optional[List[str]] = None,
                      bcc: Optional[List[str]] = None) -> str:
    return compose(subject, body_as_markdown, to, cc, bcc, thread_id=None)

@mcp.tool(description=f"Compose a reply to an existing email thread{SIGNATURE_NOTE}")
@safe_json_output
@log
def compose_email_reply(thread_id: str, subject: str, body_as_markdown: str, to: List[str],
                        cc: Optional[List[str]] = None, bcc: Optional[List[str]] = None) -> str:
    return compose(subject, body_as_markdown, to, cc, bcc, thread_id)

@mcp.tool(description="Sends the composed email draft")
@safe_json_output
@log
def send_email() -> str:
    return send()

@mcp.tool(description="Read content from an email attachment with pagination support")
@safe_json_output
@log
def read_email_attachment(thread_id: str, filename: str, page: int = 0) -> str:
    """Read attachment content with pagination.
    
    Args:
        thread_id: The email thread ID
        filename: The attachment filename to read
        page: Page number (0-based) for paginated reading
    
    Returns:
        Extracted text content with pagination info if applicable
    """
    return read_attachment_from_thread(thread_id, filename, page)

if NOTMUCH_SYNC_SCRIPT is not None:

    @mcp.tool(description="Sync emails by running the configured script")
    @safe_json_output
    @log
    def sync_emails() -> str:
        return fetch_new_emails()

def main():
    """Main entry point for the mcp-notmuch-sendmail package."""
    mcp.run()

if __name__ == "__main__":
    main()
