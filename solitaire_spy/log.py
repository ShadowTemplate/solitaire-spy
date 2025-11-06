import logging
from pathlib import Path

def posix_path(*args: str) -> str:
    return Path().joinpath(*args).as_posix()


APPLICATION_NAME = "solitaire-spy"
DEFAULT_LOG_FORMAT = (
    "%(levelname)s:%(asctime)s:%(module)s:%(funcName)s:"
    "L%(lineno)d: %(message)s"
)
DEFAULT_LOGGING_FILE = posix_path(Path.home().as_posix(), f"{APPLICATION_NAME}.log")

def get_logger(
    name=APPLICATION_NAME,
    log_format=DEFAULT_LOG_FORMAT,
    stdout_level=logging.INFO,
    file_name=DEFAULT_LOGGING_FILE,
    file_level=logging.INFO,
):
    Path(file_name).parent.mkdir(exist_ok=True)
    Path(file_name).touch(exist_ok=True)
    logging.basicConfig(format=log_format)
    logger = logging.getLogger(name)
    logger.setLevel(stdout_level)
    file_handler = logging.FileHandler(file_name)
    file_handler.setLevel(file_level)
    file_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(file_handler)
    return logger
