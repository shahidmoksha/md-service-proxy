"""
Maintains the state of all running tasks
"""

from threading import Lock

# Shared set of currently running study exports
active_exports = set()
active_exports_lock = Lock()
