# app/core/logger.py
import logging
import logging.handlers
import sys
import queue
import structlog
from pathlib import Path
from app.core.config import settings

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def setup_logger():
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.DEBUG:
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    # Handler consola — queda igual, stdout no bloquea de forma relevante
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Handler archivo — el cambio importante:
    # en vez de escribir a disco directamente en el hilo que atiende
    # la request, mandamos el registro a una cola en memoria y un
    # hilo aparte (QueueListener) hace la escritura real a disco.
    file_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=shared_processors,
    )
    file_handler = logging.FileHandler(LOG_DIR / "app.log")
    file_handler.setFormatter(file_formatter)

    log_queue: queue.Queue = queue.Queue(-1)
    queue_handler = logging.handlers.QueueHandler(log_queue)
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