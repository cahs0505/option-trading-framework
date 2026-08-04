import logging
import sys
from loguru import logger


class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_back and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(log_level="INFO"):
    # Remove default loguru handler and add your own
    logger.remove()
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        serialize=False,  # set True for JSON logs
    )

    # Route standard logging through loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Make sure specific loggers propagate through the intercept handler
    for name in (
        "gunicorn",
        "gunicorn.access",
        "gunicorn.error",
        "werkzeug",
        "flask.app",
    ):
        logging.getLogger(name).handlers = [InterceptHandler()]
        logging.getLogger(name).propagate = False