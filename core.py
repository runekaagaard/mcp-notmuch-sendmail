import os
import logging
import traceback
from functools import wraps
from argparse import ArgumentParser

### Constants ###
NOTMUCH_DATABASE_PATH = os.environ["NOTMUCH_DATABASE_PATH"]
NOTMUCH_REPLY_SEPARATORS = list(os.environ["REPLY_SEPARATORS"].split("|"))
LOG_FILE_PATH = os.environ.get('LOG_FILE_PATH', False)
SENDMAIL_FROM_EMAIL = os.environ["FROM_EMAIL"]

### Logging ###
def setup_logger():
    if LOG_FILE_PATH:
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

def parse_arguments():
    """Parse command line arguments for the email client.
    
    Returns:
        bool: True if the script should run in test mode, False otherwise
    """
    parser = ArgumentParser()
    parser.add_argument('--test-html', action='store_true', help='Generate HTML from email_example.md')
    args = parser.parse_args()
    return args.test_html
