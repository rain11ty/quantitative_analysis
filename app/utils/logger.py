# -*- coding: utf-8 -*-
import os

from loguru import logger

from runtime_encoding import configure_utf8_environment, safe_console_write


def setup_logger(log_level='INFO', log_file='logs/stock_analysis.log'):
    """Set up application logging with UTF-8 safe console/file sinks."""
    configure_utf8_environment()

    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger.remove()

    logger.add(
        sink=safe_console_write,
        level=log_level,
        format='<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>',
        colorize=True,
        catch=True,
    )

    logger.add(
        sink=log_file,
        level=log_level,
        format='{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}',
        rotation='10 MB',
        retention='30 days',
        compression='zip',
        encoding='utf-8',
    )

    return logger
