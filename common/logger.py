import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
import pytz

# EST timezone for consistent logging
est_timezone = pytz.timezone('US/Eastern')

# Ensure logs directory exists
os.makedirs('./logs', exist_ok=True)
log_date = datetime.now(est_timezone).strftime('%Y-%m-%d')
TARGET_TAG = os.environ.get("PATCH_TAG", "notag")
log_filename = f'./logs/patching_{log_date}_{TARGET_TAG}.log'

formatter = logging.Formatter('%(asctime)s - %(process)d - %(levelname)s - %(message)s')
file_handler = logging.FileHandler(log_filename)
file_handler.setFormatter(formatter)

logger = logging.getLogger('patching_main')
logger.setLevel(logging.INFO)
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
logger.addHandler(file_handler)
logging.getLogger().handlers.clear()
