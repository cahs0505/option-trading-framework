from loguru import logger
import sys

format: str = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
    "| <level>{level}</level> "
    "| <level>{module}</level> "
    "| <level>{message}</level>"
)
logger.remove()
logger.add(sink=sys.stdout, level='INFO', format=format)
logger.add("log/file.log", level="ERROR", rotation="500 MB")