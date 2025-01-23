import base64, re, quopri
from datetime import datetime
import html2text
from notmuch import Query, Database
from core import NOTMUCH_DATABASE_PATH, NOTMUCH_REPLY_SEPARATORS, log

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

    def decode_qp(text):
        try:
            return quopri.decodestring(text.encode('utf-8')).decode('utf-8')
        except UnicodeDecodeError:
            return quopri.decodestring(text.encode('utf-8')).decode('latin1')

    from_addr = message.get_header('From').strip()
    date_str = fmt_timestamp(message.get_date())

    result = [f"FROM: {from_addr}", f"DATE: {date_str}"]
    parts = list(message.get_message_parts())

    for part in parts:
        if part.get_content_type() == "text/html":
            html = part.get_payload()
            encoding = part.get('Content-Transfer-Encoding', '').lower()
            if encoding == "base64":
                html = base64.b64decode(html).decode("utf-8")
            elif encoding == "quoted-printable":
                html = decode_qp(html)
            h = html2text.HTML2Text()
            h.body_width = 0
            h.emphasis_mark = ""
            h.strong_mark = ""
            plain = h.handle(html)
            plain = normalize_empty_lines(plain)
            plain = extract_reply(plain)
            result.append(plain)

    return "\n".join(result)

@log
def find_threads(notmuch_search_query: str) -> str:
    db = Database(NOTMUCH_DATABASE_PATH)
    query = Query(db, notmuch_search_query)
    query.set_sort(Query.SORT.NEWEST_FIRST)
    threads = query.search_threads()

    result = []
    for i, thread in enumerate(threads):
        if i == 25:
            break
        parts = [
            thread.get_thread_id(),
            fmt_timestamp(thread.get_newest_date()),
            thread.get_subject()[:80],
            ",".join([x.split()[0].lower() for x in thread.get_authors().split(",")])[:40],
        ]
        result.append("\t".join(parts))

    db.close()
    del query
    del db

    return "\n".join(result)

@log
@log
def get_thread_info(thread_id: str) -> dict:
    """Get threading information from the latest message in a thread.
    
    Args:
        thread_id: The notmuch thread ID
        
    Returns:
        dict with keys: message_id, references, in_reply_to, subject
    """
    db = Database(NOTMUCH_DATABASE_PATH)
    query = Query(db, f'thread:{thread_id}')
    query.set_sort(Query.SORT.NEWEST_FIRST)
    messages = query.search_messages()
    
    # Get the latest message
    latest = next(messages)
    
    info = {
        'message_id': latest.get_header('Message-ID'),
        'references': latest.get_header('References'),
        'in_reply_to': latest.get_header('In-Reply-To'),
        'subject': latest.get_header('Subject'),
        'from': latest.get_header('From'),
        'reply_to': latest.get_header('Reply-To')
    }
    
    db.close()
    del query
    del db
    
    return info

@log
def view_thread(thread_id: str) -> str:
    db = Database(NOTMUCH_DATABASE_PATH)
    query = Query(db, f'thread:{thread_id}')
    query.set_sort(Query.SORT.OLDEST_FIRST)
    messages = query.search_messages()
    result = "- - -\n".join([message_to_text(message) for message in messages])

    db.close()
    del query
    del db

    return result
