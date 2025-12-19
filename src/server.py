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
import pyuac
from playsound import playsound
from libuniversal import *
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

used_voucher_today = False
used_manual_override = False

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
    if action is Actions.INTERNET_OFF: shutdown_times.append(target - timedelta(days=1))

def update():
    global sound_on
    global json_data
    global now
    global warning_sound_time
    global warned
    global internet_on
    global used_voucher_today
    global used_manual_override

    now = datetime.now()
    json_data = configreader.get_storage()

    if now > cutoff_time:
        recalculate_cutoff_time()
        cull_vouchers()
        configreader.set_manual_override(False)

    used_manual_override = configreader.get_manual_used()

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
        used_voucher_today = True
        print(f"{data} - [VOUCHED] {data.action}")
    elif data.action == Actions.INTERNET_OFF:
        play_sfx("internet_off.wav")
        internet_management.turn_off_wifi()
        internet_management.turn_off_ethernet()
        if internet_on and not used_voucher_today and not used_manual_override: 
            configreader.try_add_shutdown_loot_box()
            libserver.start_loot_box_timer(1)
        internet_on = False
        print(f"{data} - {data.action}")
    elif data.action == Actions.INTERNET_ON:
        play_sfx("internet_on.wav")
        internet_management.turn_on_wifi()
        internet_management.turn_on_ethernet()
        internet_on = True
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

def get_last_relapse() -> datetime:
    global json_data
    global cfg
    global cutoff_time

    last_relapse = datetime.strptime(json_data[StorageKey.SINCE_LAST_RELAPSE], '%m/%d/%y %H:%M:%S')
    return last_relapse.replace(hour=cutoff_time.hour, minute=cutoff_time.minute)

def cull_vouchers():
    global cutoff_time
    global used_voucher_today
    
    last_cutoff = cutoff_time - timedelta(days=1)
    for i in reversed(range(len(json_data[StorageKey.VOUCHERS_USED]))):
        vouched_time = json_data[StorageKey.VOUCHERS_USED][i]
        vouched_datetime = configreader.str_to_datetime(vouched_time)
        print(f"Culling Voucher {i} {vouched_datetime}")
        if last_cutoff > vouched_datetime:
            json_data[StorageKey.VOUCHERS_USED].pop(i)
    configreader.force_storage(json_data)
    used_voucher_today = False
    
def play_sfx(sfx : str):
    if sound_on:
        try:
            playsound(resource_path(Paths.SFX_FOLDER + '\\' + sfx))
        except:
            playsound(resource_path(Paths.SFX_FOLDER + '\\' + sfx))


if not pyuac.isUserAdmin():
   print("Re-launching as admin!")
   pyuac.runAsAdmin()
   sys.exit()

# Getting Application Path - Thanks Max Tet
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
configreader.init(application_path)

# Defining basic time variables
now = datetime.now()
yesterday = now - timedelta(days=1)
tomorrow = now + timedelta(days=1)

# Reading config
cfg = configreader.get_config()

if ConfigKey.SOUND_ON in cfg:
    sound_on = cfg[ConfigKey.SOUND_ON]

if ConfigKey.WARNING_MINUTES in cfg:
    warning_sound_time = cfg[ConfigKey.WARNING_MINUTES]

# Modifying streak time
recalculate_cutoff_time()

# Reading/Initializing storage json
json_data = {}
if os.path.isfile(configreader.get_json_path()):
   json_data = configreader.get_storage()
else:
   json_data = {StorageKey.VOUCHER:3, StorageKey.SINCE_LAST_RELAPSE: string_now(),
                StorageKey.VOUCHER_LIMIT : 5, StorageKey.VOUCHERS_USED : [],
                StorageKey.MANUAL_USED : False}
   
json_time_data = {}
if os.path.isfile(configreader.get_json_time_path()):
   json_time_data = configreader.get_json_time()
else:
   json_time_data = {TimeKey.LAST_TIME_ACTIVE: string_now()}


if StorageKey.SINCE_LAST_RELAPSE in json_data:
    relapse_time = get_last_relapse()
    if relapse_time <= cutoff_time:
        json_data[StorageKey.MANUAL_USED] = False

# Removes references to vouchers already used from storage
cull_vouchers()

# save json
configreader.force_storage(json_data)

if StorageKey.VOUCHERS_USED in json_data:
    for _time in json_data[StorageKey.VOUCHERS_USED]:
        used_time = datetime.strptime(_time, '%m/%d/%y %H:%M:%S')
        if now > used_time:
            used_voucher_today = True
            break

used_manual_override = configreader.get_manual_used()

time_datas = []
shutdown_times = []

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

disabled = False
if ConfigKey.DISABLED in cfg:
    internet_management.set_disabled(cfg[ConfigKey.DISABLED])

internet_on = False

# Calculating what state the manager should be in:
if time_datas[-1].action == Actions.INTERNET_OFF:
    internet_management.turn_off_wifi()
    internet_management.turn_off_ethernet()
    internet_on = False
elif time_datas[-1].action == Actions.INTERNET_ON:
    internet_management.turn_on_wifi()
    internet_management.turn_on_ethernet()
    internet_on = True

print(f" Cut-off time: {cutoff_time}")

# Roll for a morning loot box
last_active_time = configreader.get_active_time()
print(f" Last Active Time: {last_active_time}")

first_shutdown_yesterday = min(shutdown_times)
print(f" First Shutdown Yesterday: {first_shutdown_yesterday}")

pre_box_amount = configreader.get_all_loot_boxes()
if last_active_time <= cutoff_time - timedelta(days=1) and last_active_time <= first_shutdown_yesterday and internet_on:
    difference = cutoff_time - last_active_time
    loot_boxes = difference.days

    for i in range(loot_boxes): configreader.try_add_loot_box()

    loot_boxes_found = configreader.get_all_loot_boxes() - pre_box_amount
    if loot_boxes_found > 0: libserver.start_loot_box_timer(loot_boxes_found)
    print(f" Morning Lootboxes: {loot_boxes_found}")

data_thread = StoppableThread(target=lambda: every(0.25, update))
data_thread.daemon = True
data_thread.start()

time_thread = StoppableThread(target=lambda: every(20, configreader.set_active_time))
time_thread.daemon = True
time_thread.start()

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