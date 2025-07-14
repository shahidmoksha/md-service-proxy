import zipfile
import shutil
from pathlib import Path
from logger import logger
from config import TEMP_DIR, CACHE_DIR, DELETE_TEMP_JPEGS
from utils.dcm4chee_proxy import get_study_date, fetch_jpeg_instance

def export_study_as_jpeg_zip(study_uid: str, series_instances: list[dict]) -> Path:
    """
    Fetch JPEGs via WADO for all SOPs and create a ZIP.
    Each dict in series_instances must contain: series_uid, sop_uid
    Returns path to the generated ZIP file.
    """
    try:
        study_date = get_study_date(study_uid)
    except Exception as e:
        logger.error(f"Failed to get StudyDate for {study_uid}: {e}")
        raise

    zip_filename = f"{study_date}_{study_uid}.zip"
    zip_path = CACHE_DIR / zip_filename

    if zip_path.exists():
        logger.info(f"ZIP already cached: {zip_path}")
        return zip_path
    
    study_temp_dir = TEMP_DIR / study_uid
    study_temp_dir.mkdir(parents=True, exist_ok=True)

    fetched_files = []
    for item in series_instances:
        series_uid = item["series_uid"]
        sop_uid = item["sop_uid"]
        try:
            jpeg_path = fetch_jpeg_instance(study_uid, series_uid, sop_uid)
            fetched_files.append(jpeg_path)
        except Exception as e:
            logger.error(f"Skipping failed JPEG fetch for SOP {sop_uid}: {e}")

        if not fetched_files:
            raise RuntimeError(f"No JPEGS fetched for study {study_uid}. Aborting ZIP creation.")
        
        try:
            with zipfile.ZipFile(zip_path, 'w') as zip_file:
                for jpeg_file in fetched_files:
                    zip_file.write(jpeg_file, arcname=jpeg_file.name)
            logger.info(f"Create ZIP file: {zip_path} with {len(fetched_files)} JPEGs")

            if DELETE_TEMP_JPEGS:
                shutil.rmtree(study_temp_dir, ignore_errors=False)
                logger.info(f"Deleted temporary JPEGs for {study_uid}")
            else:
                logger.info(f"Temporary JPEGs retained for {study_uid}")

            return zip_path
        
        except Exception as e:
            logger.error(f"Failed to create ZIP for study {study_uid}: {e}")
            logger.info(f"Retaining temp JPEGs at: {study_temp_dir}")
            raise