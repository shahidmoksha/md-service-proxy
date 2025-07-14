"""
Module with logic to clean up old cache files.
"""
import re
from datetime import datetime
from config import CACHE_DIR, CACHE_EXPIRY
from logger import logger

STUDY_DATE_PATTERN = re.compile(r'^(\d{8})_(.+)\.zip$')

def cleanup_old_cache_files():
    """
    Clean up cache files older than CACHE_EXPIRY days.
    """
    now = datetime.now()
    expired_count = 0

    for zip_file in CACHE_DIR.glob("*.zip"):
        match = STUDY_DATE_PATTERN.match(zip_file.name)
        if not match:
            logger.warning("Skipping non-standard ZIP filename: %s", zip_file.name)
            continue

        study_date_str = match.group(1)
        try:
            study_date = datetime.strptime(study_date_str, "%Y%m%d")
            if now - study_date > CACHE_EXPIRY:
                zip_file.unlink()
                expired_count += 1
                logger.info("Deleted expired ZIP: %s", zip_file.name)
        except Exception as e:
            logger.error("Error parsing date from %s: %s", zip_file.name, e)

    logger.info("Cache cleanup complete. %d expired ZIPs deleted.", expired_count)
