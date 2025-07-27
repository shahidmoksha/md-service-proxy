"""
Module with logic to export DICOM JPEGs as ZIP files.
"""

import zipfile
import shutil
from pathlib import Path
from logger import logger
from config import TEMP_DIR, CACHE_DIR, DELETE_TEMP_JPEGS
from utils.dcm4chee_proxy import (
    get_study_date,
    fetch_jpeg_instance,
    get_study_series_and_instances,
    get_instance_metadata,
)
from utils.image_utils import burn_metadata_on_jpeg


def get_zip_path_for_study(study_uid: str) -> Path:
    """
    Returns the path for the ZIP file for a given study UID.
    """
    study_date = get_study_date(study_uid)
    zip_filename = f"{study_date}_{study_uid}.zip"
    return CACHE_DIR / zip_filename


def background_export_zip(study_uid: str):
    """
    Background task to export JPEGs for a study UID and create a ZIP file.
    """
    try:
        logger.info("[Background Task] Starting export for study UID: %s", study_uid)
        export_study_jpeg_logic(study_uid)
        logger.info("[Background Task] Completed export for study UID: %s", study_uid)
    except Exception as e:
        logger.error(
            "[Background Task] Export failed for study UID %s: %s", study_uid, e
        )


def export_study_jpeg_logic(study_uid: str) -> Path:
    """
    Fetch instances for all series of a study.
    Create the ZIP file.
    Returns path to the ZIP file.
    """
    study_uid = str(study_uid).strip()
    series_instances = get_study_series_and_instances(study_uid)
    if not series_instances:
        raise ValueError(f"No instances found for StudyUID: {study_uid}")

    zip_path = create_study_jpeg_zip(study_uid, series_instances)
    return zip_path


def create_study_jpeg_zip(study_uid: str, series_instances: list[dict]) -> Path:
    """
    Fetch JPEGs via WADO for all SOPs and create a ZIP.
    Each dict in series_instances must contain: series_uid, sop_uid
    Returns path to the generated ZIP file.
    """
    try:
        study_date = get_study_date(study_uid)
    except Exception as e:
        # The line `logger.error("Failed to get StudyDate for %s: %s", study_uid, e)` is logging an
        # error message using the logger object.
        logger.error("Failed to get StudyDate for %s: %s", study_uid, e)
        raise

    zip_filename = f"{study_date}_{study_uid}.zip"
    zip_path = CACHE_DIR / zip_filename

    if zip_path.exists():
        logger.info("ZIP already cached: %s", zip_path)
        return zip_path

    study_temp_dir = TEMP_DIR / study_uid
    study_temp_dir.mkdir(parents=True, exist_ok=True)

    fetched_files = []
    for item in series_instances:
        series_uid = item["series_uid"]
        sop_uid = item["sop_uid"]
        try:
            jpeg_path = fetch_jpeg_instance(study_uid, series_uid, sop_uid)
            metadata = get_instance_metadata(study_uid, series_uid, sop_uid)
            burn_metadata_on_jpeg(jpeg_path, metadata)

            fetched_files.append(jpeg_path)
        except Exception as e:
            logger.error("Skipping failed JPEG fetch for SOP %s: %s", sop_uid, e)

    if not fetched_files:
        raise RuntimeError(
            f"No JPEGS fetched for study {study_uid}. Aborting ZIP creation."
        )

    try:
        with zipfile.ZipFile(zip_path, "w") as zip_file:
            for jpeg_file in fetched_files:
                zip_file.write(jpeg_file, arcname=jpeg_file.name)

        logger.info("Create ZIP file: %s with %d JPEGs", zip_path, len(fetched_files))

        if DELETE_TEMP_JPEGS:
            shutil.rmtree(study_temp_dir, ignore_errors=False)
            logger.info("Deleted temporary JPEGs for %s", study_uid)
        else:
            logger.info("Temporary JPEGs retained for %s", study_uid)

        return zip_path

    except Exception as e:
        logger.error("Failed to create ZIP for study %s: %s", study_uid, e)
        logger.info("Retaining temp JPEGs at: %s", study_temp_dir)
        raise
