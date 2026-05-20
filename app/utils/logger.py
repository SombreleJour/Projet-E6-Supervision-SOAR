import logging
import sys
from logging.handlers import RotatingFileHandler


def setup_logger(name='supervision_app', log_file='logs/supervision.log', level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    try:
        file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        logger.warning(f'Could not create log file at {log_file}, logging to stdout only.')

    return logger


logger = setup_logger()
