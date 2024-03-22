import tkinter
import customtkinter
import threading
import yaml
import time, traceback
import subprocess
import json
import os.path
from colour import Color
from datetime import datetime, timedelta

# from https://github.com/abagh0703/turn-off-wifi
CMD_BASE = 'cmd /c "{}"'  # first is remain/terminate, then is enable/disable
WIFI_CMD_BASE = 'wmic path win32_networkadapter where NetConnectionID="Wi-fI" call {}'
ETHERNET_CMD_BASE = 'netsh interface set interface {}'
WIFI_CMD_ENABLE = WIFI_CMD_BASE.format('enable')
WIFI_CMD_DISABLE = WIFI_CMD_BASE.format('disable')

COLOR_AMOUNT = 1000
COLORS = [(224, 0, 0), (8, 135, 4),(0, 0, 255),(0, 0, 0)]
#COLORS = [(30, 198, 244), (99, 200, 72),(120, 50, 80),(200, 90, 140)]

JSON_FILE = "storage.json"
SECONDS_DATA_UPDATE = 60
LAST_TIME_OPEN_KEY = "lasttimeopen"

STREAKSHIFT_KEY = "streakshift"
STREAK_KEY = "streak"

DEBUG_KEY = "debug"

global now
global time_since_json_write
global colors
global shutdown_labels
global json_data
global date_label
global time_label

class shutdown_data():
    def __init__(self, time, label):
        self.datetime = time
        self.label = label

    def update(self):
        global now
        global colors
        delta = self.datetime - now
        if self.datetime <= now:
            color_index = 0
        else:
            hour_delta = int(delta.total_seconds() ** 1.4) / int(60 * 60)
            color_index = clamp(int(hour_delta * (COLOR_AMOUNT / 100)), 0, COLOR_AMOUNT-1)
        bg_color = Color('#%02x%02x%02x' % tuple(map(round, colors[color_index])))
        time_left = ':'.join(str(delta).split(':')[:2])
        date_time = self.datetime.strftime("%H:%M:%S")
        self.label.configure(text=f"{date_time} | {time_left}", bg_color=bg_color.get_hex())

def clamp(n, smallest, largest): return max(smallest, min(n, largest))

def every(delay, task):
  next_time = time.time() + delay
  while True:
    time.sleep(max(0, next_time - time.time()))
    try:
      task()
    except Exception:
      traceback.print_exc()
    next_time += (time.time() - next_time) // delay * delay + delay

def update_datetime_labels():
    global time_since_json_write
    global shutdown_labels
    global json_data
    global now
    global date_label
    global time_label

    (date, time) = get_datetime()
    date_label.configure(text=date)
    time_label.configure(text=time)

    soonest_time_delta = shutdown_labels[0].datetime  - now
    time_until_label.configure(text=':'.join(str(soonest_time_delta).split(':')[:2]))

    now = datetime.now()
    tomorrow = now + timedelta(days=1)

    # Streak maintenance on hitting day shift
    if now <= cutoff_time:
        json_data[STREAK_KEY] += 1
        cutoff_time.replace(day=tomorrow.day)

    # Setting last time open
    time_since_json_write += 1
    if time_since_json_write >= SECONDS_DATA_UPDATE:
        json_data["lasttimeopen"] = datetime.strftime(now, '%m/%d/%y %H:%M:%S')
        time_since_json_write = 0
        write_data_to_json()
        sort_labels()

    # shutdown label maintenance
    for data in shutdown_labels:
        data.update()

        # actual shutdown
        if data.datetime <= now:
           recalculate_time(data)
           turn_off_wifi()
           turn_off_ethernet()
           json_data[STREAK_KEY] = 0

def recalculate_time(data: shutdown_data):
   data.datetime = data.datetime.replace(day=tomorrow.day)
   data.update()

def get_datetime():
    now = datetime.now()
    date = now.strftime("%m/%d/%Y")
    time = now.strftime("%H:%M:%S")
    return date, time

def execute_cmd(cmd):
    subprocess.call(cmd, shell=True)

def turn_on_wifi():
    execute_cmd(CMD_BASE.format(WIFI_CMD_ENABLE))

def turn_off_wifi():
    execute_cmd(CMD_BASE.format(WIFI_CMD_DISABLE))

def turn_on_ethernet():
    for ethernet in cfg["ethernet"]:
        execute_cmd(CMD_BASE.format(ETHERNET_CMD_BASE.format(ethernet) + " enabled"))
    status_label.pack_forget()

def turn_off_ethernet():
    for ethernet in cfg["ethernet"]:
        execute_cmd(CMD_BASE.format(ETHERNET_CMD_BASE.format(ethernet) + " disabled"))
    status_label.configure(text="Internet Shutdown Triggered", fg_color="red")
    status_label.pack()

def write_data_to_json():
    with open(JSON_FILE, 'w') as f:
        json.dump(json_data, f)

def string_now():
    return  datetime.strftime(datetime.now(), '%m/%d/%y %H:%M:%S')

def LerpColour(c1,c2,t):
    return (c1[0]+(c2[0]-c1[0])*t, c1[1]+(c2[1]-c1[1])*t, c1[2]+(c2[2]-c1[2])*t)

def create_gradient():
    gradient = []
    for i in range(len(COLORS)-2):
        for j in range(COLOR_AMOUNT):
            gradient.append(LerpColour(COLORS[i],COLORS[i+1],j/COLOR_AMOUNT))
    return gradient

def sort_labels():
    global shutdown_labels
    shutdown_labels = sorted(shutdown_labels, key=lambda x: x.datetime)
    for data in shutdown_labels:
        data.label.pack_forget()

    for data in shutdown_labels:
        data.label.pack(ipadx=10, ipady=10, fill="both")

# Defining basic time variables
now = datetime.now()
tomorrow = now + timedelta(days=1)

# Reading/Initializing storage json
json_data = {}
if os.path.isfile(JSON_FILE):
   f = open(JSON_FILE) 
   json_data = json.load(f)
else:
   json_data = {"streak":0, "voucher":0, LAST_TIME_OPEN_KEY: string_now()}
   write_data_to_json()

# Reading config
with open("config.yaml") as f:
    cfg = yaml.load(f, Loader=yaml.FullLoader)

# Modifying streak time
cutoff_time = datetime.strptime(cfg[STREAKSHIFT_KEY], '%H:%M')
cutoff_time = now.replace(hour=cutoff_time.hour, minute=cutoff_time.minute)
last_time_open = datetime.strptime(json_data[LAST_TIME_OPEN_KEY], '%m/%d/%y %H:%M:%S')

if  last_time_open < cutoff_time:
    since_open = now - last_time_open
    json_data[STREAK_KEY] += since_open.days
    print(f"Added {since_open.days} days to streak")

json_data[LAST_TIME_OPEN_KEY] = string_now()
write_data_to_json()

# System Settings
customtkinter.set_appearance_mode("System")
customtkinter.set_default_color_theme("blue")

# Our app frame
app = customtkinter.CTk()
app.geometry("720x480")
app.title("Internet Manager")
app_bg_color = app.cget('bg')

# Shutdown label parent
widget_frame = customtkinter.CTkFrame(app, bg_color='gray')
widget_frame.pack(side='left', fill="y")

bottom_frame = customtkinter.CTkFrame(app)
bottom_frame.pack(side='bottom', fill="x")

# Making shutdown label color gradient
colors = create_gradient()

shutdown_labels = []

# Intializing shutdown labels
for shutdown_time in cfg["shutdowntimes"]:
    target = datetime.strptime(shutdown_time, '%H:%M:%S')
    target = target.replace(year=now.year, month=now.month, day=now.day)

    if now > target:
      target = target.replace(day=tomorrow.day)

    shutdown_time_label = customtkinter.CTkLabel(widget_frame, text=target)
    shutdown_time_label.pack(ipadx=10, ipady=10, fill="both")

    shutdown_labels.append(shutdown_data(target, shutdown_time_label))

# Adding Time
date_label = customtkinter.CTkLabel(app, text="Date", font=("Arial", 20))
time_label = customtkinter.CTkLabel(app, text=string_now(), font=("Arial", 40))

date_label.pack()
time_label.pack()

time_until_label = tkinter.Label(app, text='', background=app_bg_color , foreground="gray", font=("Arial", 20))
time_until_label.pack()

status_label = customtkinter.CTkLabel(app, text=f"" )
status_label.pack_forget()

# Debug turn internet on and off buttons
if cfg[DEBUG_KEY]:
    turn_off = customtkinter.CTkButton(bottom_frame, text = 'Turn off Internet',
                            command = turn_off_ethernet) 
    turn_on = customtkinter.CTkButton(bottom_frame, text = 'Turn on Internet',
                            command = turn_on_ethernet)  
    turn_off.pack(side = 'top')
    turn_on.pack()

streak_label = customtkinter.CTkLabel(bottom_frame, text=f"Streak: {json_data[STREAK_KEY]}" )
streak_label.pack()

# Run time update
time_since_json_write = 0
sort_labels()
update_datetime_labels()
t = threading.Thread(target=lambda: every(1, update_datetime_labels))
t.daemon = True
t.start()

# Run app
app.mainloop()