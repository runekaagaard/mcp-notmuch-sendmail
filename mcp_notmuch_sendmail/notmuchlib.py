import email, re, os, subprocess
from datetime import datetime
from typing import Dict, Optional
import html2text
import notmuch2
from mcp_notmuch_sendmail.core import ROOT_DIR, NOTMUCH_DATABASE_PATH, NOTMUCH_REPLY_SEPARATORS

# Optional script to sync emails
NOTMUCH_SYNC_SCRIPT = os.environ.get("NOTMUCH_SYNC_SCRIPT", None)

### Core Functions ###

def fmt_timestamp(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")

def message_to_text(message):
    def normalize_empty_lines(text):
        return re.sub(r'(\n\s*){2,}', '\n\n', text)

    def extract_reply(text):
        result = []
        for line in text.splitlines():
            for reply_separator in NOTMUCH_REPLY_SEPARATORS:
                if line.lower().startswith(reply_separator):
                    return "\n".join(result).strip()
            result.append(line)
        return text

    from_addr = message.header('From').strip()
    date_str = fmt_timestamp(message.date)

    result = [f"FROM: {from_addr}", f"DATE: {date_str}"]

    with message.path.open("rb") as f:
        msg = email.message_from_binary_file(f)

    for part in msg.walk():
        if part.get_content_type() == "text/html":
            html_payload = part.get_payload(decode=True)
            if html_payload is None:
                continue
            try:
                html = html_payload.decode("utf-8")
            except UnicodeDecodeError:
                html = html_payload.decode("latin1")
            h = html2text.HTML2Text()
            h.body_width = 0
            h.emphasis_mark = ""
            h.strong_mark = ""
            plain = h.handle(html)
            plain = normalize_empty_lines(plain)
            plain = extract_reply(plain)
            result.append(plain)

    return "\n".join(result)

def find_threads(notmuch_search_query: str, max_threads: int) -> str:
    db = notmuch2.Database(NOTMUCH_DATABASE_PATH, mode='ro')
    threads = db.threads(notmuch_search_query, sort=notmuch2.Database.SORT.NEWEST_FIRST)

    result = []
    for i, thread in enumerate(threads):
        if i == max_threads:
            break
        parts = [
            str(thread.threadid),
            fmt_timestamp(thread.last),
            str(thread.subject)[:80],
            ",".join([x.split()[0].lower() for x in str(thread.authors).split(",")])[:40],
        ]
        result.append("\t".join(parts))

    db.close()

    return "\n".join(result)

def get_thread_info(thread_id: str) -> Dict:
    """Get threading information from the latest message in a thread.
    
    Args:
        thread_id: The notmuch thread ID
        
    Returns:
        dict with keys: message_id, references, in_reply_to, subject
    """
    db = notmuch2.Database(NOTMUCH_DATABASE_PATH, mode='ro')
    messages = db.messages(f'thread:{thread_id}', sort=notmuch2.Database.SORT.NEWEST_FIRST)

    # Get the latest message
    latest = next(messages)

    info = {
        'message_id': latest.header('Message-ID'),
        'references': latest.header('References'),
        'in_reply_to': latest.header('In-Reply-To'),
        'subject': latest.header('Subject'),
        'from': latest.header('From'),
        'reply_to': latest.header('Reply-To')
    }

    db.close()

    return info

def view_thread(thread_id: str) -> str:
    db = notmuch2.Database(NOTMUCH_DATABASE_PATH, mode='ro')
    messages = db.messages(f'thread:{thread_id}', sort=notmuch2.Database.SORT.OLDEST_FIRST)
    result = "- - -\n".join([message_to_text(message) for message in messages])

    db.close()

    return result

def fetch_new_emails() -> str:
    """Sync emails by executing the script specified in NOTMUCH_SYNC_SCRIPT.
    
    Returns:
        str: Output from the script, including both stdout and stderr
    """
    if not NOTMUCH_SYNC_SCRIPT:
        return "NOTMUCH_SYNC_SCRIPT environment variable not set"
    
    script_path = NOTMUCH_SYNC_SCRIPT
    if not os.path.isabs(script_path):
        script_path = ROOT_DIR / script_path
    
    if not os.path.exists(script_path):
        return f"Script not found: {script_path}"
    
    try:
        # Check if the script is executable
        if not os.access(script_path, os.X_OK):
            # Try to make it executable
            try:
                os.chmod(script_path, 0o755)  # rwxr-xr-x
            except Exception:
                return f"Script is not executable and couldn't be made executable: {script_path}"
        
        # Execute the script directly
        result = subprocess.run([script_path], capture_output=True, text=True)
        output = "STDOUT:\n" + result.stdout
        if result.stderr:
            output += "\n\nSTDERR:\n" + result.stderr
        return output
    except Exception as e:
        return f"Error executing notmuch sync script: {str(e)}"
