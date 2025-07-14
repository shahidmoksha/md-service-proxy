import os
from pathlib import Path
from datetime import timedelta

# Configuration for JPEG export settings

# DICOM Server settings
PACS_CONFIG = {
    "AETITLE": "MOKSHASERVER",
    "HOST": "localhost",
    "PORT": 11112,
    "CALLING_AETITLE": "MDPROXY",
}

# WADO-URI endpoint settings
DICOM_SERVER_BASE_URL = "http://localhost:8000/dicom-wado"
MAX_RETRIES = 3 # Number of retries for network requests
RETRY_DELAY = 5  # Delay in seconds between retries

# Local paths for ZIP and JPEG storage
CACHE_DIR = Path(os.getenv("JPEG_EXPORT_CACHE_DIR", "cache"))
TEMP_DIR = Path(os.getenv("JPEG_EXPORT_TEMP_DIR", "temp"))
CACHE_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

# Cache control settings
CACHE_EXPIRY = timedelta(days=1)  # delete ZIPs after 1 day
DELETE_TEMP_JPEGS = os.getenv("JPEG_EXPORT_DELETE_TEMP_JPEGS", "true").lower() == "true"

# Precache settings
PRECACHE_INTERVAL_MINUTES = int(os.getenv("JPEG_EXPORT_PRECACHE_INTERVAL_MINUTES", 15))  # Default to 15 minutes