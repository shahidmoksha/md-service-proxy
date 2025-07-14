"""
Configuration settings for the JPEG export service.
"""
import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# DICOM Server settings
PACS_CONFIG = {
    "HOST": os.getenv("PACS_HOST", "localhost"),
    "AETITLE": os.getenv("PACS_AETITLE", "MOKSHASERVER"),
    "PORT": int(os.getenv("PACS_PORT", "11112")),
    "CALLING_AETITLE": os.getenv("CALLING_AETITLE", "MDPROXY"),
}

# WADO-URI endpoint settings
DICOM_SERVER_BASE_URL = os.getenv("DICOM_SERVER_BASE_URL", "http://localhost:8000/wado")

# Retry settings
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS"))

# Cache directory for ZIP files
CACHE_DIR = Path(os.getenv("JPEG_ZIP_CACHE_DIR", "cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Temporary directory for JPEGs
TEMP_DIR = Path(os.getenv("JPEG_TEMP_DIR", "temp"))
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Directory for log files
LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Cache control settings
CACHE_EXPIRY_DAYS = int(os.getenv("CACHE_EXPIRY_DAYS", "1"))  # Default to 1 day
CACHE_EXPIRY = timedelta(days=CACHE_EXPIRY_DAYS)  # delete ZIPs after 1 day

# Auto-delete temporary JPEG settings
DELETE_TEMP_JPEGS = os.getenv("DELETE_TEMP_JPEGS", "true").lower() == "true"

# Precache settings
PRECACHE_INTERVAL_MINUTES = int(os.getenv("PRECACHE_INTERVAL_MINUTES", "5"))
