import json
import os
from pathlib import Path
from fastapi import Depends, HTTPException

def _get_config_file_path() -> Path:
    if config_dir_override := os.getenv("BERNERSPACE_CONFIG_DIR"):
        return Path(config_dir_override) / "config.json"

    system = os.name
    home = Path.home()

    if system == "nt":
        app_data = Path(os.getenv("APPDATA", home / "AppData" / "Roaming"))
        config_dir = app_data / "bernerspace"
    elif system == "posix" and "darwin" in os.uname().sysname.lower():
        config_dir = home / ".bernerspace"
    else:
        xdg_config_home = os.getenv("XDG_CONFIG_HOME", home / ".config")
        config_dir = Path(xdg_config_home) / "bernerspace"

    return config_dir / "config.json"

def get_current_user_email() -> str:
    config_file = _get_config_file_path()

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        email = config.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Email not found in config.")
        
        return email

    except (FileNotFoundError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Unauthorized: Not logged in. Please run 'bernitespace init'.")