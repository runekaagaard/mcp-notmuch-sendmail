import tempfile, subprocess, hashlib, mimetypes, json, os
from pathlib import Path
from typing import Optional, Dict, List
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

import markdown_it
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

### Constants ###
from mcp_notmuch_sendmail.core import (ROOT_DIR, DRAFT_DIR, SENDMAIL_FROM_EMAIL, SENDMAIL_EMAIL_SIGNATURE_HTML,
                                       SENDMAIL_ALLOWED_UPLOAD_DIRECTORIES)

MARKDOWN_IT_FEATURES = ["table", "strikethrough"]
MARKDOWN_IT_PLUGINS = [deflist_plugin, footnote_plugin, tasklists_plugin]

### Core Functions ###

def validate_image_path(src: str) -> tuple[Optional[str], Optional[Path]]:
    """Validate a local image path from markdown against SENDMAIL_ALLOWED_UPLOAD_DIRECTORIES.

    Returns (None, resolved_path) on success, (error_message, None) on failure.
    """
    if not SENDMAIL_ALLOWED_UPLOAD_DIRECTORIES:
        return (f"Inline image '{src}' refused: image embedding is disabled. "
                "Set SENDMAIL_ALLOWED_UPLOAD_DIRECTORIES to enable it.", None)

    path = Path(src).expanduser()
    if not path.is_absolute():
        return f"Inline image '{src}' refused: path must be absolute.", None

    path = path.resolve()
    if not any(path.is_relative_to(allowed) for allowed in SENDMAIL_ALLOWED_UPLOAD_DIRECTORIES):
        return f"Inline image '{src}' refused: not inside SENDMAIL_ALLOWED_UPLOAD_DIRECTORIES.", None

    if not path.is_file():
        return f"Inline image '{src}' not found.", None

    return None, path


def create_draft(markdown_text: str, metadata: Dict, thread_info: Optional[Dict] = None) -> Dict:
    """Creates a draft in its own directory under DRAFT_DIR, so drafts never collide."""
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    draft_dir = Path(tempfile.mkdtemp(prefix="draft-", dir=DRAFT_DIR))

    md_path = draft_dir / 'draft.md'
    md_path.write_text(markdown_text)

    css_path = ROOT_DIR / 'latex.css'
    html, images = markdown_to_html(markdown_text, css_path=css_path, metadata=metadata)
    html_path = draft_dir / 'draft.html'
    html_path.write_text(html)

    metadata_path = draft_dir / 'draft.json'
    metadata_path.write_text(json.dumps(metadata, indent=2))

    return {'dir': draft_dir, 'markdown': md_path, 'html': html_path, 'metadata': metadata_path, 'images': images}


def resolve_draft(draft: str) -> tuple[Optional[str], Optional[Path]]:
    """Accepts a draft directory or any file inside it. Returns (None, draft_dir) or (error, None)."""
    path = Path(draft).expanduser().resolve()
    draft_dir = path if path.is_dir() else path.parent
    root = DRAFT_DIR.resolve()
    if draft_dir == root or not draft_dir.is_relative_to(root):
        return f"Not a draft: {draft} (drafts live in {DRAFT_DIR})", None
    if not (draft_dir / 'draft.md').is_file() or not (draft_dir / 'draft.json').is_file():
        return f"No draft found at {draft}", None
    if (draft_dir / 'sent').exists():
        return f"Draft {draft_dir} was already sent", None
    return None, draft_dir


def read_body(body_as_markdown: Optional[str], body_file: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """The body comes either inline or from a file. Returns (None, markdown) or (error, None)."""
    if (body_as_markdown is None) == (body_file is None):
        return "Pass exactly one of body_as_markdown and body_file", None
    if body_as_markdown is not None:
        return None, body_as_markdown
    path = Path(body_file).expanduser()
    if not path.is_absolute():
        return f"body_file must be an absolute path: {body_file}", None
    path = path.resolve()
    if not any(path.is_relative_to(d) for d in [DRAFT_DIR.resolve(), *SENDMAIL_ALLOWED_UPLOAD_DIRECTORIES]):
        return f"body_file refused: {body_file} is not inside DRAFT_DIR or SENDMAIL_ALLOWED_UPLOAD_DIRECTORIES", None
    if not path.is_file():
        return f"body_file not found: {body_file}", None
    return None, path.read_text()

def markdown_to_html(markdown_text: str, css_path: Optional[Path] = None, extra_options: Optional[Dict] = None,
                     metadata: Optional[Dict] = None) -> tuple[str, Dict]:
    """Convert markdown content to HTML with optional CSS styling."""
    css = css_path.read_text() if css_path else ''

    md = markdown_it.MarkdownIt('commonmark', {'html': True})
    for feature in MARKDOWN_IT_FEATURES:
        md = md.enable(feature)
    for plugin in MARKDOWN_IT_PLUGINS:
        md = md.use(plugin)

    html_content = md.render(markdown_text)

    images = {}
    soup = BeautifulSoup(html_content, "html.parser")
    imgs = soup.findAll('img')

    for img in imgs:
        src = img['src']
        if src.startswith('data:') or src.startswith('http'):
            continue

        error, img_path = validate_image_path(src)
        if error:
            raise ValueError(error)

        content_id = f"{hashlib.md5(src.encode('utf-8')).hexdigest()[:6]}_{img_path.name}"
        images[content_id] = img_path
        img['src'] = f'cid:{content_id}'

    html_content = str(soup)

    # Setup Jinja2 environment
    env = Environment(loader=FileSystemLoader(ROOT_DIR))
    template = env.get_template('email_template_draft.j2' if metadata else 'email_template.j2')

    # Render the template
    full_html = template.render(content=html_content, css=css, metadata=metadata,
                                signature=SENDMAIL_EMAIL_SIGNATURE_HTML)

    return full_html, images

def compose(subject: str, body_as_markdown: Optional[str], to: List[str], cc: Optional[List[str]] = None,
            bcc: Optional[List[str]] = None, thread_id: Optional[str] = None,
            body_file: Optional[str] = None) -> str:
    """Create an HTML email draft from markdown content, optionally as a reply to a thread"""
    error, markdown_text = read_body(body_as_markdown, body_file)
    if error:
        return f"Error: {error}"

    thread_info = None
    if thread_id:
        from mcp_notmuch_sendmail.notmuchlib import get_thread_info
        thread_info = get_thread_info(thread_id)

    metadata = {
        'subject': subject,
        'to': to,
        'cc': cc or [],
        'bcc': bcc or [],
        'thread_info': thread_info
    }
    try:
        draft = create_draft(
            markdown_text=markdown_text,
            metadata=metadata)
    except ValueError as e:
        return f"Error: {e}"
    return (f"Created draft {draft['dir']}\n"
            f"- {draft['markdown']} (edit this directly, then call update_preview)\n"
            f"- {draft['html']} (preview)\n"
            f"Send with send_email(\"{draft['dir']}\")")

def update_preview(draft: str) -> str:
    """Re-render a draft's HTML preview after its draft.md was edited directly"""
    error, draft_dir = resolve_draft(draft)
    if error:
        return f"Error: {error}"
    metadata = json.loads((draft_dir / 'draft.json').read_text())
    try:
        html, _ = markdown_to_html((draft_dir / 'draft.md').read_text(), css_path=ROOT_DIR / 'latex.css',
                                   metadata=metadata)
    except ValueError as e:
        return f"Error: {e}"
    (draft_dir / 'draft.html').write_text(html)
    return f"Updated {draft_dir / 'draft.html'}"

def send(draft: str):
    """Send a composed draft"""
    error, draft_dir = resolve_draft(draft)
    if error:
        return f"Error: {error}"

    body_as_markdown = (draft_dir / 'draft.md').read_text()
    metadata = json.loads((draft_dir / 'draft.json').read_text())
    css_path = ROOT_DIR / 'latex.css'
    try:
        html, images = markdown_to_html(body_as_markdown, css_path=css_path)
    except ValueError as e:
        return f"Error: {e}"

    # Create email message
    msg = MIMEMultipart('alternative')

    # Add threading headers if this is a reply
    if 'thread_info' in metadata and metadata['thread_info']:
        thread_info = metadata['thread_info']
        if thread_info['references']:
            msg['References'] = thread_info['references']
            if thread_info['message_id']:
                msg['References'] = f"{msg['References']} {thread_info['message_id']}"
        elif thread_info['message_id']:
            msg['References'] = thread_info['message_id']

        if thread_info['message_id']:
            msg['In-Reply-To'] = thread_info['message_id']
    msg['From'] = SENDMAIL_FROM_EMAIL
    msg['To'] = ', '.join(metadata['to'])
    if metadata['cc']:
        msg['Cc'] = ', '.join(metadata['cc'])
    if metadata['bcc']:
        msg['Bcc'] = ', '.join(metadata['bcc'])
    msg['Subject'] = metadata['subject']

    msg_related = MIMEMultipart('related')
    msg_related.attach(MIMEText(html, 'html'))

    if images:
        for cid, image_path in images.items():
            with open(image_path, 'rb') as img:
                mime_type = mimetypes.guess_type(image_path)[0]
                maintype, subtype = mime_type.split('/')
                img_data = img.read()
                image = MIMEImage(img_data, _subtype=subtype)
                image.add_header('Content-ID', f'<{cid}>')
                image.add_header('Content-Disposition', 'inline')
                msg_related.attach(image)

    msg.attach(msg_related)

    try:
        with tempfile.NamedTemporaryFile(mode='w+') as tmp:
            tmp.write(msg.as_string())
            tmp.flush()
            subprocess.run(['sendmail', '-t'], input=Path(tmp.name).read_text(), text=True, check=True,
                           capture_output=True)
        (draft_dir / 'sent').touch()  # a draft is sent once
        return "Email sent successfully"
    except subprocess.CalledProcessError as e:
        return f"Error sending email: {e.stderr}"
