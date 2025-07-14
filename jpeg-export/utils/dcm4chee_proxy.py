"""
Module for interacting with DCM4CHEE PACS to fetch JPEG images and study metadata.
"""
from pathlib import Path
from urllib.parse import urlencode
import time
import requests
from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.sop_class import StudyRootQueryRetrieveInformationModelFind
from config import PACS_CONFIG, TEMP_DIR, DICOM_SERVER_BASE_URL, MAX_RETRIES, RETRY_DELAY_SECONDS
from logger import logger

def get_study_date(study_uid: str) -> str:
    """
    Fetch the StudyDate for a given StudyInstanceUID.
    """
    ae = AE(ae_title=PACS_CONFIG["AETITLE"])
    ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)

    assoc = ae.associate(
        PACS_CONFIG["HOST"],
        PACS_CONFIG["PORT"],
        ae_title=PACS_CONFIG["CALLING_AETITLE"]
    )

    if not assoc.is_established:
        logger.error("C-FIND association to PACS failed")
        raise ConnectionError("C-FIND association failed")

    ds = Dataset()
    ds.QueryRetrieveLevel = "STUDY"
    ds.StudyInstanceUID = str(study_uid).strip()
    ds.StudyDate = ""

    study_date = None
    responses = assoc.send_c_find(ds, StudyRootQueryRetrieveInformationModelFind)
    for (status, identifier) in responses:
        if status and identifier and hasattr(identifier, "StudyDate"):
            study_date = identifier.StudyDate
            break

    assoc.release()

    if not study_date:
        logger.warning("No StudyDate found for StudyInstanceUID: %s", study_uid)
        raise ValueError(f"StudyDate not found for StudyInstanceUID: {study_uid}")

    return study_date


def fetch_jpeg_instance(study_uid: str, series_uid: str, sop_uid: str) -> Path:
    """
    Fetch a JPEG image for the given study, series, and SOP instance UID.
    """
    jpeg_path = TEMP_DIR / study_uid / f"{sop_uid}.jpeg"
    jpeg_path.parent.mkdir(parents=True, exist_ok=True)

    if jpeg_path.exists():
        try:
            jpeg_path.unlink()
            logger.info("Overwriting existing JPEG:")
        except Exception as e:
            logger.warning("Could not delete existing JPEG %s: %s", jpeg_path, e)

    params = {
        "requestType": "WADO",
        "studyUID": study_uid,
        "seriesUID": series_uid,
        "objectUID": sop_uid,
        "contentType": "image/jpeg"
    }
    url = f"{DICOM_SERVER_BASE_URL}?{urlencode(params)}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200 and response.headers.get("Content-Type") == "image/jpeg":
                with open(jpeg_path, "wb") as f:
                    f.write(response.content)
                logger.info("Fetched JPEG for SOP: %s", sop_uid)
                return jpeg_path
            else:
                logger.warning("JPEG fetch failed (%s) for %s", response.status_code, sop_uid)
        except Exception as e:
            logger.warning("Attempt %d failed to fetch JPEG for %s: %s", attempt, sop_uid, e)
        time.sleep(RETRY_DELAY_SECONDS)

    logger.error("JPEG fetch failed after %d attempts: %s", MAX_RETRIES, url)
    raise Exception (f"JPEG fetch failed after {MAX_RETRIES} attempts: {url}")

def get_study_series_and_instances(study_uid: str) -> list[dict]:
    """
    Returns list of dicts with keys: series_uid, sop_uid for the given study UID.
    """
    ae = AE(ae_title=PACS_CONFIG["AETITLE"])
    ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)

    assoc = ae.associate(
        PACS_CONFIG["HOST"],
        PACS_CONFIG["PORT"],
        ae_title=PACS_CONFIG["CALLING_AETITLE"]
    )

    if not assoc.is_established:
        logger.error("C-FIND asoociation failed for series/sop query")
        raise ConnectionError("C-FIND association failed")

    ds = Dataset()
    ds.QueryRetrieveLevel = "IMAGE"
    ds.StudyInstanceUID = str(study_uid).strip()
    ds.SeriesInstanceUID = ""
    ds.SOPInstanceUID = ""

    results = []
    responses = assoc.send_c_find(ds, StudyRootQueryRetrieveInformationModelFind)
    for (status, identifier) in responses:
        if status and identifier and hasattr(identifier, "SeriesInstanceUID") and hasattr(identifier, "SOPInstanceUID"):
            results.append({
                "series_uid": identifier.SeriesInstanceUID,
                "sop_uid": identifier.SOPInstanceUID
            })

    assoc.release()
    logger.info("Found %d series/sop entires for Study %s", len(results), study_uid)
    return results
