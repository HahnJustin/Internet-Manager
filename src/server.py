#!/usr/bin/env python3

import threading
import time, traceback
import json
import os.path
import sys
import socket
import selectors
import libserver
import internet_management
import configreader
from playsound import playsound
from libuniversal import Actions, ConfigKey, StorageKey, Paths
from datetime import datetime, timedelta

SECONDS_DATA_UPDATE = 60

LAUNCH_GUI = 'xterm -e \"python gui.py\" &'

# Time is in milliseconds
GUI_THREAD_TIME = 1000

# Time is in seconds
SAVE_THREAD_TIME = 3

ASSET_FOLDER = "assets"

global now
global time_datas
global json_data

warned = False
sound_on = True
warning_sound_time = 15

class time_action_data():
    def __init__(self, time : datetime, action : Actions):
        self.datetime = time
        self.action = action

    def __str__(self) -> str:
        return datetime.strftime(self.datetime, '%m/%d/%y %H:%M:%S')

class StoppableThread(threading.Thread):

    def __init__(self,  *args, **kwargs):
        super(StoppableThread, self).__init__(*args, **kwargs)
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def every(delay, task):
    while True:
        time.sleep(delay)
        try:
            task()
        except Exception:
            traceback.print_exc()

def time_data_create(time : str, action : Actions):
    global tomorrow
    global now

    target = datetime.strptime(time, '%H:%M:%S')
    target = target.replace(year=now.year, month=now.month, day=now.day)

    if now > target:
        target = target.replace(year=tomorrow.year, month=tomorrow.month, day=tomorrow.day)

    time_datas.append(time_action_data(target, action))

def update():
    global sound_on
    global json_data
    global now
    global warning_sound_time
    global warned

    now = datetime.now()
    json_data = configreader.get_storage()

    if now > cutoff_time:
        recalculate_cutoff_time()
        cull_vouchers()
        configreader.set_manual_override(False)

    data = time_datas[0]
    warning_time = data.datetime - timedelta(minutes=warning_sound_time)

    if now > warning_time and not warned:
        warned = True
        play_sfx("warning.wav")

    # actual shutdown
    if data.datetime > now:
        return
    # vouched used condition
    if str(data) in json_data[StorageKey.VOUCHERS_USED]:
        play_sfx("vouched.wav")
        print(f"{data} - [VOUCHED] {data.action}")
    elif data.action == Actions.INTERNET_OFF:
        play_sfx("internet_off.wav")
        internet_management.turn_off_wifi()
        internet_management.turn_off_ethernet()
        print(f"{data} - {data.action}")
    elif data.action == Actions.INTERNET_ON:
        play_sfx("internet_on.wav")
        internet_management.turn_on_wifi()
        internet_management.turn_on_ethernet()
        print(f"{data} - {data.action}")
    recalculate_time(data)
    sort_data()
    warned = False

def recalculate_time(data: time_action_data):
   global tomorrow
   tomorrow = now + timedelta(days=1)
   data.datetime = data.datetime.replace(year=tomorrow.year, month=tomorrow.month, day=tomorrow.day)

def get_datetime():
    now = datetime.now()
    date = now.strftime("%m/%d/%Y")
    time = now.strftime("%H:%M:%S")
    return date, time

def launch_gui():
    os.system(LAUNCH_GUI)

def run_function_in_minute(func):
    thread = threading.Timer(60.0, func) # 60 seconds = 1 minute
    thread.daemon = True
    thread.start()

def string_now():
    return  datetime.strftime(datetime.now(), '%m/%d/%y %H:%M:%S')

def sort_data():
    global time_datas
    time_datas = sorted(time_datas, key=lambda x: x.datetime)

def accept_wrapper(sock):
    conn, addr = sock.accept()  # Should be ready to read
    print(f"Accepted connection from {addr}")
    conn.setblocking(False)
    message = libserver.Message(sel, conn, addr)
    sel.register(conn, selectors.EVENT_READ, data=message)

def recalculate_cutoff_time():
    global cutoff_time
    global now

    cutoff_time = datetime.strptime(cfg[ConfigKey.STREAK_SHIFT], '%H:%M')
    cutoff_time = cutoff_time.replace(year=now.year, month=now.month, day=now.day)

    if now > cutoff_time:
        cutoff_time = cutoff_time.replace(year=tomorrow.year, month=tomorrow.month, day=tomorrow.day)

def cull_vouchers():
    global cutoff_time
    
    last_cutoff = cutoff_time - timedelta(days=1)
    for i in reversed(range(len(json_data[StorageKey.VOUCHERS_USED]))):
        vouched_time = json_data[StorageKey.VOUCHERS_USED][i]
        vouched_datetime = configreader.str_to_datetime(vouched_time)
        print(f"hello {i} {vouched_datetime}")
        if last_cutoff > vouched_datetime:
            json_data[StorageKey.VOUCHERS_USED].pop(i)
    configreader.force_storage(json_data)
    
def play_sfx(sfx : str):
    if sound_on:
        try:
            playsound(resource_path(Paths.SFX_FOLDER + '\\' + sfx))
        except:
            playsound(resource_path(Paths.SFX_FOLDER + '\\' + sfx))

# Getting Application Path
if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the PyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app 
    # path into variable _MEIPASS'.
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
configreader.set_application_path(application_path)

# Defining basic time variables
now = datetime.now()
tomorrow = now + timedelta(days=1)

# Reading/Initializing storage json
json_data = {}
if os.path.isfile(configreader.get_json_path()):
   f = open(configreader.get_json_path()) 
   json_data = json.load(f)
else:
   json_data = {StorageKey.VOUCHER:3, StorageKey.SINCE_LAST_RELAPSE: string_now(),
                StorageKey.VOUCHER_LIMIT : 5, StorageKey.VOUCHERS_USED : [],
                StorageKey.MANUAL_USED : False}

# save json
configreader.force_storage(json_data)

# Reading config
cfg = configreader.get_config()

if ConfigKey.SOUND_ON in cfg:
    sound_on = cfg[ConfigKey.SOUND_ON]

if ConfigKey.WARNING_MINUTES in cfg:
    warning_sound_time = cfg[ConfigKey.WARNING_MINUTES]

# Modifying streak time
recalculate_cutoff_time()
cull_vouchers()

time_datas = []

# Intializing shutdown times
for shutdown_time in cfg[ConfigKey.SHUTDOWN_TIMES]:
    time_data_create(shutdown_time, Actions.INTERNET_OFF)

# Intializing enforced shutdown times
for enforced_time in cfg[ConfigKey.ENFORCED_SHUTDOWN_TIMES]:
    time_data_create(enforced_time, Actions.INTERNET_OFF)

# Intializing internet up times
for up_time in cfg[ConfigKey.UP_TIMES]:
    time_data_create(up_time, Actions.INTERNET_ON)

sort_data()

# Calculating what state the manager should be in:
if time_datas[-1].action == Actions.INTERNET_OFF:
    internet_management.turn_off_wifi()
    internet_management.turn_off_ethernet()
elif time_datas[-1].action == Actions.INTERNET_ON:
    internet_management.turn_on_wifi()
    internet_management.turn_on_ethernet()

data_thread = StoppableThread(target=lambda: every(0.25, update))
data_thread.daemon = True
data_thread.start()

sel = selectors.DefaultSelector()

host, port = cfg[ConfigKey.HOST], cfg[ConfigKey.PORT]
lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# Avoid bind() exception: OSError: [Errno 48] Address already in use
lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
lsock.setblocking(False)
lsock.bind((host, port))
lsock.listen()
print(f"Listening on {(host, port)}")
sel.register(lsock, selectors.EVENT_READ, data=None)

try:
    while True:
        events = sel.select(timeout=1)
        for key, mask in events:
            if key.data is None:
                accept_wrapper(key.fileobj)
            else:
                message = key.data
                try:
                    message.process_events(mask)
                except Exception:
                    print(
                        f"Main: Error: Exception for {message.addr}:\n"
                        f"{traceback.format_exc()}"
                    )
                    message.close()
        time.sleep(0.01)
except KeyboardInterrupt:
    print("Caught keyboard interrupt, exiting")
finally:
    sel.close()

sys.exit()