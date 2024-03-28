import tkinter
import customtkinter
import threading
import yaml
import json
import socket
import sys
import selectors
import traceback
import libclient
import os.path
from libuniversal import Actions, ConfigKey, StorageKey, Paths
from customtkinter import CTkButton
from queue import Queue
from colour import Color
from datetime import datetime, timedelta
from PIL import Image

COLOR_AMOUNT = 100
SHUTDOWN_COLORS = [(224, 0, 0), (8, 135, 4),(0, 0, 255),(0, 0, 0)]
UP_COLORS = [(0, 144, 227), (0, 135, 90),(0, 0, 255),(0, 0, 0)]

# Time is in milliseconds
GUI_THREAD_TIME = 1000

# Time is in seconds
SAVE_THREAD_TIME = 3

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

    def update_gui(self):
        a = 1

    def update_helper(self, color_list):
        global now
        global shutdown_colors
        delta = self.datetime - now
        if self.datetime <= now:
            color_index = 0
        else:
            delta_scaled = int(delta.total_seconds() ** 1.4) / int(60 * 60)
            color_index = clamp(int(delta_scaled * (COLOR_AMOUNT / 100)), 0, COLOR_AMOUNT-1)
        bg_color = Color('#%02x%02x%02x' % tuple(map(round, color_list[color_index])))
        time_left = ':'.join(str(delta).split(':')[:2])
        date_time = self.datetime.strftime("%H:%M:%S")
        self.label.configure(text=f"{date_time} | {time_left}", bg_color=bg_color.get_hex())

class shutdown_data(time_action_data):
    def update_gui(self):
        super().update_helper(shutdown_colors)

class internet_up_data(time_action_data):
    def update_gui(self):
        super().update_helper(up_colors)

def clamp(n, smallest, largest): return max(smallest, min(n, largest))

def update_gui():
    # Update Large Time Labels
    (date, time) = get_datetime()
    date_label.configure(text=date)
    time_label.configure(text=time)

    # Update Soonest time till action label
    soonest_time_delta = time_action_labels[0].datetime  - now
    time_until_label.configure(text=':'.join(str(soonest_time_delta).split(':')[:2]))

    # Update all action labels gui
    for data in time_action_labels:
        data.update_gui()

    # Waits for action by the code thread to show graphically
    while not gui_queue.empty():
        action = gui_queue.get()
        print(f"GUI Received Enqueued Action: {action}")
        if action == Actions.INTERNET_OFF:
            status_label.configure(text="Internet Shutdown Triggered", fg_color="red")
            status_label.pack()
            run_function_in_minute(lambda: status_label.pack_forget())
        elif action == Actions.INTERNET_ON:
            status_label.configure(text="Internet Activation Triggered", fg_color="blue")
            status_label.pack()
            run_function_in_minute(lambda: status_label.pack_forget())
        elif action == Actions.SORT_LABELS:
            sort_labels()
    app.after(GUI_THREAD_TIME, update_gui)

def recalculate_time(data: time_action_data):
   data.datetime = data.datetime.replace(day=tomorrow.day)

def get_datetime():
    now = datetime.now()
    date = now.strftime("%m/%d/%Y")
    time = now.strftime("%H:%M:%S")
    return date, time

def run_function_in_minute(func):
    thread = threading.Timer(60.0, func) # 60 seconds = 1 minute
    thread.daemon = True
    thread.start()

def write_data_to_json():
    with open(JSON_FILE, 'w') as f:
        json.dump(json_data, f)

def string_now():
    return  datetime.strftime(datetime.now(), '%m/%d/%y %H:%M:%S')

def lerp_color(c1,c2,t):
    return (c1[0]+(c2[0]-c1[0])*t, c1[1]+(c2[1]-c1[1])*t, c1[2]+(c2[2]-c1[2])*t)

def create_gradient(colors):
    gradient = []
    for i in range(len(colors)-2):
        for j in range(COLOR_AMOUNT):
            gradient.append(lerp_color(colors[i],colors[i+1],j/COLOR_AMOUNT))
    return gradient

def sort_labels():
    global time_action_labels
    time_action_labels = sorted(time_action_labels, key=lambda x: x.datetime)
    for data in time_action_labels:
        data.label.pack_forget()

    for data in time_action_labels:
        data.label.pack(ipadx=10, ipady=10, fill="both")

def get_streak_icon(streak : int) -> customtkinter.CTkImage:
    path = ""
    if streak >= 60:
        path = Paths.ASSETS_FOLDER + "/streak3.png"
    elif streak >= 30:
        path = Paths.ASSETS_FOLDER + "/streak2.png"
    else:
        path = Paths.ASSETS_FOLDER + "/streak.png"
    img = Image.open(path).convert("RGBA")
    streak_img = customtkinter.CTkImage(img)

    return streak_img

def update_streak_graphics():
    last_relapse = json_data[StorageKey.SINCE_LAST_RELAPSE]
    delta = now - last_relapse
    # Dividing by the amount of seconds in a day
    if delta.total_seconds() / 86400 <= 1:
        streak_icon.pack_forget()
        streak_label.pack(side='top', anchor='center', expand=False)
    else:
        streak_icon.pack(side='left', anchor='e', expand=True)
        streak_label.pack(side='right', anchor='w', expand=True)
    streak_icon.configure(image=get_streak_icon(streak))
    streak_label.configure(text=f"Streak: {streak}")

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


json_data = {}
if os.path.isfile(Paths.JSON_FILE):
   f = open(Paths.JSON_FILE) 
   json_data = json.load(f)

# Reading config
with open(Paths.CONFIG_FILE) as f:
    cfg = yaml.load(f, Loader=yaml.FullLoader)


# Defining basic time variables
now = datetime.now()
tomorrow = now + timedelta(days=1)

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
for shutdown_time in cfg[ConfigKey.SHUTDOWN_TIMES]:
    time_action_label_create(shutdown_time, True)

# Intializing internet up labels
for up_time in cfg[ConfigKey.UP_TIMES]:
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


"""
# Debug turn internet on and off buttons
if cfg[DEBUG_KEY]:
    debug_frame = customtkinter.CTkFrame(app)
    debug_frame.pack(side='bottom', fill="x")

    turn_off = CTkButton(debug_frame, text = 'Turn off Internet',
                            command = turn_off_ethernet) 
    turn_on = CTkButton(debug_frame, text = 'Turn on Internet',
                            command = turn_on_ethernet)  
    turn_off.pack(side = 'left', anchor='e', expand=False)
    turn_on.pack(side='left', anchor='w', expand=False)

    streak_inc = CTkButton(debug_frame, text = 'Streak +',
                            command = lambda : streak_mod(30)) 
    streak_dec = CTkButton(debug_frame, text = 'Streak -',
                            command = lambda : streak_mod(-30))  
    streak_inc.pack(side = 'right', anchor='e', expand=False)
    streak_dec.pack(side= 'right', anchor='w', expand=False)

    total_shutdown = CTkButton(debug_frame, text = 'Total Shutdown',
                            command = shutdown_threads) 
    total_shutdown.pack(side = 'top', expand=True)


streak_icon = customtkinter.CTkLabel(bottom_frame, text="")
streak_icon.pack(side='left', anchor='e', expand=True)
streak_label = customtkinter.CTkLabel(bottom_frame, text=f"Streak: {json_data[STREAK_KEY]}" )
streak_label.pack(side='right', anchor='w', expand=True)
update_streak_graphics()
"""

sel = selectors.DefaultSelector()

def create_request(action, value):
    if action == Actions.SEARCH:
        return dict(
            type="text/json",
            encoding="utf-8",
            content=dict(action=action, value=value),
        )
    elif action == Actions.INTERNET_ON or action == Actions.INTERNET_OFF or action == Actions.GRAB_CONFIG:
        return dict(
            type="text/json",
            encoding="utf-8",
            content=dict(action=action),
        )
    else:
        return dict(
            type="binary/custom-client-binary-type",
            encoding="binary",
            content=bytes(action + value, encoding="utf-8"),
        )


def start_connection(host, port, request):
    addr = (host, port)
    print(f"Starting connection to {addr}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.connect_ex(addr)
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    message = libclient.Message(sel, sock, addr, request)
    sel.register(sock, events, data=message)


if len(sys.argv) > 5 or len(sys.argv) < 4:
    print(f"Usage: {sys.argv[0]} <host> <port> <action> <value>")
    sys.exit(1)

host, port = sys.argv[1], int(sys.argv[2])

if(len(sys.argv) == 4):
    action, value = sys.argv[3], ""
else:
    action, value = sys.argv[3], sys.argv[4]
request = create_request(action, value)
start_connection(host, port, request)

try:
    while True:
        events = sel.select(timeout=1)
        for key, mask in events:
            message = key.data
            try:
                message.process_events(mask)
            except Exception:
                print(
                    f"Main: Error: Exception for {message.addr}:\n"
                    f"{traceback.format_exc()}"
                )
                message.close()
        # Check for a socket being monitored to continue.
        if not sel.get_map():
            break
except KeyboardInterrupt:
    print("Caught keyboard interrupt, exiting")
finally:
    sel.close()


# Run app
app.mainloop()