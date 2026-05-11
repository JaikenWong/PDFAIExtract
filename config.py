import json
import os
import logging
from copy import deepcopy

from dotenv import load_dotenv

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = logging.INFO

_CONFIG = None

_DEFAULT_CONFIG = {
    "llm": {
        "provider": "openai",
        "model": "gpt-4o",
        "vision_model": "gpt-4o",
        "api_key": "",
        "api_secret": "",
        "base_url": "",
        "vision_base_url": "",
        "vision_api_key": "",
        "vision_model_id": "",
    },
    "extraction": {
        "min_text_length": 100,
        "raw_text_preview": 500,
        "max_retries": 3,
        "retry_delay": 1.0,
        "concurrent_workers": 4,
        "dpi": 150,
    },
}


def _merge_dict(base: dict, overrides: dict) -> dict:
    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _env_config() -> dict:
    llm = {
        "provider": os.getenv("LLM_PROVIDER"),
        "model": os.getenv("LLM_MODEL"),
        "vision_model": os.getenv("LLM_VISION_MODEL"),
        "api_key": os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"),
        "api_secret": os.getenv("LLM_API_SECRET"),
        "base_url": os.getenv("LLM_BASE_URL"),
        "vision_base_url": os.getenv("LLM_VISION_BASE_URL"),
        "vision_api_key": os.getenv("LLM_VISION_API_KEY"),
        "vision_model_id": os.getenv("LLM_VISION_MODEL_ID"),
    }
    extraction = {
        "min_text_length": os.getenv("MIN_TEXT_LENGTH"),
        "raw_text_preview": os.getenv("RAW_TEXT_PREVIEW"),
        "max_retries": os.getenv("MAX_RETRIES"),
        "retry_delay": os.getenv("RETRY_DELAY"),
        "concurrent_workers": os.getenv("CONCURRENT_WORKERS"),
        "dpi": os.getenv("DPI"),
    }

    env_cfg = {
        "llm": {k: v for k, v in llm.items() if v not in (None, "")},
        "extraction": {},
    }

    for key, value in extraction.items():
        if value in (None, ""):
            continue
        if key in {"min_text_length", "raw_text_preview", "max_retries", "concurrent_workers", "dpi"}:
            env_cfg["extraction"][key] = int(value)
        elif key == "retry_delay":
            env_cfg["extraction"][key] = float(value)

    return env_cfg


def load_config(path: str = None):
    global _CONFIG
    load_dotenv()

    cfg = deepcopy(_DEFAULT_CONFIG)
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            file_cfg = json.load(f)
        cfg = _merge_dict(cfg, file_cfg)

    cfg = _merge_dict(cfg, _env_config())
    _CONFIG = cfg
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
