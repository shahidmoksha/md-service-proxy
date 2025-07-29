"""
Module with logic to precache zip files.
"""

# pylint: disable=no-name-in-module
from datetime import datetime
from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.sop_class import StudyRootQueryRetrieveInformationModelFind
from config import PACS_CONFIG
from utils.jpeg_to_zip import create_study_jpeg_zip
from logger import logger


def precache_studies_by_date(date_str: str):
    """
    Precache studies for a specific date in the format YYYYMMDD.
    """
    try:
        # Validate date format
        datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        logger.error("Invalid date format: %s. Expected YYYYMMDD.", date_str)
        return

    logger.info("Starting precache for studies with StudyDate=%s", date_str)

    try:
        ae = AE(ae_title=PACS_CONFIG["AETITLE"])
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)

        assoc = ae.associate(
            PACS_CONFIG["HOST"],
            PACS_CONFIG["PORT"],
            ae_title=PACS_CONFIG["CALLING_AETITLE"],
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
        logger.info("Found %d studies for date %s", len(study_uids), date_str)

        for study_uid in study_uids:
            try:
                create_study_jpeg_zip(study_uid)
            except Exception as e:
                logger.warning("Precache failed for %s: %s", study_uid, e)

        logger.info("Precache job complete!")

    except Exception as e:
        logger.error("Precache job failed: %s", e)


def precache_todays_studies():
    """
    Triggers the precaching process for studies corresponding to today's date.
    """
    today_str = datetime.now().strftime("%Y%m%d")
    logger.info("Triggering precache for Today: %s", today_str)
    precache_studies_by_date(today_str)
