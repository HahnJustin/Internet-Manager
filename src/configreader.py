import math
import random
import json  # Removed import of yaml
import os
from os import path
from cryptography.fernet import Fernet
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
    global key

    # decrypt storage
    if not json_data and os.path.isfile(get_json_path()):
        with open(get_json_path(), 'rb') as f: 
            encrypted_data = f.read()
            fernet = Fernet(key)
            decrypted_data = fernet.decrypt(encrypted_data)
            json_data = json.loads(decrypted_data.decode('utf-8'))

    return json_data

def get_json_time() -> dict:
    global json_time_data
    global key

    # decrypt storage
    if not json_time_data and os.path.isfile(get_json_time_path()):
        with open(get_json_time_path(), 'rb') as f: 
            encrypted_data = f.read()
            fernet = Fernet(key)
            try:
                decrypted_data = fernet.decrypt(encrypted_data)
                json_time_data = json.loads(decrypted_data.decode('utf-8'))
            except:
                json_time_data = {TimeKey.LAST_TIME_ACTIVE: now_datetime_to_str()}
                save_json_time()

    return json_time_data

def force_storage(forced_json_data):
    global json_data
    json_data = forced_json_data
    save_storage()

# encrypts and saves storage
def save_storage():
    global key
    fernet = Fernet(key)
    encrypted = fernet.encrypt(json.dumps(json_data, indent=2).encode('utf-8'))

    with open(get_json_path(), 'wb') as f:
        f.write(encrypted)

# encrypts and saves time json file
def save_json_time():
    global key
    fernet = Fernet(key)
    encrypted = fernet.encrypt(json.dumps(json_time_data, indent=2).encode('utf-8'))

    with open(get_json_time_path(), 'wb') as f:
        f.write(encrypted)

def use_voucher(time):
    json_data[StorageKey.VOUCHER] -= 1

    if StorageKey.VOUCHERS_USED not in json_data:
        json_data[StorageKey.VOUCHERS_USED] = []
    json_data[StorageKey.VOUCHERS_USED].append(time)
    save_storage()

    return f"Used voucher on time {time}"

def get_voucher_limit() -> int:
    if StorageKey.VOUCHER_LIMIT in json_data:
        return json_data[StorageKey.VOUCHER_LIMIT]
    
    json_data[StorageKey.VOUCHER_LIMIT] = DEFAULT_VOUCHER_LIMIT
    save_storage()
    return DEFAULT_VOUCHER_LIMIT

def get_vouchers_used() -> int:
    vouchers_used = 0
    if StorageKey.VOUCHERS_USED in json_data:
        vouchers_used = len(json_data[StorageKey.VOUCHERS_USED])
    
    return vouchers_used

def get_loot_box_limit() -> int:
    if StorageKey.LOOT_BOX_LIMIT in json_data:
        return json_data[StorageKey.LOOT_BOX_LIMIT]
    
    json_data[StorageKey.LOOT_BOX_LIMIT] = DEFAULT_LOOT_BOX_LIMIT
    save_storage()
    return DEFAULT_LOOT_BOX_LIMIT

# adds a voucher number to json file then removes voucher
def unuse_voucher(time):
    if StorageKey.VOUCHERS_USED in json_data and time in json_data[StorageKey.VOUCHERS_USED]:
        json_data[StorageKey.VOUCHER] += 1
        remove_voucher(time)
        return f"Unused voucher on time {time}"
    return "Error: The specified time was not vouched for."

# remove voucher_used tag to json storage
def remove_voucher(time):
    if time in json_data.get(StorageKey.VOUCHERS_USED, []):
        json_data[StorageKey.VOUCHERS_USED].remove(time)
        save_storage()

def set_manual_override(used: bool):
    if json_data is not None:
        json_data[StorageKey.MANUAL_USED] = used
        save_storage()

def add_voucher(amount: int = 1):
    if json_data is not None and StorageKey.VOUCHER in json_data:
        current_vouchers = json_data[StorageKey.VOUCHER]
        json_data[StorageKey.VOUCHER] = min(get_voucher_limit() - get_vouchers_used(), current_vouchers + amount)
        save_storage()

def reset_relapse_time():
    if json_data is not None:
        json_data[StorageKey.SINCE_LAST_RELAPSE] = now_datetime_to_str()
        save_storage()

def now_datetime_to_str() -> str:
    return datetime.strftime(datetime.now(), '%m/%d/%y %H:%M:%S')

def str_to_datetime(time: str) -> datetime:
    return datetime.strptime(time, '%m/%d/%y %H:%M:%S')

def get_json_path():
    return os.path.join(application_path, Paths.JSON_FILE.value)

def get_json_time_path():
    return os.path.join(application_path, Paths.JSON_TIME_FILE.value)

def try_add_loot_box():
    add_box = random.randint(0, 99) < LOOT_BOX_ODDS

    if get_loot_box_limit() <= get_all_loot_boxes():
        return

    if StorageKey.LOOT_BOXES in json_data and add_box:
        json_data[StorageKey.LOOT_BOXES] += 1
    elif add_box:
        json_data[StorageKey.LOOT_BOXES] = 1
    save_storage()

def try_add_shutdown_loot_box():
    add_box = random.randint(0, 99) < SHUTDOWN_LOOT_BOX_ODDS

    if get_loot_box_limit() <= get_all_loot_boxes():
        return

    if StorageKey.SHUTDOWN_LOOT_BOXES in json_data and add_box:
        json_data[StorageKey.SHUTDOWN_LOOT_BOXES] += 1
    elif add_box:
        json_data[StorageKey.SHUTDOWN_LOOT_BOXES] = 1
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