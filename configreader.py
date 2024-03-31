import yaml
import os
import json
from datetime import datetime, timedelta
from libuniversal import ConfigKey, StorageKey, Paths

cfg = None
json_data = {}

def get_config() -> dict:
    global cfg
    
    if cfg is None:
        # Reading config
        with open(Paths.CONFIG_FILE) as f:
            cfg = yaml.load(f, Loader=yaml.FullLoader)

    return cfg

def get_storage() -> dict:
    global json_data
    
    # apparently empty dicts evaluate to false
    if not json_data and os.path.isfile(Paths.JSON_FILE):
        f = open(Paths.JSON_FILE) 
        json_data = json.load(f)
    return json_data

def save_storage():
    with open(Paths.JSON_FILE, 'w') as f:
        json.dump(json_data, f)

def use_voucher(time):
    real_time = str_to_datetime(time)
    json_data[StorageKey.VOUCHER] -= 1

    if not StorageKey.VOUCHERS_USED in json_data:
        json_data[StorageKey.VOUCHERS_USED] = []
    json_data[StorageKey.VOUCHERS_USED].append(time)
    save_storage()

    return f"Used voucher on time {time}"
    #add voucher_used tag to json storage that takes in a list of time stamps
    #basically every time a time data tries to be triggered check the vouched list
    #is that exact time is in the vouched list, ignore the trigger, remove it from the list (call unuse_voucher)

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

def reset_relapse_time():
    if json_data:
        json_data[StorageKey.SINCE_LAST_RELAPSE] =  datetime.strftime(datetime.now(), '%m/%d/%y %H:%M:%S')
        save_storage()

def str_to_datetime(time : str) -> datetime:
    return datetime.strptime(time, '%m/%d/%y %H:%M:%S')