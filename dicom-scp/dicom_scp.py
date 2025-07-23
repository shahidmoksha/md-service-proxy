"""
C-STORE SCP Proxy for pre-processing DICOM tags.
"""

import os
import logging
import threading
import signal
from pathlib import Path
from time import sleep
from queue import Queue, Empty
from dotenv import load_dotenv
from pydicom import dcmread
from pynetdicom import AE, evt, StoragePresentationContexts

# Load environment variables
load_dotenv()
AE_TITLE = os.getenv("AE_TITLE", "CLEANSCP")
PORT = int(os.getenv("PORT", "104"))
TARGET_AE = os.getenv("TARGET_AE", "LCHBLR")
TARGET_HOST = os.getenv("TARGET_HOST", "127.0.0.1")
TARGET_PORT = int(os.getenv("TARGET_PORT", "11112"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "5"))
NUM_WORKERS = int(os.getenv("NUM_WORKERS", "4"))

# Configure logging
Path("logs").mkdir(exist_ok=True)
Path("cleaned").mkdir(exist_ok=True)
Path("quarantine").mkdir(exist_ok=True)

logging.basicConfig(
    filename="logs/dicom_scp.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Forwading queue
forward_queue = Queue()
stop_event = threading.Event()


# Worker function to forward DICOM files
def forward_worker(worker_id):
    while not stop_event.is_set():
        try:
            file_path = forward_queue.get(timeout=2)
            logging.info("Worker {%s}] Processing file: {%s}", worker_id, file_path)
            success = forward_to_target(file_path)
            if success:
                os.remove(file_path)
                logging.info(
                    "[Worker {%s}] Forwarded and deleted: {%s}", worker_id, file_path
                )
            else:
                logging.error(
                    "[Worker {%s}] Failed after retries: {%s}", worker_id, file_path
                )
            forward_queue.task_done()
        except Empty:
            continue
        except Exception as e:
            logging.exception("[Worker %s] Unexpected error: %s", worker_id, e)


# Function to forward DICOM file to target AE
def forward_to_target(file_path):
    for attempt in range(MAX_RETRIES):
        ae = AE()
        ae.requested_contexts = StoragePresentationContexts
        assoc = ae.associate(TARGET_HOST, TARGET_PORT, ae_title=TARGET_AE)
        if assoc.is_established:
            try:
                ds = dcmread(file_path)
                status = assoc.send_c_store(ds)
                assoc.release()
                if status and status.Status in (0x0000, 0xB000):
                    return True
            except Exception as e:
                logging.exception(
                    "Read/Send failed on attempt %d. Unexpected error: %s",
                    attempt + 1,
                    e,
                )
        sleep(RETRY_DELAY)
    return False


# C-STORE Handler
def handle_store(event):
    try:
        ds = event.dataset
        ds.file_meta = event.file_meta
        ds.remove_private_tags()

        filepath = Path("cleaned") / f"{ds.SOPInstanceUID}.dcm"
        ds.save_as(filepath, write_like_original=False)
        forward_queue.put(filepath)
        return 0x0000
    except Exception:
        logging.exception("C-STORE failure, quarantining file")
        bad_path = (
            Path("quarantine") / f"bad_{ds.SOPInstanceUID}_{event.context_id}.dcm"
        )
        with open(bad_path, "wb") as f:
            f.write(event.request.DataSet)
        return 0xC210

# Queue monitor
def queue_monitor():
    while not stop_event.is_set():
        if forward_queue.qsize() > 0:
            logging.info("[Monitor] Queue size: {%d}", forward_queue.qsize())
        sleep(10)

# Gracefule shutdown
def shutdown_handler(signum, frame):
    logging.info("Shudown signal received. Waiting for queue to drain...")
    stop_event.set()
    forward_queue.join()
    logging.info("All queued items processed. Shutting down.")
    os._exit(0)

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

# Start background workers
for i in range(NUM_WORKERS):
    t = threading.Thread(target=forward_worker, args=(i+1,), daemon=True)
    t.start()

# Start monitor thread
monitor_thread = threading.Thread(target=queue_monitor, daemon=True)
monitor_thread.start()

# SCP Listener
handlers = [(evt.EVT_C_STORE, handle_store)]
ae = AE(ae_title=AE_TITLE)
ae.supported_contexts = StoragePresentationContexts
print("Starting SCP on port %d, AE Title: %s", PORT, AE_TITLE)
ae.start_server(("0.0.0.0", PORT), block=True, evt_handlers=handlers)
