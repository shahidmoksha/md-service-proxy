from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from config import DELETE_TEMP_JPEGS, PRECACHE_INTERVAL_MINUTES
from logger import logger
from utils.jpeg_to_zip import export_study_as_jpeg_zip
from utils.cache_cleanup import cleanup_old_cache_files
from utils.dcm4chee_proxy import get_study_series_and_instances
from precache import precache_studies_by_date, precache_todays_studies
import re

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

@app.post("/precache/{date_str}")
def trigger_precache_by_date(date_str: str, background_tasks: BackgroundTasks):
    """
    Trigger precache for studies on a specific date in YYYYMMDD format.
    """
    if not re.fullmatch(r"^\d{8}$", date_str):
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYYMMDD.")
    
    background_tasks.add_task(precache_studies_by_date, date_str)
    return {"status": "Precache job scheduled in the background", "date": date_str}

@app.post("/precache/today")
def trigger_precache_today(background_tasks: BackgroundTasks):
    """
    Trigger precache for today's studies.
    """
    background_tasks.add_task(precache_todays_studies)
    return {"status": "Precache job for Today scheduled in the background"}

# Schedule periodic jobs
scheduler.add_job(precache_todays_studies, trigger='cron', minute=PRECACHE_INTERVAL_MINUTES)
scheduler.add_job(cleanup_old_cache_files, trigger='cron', hour=2, minute=0)
scheduler.start()

if DELETE_TEMP_JPEGS:
    logger.info("Temporary JPEG deletion is enabled")
else:
    logger.info("Temporary JPEG deletion is disabled")