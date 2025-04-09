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
from mcp_notmuch_sendmail.core import ROOT_DIR, DRAFT_DIR, SENDMAIL_FROM_EMAIL, SENDMAIL_EMAIL_SIGNATURE_HTML

MARKDOWN_IT_FEATURES = ["table", "strikethrough"]
MARKDOWN_IT_PLUGINS = [deflist_plugin, footnote_plugin, tasklists_plugin]

### Core Functions ###

def create_draft(markdown_text: str, metadata: Dict, thread_info: Optional[Dict] = None) -> Dict:
    """Creates a draft from markdown content and metadata."""
    DRAFT_DIR.mkdir(exist_ok=True)

    md_path = DRAFT_DIR / 'draft.md'
    md_path.write_text(markdown_text)

    css_path = ROOT_DIR / 'latex.css'
    html, images = markdown_to_html(markdown_text, css_path=css_path, metadata=metadata)
    html_path = DRAFT_DIR / 'draft.html'
    html_path.write_text(html)

    metadata_path = DRAFT_DIR / 'draft.json'
    metadata_path.write_text(json.dumps(metadata, indent=2))

    return {'markdown': md_path, 'html': html_path, 'metadata': metadata_path, 'images': images}

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
        if src.startswith('data:'):
            continue
        elif not src.startswith('http'):
            content_id = f"{hashlib.md5(src.encode('utf-8')).hexdigest()[:6]}_{Path(src).name}"
            img_path = ROOT_DIR / src

            if img_path.exists():
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

def compose(subject: str, body_as_markdown: str, to: List[str], cc: Optional[List[str]] = None,
            bcc: Optional[List[str]] = None, thread_id: Optional[str] = None) -> str:
    """Create an HTML email draft from markdown content, optionally as a reply to a thread"""
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
    draft = create_draft(
        markdown_text=body_as_markdown,
        metadata=metadata)
    return f"Created drafts:\n- {draft['markdown']} (edit this)\n- {draft['html']} (preview)"

def send():
    """Send the previously composed email draft"""
    md_path = DRAFT_DIR / 'draft.md'
    metadata_path = DRAFT_DIR / 'draft.json'

    if not md_path.exists() or not metadata_path.exists():
        raise ValueError("No draft found - compose an email first")

    body_as_markdown = md_path.read_text()
    metadata = json.loads(metadata_path.read_text())
    css_path = ROOT_DIR / 'latex.css'
    html, images = markdown_to_html(body_as_markdown, css_path=css_path)

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
        return "Email sent successfully"
    except subprocess.CalledProcessError as e:
        return f"Error sending email: {e.stderr}"
