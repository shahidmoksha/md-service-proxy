from datetime import datetime
from config import PACS_CONFIG
from utils.dcm4chee_proxy import get_study_series_and_instances
from utils.jpeg_to_zip import create_study_jpeg_zip
from logger import logger
from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.sop_class import StudyRootQueryRetrieveInformationModelFind

def precache_studies_by_date(date_str: str):
    """
    Precache studies for a specific date in the format YYYYMMDD.
    """
    try:
        # Validate date format
        datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        logger.error(f"Invalid date format: {date_str}. Expected YYYYMMDD.")
        return
    
    logger.info(f"Starting precache for studies with StudyDate={date_str}")

    try:
        ae = AE(ae_title=PACS_CONFIG["AETITLE"])
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)

        assoc = ae.associate(
            PACS_CONFIG["HOST"],
            PACS_CONFIG["PORT"],
            ae_title=PACS_CONFIG["CALLING_AETITLE"]
        )

        if not assoc.is_established:
            logger.error("Precache: C-FIND association failed")
            return
        
        ds = Dataset()
        ds.QueryRetrieveLevel = "STUDY"
        ds.StudyDate = date_str
        ds.StudyInstanceUID = ""

        study_uids = []
        responses = assoc.send_c_find(ds, StudyRootQueryRetrieveInformationModelFind)
        for status, identifier in responses:
            if status and identifier and hasattr(identifier, "StudyInstanceUID"):
                study_uids.append(identifier.StudyInstanceUID)

        assoc.release()
        logger.info(f"Found {len(study_uids)} studies for date {date_str}")

        for study_uid in study_uids:
            try:
                series_instances = get_study_series_and_instances(study_uid)
                if series_instances:
                    create_study_jpeg_zip(study_uid, series_instances)
            except Exception as e:
                logger.warning(f"Precache failed for {study_uid}: {e}")

        logger.info("Precache job complete!")

    except Exception as e:
        logger.error(f"Precache job failed: {e}")


def precache_todays_studies():
    today_str = datetime.now().strftime("%Y%m%d")
    logger.info(f"Triggering precache for Today: {today_str}")
    precache_studies_by_date(today_str)

