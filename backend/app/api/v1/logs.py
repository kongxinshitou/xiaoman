"""Frontend log upload endpoint.

Receives batched log entries from the browser and writes them to
logs/frontend/frontend.log (same rotation rules as the backend log).
"""

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from typing import List, Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

_LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "logs",
    "frontend",
)

_frontend_logger: Optional[logging.Logger] = None


def _get_frontend_logger() -> logging.Logger:
    global _frontend_logger
    if _frontend_logger is not None:
        return _frontend_logger

    os.makedirs(_LOG_DIR, exist_ok=True)
    lg = logging.getLogger("frontend")
    lg.propagate = False
    if not lg.handlers:
        fh = TimedRotatingFileHandler(
            os.path.join(_LOG_DIR, "frontend.log"),
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8",
        )
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] [frontend] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        lg.addHandler(fh)
    lg.setLevel(logging.DEBUG)
    _frontend_logger = lg
    return lg


class LogEntry(BaseModel):
    level: str = "info"
    message: str
    timestamp: str = ""
    data: Any = None


class LogBatch(BaseModel):
    logs: List[LogEntry]


@router.post("")
async def upload_logs(batch: LogBatch):
    """Receive frontend log entries and write to the frontend log file."""
    lg = _get_frontend_logger()
    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warn": logging.WARNING,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }
    for entry in batch.logs:
        lvl = level_map.get(entry.level.lower(), logging.INFO)
        msg = entry.message
        if entry.data:
            msg = f"{msg} | data={entry.data}"
        if entry.timestamp:
            msg = f"[{entry.timestamp}] {msg}"
        lg.log(lvl, msg)
    return {"received": len(batch.logs)}
