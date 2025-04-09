import os
import logging
import traceback
from functools import wraps
from pathlib import Path

### Constants ###
ROOT_DIR = Path(__file__).parent
NOTMUCH_DATABASE_PATH = os.environ["NOTMUCH_DATABASE_PATH"]
NOTMUCH_REPLY_SEPARATORS = list(os.environ["NOTMUCH_REPLY_SEPARATORS"].split("|"))
SENDMAIL_FROM_EMAIL = os.environ["SENDMAIL_FROM_EMAIL"]
SENDMAIL_EMAIL_SIGNATURE_HTML = os.environ.get("SENDMAIL_EMAIL_SIGNATURE_HTML", "")
LOG_FILE_PATH = os.environ.get('LOG_FILE_PATH', False)
DRAFT_DIR = Path(os.environ.get('DRAFT_DIR', '/tmp/mcp-notmuch-sendmail'))

# Create drafts directory if it doesn't exist
DRAFT_DIR.mkdir(parents=True, exist_ok=True)

### Logging ###
def setup_logger():
    if LOG_FILE_PATH is not False:
        logger = logging.getLogger('function_logger')
        fh = logging.FileHandler(LOG_FILE_PATH)
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(fh)
        return logger
    return None

logger = setup_logger()

def log(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not logger:
            return func(*args, **kwargs)

        try:
            logger.info(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
            result = func(*args, **kwargs)
            logger.info(f"{func.__name__} returned {result}")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} raised {type(e).__name__}: {str(e)}\n{traceback.format_exc()}")
            raise

    return wrapper
