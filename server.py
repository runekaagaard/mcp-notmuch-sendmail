from pathlib import Path
from core import parse_arguments, SENDMAIL_FROM_EMAIL, SENDMAIL_EMAIL_SIGNATURE_HTML
from mcp.server.fastmcp import FastMCP
from notmuchlib import find_threads, view_thread
from sendmail import compose, send, create_draft

### MCP Setup ###
mcp = FastMCP("Notmuch Email Client")

# Prepare tool descriptions
SIGNATURE_NOTE = ". A signature will be automatically added." if SENDMAIL_EMAIL_SIGNATURE_HTML else ""

@mcp.tool(description="Find email threads in the notmuch database")
def find_email_thread(notmuch_search_query: str) -> str:
    return find_threads(notmuch_search_query)

@mcp.tool(description="View all messages for an email thread")
def view_email_thread(thread_id: str) -> str:
    return view_thread(thread_id)

@mcp.tool(description=f"Compose a new email draft from markdown{SIGNATURE_NOTE}")
def compose_new_email(subject: str, body_as_markdown: str, to: list, cc: list = None, bcc: list = None) -> str:
    return compose(subject, body_as_markdown, to, cc, bcc, thread_id=None)

@mcp.tool(description=f"Compose a reply to an existing email thread{SIGNATURE_NOTE}")
def compose_email_reply(thread_id: str, subject: str, body_as_markdown: str, to: list, cc: list = None,
                        bcc: list = None) -> str:
    return compose(subject, body_as_markdown, to, cc, bcc, thread_id)

@mcp.tool(description="Sends the composed email draft")
def send_email() -> str:
    return send()

if __name__ == "__main__":
    test_mode = parse_arguments()

    if test_mode:
        draft = create_draft(markdown_text=Path('email_example.md').read_text(), metadata={
            'subject': 'Test Email',
            'to': [SENDMAIL_FROM_EMAIL],
            'cc': [],
            'bcc': []
        }, base_path=Path.cwd())
    else:
        mcp.run()
