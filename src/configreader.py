import yaml
import os
import json
import sys
from os import path
from datetime import datetime
from libuniversal import ConfigKey, StorageKey, Paths

cfg = None
json_data = {}
application_path = None

default_cfg = {ConfigKey.HOST.value: str("127.0.0.1"),
            ConfigKey.PORT.value : 65432, 
            ConfigKey.SHUTDOWN_TIMES.value : ["23:00:00","0:00:00"], 
            ConfigKey.ENFORCED_SHUTDOWN_TIMES.value: ["1:00:00","2:00:00"],
            ConfigKey.UP_TIMES.value : ["5:00:00"],
            ConfigKey.STREAK_SHIFT.value: "4:00",
            ConfigKey.ETHERNET.value : ["Ethernet", "Ethernet 2"],
            ConfigKey.MILITARY_TIME.value : True,
            ConfigKey.SOUND_ON.value : True,
            ConfigKey.WARNING_MINUTES.value : 15}

def set_application_path(path):
    global application_path
    application_path = path

def get_config() -> dict:
    global cfg
    global application_path
    
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
            cfg = yaml.load(f, Loader=yaml.FullLoader)

    return cfg

def get_storage() -> dict:
    global json_data
    
    # apparently empty dicts evaluate to false
    if not json_data and os.path.isfile(get_json_path()):
        f = open(get_json_path()) 
        json_data = json.load(f)
    return json_data

def force_storage(forced_json_data):
    global json_data
    json_data = forced_json_data
    save_storage()

def save_storage():
    with open(get_json_path(), 'w') as f:
        json.dump(json_data, f)

def use_voucher(time):
    json_data[StorageKey.VOUCHER] -= 1

    if not StorageKey.VOUCHERS_USED in json_data:
        json_data[StorageKey.VOUCHERS_USED] = []
    json_data[StorageKey.VOUCHERS_USED].append(time)
    save_storage()

    return f"Used voucher on time {time}"

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
    if json_data and StorageKey.VOUCHER in json_data:
        json_data[StorageKey.VOUCHER] += 1
        save_storage()

def reset_relapse_time():
    if json_data:
        json_data[StorageKey.SINCE_LAST_RELAPSE] =  datetime.strftime(datetime.now(), '%m/%d/%y %H:%M:%S')
        save_storage()

def str_to_datetime(time : str) -> datetime:
    return datetime.strptime(time, '%m/%d/%y %H:%M:%S')

def get_json_path():
    return path.abspath(path.join(path.dirname(__file__), Paths.JSON_FILE.value))