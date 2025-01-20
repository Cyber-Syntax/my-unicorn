import os
import logging
from logging.handlers import RotatingFileHandler


class LogManager:
    def __init__(self, log_file="my-unicorn.log", log_level=logging.INFO):
        """Initializes the logger with file path and log level"""
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, log_file)
        self.logger = logging.getLogger()
        self._setup_logger(log_file_path, log_level)

    def _setup_logger(self, log_file_path, log_level):
        """Sets up the logging configuration"""
        log_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=1024 * 1024,
            backupCount=3,  # Keep 3 backups
        )
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        log_handler.setFormatter(formatter)

        self.logger.setLevel(log_level)
        self.logger.addHandler(log_handler)

    # Expose standard logging methods
    def debug(self, msg):
        self.logger.debug(msg)

    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

    def critical(self, msg):
        self.logger.critical(msg)
