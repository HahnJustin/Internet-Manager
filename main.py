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
from PIL import Image, ImageTk

# from https://github.com/abagh0703/turn-off-wifi
CMD_BASE = 'cmd /c "{}"'  # first is remain/terminate, then is enable/disable
WIFI_CMD_BASE = 'wmic path win32_networkadapter where NetConnectionID="Wi-fI" call {}'
ETHERNET_CMD_BASE = 'netsh interface set interface {}'
WIFI_CMD_ENABLE = WIFI_CMD_BASE.format('enable')
WIFI_CMD_DISABLE = WIFI_CMD_BASE.format('disable')

COLOR_AMOUNT = 100
SHUTDOWN_COLORS = [(224, 0, 0), (8, 135, 4),(0, 0, 255),(0, 0, 0)]
UP_COLORS = [(0, 144, 227), (0, 135, 90),(0, 0, 255),(0, 0, 0)]

JSON_FILE = "storage.json"
SECONDS_DATA_UPDATE = 60
LAST_TIME_OPEN_KEY = "lasttimeopen"

STREAKSHIFT_KEY = "streakshift"
STREAK_KEY = "streak"

DEBUG_KEY = "debug"

ASSET_FOLDER = "assets"

global now
global time_since_json_write
global colors
global time_action_labels
global json_data
global date_label
global time_label

class time_action_data():
    def __init__(self, time, label):
        self.datetime = time
        self.label = label

    def update(self):
        a = 1

    def update_helper(self, color_list):
        global now
        global shutdown_colors
        delta = self.datetime - now
        if self.datetime <= now:
            color_index = 0
        else:
            hour_delta = int(delta.total_seconds() ** 1.4) / int(60 * 60)
            color_index = clamp(int(hour_delta * (COLOR_AMOUNT / 100)), 0, COLOR_AMOUNT-1)
        bg_color = Color('#%02x%02x%02x' % tuple(map(round, color_list[color_index])))
        time_left = ':'.join(str(delta).split(':')[:2])
        date_time = self.datetime.strftime("%H:%M:%S")
        self.label.configure(text=f"{date_time} | {time_left}", bg_color=bg_color.get_hex())

class shutdown_data(time_action_data):
    def update(self):
        super().update_helper(shutdown_colors)

class internet_up_data(time_action_data):
    def update(self):
        super().update_helper(up_colors)

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
    global time_action_labels
    global json_data
    global now
    global date_label
    global time_label

    (date, time) = get_datetime()
    date_label.configure(text=date)
    time_label.configure(text=time)

    soonest_time_delta = time_action_labels[0].datetime  - now
    time_until_label.configure(text=':'.join(str(soonest_time_delta).split(':')[:2]))

    now = datetime.now()
    tomorrow = now + timedelta(days=1)

    # Streak maintenance on hitting day shift
    if now <= cutoff_time:
        json_data[STREAK_KEY] += 1
        cutoff_time.replace(day=tomorrow.day)
        update_streak_graphics()

    # Setting last time open
    time_since_json_write += 1
    if time_since_json_write >= SECONDS_DATA_UPDATE:
        json_data["lasttimeopen"] = datetime.strftime(now, '%m/%d/%y %H:%M:%S')
        time_since_json_write = 0
        write_data_to_json()
        sort_labels()

    # shutdown label maintenance
    for data in time_action_labels:
        data.update()

        # actual shutdown
        if data.datetime > now:
            continue
        elif type(data) is shutdown_data:
            turn_off_wifi()
            turn_off_ethernet()
        elif type(data) is internet_up_data:
            turn_on_wifi()
            turn_on_ethernet()
        recalculate_time(data)
        sort_labels()

def recalculate_time(data: time_action_data):
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
    status_label.configure(text="Internet Activation Triggered", fg_color="blue")
    status_label.pack()
    run_function_in_minute(lambda: status_label.pack_forget())

def turn_off_ethernet():
    for ethernet in cfg["ethernet"]:
        execute_cmd(CMD_BASE.format(ETHERNET_CMD_BASE.format(ethernet) + " disabled"))
    status_label.configure(text="Internet Shutdown Triggered", fg_color="red")
    status_label.pack()
    run_function_in_minute(lambda: status_label.pack_forget())

def run_function_in_minute(func):
    thread = threading.Timer(60.0, func) # 60 seconds = 1 minute
    thread.daemon = True
    thread.start()

def write_data_to_json():
    with open(JSON_FILE, 'w') as f:
        json.dump(json_data, f)

def string_now():
    return  datetime.strftime(datetime.now(), '%m/%d/%y %H:%M:%S')

def LerpColour(c1,c2,t):
    return (c1[0]+(c2[0]-c1[0])*t, c1[1]+(c2[1]-c1[1])*t, c1[2]+(c2[2]-c1[2])*t)

def create_gradient(colors):
    gradient = []
    for i in range(len(colors)-2):
        for j in range(COLOR_AMOUNT):
            gradient.append(LerpColour(colors[i],colors[i+1],j/COLOR_AMOUNT))
    return gradient

def sort_labels():
    global time_action_labels
    time_action_labels = sorted(time_action_labels, key=lambda x: x.datetime)
    for data in time_action_labels:
        data.label.pack_forget()

    for data in time_action_labels:
        data.label.pack(ipadx=10, ipady=10, fill="both")

def get_streak_icon(streak : int) -> ImageTk:
    path = ""
    if streak >= 60:
        path = ASSET_FOLDER + "/streak3.png"
    elif streak >= 30:
        path = ASSET_FOLDER + "/streak2.png"
    else:
        path = ASSET_FOLDER + "/streak.png"
    img = Image.open(path).convert("RGBA")
    streak_img = ImageTk.PhotoImage(img)

    return streak_img

def update_streak_graphics():
    streak = json_data[STREAK_KEY]
    if streak <= 0:
        streak_icon.pack_forget()
        streak_label.pack(side='top', anchor='center', expand=False)
    else:
        streak_icon.pack(side='left', anchor='e', expand=True)
        streak_label.pack(side='right', anchor='w', expand=True)
    streak_icon.configure(image=get_streak_icon(streak))
    streak_label.configure(text=f"Streak: {streak}")

def streak_mod(mod : int):
    json_data[STREAK_KEY] += mod
    update_streak_graphics()

def time_action_label_create(time : str, shutdown : bool):
    target = datetime.strptime(time, '%H:%M:%S')
    target = target.replace(year=now.year, month=now.month, day=now.day)

    if now > target:
      target = target.replace(day=tomorrow.day)

    shutdown_time_label = customtkinter.CTkLabel(widget_frame, text=target)
    shutdown_time_label.pack(ipadx=10, ipady=10, fill="both")

    if shutdown:
        time_action_labels.append(shutdown_data(target, shutdown_time_label))
    else:
        time_action_labels.append(internet_up_data(target, shutdown_time_label))

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
shutdown_colors = create_gradient(SHUTDOWN_COLORS)
up_colors = create_gradient(UP_COLORS)

time_action_labels = []

# Intializing shutdown labels
for shutdown_time in cfg["shutdowntimes"]:
    time_action_label_create(shutdown_time, True)

# Intializing internet up labels
for up_time in cfg["uptimes"]:
    time_action_label_create(up_time, False)

sort_labels()

# Adding Time
date_label = customtkinter.CTkLabel(app, text="Date", font=("Arial", 20))
time_label = customtkinter.CTkLabel(app, text=string_now(), font=("Arial", 40))

date_label.pack()
time_label.pack()

time_until_label = tkinter.Label(app, text='', background=app_bg_color , foreground="gray", font=("Arial", 20))
time_until_label.pack()

status_label = customtkinter.CTkLabel(app, text=f"" )
status_label.pack_forget()

# Calculating what state the manager should be in:
if type(time_action_labels[-1]) is shutdown_data:
    turn_off_wifi()
    turn_off_ethernet()
elif type(time_action_labels[-1]) is internet_up_data:
    turn_on_wifi()
    turn_on_ethernet()

# Debug turn internet on and off buttons
if cfg[DEBUG_KEY]:
    debug_frame = customtkinter.CTkFrame(app)
    debug_frame.pack(side='bottom', fill="x")

    turn_off = customtkinter.CTkButton(debug_frame, text = 'Turn off Internet',
                            command = turn_off_ethernet) 
    turn_on = customtkinter.CTkButton(debug_frame, text = 'Turn on Internet',
                            command = turn_on_ethernet)  
    turn_off.pack(side = 'left', anchor='e', expand=False)
    turn_on.pack(side='left', anchor='w', expand=False)

    streak_inc = customtkinter.CTkButton(debug_frame, text = 'Streak +',
                            command = lambda : streak_mod(30)) 
    streak_dec = customtkinter.CTkButton(debug_frame, text = 'Streak -',
                            command = lambda : streak_mod(-30))  
    streak_inc.pack(side = 'right', anchor='e', expand=False)
    streak_dec.pack(side= 'right', anchor='w', expand=False)

streak_icon = customtkinter.CTkLabel(bottom_frame, text="")
streak_icon.pack(side='left', anchor='e', expand=True)
streak_label = customtkinter.CTkLabel(bottom_frame, text=f"Streak: {json_data[STREAK_KEY]}" )
streak_label.pack(side='right', anchor='w', expand=True)
update_streak_graphics()

# Apparently resizes the window
app.update_idletasks()
app.minsize(app.winfo_width(), app.winfo_height())

# Run time update
time_since_json_write = 0
update_datetime_labels()
t = threading.Thread(target=lambda: every(1, update_datetime_labels))
t.daemon = True
t.start()

# Run app
app.mainloop()