import yaml
import os
import json
from libuniversal import ConfigKey,  Paths

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