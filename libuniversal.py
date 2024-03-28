from enum import Enum

class Actions(str, Enum):
    SEARCH = "search"
    INTERNET_OFF = "internet_off"
    INTERNET_ON = "internet_on"
    GRAB_CONFIG = "grab_config"
    GRAB_STORAGE = "grab_storage"
    INTERNET_STATUS = "internet_status"
    ADMIN_STATUS = "admin_status"

class MessageKey(str, Enum):
    RESULT = "result"

class ConfigKey(str, Enum):
    STREAK_SHIFT = "streak_shift"
    UP_TIMES = "up_times"
    SHUTDOWN_TIMES = "shutdown_times"
    ETHERNET = "ethernet"
    HOST = "host"
    PORT = "port"
    DEBUG = "debug"

class StorageKey(str, Enum):
    SINCE_LAST_RELAPSE = "last_relapse"
    VOUCHER = "voucher"

class Paths(str, Enum):
    JSON_FILE = "storage.json"
    CONFIG_FILE = "config.yaml"
    ASSETS_FOLDER = "assets"