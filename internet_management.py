
import subprocess
import os.path
import ctypes
import configreader
from libuniversal import ConfigKey

# from https://github.com/abagh0703/turn-off-wifi
CMD_BASE = 'cmd /c "{}"'  # first is remain/terminate, then is enable/disable
WIFI_CMD_BASE = 'wmic path win32_networkadapter where NetConnectionID="Wi-fI" call {}'
ETHERNET_CMD_BASE = 'netsh interface set interface {}'
WIFI_CMD_ENABLE = WIFI_CMD_BASE.format('enable')
WIFI_CMD_DISABLE = WIFI_CMD_BASE.format('disable')

internet_on = True

request_search = {
    "morpheus": "Follow the white rabbit. \U0001f430",
    "ring": "In the caves beneath the Misty Mountains. \U0001f48d",
    "\U0001f436": "\U0001f43e Playing ball! \U0001f3d0",
}

def execute_cmd(cmd):
    subprocess.call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

def turn_on_wifi():
    execute_cmd(CMD_BASE.format(WIFI_CMD_ENABLE))

def turn_off_wifi():
    execute_cmd(CMD_BASE.format(WIFI_CMD_DISABLE))

def turn_on_ethernet():
    global internet_on
    cfg = configreader.get_config()
    for ethernet in cfg[ConfigKey.ETHERNET]:
        execute_cmd(CMD_BASE.format(ETHERNET_CMD_BASE.format(ethernet) + " enabled"))
    internet_on = True

def turn_off_ethernet():
    global internet_on
    cfg = configreader.get_config()
    for ethernet in cfg[ConfigKey.ETHERNET]:
        execute_cmd(CMD_BASE.format(ETHERNET_CMD_BASE.format(ethernet) + " disabled"))
    internet_on = False

def is_admin():
    try:
        is_admin = (os.getuid() == 0)
    except AttributeError:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    return is_admin

def is_internet_on() -> bool:
    global internet_on
    return internet_on