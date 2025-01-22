import argparse
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from notmuch import find_threads, view_thread
from sendmail import compose, send, create_draft

### MCP Setup ###
mcp = FastMCP("Notmuch Email Client")

@mcp.tool(description="Find email threads in the notmuch database")
def find_email_thread(notmuch_search_query: str) -> str:
    return find_threads(notmuch_search_query)

@mcp.tool(description="View all messages for an email thread")
def view_email_thread(thread_id: str) -> str:
    return view_thread(thread_id)

@mcp.tool(description="Compose an html email draft from markdown")
def compose_email(subject: str, body_as_markdown: str, to: list, cc: list = None, bcc: list = None) -> str:
    return compose(subject, body_as_markdown, to, cc, bcc)

@mcp.tool(description="Sends the composed email draft")
def send_draft() -> str:
    return send()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--test-html', action='store_true', help='Generate HTML from email_example.md')
    args = parser.parse_args()

    if args.test_html:
        draft = create_draft(
            markdown_text=Path('email_example.md').read_text(),
            metadata={
                'subject': 'Test Email',
                'to': [os.environ["FROM_EMAIL"]],
                'cc': [],
                'bcc': []
            },
            base_path=Path.cwd()
        )
    else:
        mcp.run()