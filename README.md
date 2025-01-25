# MCP Notmuch Sendmail

**Status: Works for me but is still very beta**

Let Claude be your email assistant! MCP Notmuch Sendmail connects Claude Desktop to your notmuch email database, allowing it to:

- Search and browse your email threads
- View conversations in a clean text format
- Compose new emails using markdown
- Reply to threads with smart deduplication of quoted content
- Create beautiful emails with LaTeX-inspired styling

Uses html2text for HTML email rendering and markdown-it for composing rich HTML emails with inline images.

![MCP Notmuch Sendmail in action](screenshot.png)

## Requirements

- A working notmuch database setup
- A configured sendmail command for sending emails
- Python 3.10+

## API

### Tools

- **find_email_thread**
  - Find email threads in the notmuch database
  - Input: `notmuch_search_query` (string)
  - Returns tab-separated list of threads with format:
  ```
  thread_id    date    subject    authors
  ```

- **view_email_thread**
  - View all messages for an email thread
  - Input: `thread_id` (string)
  - Returns conversation in text format with HTML->text conversion
  ```
  FROM: sender@example.com
  DATE: 2024-01-25
  Message content...
  - - -
  FROM: another@example.com
  DATE: 2024-01-24
  Earlier message...
  ```

- **compose_email**
  - Compose an HTML email draft from markdown
  - Inputs:
    - `subject` (string): Email subject
    - `body_as_markdown` (string): Email body in markdown
    - `to` (list): Recipient email addresses
    - `cc` (list, optional): CC recipients
    - `bcc` (list, optional): BCC recipients
    - `thread_id` (string, optional): Thread ID when replying
  - Creates draft files and returns paths:
  ```
  Created drafts:
  - drafts/draft.md (edit this)
  - drafts/draft.html (preview)
  ```

- **send_draft**
  - Sends the composed email draft
  - No input required
  - Returns success/error message

## Usage with Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "email": {
      "command": "uv",
      "args": ["--directory", "/path/to/mcp-notmuch-sendmail", "run", "server.py"],
      "env": {
        "NOTMUCH_DATABASE_PATH": "/path/to/your/notmuch/db",
        "NOTMUCH_REPLY_SEPARATORS": "On|Le|El|Am|В|Den",
        "SENDMAIL_FROM_EMAIL": "your.email@example.com",
        "SENDMAIL_EMAIL_SIGNATURE_HTML": "<p>Optional HTML signature</p>",
        "LOG_FILE_PATH": "/path/to/log/file.log"
      }
    }
  }
}
```

Environment Variables:

- `NOTMUCH_DATABASE_PATH`: Path to your notmuch database (required)
- `NOTMUCH_REPLY_SEPARATORS`: Pipe-separated list of text markers used to detect and deduplicate reply content (required)
- `SENDMAIL_FROM_EMAIL`: Your email address for the From: field (required)
- `SENDMAIL_EMAIL_SIGNATURE_HTML`: HTML signature to append to emails (optional)
- `LOG_FILE_PATH`: Path for logging file (optional)

## Installation

1. Clone repository:
```bash
git clone https://github.com/runekaagaard/mcp-notmuch-sendmail.git
```

2. Ensure you have uv
```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. Add email configuration to claude_desktop_config.json (see above)

## License

Mozilla Public License Version 2.0