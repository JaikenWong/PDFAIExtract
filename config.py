import json
import os
import logging

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = logging.INFO

_CONFIG = None


def load_config(path: str = None):
    global _CONFIG
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(path, encoding="utf-8") as f:
        _CONFIG = json.load(f)
    return _CONFIG


def get_config():
    global _CONFIG
    if _CONFIG is None:
        return load_config()
    return _CONFIG


def setup_logging(level: int = None):
    level = level or LOG_LEVEL
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        handlers=[logging.StreamHandler()],
    )
    return logging.getLogger("pdf_extractor")