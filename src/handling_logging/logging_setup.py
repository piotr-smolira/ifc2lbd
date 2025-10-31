# The file and logging_config was originally written by https://github.com/mCodingLLC/
# It contains slight modifications


import atexit
import json
import logging.config
import logging.handlers
from logging.handlers import RotatingFileHandler
from queue import Queue
from config import LOGGING_CONFIG_PATH, LOGS_PATH

def setup_logging():
    """
    Set up the logging configuration.
    """
    # Load the config, ensure the logs directory exists and update the config
    config = load_config()
    if config:
        create_log_directory()
        update_config_with_logfile_path(config)

        # Apply the logging configuration
        logging.config.dictConfig(config)
        print("Logging configuration applied")

        # Start the queue handler for logs
        #start_queue_handler(config)
    else:
        print("Logging configuration is not valid")

def load_config():
    """
    Load the logging configuration from a file.
    """
    print(f"Logging configuration file: {LOGGING_CONFIG_PATH}")
    if not LOGGING_CONFIG_PATH.exists():
        print(f"Config file not found: {LOGGING_CONFIG_PATH}")
        return None
    with open(LOGGING_CONFIG_PATH) as f:
        return json.load(f)

def create_log_directory():
    """
    Create a directory for the logs if it doesn't exist.
    """
    LOGS_PATH.mkdir(parents=True, exist_ok=True)
    print(f"Log directory ensured at: {LOGS_PATH}")

def update_config_with_logfile_path(config):
    """
    Update the logging configuration with the correct path for the log file.
    """
    if config and 'handlers' in config:
        if not config['handlers']:
            print("No handlers found in config.")
            return
        for handler in config['handlers'].values():
            if 'filename' in handler:
                handler['filename'] = str(LOGS_PATH / handler['filename'])
                print(f"Log file path updated for handler: {handler['filename']}")



    """
def start_queue_handler(config):
    """
    #Start the queue handler for logging.
    """
    logging.config.dictConfig(config)
    queue_handler = logging.getHandlerByName("queue_handler")
    if queue_handler is not None:
        queue_handler.listener.start()
        atexit.register(queue_handler.listener.stop)
    """