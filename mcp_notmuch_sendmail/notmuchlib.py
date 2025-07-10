import base64, re, quopri, os, subprocess, tempfile
from datetime import datetime
from typing import Dict, Optional, List, Tuple
import html2text
from pathlib import Path
from notmuch import Query, Database
from unstructured.partition.auto import partition
from mcp_notmuch_sendmail.core import ROOT_DIR, NOTMUCH_DATABASE_PATH, NOTMUCH_REPLY_SEPARATORS, READ_ATTACHMENT_PAGE_SIZE

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

    def decode_qp(text):
        try:
            return quopri.decodestring(text.encode('utf-8')).decode('utf-8')
        except UnicodeDecodeError:
            return quopri.decodestring(text.encode('utf-8')).decode('latin1')

    from_addr = (message.get_header('From') or "Unknown").strip()
    date_str = fmt_timestamp(message.get_date())

    result = [f"FROM: {from_addr}", f"DATE: {date_str}"]
    
    # Get attachment list
    attachments = get_message_attachments(message)
    if attachments:
        result.append(f"ATTACHMENTS: {', '.join(attachments)}")
    parts = list(message.get_message_parts())

    for part in parts:
        content_type = part.get_content_type()
        if content_type == "text/html":
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
        elif content_type == "text/plain":
            # Handle plain text parts as well
            text = part.get_payload()
            encoding = part.get('Content-Transfer-Encoding', '').lower()
            if encoding == "base64":
                text = base64.b64decode(text).decode("utf-8")
            elif encoding == "quoted-printable":
                text = decode_qp(text)
            text = normalize_empty_lines(text)
            text = extract_reply(text)
            result.append(text)

    return "\n".join(result)

def find_threads(notmuch_search_query: str) -> str:
    db = Database(NOTMUCH_DATABASE_PATH)
    query = Query(db, notmuch_search_query)
    query.set_sort(Query.SORT.NEWEST_FIRST)
    threads = query.search_threads()

    result = []
    for i, thread in enumerate(threads):
        if i == 100:
            break
        parts = [
            thread.get_thread_id(),
            fmt_timestamp(thread.get_newest_date()),
            (thread.get_subject() or "(No Subject)")[:80],
            ",".join([x.split()[0].lower() for x in (thread.get_authors() or "Unknown").split(",")])[:40],
        ]
        result.append("\t".join(parts))

    db.close()
    del query
    del db

    return "\n".join(result)

def get_thread_info(thread_id: str) -> Dict:
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
        'message_id': latest.get_header('Message-ID') or '',
        'references': latest.get_header('References') or '',
        'in_reply_to': latest.get_header('In-Reply-To') or '',
        'subject': latest.get_header('Subject') or '',
        'from': latest.get_header('From') or '',
        'reply_to': latest.get_header('Reply-To') or ''
    }

    db.close()
    del query
    del db

    return info

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

def view_threads(thread_ids: list) -> str:
    """View multiple email threads with clear separation and thread ID display.
    
    Args:
        thread_ids: List of thread IDs to view
        
    Returns:
        str: Formatted output with thread separators and IDs
    """
    results = []

    for thread_id in thread_ids:
        # Simple header with thread ID
        header = f"## THREAD: {thread_id}"
        thread_content = view_thread(thread_id)
        results.append(f"{header}\n{thread_content}")

    # Join threads with simple double newline
    return "\n\n".join(results)

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

def get_message_attachments(message) -> List[str]:
    """Get list of attachment filenames from a message using notmuch's native capabilities.
    
    Args:
        message: Notmuch message object
        
    Returns:
        List of attachment filenames
    """
    attachments = []
    
    try:
        parts = list(message.get_message_parts())
        
        for part in parts:
            # Get the filename from the part
            filename = part.get_filename()
            
            # Also check Content-Disposition for attachment info
            content_disposition = part.get('Content-Disposition', '')
            
            # Skip inline text/html and text/plain parts that are not attachments
            content_type = part.get_content_type()
            if not filename and content_type in ['text/plain', 'text/html'] and 'attachment' not in content_disposition:
                continue
                
            # If we have a filename, it's an attachment
            if filename and filename not in attachments:
                attachments.append(filename)
        
        return attachments
    except Exception:
        # If something fails, fall back to empty list
        return []

def read_attachment_from_thread(thread_id: str, filename: str, page: int = 0) -> str:
    """Read content from a specific attachment in a thread.
    
    Args:
        thread_id: The notmuch thread ID
        filename: Name of the attachment to read
        page: Page number for pagination (0-based)
        
    Returns:
        Extracted text content with pagination info if applicable
    """
    db = Database(NOTMUCH_DATABASE_PATH)
    query = Query(db, f'thread:{thread_id}')
    query.set_sort(Query.SORT.NEWEST_FIRST)  # Start with newest message
    messages = query.search_messages()
    
    found_count = 0
    attachment_content = None
    
    try:
        for message in messages:
            parts = list(message.get_message_parts())
            
            # Look through parts for our attachment
            for part in parts:
                part_filename = part.get_filename()
                
                if part_filename == filename:
                    found_count += 1
                    
                    # Keep the most recent (first found)
                    if attachment_content is None:
                        # Get the attachment data
                        payload = part.get_payload(decode=True)
                        
                        if payload:
                            # Save to temp file and extract text using unstructured
                            with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False) as tmp:
                                tmp.write(payload)
                                tmp_path = tmp.name
                            
                            try:
                                # Use unstructured to extract text from the attachment
                                elements = partition(filename=tmp_path)
                                attachment_content = "\n".join([str(el) for el in elements])
                            finally:
                                # Clean up temp file
                                os.unlink(tmp_path)
        
        if attachment_content is None:
            return f"Attachment '{filename}' not found in thread {thread_id}"
        
        # Handle pagination
        total_chars = len(attachment_content)
        total_pages = (total_chars + READ_ATTACHMENT_PAGE_SIZE - 1) // READ_ATTACHMENT_PAGE_SIZE
        
        # Add note if multiple files with same name
        prefix = ""
        if found_count > 1:
            prefix = f"[Note: Found {found_count} files named '{filename}', reading the most recent one]\n\n"
        
        if total_pages > 1:
            start = page * READ_ATTACHMENT_PAGE_SIZE
            end = min(start + READ_ATTACHMENT_PAGE_SIZE, total_chars)
            
            if page >= total_pages:
                return f"Error: Page {page} does not exist. Document has {total_pages} pages."
            
            page_content = attachment_content[start:end]
            return f"Reading page {page + 1} of {total_pages}\n{prefix}\n{page_content}"
        else:
            return f"{prefix}{attachment_content}"
            
    finally:
        db.close()
        del query
        del db
