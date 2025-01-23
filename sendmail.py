import tempfile, subprocess, hashlib, mimetypes, json, os
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

import markdown_it
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from bs4 import BeautifulSoup

### Constants ###
from core import SENDMAIL_FROM_EMAIL
MARKDOWN_IT_FEATURES = ["table", "strikethrough"]
MARKDOWN_IT_PLUGINS = [deflist_plugin, footnote_plugin, tasklists_plugin]

### Core Functions ###

def create_draft(markdown_text: str, metadata: dict, thread_info: dict = None, base_path: Path = None) -> dict:
    """Creates a draft from markdown content and metadata."""
    drafts_dir = Path('drafts')
    drafts_dir.mkdir(exist_ok=True)

    md_path = drafts_dir / 'draft.md'
    md_path.write_text(markdown_text)

    css_path = base_path / 'latex.css' if base_path else Path('latex.css')
    html, images = markdown_to_html(markdown_text, css_path=css_path, base_path=base_path, metadata=metadata)
    """Creates a draft from markdown content and metadata."""
    drafts_dir = Path('drafts')
    drafts_dir.mkdir(exist_ok=True)

    md_path = drafts_dir / 'draft.md'
    md_path.write_text(markdown_text)

    css_path = base_path / 'latex.css' if base_path else Path('latex.css')
    html, images = markdown_to_html(markdown_text, css_path=css_path, base_path=base_path, metadata=metadata)
    html_path = drafts_dir / 'draft.html'
    html_path.write_text(html)

    metadata_path = drafts_dir / 'draft.json'
    metadata_path.write_text(json.dumps(metadata, indent=2))

    return {'markdown': md_path, 'html': html_path, 'metadata': metadata_path, 'images': images}

def format_email_header(metadata):
    """Format email metadata as HTML."""
    parts = []
    
    if metadata.get('subject'):
        parts.append(f"<strong>Subject:</strong> {metadata['subject']}")
    if metadata.get('to'):
        parts.append(f"<strong>To:</strong> {', '.join(metadata['to'])}")
    if metadata.get('cc') and metadata['cc']:
        parts.append(f"<strong>Cc:</strong> {', '.join(metadata['cc'])}")
    if metadata.get('bcc') and metadata['bcc']:
        parts.append(f"<strong>Bcc:</strong> {', '.join(metadata['bcc'])}")
    
    if 'thread_info' in metadata and metadata['thread_info']:
        ti = metadata['thread_info']
        if ti.get('in_reply_to'):
            parts.append(f"<strong>In-Reply-To:</strong> {ti['in_reply_to']}")
    
    if parts:
        return f"<div class='email-header'>{' <br> '.join(parts)}<hr></div>"
    return ""

def markdown_to_html(markdown_text, css_path=None, base_path=None, extra_options=None, metadata=None):
    """Convert markdown to HTML using markdown-it-py"""
    css = css_path.read_text() if css_path else ''

    md = markdown_it.MarkdownIt('commonmark', {'html': True})
    for feature in MARKDOWN_IT_FEATURES:
        md = md.enable(feature)
    for plugin in MARKDOWN_IT_PLUGINS:
        md = md.use(plugin)

    html_content = md.render(markdown_text)

    if base_path:
        soup = BeautifulSoup(html_content, "html.parser")
        imgs = soup.findAll('img')
        images = {}

        for img in imgs:
            src = img['src']
            if src.startswith('data:'):
                continue
            elif not src.startswith('http'):
                content_id = f"{hashlib.md5(src.encode('utf-8')).hexdigest()[:6]}_{Path(src).name}"
                img_path = Path(base_path) / src

                if img_path.exists():
                    images[content_id] = img_path
                    img['src'] = f'cid:{content_id}'

        html_content = str(soup)
    else:
        images = {}

    """Convert markdown content to HTML with optional CSS styling.
    
    Args:
        markdown_text (str): The markdown content to convert
        css_path (Path, optional): Path to CSS file to include
        base_path (Path, optional): Base path for resolving relative image paths
        extra_options (dict, optional): Additional conversion options
        
    Returns:
        tuple: (html_string, dict_of_images)
    """
    css_content = css + '''
        /* Email header styles */
        .email-header {
            padding: 1em;
            background: #f5f5f5;
            margin-bottom: 2em;
        }
        .email-header hr {
            margin-top: 1em;
        }
    '''
    
    full_html = f"""<html>
<head>
    <meta charset="utf-8">
    <style>
        {css_content}
    </style>
</head>
<body>
    {format_email_header(metadata) if metadata else ''}
    <article>
        {html_content}
    </article>
</body>
</html>"""

    return full_html, images

def compose(subject: str, body_as_markdown: str, to: list, cc: list = None, bcc: list = None, thread_id: str = None) -> str:
    """Create an HTML email draft from markdown content, optionally as a reply to a thread"""
    thread_info = None
    if thread_id:
        from notmuchlib import get_thread_info
        thread_info = get_thread_info(thread_id)
        # If subject doesn't start with Re:, add it
        if not subject.lower().startswith('re:') and thread_info['subject'].lower().startswith('re:'):
            subject = f"Re: {subject}"
            
    draft = create_draft(
        markdown_text=body_as_markdown,
        metadata={
            'subject': subject,
            'to': to,
            'cc': cc or [],
            'bcc': bcc or [],
            'thread_info': thread_info
        },
        thread_info=thread_info,
        base_path=Path.cwd()
    )
    return f"Created drafts:\n- {draft['markdown']} (edit this)\n- {draft['html']} (preview)"

def send():
    """Send the previously composed email draft"""
    drafts_dir = Path('drafts')
    md_path = drafts_dir / 'draft.md'
    metadata_path = drafts_dir / 'draft.json'

    if not md_path.exists() or not metadata_path.exists():
        raise ValueError("No draft found - compose an email first")

    body_as_markdown = md_path.read_text()
    metadata = json.loads(metadata_path.read_text())
    base_path = Path.cwd()
    css_path = base_path / 'latex.css'
    html, images = markdown_to_html(body_as_markdown, css_path=css_path, base_path=base_path)

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
