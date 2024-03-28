#!/usr/bin/env python3

import threading
import yaml
import time, traceback
import subprocess
import json
import os.path
import sys
import socket
import selectors
import types
import libserver
import internet_management
from libuniversal import Actions, ConfigKey, StorageKey, Paths
from queue import Queue
from colour import Color
from datetime import datetime, timedelta
from enum import Enum

SECONDS_DATA_UPDATE = 60

LAUNCH_GUI = 'xterm -e \"python gui.py\" &'

# Time is in milliseconds
GUI_THREAD_TIME = 1000

# Time is in seconds
SAVE_THREAD_TIME = 3

ASSET_FOLDER = "assets"

global now
global time_since_json_write
global colors
global time_action_labels
global json_data
global date_label
global time_label

class time_action_data():
    def __init__(self, time : datetime, action : Actions):
        self.datetime = time
        self.action = action

class StoppableThread(threading.Thread):

    def __init__(self,  *args, **kwargs):
        super(StoppableThread, self).__init__(*args, **kwargs)
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

def every(delay, task):
    next_time = time.time() + delay
    while True:
        time.sleep(max(0, next_time - time.time()))
        try:
            task()
        except Exception:
            traceback.print_exc()
            next_time += (time.time() - next_time) // delay * delay + delay

def update():
    global time_since_json_write
    global json_data
    global now

    now = datetime.now()
    tomorrow = now + timedelta(days=1)

    # label time check
    for data in time_action_labels:

        # actual shutdown
        if data.datetime > now:
            continue
        elif data.action == Actions.INTERNET_OFF:
            internet_management.turn_off_wifi()
            internet_management.turn_off_ethernet()
            gui_queue.put(Actions.INTERNET_OFF)
        elif data.action == Actions.INTERNET_ON:
            internet_management.turn_on_wifi()
            internet_management.turn_on_ethernet()
            gui_queue.put(Actions.INTERNET_ON)
        recalculate_time(data)
        gui_queue.put(Actions.SORT_LABELS)

def recalculate_time(data: time_action_data):
   data.datetime = data.datetime.replace(day=tomorrow.day)

def update_json():
    print("Json Saved")
    json_data["lasttimeopen"] = datetime.strftime(now, '%m/%d/%y %H:%M:%S')
    write_data_to_json()
    gui_queue.put(Actions.SORT_LABELS)

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

def write_data_to_json():
    with open(Paths.JSON_FILE, 'w') as f:
        json.dump(json_data, f)

def string_now():
    return  datetime.strftime(datetime.now(), '%m/%d/%y %H:%M:%S')

# Defining basic time variables
now = datetime.now()
tomorrow = now + timedelta(days=1)

# Reading/Initializing storage json
json_data = {}
if os.path.isfile(Paths.JSON_FILE):
   f = open(Paths.JSON_FILE) 
   json_data = json.load(f)
else:
   json_data = {StorageKey.VOUCHER:0, StorageKey.SINCE_LAST_RELAPSE: string_now()}
   write_data_to_json()

# Reading config
with open(Paths.CONFIG_FILE) as f:
    cfg = yaml.load(f, Loader=yaml.FullLoader)

"""
# Modifying streak time
cutoff_time = datetime.strptime(cfg[STREAKSHIFT_KEY], '%H:%M')
cutoff_time = now.replace(hour=cutoff_time.hour, minute=cutoff_time.minute)
last_time_open = datetime.strptime(json_data[LAST_TIME_OPEN_KEY], '%m/%d/%y %H:%M:%S')

# Should change to just store last failed date, then calc from how long ago that was
if  last_time_open < cutoff_time:
    since_open = now - last_time_open
    json_data[STREAK_KEY] += since_open.days
    print(f"Added {since_open.days} days to streak")


json_data[LAST_TIME_OPEN_KEY] = string_now()
write_data_to_json()

# Calculating what state the manager should be in:
if type(time_action_labels[-1]) is shutdown_data:
    turn_off_wifi()
    turn_off_ethernet()
elif type(time_action_labels[-1]) is internet_up_data:
    turn_on_wifi()
    turn_on_ethernet()

"""

sel = selectors.DefaultSelector()

def accept_wrapper(sock):
    conn, addr = sock.accept()  # Should be ready to read
    print(f"Accepted connection from {addr}")
    conn.setblocking(False)
    message = libserver.Message(sel, conn, addr)
    sel.register(conn, selectors.EVENT_READ, data=message)

host, port = cfg[ConfigKey.HOST], cfg[ConfigKey.PORT]
lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# Avoid bind() exception: OSError: [Errno 48] Address already in use
lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
lsock.bind((host, port))
lsock.listen()
print(f"Listening on {(host, port)}")
lsock.setblocking(False)
sel.register(lsock, selectors.EVENT_READ, data=None)

try:
    while True:
        events = sel.select(timeout=None)
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
except KeyboardInterrupt:
    print("Caught keyboard interrupt, exiting")
finally:
    sel.close()

"""
gui_queue = Queue()

data_thread = StoppableThread(target=lambda: every(1, update))
data_thread.daemon = False
data_thread.start()

save_thread = StoppableThread(update_json)
save_thread.daemon = False
save_thread.start()
"""

sys.exit()