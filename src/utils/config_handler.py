import json
from pathlib import Path
from typing import Any, Dict

# Absolute path to config.json at the repo root (two levels up from src/utils)
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"


def load_config() -> Dict[str, Any]:
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def has_integration(name: str) -> bool:
    return bool(load_config().get(name))


def is_slack_enabled() -> bool:
    return has_integration("slack")


def is_google_enabled() -> bool:
    return has_integration("google")

