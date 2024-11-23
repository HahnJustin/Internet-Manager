import math
import random
import yaml
import os
import json
from os import path
from cryptography.fernet import Fernet
from datetime import datetime, timedelta
from libuniversal import ConfigKey, MessageKey, StorageKey, Paths

SHUTDOWN_LOOT_BOX_ODDS = 90
SHUTDOWN_VOUCHER_ODDS = 50

LOOT_BOX_ODDS = 80
VOUCHER_ODDS = 65

DEFAULT_VOUCHER_LIMIT = 5
DEFAULT_LOOT_BOX_LIMIT = 5

cfg = None
json_data = {}
application_path = None

key = Fernet.generate_key()

default_cfg = {ConfigKey.HOST.value: str("127.0.0.1"),
            ConfigKey.PORT.value : 65432, 
            ConfigKey.SHUTDOWN_TIMES.value : ["23:00:00","0:00:00"], 
            ConfigKey.ENFORCED_SHUTDOWN_TIMES.value: ["1:00:00","2:00:00"],
            ConfigKey.UP_TIMES.value : ["5:00:00"],
            ConfigKey.STREAK_SHIFT.value: "4:00",
            ConfigKey.ETHERNET.value : ["Ethernet", "Ethernet 2"],
            ConfigKey.MILITARY_TIME.value : True,
            ConfigKey.SOUND_ON.value : True,
            ConfigKey.WARNING_MINUTES.value : 15,
            ConfigKey.KEY.value : key.decode('utf-8')}

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
            f = open(cfg_path)
        except OSError:
            with open(cfg_path, 'w') as yaml_file:
                yaml_file.write("# Config Class for Internet Manager's Server Component \n")
                yaml_file.write("# All Times must be in military time \n")
                yaml_file.write("# By Justin Hahn 2024 [https://github.com/HahnJustin] \n \n")
                yaml.dump(default_cfg, yaml_file)

                raise Exception(f"Server did not have a config, so it made one at {cfg_path}")
        with f:
            cfg = yaml.safe_load(f)

    if ConfigKey.KEY in cfg:
        key = cfg[ConfigKey.KEY]

    return cfg

def get_storage() -> dict:
    global json_data
    global key

    # decrypt storage
    if not json_data and os.path.isfile(get_json_path()):
        f = open(get_json_path()) 
        encodedBytes = bytes(f.read(), 'utf-8')
        fernet = Fernet(key)
        json_data = json.loads(fernet.decrypt(encodedBytes))

    return json_data

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

def use_voucher(time):
    json_data[StorageKey.VOUCHER] -= 1

    if not StorageKey.VOUCHERS_USED in json_data:
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
    return "Error that time was not vouched for"

# remove voucher_used tag to json storage
def remove_voucher(time):
    if time in json_data[StorageKey.VOUCHERS_USED]:
        json_data[StorageKey.VOUCHERS_USED].remove(time)
        save_storage()

def set_manual_override(used : bool):
    if json_data and StorageKey.MANUAL_USED in json_data:
        json_data[StorageKey.MANUAL_USED] = used
        save_storage()

def add_voucher():
    add_voucher(1)

def add_voucher(amount : int):
    if json_data and StorageKey.VOUCHER in json_data:
        current_vouchers = json_data[StorageKey.VOUCHER]
        json_data[StorageKey.VOUCHER] = min(get_voucher_limit(), current_vouchers + amount)
        save_storage()

def reset_relapse_time():
    if json_data:
        json_data[StorageKey.SINCE_LAST_RELAPSE] = now_datetime_to_str()
        save_storage()

def now_datetime_to_str() -> str:
    return datetime.strftime(datetime.now(), '%m/%d/%y %H:%M:%S')

def str_to_datetime(time : str) -> datetime:
    return datetime.strptime(time, '%m/%d/%y %H:%M:%S')

def get_json_path():
    return os.path.join(application_path, Paths.JSON_FILE.value)

def try_add_loot_box():
    add_box = random.randint(0,99) < LOOT_BOX_ODDS

    if get_loot_box_limit() <= get_all_loot_boxes():
        return

    if StorageKey.LOOT_BOXES in json_data and add_box:
        json_data[StorageKey.LOOT_BOXES] += 1
    elif add_box:
        json_data[StorageKey.LOOT_BOXES] = 1
    save_storage()

def try_add_shutdown_loot_box():
    add_box = random.randint(0,99) < SHUTDOWN_LOOT_BOX_ODDS

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
    loot_boxes = 0

    if StorageKey.LOOT_BOXES in json_data:
        loot_boxes += json_data[StorageKey.LOOT_BOXES]

    return loot_boxes

def get_shutdown_loot_boxes() -> int:
    loot_boxes = 0

    if StorageKey.SHUTDOWN_LOOT_BOXES in json_data:
        loot_boxes += json_data[StorageKey.SHUTDOWN_LOOT_BOXES]

    return loot_boxes

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
    if box_amount > 0 and random.randint(0, 99) < max(SHUTDOWN_VOUCHER_ODDS - streak / 14, 5):
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

    if total_amount <= 0: return MessageKey.NO_LOOT_BOX

    normal_chance = (normal_amount * 100) / float(total_amount)

    if normal_amount > 0 and random.randint(0, 99) < normal_chance:
        return MessageKey.NORMAL_LOOT_BOX
    elif shutdown_amount > 0:
        return MessageKey.SHUTDOWN_LOOT_BOX

    return MessageKey.NO_LOOT_BOX


def set_if_shutdown(shutdown : bool):
    json_data[StorageKey.SHUTDOWN_SINCE_SHIFT] = shutdown
    save_storage()

def get_if_shutdown_since() -> bool:
    if StorageKey.SHUTDOWN_SINCE_SHIFT in json_data:
        return json_data[StorageKey.SHUTDOWN_SINCE_SHIFT]
    else:
        return False

def set_active_time():
    json_data[StorageKey.LAST_TIME_ACTIVE] = now_datetime_to_str()
    save_storage()

def get_active_time() -> datetime:
    if StorageKey.LAST_TIME_ACTIVE in json_data:
        return str_to_datetime(json_data[StorageKey.LAST_TIME_ACTIVE])
    else:
        return datetime.now()
    
def get_manual_used() -> bool:
    if StorageKey.MANUAL_USED in json_data:
        return json_data[StorageKey.MANUAL_USED]
    else:
        return False
    
def get_streak() -> int:

    if (not ConfigKey.STREAK_SHIFT in cfg or
        not StorageKey.SINCE_LAST_RELAPSE in json_data): return 0

    now = datetime.now()
    tomorrow = now + timedelta(days=1)

    cutoff_time = datetime.strptime(cfg[ConfigKey.STREAK_SHIFT], '%H:%M')
    cutoff_time = cutoff_time.replace(year=now.year, month=now.month, day=now.day)

    if now > cutoff_time:
        cutoff_time = cutoff_time.replace(year=tomorrow.year, month=tomorrow.month, day=tomorrow.day)

    last_relapse = str_to_datetime(json_data[StorageKey.SINCE_LAST_RELAPSE])
    return clamp(math.floor((now - last_relapse).total_seconds() / 86400), 0, 999999)

def clamp(n, smallest, largest): return max(smallest, min(n, largest))