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
        "azure_api_version": "2024-02-15-preview",
        "azure_endpoint": "",
    },
    "extraction": {
        "min_text_length": 100,
        "min_text_alpha_ratio": 0.22,
        "raw_text_preview": 500,
        "max_retries": 3,
        "retry_delay": 1.0,
        "concurrent_workers": 4,
        "dpi": 150,
        "max_upload_bytes": 52428800,
        "vision_fallback_min_chars": 30,
        "fields": {},
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
        "azure_api_version": os.getenv("LLM_AZURE_API_VERSION"),
        "azure_endpoint": os.getenv("LLM_AZURE_ENDPOINT"),
    }
    extraction = {
        "min_text_length": os.getenv("MIN_TEXT_LENGTH"),
        "min_text_alpha_ratio": os.getenv("MIN_TEXT_ALPHA_RATIO"),
        "raw_text_preview": os.getenv("RAW_TEXT_PREVIEW"),
        "max_retries": os.getenv("MAX_RETRIES"),
        "retry_delay": os.getenv("RETRY_DELAY"),
        "concurrent_workers": os.getenv("CONCURRENT_WORKERS"),
        "dpi": os.getenv("DPI"),
        "max_upload_bytes": os.getenv("MAX_UPLOAD_BYTES"),
        "vision_fallback_min_chars": os.getenv("VISION_FALLBACK_MIN_CHARS"),
    }

    env_cfg = {
        "llm": {k: v for k, v in llm.items() if v not in (None, "")},
        "extraction": {},
    }

    for key, value in extraction.items():
        if value in (None, ""):
            continue
        if key in {
            "min_text_length",
            "raw_text_preview",
            "max_retries",
            "concurrent_workers",
            "dpi",
            "max_upload_bytes",
            "vision_fallback_min_chars",
        }:
            env_cfg["extraction"][key] = int(value)
        elif key in {"retry_delay", "min_text_alpha_ratio"}:
            env_cfg["extraction"][key] = float(value)

    # Support custom extraction fields via JSON string
    fields_json = os.getenv("EXTRACTION_FIELDS")
    if fields_json:
        try:
            env_cfg["extraction"]["fields"] = json.loads(fields_json)
        except json.JSONDecodeError:
            pass

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
