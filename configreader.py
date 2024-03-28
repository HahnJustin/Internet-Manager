import yaml
from libuniversal import ConfigKey,  Paths

cfg = None

def get_config() -> dict:
    global cfg
    
    if cfg is None:
        # Reading config
        with open(Paths.CONFIG_FILE) as f:
            cfg = yaml.load(f, Loader=yaml.FullLoader)

    return cfg