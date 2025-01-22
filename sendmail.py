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
FROM_EMAIL = os.environ["FROM_EMAIL"]
MARKDOWN_IT_FEATURES = ["table", "strikethrough"]
MARKDOWN_IT_PLUGINS = [deflist_plugin, footnote_plugin, tasklists_plugin]

### Core Functions ###

def create_draft(markdown_text: str, metadata: dict, base_path: Path = None) -> dict:
    """Creates a draft from markdown content and metadata."""
    drafts_dir = Path('drafts')
    drafts_dir.mkdir(exist_ok=True)

    md_path = drafts_dir / 'draft.md'
    md_path.write_text(markdown_text)

    css_path = base_path / 'latex.css' if base_path else Path('latex.css')
    html, images = markdown_to_html(markdown_text, css_path=css_path, base_path=base_path)
    html_path = drafts_dir / 'draft.html'
    html_path.write_text(html)

    metadata_path = drafts_dir / 'draft.json'
    metadata_path.write_text(json.dumps(metadata, indent=2))

    return {'markdown': md_path, 'html': html_path, 'metadata': metadata_path, 'images': images}

def markdown_to_html(markdown_text, css_path=None, base_path=None, extra_options=None):
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

    full_html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>{css}</style>
    </head>
    <body>
        <article>
            {html_content}
        </article>
    </body>
    </html>
    """

    return full_html, images

def compose(subject: str, body_as_markdown: str, to: list, cc: list = None, bcc: list = None) -> str:
    """Create an HTML email draft from markdown content"""
    draft = create_draft(
        markdown_text=body_as_markdown,
        metadata={
            'subject': subject,
            'to': to,
            'cc': cc or [],
            'bcc': bcc or []
        },
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
    msg['From'] = FROM_EMAIL
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