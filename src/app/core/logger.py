# app/core/logger.py
import logging
import logging.handlers
import queue
import sys
from pathlib import Path

import structlog
from app.core.config import settings

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


class StructlogQueueHandler(logging.handlers.QueueHandler):
    """
    QueueHandler personalizado que evita que prepare() convierta
    el dict de structlog (record.msg) en una cadena de texto.
    """
    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        return record


def setup_logger():
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.DEBUG:
        console_renderer = structlog.dev.ConsoleRenderer()
    else:
        console_renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Formatter para Consola
    console_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            console_renderer,
        ],
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)

    # Formatter para Archivo JSON
    file_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )

    file_handler = logging.FileHandler(LOG_DIR / "app.log")
    file_handler.setFormatter(file_formatter)

    # QueueHandler personalizado sin corrupción de dict
    log_queue: queue.Queue = queue.Queue(-1)
    queue_handler = StructlogQueueHandler(log_queue)
    queue_listener = logging.handlers.QueueListener(
        log_queue, file_handler, respect_handler_level=True
    )
    queue_listener.start()

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(queue_handler)
    root_logger.setLevel(logging.INFO)

    return structlog.get_logger("shion_ai"), queue_listener


logger, _queue_listener = setup_logger()