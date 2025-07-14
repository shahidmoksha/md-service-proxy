from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from config import DELETE_TEMP_JPEGS, PRECACHE_INTERVAL_MINUTES
from logger import logger
from utils.jpeg_to_zip import export_study_as_jpeg_zip
from utils.cache_cleanup import cleanup_old_cache_files
from utils.dcm4chee_proxy import get_study_series_and_instances, get_study_date

app = FastAPI(title="DICOM JPEG ZIP Proxy")
scheduler = BackgroundScheduler()

@app.get("/export/{study_uid}")
def export_study(study_uid: str):
    try:
        study_uid = str(study_uid).strip()
        series_instances = get_study_series_and_instances(study_uid)
        if not series_instances:
            raise HTTPException(status_code=404, detail="No instances found for StudyUID")
        
        zip_path = export_study_as_jpeg_zip(study_uid, series_instances)
        return FileResponse(path=zip_path, filename=zip_path.name, media_type="application/zip")
    except Exception as e:
        logger.error(f"Export failed for {study_uid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/cleanup")
def trigger_cleanup():
    try:
        cleanup_old_cache_files()
        return {"message": "Cache cleanup triggered"}
    except Exception as e:
        logger.error(f"Manual cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
def precache_todays_studies():
    today_str = datetime.now().strftime("%Y%m%d")
    logger.info(f"Starting precache for studies with StudyDate={today_str}")

    try:
        from pynetdicom import AE
        from pydicom.dataset import Dataset
        from pynetdicom.sop_class import StudyRootQueryRetieveInformationModelFind
        from config import PACS_CONFIG

        ae = AE(ae_title=PACS_CONFIG["CALLING_AETITLE"])
        ae.add_requested_context(StudyRootQueryRetieveInformationModelFind)

        assoc = ae.associate(PACS_CONFIG["HOST"], PACS_CONFIG["PORT"], ae_title=PACS_CONFIG["AETITLE"])
        if not assoc.is_established:
            logger.error("Precache: C-FIND association failed")
            return
        
        ds = Dataset()
        ds.QueryRetrieveLevel = "STUDY"
        ds.StudyDate = today_str
        ds.StudyInstanceUID = ""

        study_uids = []
        responses = assoc.send_c_find(ds, StudyRootQueryRetieveInformationModelFind)
        for (status, identifier) in responses:
            if status and identifier and hasattr(identifier, "StudyInstanceUID"):
                study_uids.append(identifier.StudyInstanceUID)
        
        assoc.release()
        logger.info(f"Found {len(study_uids)} studies for today")

        for study_uid in study_uids:
            try:
                series_instances = get_study_series_and_instances(study_uid)
                if series_instances:
                    export_study_as_jpeg_zip(study_uid, series_instances)
            except Exception as e:
                logger.warning(f"Precache failed for {study_uid}: {e}")

        logger.info("Precache job complete!")

    except Exception as e:
        logger.error(f"Precache job failed: {e}")

# Schedule periodic jobs
scheduler.add_job(precache_todays_studies, trigger='cron', minute=PRECACHE_INTERVAL_MINUTES)
scheduler.add_job(cleanup_old_cache_files, trigger='cron', hour=2, minute=0)
scheduler.start()

if DELETE_TEMP_JPEGS:
    logger.info("Temporary JPEG deletion is enabled")
else:
    logger.info("Temporary JPEG deletion is disabled")