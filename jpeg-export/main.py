"""
FastAPI application for managing DICOM JPEG ZIP exports.
"""

import re
import shutil
import signal
import sys
from contextlib import asynccontextmanager
from fastapi.responses import FileResponse
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from config import DELETE_TEMP_JPEGS, TEMP_DIR
from logger import logger
from utils.jpeg_to_zip import (
    get_zip_path_for_study,
    background_export_zip,
    create_study_jpeg_zip,
)
from utils.cache_cleanup import cleanup_old_cache_files
from utils.precache import precache_studies_by_date, precache_todays_studies
from utils.dcm4chee_proxy import get_study_series_and_instances
from state import active_exports, active_exports_lock

# Initialize background scheduler
scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context
    """
    # StartUp logic
    logger.info("Starting JPEG Export Service")

    if DELETE_TEMP_JPEGS:
        logger.info("Temporary JPEG deletion is enabled")

        # Clean temp directory at startup
        try:
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
            TEMP_DIR.mkdir(parents=True, exist_ok=True)
            logger.info("Temp directory cleaned on startup!")
        except Exception as e:
            logger.warning("Temp directory cleanup failed: %s", e)
    else:
        logger.info("Temporary JPEG deletion is disabled")

    # Start background scheduler
    if not scheduler.running:
        scheduler.start()

    # Hook signals for manual shutdown handling
    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    signal.signal(signal.SIGINT, handle_shutdown_signal)

    yield

    # Shutdown logic
    logger.info("Shutting down gracefully...")
    try:
        if scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped.")
    except Exception as e:
        logger.warning("Scheduler shutdown error: %s", e)

    if DELETE_TEMP_JPEGS:
        try:
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
            logger.info("Temp directory cleaned on shutdown")
        except Exception as e:
            logger.warning("Temp directory removal failed: %s", e)


def handle_shutdown_signal(signum, frame):
    """
    Function to handle service shutdown signals
    """
    logger.info("Signal %d received. Triggering cleanup...", signum)
    scheduler.shutdown(wait=False)
    sys.exit(0)


def on_exit():
    """
    Function to handle cleanup if graceful shutdown is skipped
    """
    logger.info("Exiting via atexit fallback")
    scheduler.shutdown(wait=False)


# OpenAPI tags
tags_metadata = [
    {
        "name": "Production",
        "description": "APIs for checking and exporting DICOM JPEG ZIP files.",
    },
    {
        "name": "Maintenance",
        "description": "APIs for managing pre-cache, cache cleanup etc",
    },
]

# Initialize FastAPI with lifespan and OpenAPI tags
app = FastAPI(
    lifespan=lifespan, title="DICOM JPEG ZIP Proxy", openapi_tags=tags_metadata
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/check/{study_uid}/{instance_count}", tags=["Production"])
def check_or_export(
    study_uid: str, instance_count: int, background_tasks: BackgroundTasks
):
    """
    Check if a ZIP file exists for the given study UID.
    If it exists, return success; otherwise, return failure and trigger export.
    """
    try:
        clean_study_uid = str(study_uid).strip()
        zip_path = get_zip_path_for_study(clean_study_uid)

        # If zip file exists return success
        if zip_path.exists():
            return {
                "status": "success",
                "msg": "ZIP file is ready for download",
            }

        # Check and add task for export
        with active_exports_lock:
            # Check if export is already triggerd for this study_uid
            if clean_study_uid in active_exports:
                return {
                    "status": "failure",
                    "msg": "JPEG Export already running in background.",
                }

            # If not already triggered, fetch actual instances from PACS
            logger.info(
                "Checking study %s against expected instance count: %d",
                study_uid,
                instance_count,
            )

            fetched_instances = get_study_series_and_instances(clean_study_uid, False)
            server_instance_count = len(fetched_instances)
            if server_instance_count < instance_count:
                logger.warning(
                    "Aborting export: Only %d instances found on PACS Server, but %d instances are required!",
                    server_instance_count,
                    instance_count,
                )
                return {
                    "status": "failure",
                    "msg": "Server instance count does not match the requested instance count.",
                }

            # Mark export as running
            active_exports.add(clean_study_uid)
            background_tasks.add_task(background_export_zip, clean_study_uid)
            logger.info("Queued background export for study UID: %s", clean_study_uid)

            return {
                "status": "failure",
                "msg": "ZIP file not found, export job scheduled in the background",
            }

    except Exception as e:
        logger.error("Check/export enqueue failed for %s: %s", study_uid, e)
        raise HTTPException(
            status_code=500, detail="Check/export enqueue failed"
        ) from e


@app.get("/export/{study_uid}", tags=["Production"])
def export_study_jpeg(study_uid: str):
    """
    Export JPEGs for the given study UID and return the ZIP file.
    """
    try:
        clean_study_uid = str(study_uid).strip()
        zip_path = create_study_jpeg_zip(clean_study_uid)
        return FileResponse(
            path=zip_path, filename=zip_path.name, media_type="application/zip"
        )
    except Exception as e:
        logger.error("Export failed for %s: %s", clean_study_uid, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/cleanup", tags=["Maintenance"])
def trigger_cleanup():
    """
    Trigger manual cleanup of old cache files.
    """
    try:
        cleanup_old_cache_files()
        return {"message": "Cache cleanup triggered"}
    except Exception as e:
        logger.error("Manual cleanup failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/precache/{date_str}", tags=["Maintenance"])
def trigger_precache_by_date(date_str: str, background_tasks: BackgroundTasks):
    """
    Trigger precache for studies on a specific date in YYYYMMDD format.
    """
    if not re.fullmatch(r"^\d{8}$", date_str):
        raise HTTPException(
            status_code=400, detail="Invalid date format. Use YYYYMMDD."
        )

    background_tasks.add_task(precache_studies_by_date, date_str)
    return {"status": "Precache job scheduled in the background", "date": date_str}


@app.post("/precache/today", tags=["Maintenance"])
def trigger_precache_today(background_tasks: BackgroundTasks):
    """
    Trigger precache for today's studies.
    """
    background_tasks.add_task(precache_todays_studies)
    return {"status": "Precache job for Today scheduled in the background"}
