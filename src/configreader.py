import math
import random
import json
import os
import  tempfile
import threading
import shutil
from os import path
from cryptography.fernet import Fernet, InvalidToken
from datetime import datetime, timedelta
from libuniversal import ConfigKey, MessageKey, StorageKey, TimeKey, Paths

SHUTDOWN_LOOT_BOX_ODDS = 90
SHUTDOWN_VOUCHER_ODDS = 50

LOOT_BOX_ODDS = 80
VOUCHER_ODDS = 65

DEFAULT_VOUCHER_LIMIT = 5
DEFAULT_LOOT_BOX_LIMIT = 5

cfg = None
json_data = {}
json_time_data = {}
application_path = None

key = Fernet.generate_key()

default_cfg = {
    ConfigKey.HOST.value: "127.0.0.1",
    ConfigKey.PORT.value: 65432, 
    ConfigKey.SHUTDOWN_TIMES.value: ["23:00:00", "23:30:00", "00:00:00"], 
    ConfigKey.ENFORCED_SHUTDOWN_TIMES.value: ["01:00:00"],
    ConfigKey.UP_TIMES.value: ["05:00:00"],
    ConfigKey.STREAK_SHIFT.value: "04:00",
    ConfigKey.NETWORKS.value: ["Ethernet", "Wi-Fi"],
    ConfigKey.MILITARY_TIME.value: False,
    ConfigKey.SOUND_ON.value: True,
    ConfigKey.WARNING_MINUTES.value: 15,
    ConfigKey.KEY.value: key.decode('utf-8')
}

def now_datetime_to_str() -> str:
    return datetime.strftime(datetime.now(), '%m/%d/%y %H:%M:%S')

default_storage = {
    StorageKey.VOUCHER: 3,
    StorageKey.SINCE_LAST_RELAPSE: now_datetime_to_str(),
    StorageKey.VOUCHER_LIMIT: 5,
    StorageKey.VOUCHERS_USED: [],
    StorageKey.MANUAL_USED: False
}

default_time = {
    TimeKey.LAST_TIME_ACTIVE: now_datetime_to_str()
}

def set_application_path(path):
    global application_path
    application_path = path

def get_config() -> dict:
    global cfg
    global application_path
    global key
    
    cfg_path = os.path.join(application_path, Paths.CONFIG_FILE.value)

    if cfg is None:
        # Reading config
        try:
            with open(cfg_path, 'r') as f:
                cfg = json.load(f)
        except FileNotFoundError:
            # If config file doesn't exist, create it with default settings
            with open(cfg_path, 'w') as json_file:
                json.dump(default_cfg, json_file, indent=4)
            raise Exception(f"Config file was not found and has been created at {cfg_path}. Please configure it then re-launch")
        except json.JSONDecodeError as e:
            raise Exception(f"Error decoding JSON from config file: {e}")

    if ConfigKey.KEY in cfg:
        key = cfg[ConfigKey.KEY].encode('utf-8')  # Ensure key is in bytes for Fernet

    return cfg

def get_storage() -> dict:
    global json_data
    with _storage_lock:
        if not json_data:
            json_data, _ = _load_or_recover(get_json_path(), default_storage)
            # ensure a valid current file exists
            save_storage()
        return json_data

def get_json_time() -> dict:
    global json_time_data
    with _time_lock:
        if not json_time_data:
            json_time_data, _ = _load_or_recover(get_json_time_path(), default_time)
            save_json_time()
        return json_time_data

def force_storage(forced_json_data):
    global json_data
    with _storage_lock:
        json_data = forced_json_data
        save_storage()

# encrypts and saves storage
def save_storage():
    with _storage_lock:
        rotate_backups(get_json_path(), keep=2)
        encrypted = Fernet(key).encrypt(json.dumps(json_data, indent=2).encode("utf-8"))
        atomic_write_bytes(get_json_path(), encrypted)

# encrypts and saves time json file
def save_json_time():
    with _time_lock:
        rotate_backups(get_json_time_path(), keep=2)
        encrypted = Fernet(key).encrypt(json.dumps(json_time_data, indent=2).encode("utf-8"))
        atomic_write_bytes(get_json_time_path(), encrypted)

def use_voucher(time):
    with _storage_lock:
        json_data[StorageKey.VOUCHER] -= 1
        json_data.setdefault(StorageKey.VOUCHERS_USED, []).append(time)
        save_storage()
    return f"Used voucher on time {time}"

def get_voucher_limit() -> int:
    with _storage_lock:
        if StorageKey.VOUCHER_LIMIT in json_data:
            return json_data[StorageKey.VOUCHER_LIMIT]
        json_data[StorageKey.VOUCHER_LIMIT] = DEFAULT_VOUCHER_LIMIT
        save_storage()
        return DEFAULT_VOUCHER_LIMIT


def get_vouchers_used() -> int:
    with _storage_lock:
        vouchers_used = 0
        if StorageKey.VOUCHERS_USED in json_data:
            vouchers_used = len(json_data[StorageKey.VOUCHERS_USED])
        
        return vouchers_used

def get_loot_box_limit() -> int:
    with _storage_lock:
        if StorageKey.LOOT_BOX_LIMIT in json_data:
            return json_data[StorageKey.LOOT_BOX_LIMIT]
        
        json_data[StorageKey.LOOT_BOX_LIMIT] = DEFAULT_LOOT_BOX_LIMIT
        save_storage()
        return DEFAULT_LOOT_BOX_LIMIT

# adds a voucher number to json file then removes voucher
def unuse_voucher(time):
    with _storage_lock:
        if time in json_data.get(StorageKey.VOUCHERS_USED, []):
            json_data[StorageKey.VOUCHER] += 1
            json_data[StorageKey.VOUCHERS_USED].remove(time)
            save_storage()
            return f"Unused voucher on time {time}"
        return "Error: The specified time was not vouched for."

# remove voucher_used tag to json storage
def remove_voucher(time):
    with _storage_lock:
        if time in json_data.get(StorageKey.VOUCHERS_USED, []):
            json_data[StorageKey.VOUCHERS_USED].remove(time)
            save_storage()

def set_manual_override(used: bool):
    with _storage_lock:
        json_data[StorageKey.MANUAL_USED] = used
        save_storage()

def add_voucher(amount: int = 1):
    with _storage_lock:
        current_vouchers = json_data.get(StorageKey.VOUCHER, 0)
        json_data[StorageKey.VOUCHER] = min(
            get_voucher_limit() - get_vouchers_used(),
            current_vouchers + amount
        )
        save_storage()

def reset_relapse_time():
    with _storage_lock:
        json_data[StorageKey.SINCE_LAST_RELAPSE] = now_datetime_to_str()
        save_storage()

def str_to_datetime(time: str) -> datetime:
    return datetime.strptime(time, '%m/%d/%y %H:%M:%S')

def get_json_path():
    return os.path.join(application_path, Paths.JSON_FILE.value)

def get_json_time_path():
    return os.path.join(application_path, Paths.JSON_TIME_FILE.value)

def try_add_loot_box():
    add_box = random.randint(0, 99) < LOOT_BOX_ODDS
    with _storage_lock:
        if get_loot_box_limit() <= get_all_loot_boxes():
            return
        if add_box:
            json_data[StorageKey.LOOT_BOXES] = json_data.get(StorageKey.LOOT_BOXES, 0) + 1
        save_storage()

def try_add_shutdown_loot_box():
    add_box = random.randint(0, 99) < SHUTDOWN_LOOT_BOX_ODDS
    with _storage_lock:
        if get_loot_box_limit() <= get_all_loot_boxes():
            return
        if add_box:
            json_data[StorageKey.SHUTDOWN_LOOT_BOXES] = json_data.get(StorageKey.SHUTDOWN_LOOT_BOXES, 0) + 1
        save_storage()

def get_all_loot_boxes() -> int:
    loot_boxes = 0

    loot_boxes += get_normal_loot_boxes()
    loot_boxes += get_shutdown_loot_boxes()

    return loot_boxes

def get_normal_loot_boxes() -> int:
    return json_data.get(StorageKey.LOOT_BOXES, 0)

def get_shutdown_loot_boxes() -> int:
    return json_data.get(StorageKey.SHUTDOWN_LOOT_BOXES, 0)

def open_loot_box() -> int:
    with _storage_lock:
        voucher_amount = 0
        box_amount = get_normal_loot_boxes()
        if box_amount > 0 and random.randint(0, 99) < VOUCHER_ODDS:
            voucher_amount += 1
        if StorageKey.LOOT_BOXES in json_data:
            json_data[StorageKey.LOOT_BOXES] = max(0, box_amount - 1)

        add_voucher(voucher_amount)
        save_storage()

        return voucher_amount

def open_shutdown_loot_box() -> int:
    with _storage_lock:
        voucher_amount = 0
        streak = get_streak()
        box_amount = get_shutdown_loot_boxes()
        if box_amount > 0 and random.randint(0, 99) < max(SHUTDOWN_VOUCHER_ODDS - streak // 14, 5):
            voucher_amount += 1
        if StorageKey.SHUTDOWN_LOOT_BOXES in json_data:
            json_data[StorageKey.SHUTDOWN_LOOT_BOXES] = max(0, box_amount - 1)

        add_voucher(voucher_amount)
        save_storage()

        return voucher_amount

def get_a_loot_box() -> MessageKey:
    shutdown_amount = get_shutdown_loot_boxes()
    normal_amount = get_normal_loot_boxes()
    total_amount = get_all_loot_boxes()

    if total_amount <= 0: 
        return MessageKey.NO_LOOT_BOX

    normal_chance = (normal_amount * 100) / float(total_amount)

    if normal_amount > 0 and random.randint(0, 99) < normal_chance:
        return MessageKey.NORMAL_LOOT_BOX
    elif shutdown_amount > 0:
        return MessageKey.SHUTDOWN_LOOT_BOX

    return MessageKey.NO_LOOT_BOX

def set_active_time():
    with _time_lock:
        json_time_data[TimeKey.LAST_TIME_ACTIVE] = now_datetime_to_str()
        save_json_time()

def get_active_time() -> datetime:
    if TimeKey.LAST_TIME_ACTIVE in json_time_data:
        return str_to_datetime(json_time_data[TimeKey.LAST_TIME_ACTIVE])
    else:
        return datetime.now()

def get_manual_used() -> bool:
    return json_data.get(StorageKey.MANUAL_USED, False)

def get_streak() -> int:
    if (ConfigKey.STREAK_SHIFT.value not in cfg or
        StorageKey.SINCE_LAST_RELAPSE.value not in json_data):
        return 0

    now = datetime.now()
    tomorrow = now + timedelta(days=1)

    cutoff_time = datetime.strptime(cfg[ConfigKey.STREAK_SHIFT.value], '%H:%M')
    cutoff_time = cutoff_time.replace(year=now.year, month=now.month, day=now.day)

    if now > cutoff_time:
        cutoff_time = cutoff_time.replace(year=tomorrow.year, month=tomorrow.month, day=tomorrow.day)

    last_relapse = str_to_datetime(json_data[StorageKey.SINCE_LAST_RELAPSE.value])
    return clamp(math.floor((now - last_relapse).total_seconds() / 86400), 0, 999999)

def clamp(n, smallest, largest): 
    return max(smallest, min(n, largest))

def atomic_write_bytes(path: str, data: bytes):
    directory = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=os.path.basename(path) + ".", dir=directory)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)  # atomic on Windows + Linux
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except:
            pass

def rotate_backups(path: str, keep: int = 2):
    for i in range(keep, 0, -1):
        src = f"{path}.bak{i}"
        dst = f"{path}.bak{i+1}"
        if os.path.exists(src):
            os.replace(src, dst)
    if os.path.exists(path):
        shutil.copy2(path, f"{path}.bak1")

def load_storage_or_recover(default: dict) -> dict:
    paths = [get_json_path(), get_json_path()+".bak1", get_json_path()+".bak2"]
    f = Fernet(key)

    for p in paths:
        if not os.path.isfile(p):
            continue
        try:
            raw = open(p, "rb").read()
            data = json.loads(f.decrypt(raw).decode("utf-8"))
            # if we loaded from a backup, restore it to main
            if p != get_json_path():
                atomic_write_bytes(get_json_path(), raw)
            return data
        except (InvalidToken, json.JSONDecodeError, OSError):
            continue

    # nothing worked
    return default

def _load_or_recover(path: str, default: dict) -> tuple[dict, bytes | None]:
    """
    Try: path, path.bak1, path.bak2. Return (data_dict, raw_bytes_used_or_None).
    """
    candidates = [path, f"{path}.bak1", f"{path}.bak2"]
    f = Fernet(key)

    for p in candidates:
        if not os.path.isfile(p):
            continue
        try:
            raw = open(p, "rb").read()
            data = json.loads(f.decrypt(raw).decode("utf-8"))
            # If we loaded from backup, restore to main.
            if p != path:
                atomic_write_bytes(path, raw)
            return data, raw
        except (InvalidToken, json.JSONDecodeError, OSError):
            continue

    return default, None

_storage_lock = threading.RLock()
_time_lock = threading.RLock()

def init(path):
    set_application_path(path)
    global json_data, json_time_data

    get_config()  # loads key from config

    with _storage_lock:
        json_data, _ = _load_or_recover(get_json_path(), default_storage)
        save_storage()

    with _time_lock:
        json_time_data, _ = _load_or_recover(get_json_time_path(), default_time)
        save_json_time()