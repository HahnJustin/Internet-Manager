from enum import Enum
import os
import sys

class Actions(str, Enum):
    SEARCH = "search"
    INTERNET_OFF = "internet_off"
    INTERNET_ON = "internet_on"
    GRAB_CONFIG = "grab_config"
    GRAB_STORAGE = "grab_storage"
    INTERNET_STATUS = "internet_status"
    ADMIN_STATUS = "admin_status"
    USED_VOUCHER = "used_voucher"
    UNUSED_VOUCHER = "unused_voucher"
    RELAPSE = "relapse"
    ADD_VOUCHER = "add_voucher"
    CLOSE_SERVER = "close_server"
    LOOT_CHECK = "loot_check"
    LOOT_OPEN = "loot_open"
    NEW_LOOT = "new_loot"
    GET_LOOT = "get_loot"

class MessageKey(str, Enum):
    RESULT = "result"
    NORMAL_LOOT_BOX = "loot_box"
    SHUTDOWN_LOOT_BOX = "shutdown_loot_box"
    ALL_LOOT_BOXES = "all_loot_boxes"
    NO_LOOT_BOX = "no_box"

class ConfigKey(str, Enum):
    STREAK_SHIFT = "streak_shift"
    UP_TIMES = "up_times"
    SHUTDOWN_TIMES = "shutdown_times"
    ENFORCED_SHUTDOWN_TIMES = "enforced_shutdown_times"
    NETWORKS = "networks"
    HOST = "host"
    PORT = "port"
    MILITARY_TIME = "military_time"
    SOUND_ON = "sound_on"
    WARNING_MINUTES = "warning_minutes"
    KEY = "key"
    DEBUG = "debug"
    DISABLED = "disabled"

class StorageKey(str, Enum):
    SINCE_LAST_RELAPSE = "last_relapse"
    VOUCHER = "voucher"
    VOUCHERS_USED = "vouchers_used"
    VOUCHER_LIMIT = "voucher_limit"
    MANUAL_USED = "manual_used"
    LOOT_BOXES = "loot_boxes"
    SHUTDOWN_LOOT_BOXES = "shutdown_loot_boxes"
    LOOT_BOX_LIMIT = "loot_box_limit"

class TimeKey(str, Enum):
    LAST_TIME_ACTIVE = "last_active"

class Paths(str, Enum):
    JSON_FILE = "storage.txt"
    JSON_TIME_FILE = "active_time.txt"
    CONFIG_FILE = "config.json"
    CLIENT_CONFIG_FILE = "client-config.yaml"
    ASSETS_FOLDER = "assets"
    FONTS_FOLDER = "fonts"
    SFX_FOLDER = "sfx"

def app_base_dir() -> str:
    # PyInstaller exe: sys.executable is the exe path
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # Running as .py
    return os.path.dirname(os.path.abspath(__file__))

def resource_path(relative_path: str) -> str:
    """
    Absolute path to bundled/adjacent resources.
    - PyInstaller one-file: uses _MEIPASS
    - Else: uses the folder containing the exe/script (NOT the working directory)
    """
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = app_base_dir()

    return os.path.join(base_path, relative_path.lstrip("/\\"))