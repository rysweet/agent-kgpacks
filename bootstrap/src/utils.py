"""Utility functions"""

import logging
from pathlib import Path
from .config import config


def setup_logging():
    """Setup logging configuration"""
    log_level = config.get('logging.level', 'INFO')
    log_file = config.get('logging.file', 'logs/wikigr.log')
    log_format = config.get('logging.format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Create logs directory
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format=log_format,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    return logging.getLogger('wikigr')


def get_logger(name: str) -> logging.Logger:
    """Get logger for module"""
    return logging.getLogger(f'wikigr.{name}')
