"""
Module with logic to set up logging for the JPEG export service.
"""
import logging
from logging.handlers import TimedRotatingFileHandler
import os

LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_PATH = os.path.join(LOG_DIR, "jpeg_export.log")
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt="%Y-%m-%d %H:%M:%S")

file_handler = TimedRotatingFileHandler(LOG_PATH, when="midnight", interval=1, backupCount=7)
file_handler.setFormatter(formatter)
file_handler.suffix = "%Y-%m-%d"
logger.addHandler(file_handler)

# Optional: Add a console handler for real-time logging
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
