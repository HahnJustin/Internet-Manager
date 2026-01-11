#!/usr/bin/env python3

import threading
import time, traceback
import shutil
import random
import string
import subprocess
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
SHOULD_EXIT = False

RETRO_USED_KEY = StorageKey.RETROVOUCHER_USED
RETRO_SCHED_KEY = StorageKey.RETROVOUCHER_SCHEDULED
RETRO_COUNT_KEY = StorageKey.RETROVOUCHER
RETRO_LIMIT_KEY = StorageKey.RETROVOUCHER_LIMIT

global now
global time_datas
global json_data

warned = False
sound_on = True
warning_sound_time = 15

used_voucher_today = False
used_manual_override = False

# Define pools of words
prefixes = [
    "COM", "Net", "Sys", "Win", "App", "Host", "Sec", "Crypto", "Cloud", "Runtime",
    "Proxy", "Data", "Input", "Output", "Diag", "Kernel", "UI", "UX", "BIOS"
]

modifiers = [
    "Agent", "Manager", "Service", "Helper", "Monitor", "Host", "Shell", "Broker", 
    "Module", "Engine", "Daemon", "Utility", "Rider", "Loader", "Process", "Thread"
]

adjectives = [
    "Antimalware", "Telemetry", "Security", "Protocol", "Authentication", "Optimization",
    "Configuration", "Remote", "Virtual", "Adaptive", "Encrypted", "Federated", "Secure"
]

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

        # reset retro flags at cutoff too
        json_data = configreader.get_storage()
        reset_retrovoucher_flags(json_data)
        configreader.force_storage(json_data)

    # If retro is scheduled while internet is currently OFF -> consume instantly + turn internet on.
    if bool(json_data.get(RETRO_SCHED_KEY, False)) and not bool(json_data.get(RETRO_USED_KEY, False)):
        if not internet_on:
            # also refund future normal vouchers (idempotent)
            refund_and_clear_all_vouchers(json_data)

            if consume_retrovoucher(json_data):
                configreader.force_storage(json_data)

                play_sfx("internet_on.wav")  # or a retro sfx if you add one
                internet_management.turn_on_wifi()
                internet_management.turn_on_ethernet()
                internet_on = True
                print("Retrovoucher consumed immediately (internet was off).")
            else:
                # no retro available -> just unschedule
                json_data[RETRO_SCHED_KEY] = False
                configreader.force_storage(json_data)

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
    if configreader.datetime_to_str(data.datetime) in json_data[StorageKey.VOUCHERS_USED]:
        play_sfx("vouched.wav")
        used_voucher_today = True
        print(f"{data} - [VOUCHED] {data.action}")
    elif data.action == Actions.INTERNET_OFF:
    # If retro is used or scheduled, ignore shutdowns.
        if bool(json_data.get(RETRO_USED_KEY, False)):
            print(f"{data} - [RETRO USED] Ignoring shutdown.")
            # do nothing, just roll time forward
        elif bool(json_data.get(RETRO_SCHED_KEY, False)):
            # scheduled retro becomes USED at the moment shutdown would happen
            refund_and_clear_all_vouchers(json_data)

            if consume_retrovoucher(json_data):
                configreader.force_storage(json_data)

                # if internet is off, bring it back on when retro becomes used
                if not internet_on:
                    play_sfx("internet_on.wav")
                    internet_management.turn_on_wifi()
                    internet_management.turn_on_ethernet()
                    internet_on = True

                print(f"{data} - [RETRO CONSUMED] Ignoring shutdown.")
            else:
                # no retro available; unschedule and proceed with normal shutdown
                json_data[RETRO_SCHED_KEY] = False
                configreader.force_storage(json_data)

                play_sfx("internet_off.wav")
                internet_management.turn_off_wifi()
                internet_management.turn_off_ethernet()
                if internet_on and not used_voucher_today and not used_manual_override and (not retro_active(json_data)):
                    configreader.try_add_shutdown_loot_box()
                    libserver.start_loot_box_timer(1)
                internet_on = False
                print(f"{data} - {data.action}")
        else:
            # normal shutdown behavior
            play_sfx("internet_off.wav")
            internet_management.turn_off_wifi()
            internet_management.turn_off_ethernet()
            if internet_on and not used_voucher_today and not used_manual_override and (not retro_active(json_data)):
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
    global json_data
    global now

    last_cutoff = cutoff_time - timedelta(days=1)

    used_list = json_data.get(StorageKey.VOUCHERS_USED, [])
    refunded = 0

    for i in reversed(range(len(used_list))):
        s = used_list[i]

        # 1) Migration: remove junk entries that aren't TIME_FMT
        try:
            vouched_datetime = configreader.str_to_datetime(s)
        except Exception:
            # This is your old "TimeAction(...)" bug entry
            used_list.pop(i)
            refunded += 1
            continue

        # 2) Normal behavior: drop vouchers older than last cutoff
        if last_cutoff > vouched_datetime:
            used_list.pop(i)

    # Write back
    json_data[StorageKey.VOUCHERS_USED] = used_list

    # Refund only the malformed ones we removed (clamp to limit)
    if refunded > 0:
        limit = json_data.get(StorageKey.VOUCHER_LIMIT, 999999)
        json_data[StorageKey.VOUCHER] = min(
            limit,
            json_data.get(StorageKey.VOUCHER, 0) + refunded
        )

    configreader.force_storage(json_data)
    used_voucher_today = False
    
def play_sfx(sfx : str):
    if sound_on:
        try:
            playsound(resource_path(Paths.SFX_FOLDER + '\\' + sfx))
        except:
            playsound(resource_path(Paths.SFX_FOLDER + '\\' + sfx))

def retro_active(storage: dict) -> bool:
    return bool(storage.get(RETRO_USED_KEY, False) or storage.get(RETRO_SCHED_KEY, False))

def reset_retrovoucher_flags(storage: dict) -> None:
    storage[RETRO_USED_KEY] = False
    storage[RETRO_SCHED_KEY] = False

def refund_and_clear_all_vouchers(storage: dict) -> int:
    """
    Clears ALL entries in VOUCHERS_USED and refunds that many vouchers (clamped).
    This is the 'unuse everything' behavior you want when retro activates.
    """
    used_list = storage.get(StorageKey.VOUCHERS_USED, [])
    if not isinstance(used_list, list) or not used_list:
        storage[StorageKey.VOUCHERS_USED] = []
        return 0

    refunded = len(used_list)
    storage[StorageKey.VOUCHERS_USED] = []

    limit = int(storage.get(StorageKey.VOUCHER_LIMIT, 999999))
    storage[StorageKey.VOUCHER] = min(
        limit,
        int(storage.get(StorageKey.VOUCHER, 0)) + refunded
    )
    return refunded

def refund_future_vouchers(storage: dict, now: datetime) -> int:
    """
    Remove future timestamps from vouchers_used and refund that many vouchers.
    Returns refunded count.
    """
    used_list = storage.get(StorageKey.VOUCHERS_USED, [])
    if not isinstance(used_list, list):
        return 0

    refunded = 0
    for i in reversed(range(len(used_list))):
        s = used_list[i]
        try:
            dt = configreader.str_to_datetime(s)
        except Exception:
            # keep your migration behavior consistent:
            used_list.pop(i)
            refunded += 1
            continue

        if dt > now:
            used_list.pop(i)
            refunded += 1

    if refunded:
        limit = int(storage.get(StorageKey.VOUCHER_LIMIT, 999999))
        storage[StorageKey.VOUCHER] = min(limit, int(storage.get(StorageKey.VOUCHER, 0)) + refunded)
        storage[StorageKey.VOUCHERS_USED] = used_list

    return refunded

def consume_retrovoucher(storage: dict) -> bool:
    """
    Spend 1 retrovoucher: decrement count, mark used=True, scheduled=False.
    Returns True if consumed, False if none available.
    """
    count = int(storage.get(RETRO_COUNT_KEY, 0))
    if count <= 0:
        # nothing to consume
        storage[RETRO_SCHED_KEY] = False
        return False

    storage[RETRO_COUNT_KEY] = count - 1
    storage[RETRO_USED_KEY] = True
    storage[RETRO_SCHED_KEY] = False
    return True

def _dt_for_day(day: datetime, hhmmss: str) -> datetime:
    t = datetime.strptime(hhmmss, "%H:%M:%S")
    return day.replace(hour=t.hour, minute=t.minute, second=t.second, microsecond=0)

def compute_effective_internet_on(now: datetime, cfg: dict, storage: dict) -> bool:
    # Retro active => shutdowns are ignored, so we should never boot "stuck off"
    if retro_active(storage):
        return True

    pts: list[tuple[datetime, Actions]] = []
    for day in (now - timedelta(days=1), now):
        for t in cfg[ConfigKey.SHUTDOWN_TIMES]:
            pts.append((_dt_for_day(day, t), Actions.INTERNET_OFF))
        for t in cfg[ConfigKey.ENFORCED_SHUTDOWN_TIMES]:
            pts.append((_dt_for_day(day, t), Actions.INTERNET_OFF))
        for t in cfg[ConfigKey.UP_TIMES]:
            pts.append((_dt_for_day(day, t), Actions.INTERNET_ON))

    pts.sort(key=lambda x: x[0])

    used_list = storage.get(StorageKey.VOUCHERS_USED, [])
    used = set(used_list) if isinstance(used_list, list) else set()

    # Start from the last point in the past, walk backward until we find an effective action
    for dt, act in reversed(pts):
        if dt > now:
            continue

        if act == Actions.INTERNET_OFF:
            # Shutdown was vouched => it didn't apply, keep searching
            if configreader.datetime_to_str(dt) in used:
                continue
            return False

        if act == Actions.INTERNET_ON:
            return True

    # If nothing happened yet in our window, default ON
    return True

def generate_name():
    formats = [
        lambda: f"{random.choice(prefixes)} {random.choice(modifiers)}",
        lambda: f"{random.choice(adjectives)} {random.choice(modifiers)}",
        lambda: f"{random.choice(prefixes)} {random.choice(adjectives)} {random.choice(modifiers)}",
        lambda: f"{random.choice(prefixes)}-{random.choice(modifiers)}",
        lambda: f"{random.choice(adjectives)}-{random.choice(modifiers)}",
    ]
    return random.choice(formats)()

def launch_randomized_copy():
    if not getattr(sys, 'frozen', False):
        return  # Only apply when packaged

    if os.environ.get("IM_ALREADY_RENAMED") == "1":
        return  # Already running randomized copy

    current_path = sys.executable
    exe_name = generate_name() + ".exe"
    temp_dir = os.path.join(os.environ['TEMP'], 'InternetManager')
    os.makedirs(temp_dir, exist_ok=True)
    new_path = os.path.join(temp_dir, exe_name)

    try:
        shutil.copyfile(current_path, new_path)

        new_env = os.environ.copy()
        new_env["IM_ALREADY_RENAMED"] = "1"

        subprocess.Popen([new_path], env=new_env, close_fds=True)
        sys.exit()
    except Exception as e:
        print("Failed to launch obfuscated copy:", e)

def print_exe_debug():
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller EXE
        exe_path = sys.executable
        exe_name = os.path.basename(exe_path)
        print(f"Randomized name: {exe_name}")
    else:
        # Running as a normal Python script
        print("No random name - not frozen, running as .py script")

# Randomly rename the application
launch_randomized_copy()

# Start as admin
if not pyuac.isUserAdmin():
   print("Re-launching as admin!")
   pyuac.runAsAdmin()
   sys.exit()

print_exe_debug()

# Getting Application Path - Thanks Max Tet
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

configreader.init()
print("CONFIG:", configreader.config_path())  # if you expose it, or print assets.config_path()
print("STORAGE:", configreader.get_json_path())
print("TIME:", configreader.get_json_time_path())

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
   json_data = {StorageKey.VOUCHER:3, StorageKey.SINCE_LAST_RELAPSE: configreader.now_datetime_to_str(),
                StorageKey.VOUCHER_LIMIT : 5, StorageKey.VOUCHERS_USED : [],
                StorageKey.MANUAL_USED : False}
   
json_time_data = {}
if os.path.isfile(configreader.get_json_time_path()):
   json_time_data = configreader.get_json_time()
else:
   json_time_data = {TimeKey.LAST_TIME_ACTIVE: configreader.now_datetime_to_str()}


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
        used_time = configreader.str_to_datetime(_time)
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

internet_on = compute_effective_internet_on(now, cfg, json_data)

# If retro is scheduled and we're currently OFF, consume immediately and bring internet ON (matches update())
if (not internet_on) and bool(json_data.get(RETRO_SCHED_KEY, False)) and (not bool(json_data.get(RETRO_USED_KEY, False))):
    refund_and_clear_all_vouchers(json_data)
    if consume_retrovoucher(json_data):
        configreader.force_storage(json_data)
        internet_on = True
    else:
        json_data[RETRO_SCHED_KEY] = False
        configreader.force_storage(json_data)

if internet_on:
    internet_management.turn_on_wifi()
    internet_management.turn_on_ethernet()
else:
    internet_management.turn_off_wifi()
    internet_management.turn_off_ethernet()

print(f" Cut-off time: {cutoff_time}")

# Roll for a morning loot box
last_active_time = configreader.get_active_time()
print(f" Last Active Time: {last_active_time}")

json_data = configreader.get_storage()
retro_is_active = retro_active(json_data)

last_cutoff = cutoff_time - timedelta(days=1)
if last_active_time <= last_cutoff:
    json_data = configreader.get_storage()
    reset_retrovoucher_flags(json_data)
    configreader.force_storage(json_data)

first_shutdown_yesterday = min(shutdown_times)
print(f" First Shutdown Yesterday: {first_shutdown_yesterday}")

pre_box_amount = configreader.get_all_loot_boxes()
if (not retro_is_active) and last_active_time <= cutoff_time - timedelta(days=1) and last_active_time <= first_shutdown_yesterday and internet_on:
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
        if libserver.SHOULD_EXIT:
            break
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