# JPEG Export Service

A FastAPI-based microservice to fetch JPEG images of studies from a dcm4chee-2.x PACS server and export them bundled into ZIP files.

## Features
- Query DICOM metadata via DICOM C-FIND
- Retrieve images via WADO-URI and convert to JPEG
- Bundle JPEGs into ZIP named as `<StudyDate>_<StudyUID>.zip`
- Serve cached ZIPs via API
- Pre-cache today’s studies automatically
- Clean up expired ZIPs with scheduled cleanup
- Logs stored to `logs/dicom_proxy.log` with daily rotation

## Requirements
- Python 3.9+
- dcm4chee-2.x server accessible over DICOM & WADO-URI

## Development Setup

### On Windows:
```bash
# Create virtual environment
> python -m venv .venv 

# Start virtual environment
> .\.venv\Scripts\activate 

# Stop virtual environment
> deactivate 

# Install dependencies
> pip install -r requirements.txt
```