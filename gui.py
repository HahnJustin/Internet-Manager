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
import time
import math
import ctypes
from libuniversal import Actions, ConfigKey, StorageKey, Paths
from customtkinter import CTkButton
from queue import Queue
from colour import Color
from datetime import datetime, timedelta
from PIL import Image

COLOR_AMOUNT = 100
SHUTDOWN_COLORS = [(224, 0, 0), (69, 75, 92),(0, 0, 255),(0, 0, 0)]
ENFORCED_COLORS = [(48, 0, 9), (69, 75, 92),(0, 0, 255),(0, 0, 0)]
UP_COLORS = [(0, 144, 227), (69, 75, 92),(0, 0, 255),(0, 0, 0)]

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
global sel

class time_action_data():
    def __init__(self, time, label):
        self.datetime = time
        self.label = label
        self.label.configure(image=get_label_icon(self), compound="right", anchor='e', padx=10)

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

class enforced_shutdown_data(time_action_data):
    def update_gui(self):
        super().update_helper(enforced_colors)

class internet_up_data(time_action_data):
    def update_gui(self):
        super().update_helper(up_colors)

def every(delay, task):
  next_time = time.time() + delay
  while True:
    time.sleep(max(0, next_time - time.time()))
    try:
      task()
    except Exception:
      traceback.print_exc()
    next_time += (time.time() - next_time) // delay * delay + delay

def create_request(action, value):
    if action == Actions.SEARCH:
        return dict(
            type="text/json",
            encoding="utf-8",
            content=dict(action=action, value=value),
        )
    elif( action == Actions.INTERNET_ON or action == Actions.INTERNET_OFF or 
          action == Actions.GRAB_CONFIG or action == Actions.ADMIN_STATUS or
          action == Actions.INTERNET_STATUS or action == Actions.GRAB_STORAGE):
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

def do_request(action, value) -> str:
    global sel

    request = create_request(action, value)
    start_connection(host, port, request)

    try:
        while True:
            message = None
            events = sel.select(timeout=1)
            print(f"Events {events}")
            for key, mask in events:
                message = key.data
                try:
                    print("processing message")
                    message.process_events(mask)
                except Exception:
                    print(
                        f"Main: Error: Exception for {message.addr}:\n"
                        f"{traceback.format_exc()}"
                    )
                    message.close()
            # Check for a socket being monitored to continue.
            if not sel.get_map():
                return message.result
    except KeyboardInterrupt:
        print("Caught keyboard interrupt, exiting")

def clamp(n, smallest, largest): return max(smallest, min(n, largest))

def update_gui():
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

    # shutdown label maintenance
    for data in time_action_labels:
        data.update_gui()

        # actual shutdown
        if data.datetime > now:
            continue
        if type(data) == shutdown_data:
            set_icon(False)
            show_status("Internet Shutdown Triggered", False)
        if type(data) == internet_up_data:
            set_icon(True)
            show_status("Internet Reboot Triggered", True)
        recalculate_time(data)
        sort_labels()

def recalculate_time(data: time_action_data):
   data.datetime = data.datetime.replace(day=tomorrow.day)

def get_datetime():
    now = datetime.now()
    date = now.strftime("%m/%d/%Y")
    time = now.strftime("%H:%M:%S")
    return date, time

def show_status(status : str, positive : bool):
    if not positive:
        status_label.configure(text=status, text_color="red")
    else:
        status_label.configure(text=status, text_color="blue")
    status_label.pack()
    run_function_in_minute(lambda: status_label.pack_forget())

def run_function_in_minute(func):
    thread = threading.Timer(60.0, func) # 60 seconds = 1 minute
    thread.daemon = True
    thread.start()

def write_data_to_json():
    with open(Paths.JSON_FILE, 'w') as f:
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
    return get_image(path)

def get_label_icon(label_data : time_action_data) -> customtkinter.CTkImage:
    path = ""
    if type(label_data) == shutdown_data:
        path = Paths.ASSETS_FOLDER + "/no_globe.png"
    elif type(label_data) == internet_up_data:
        path = Paths.ASSETS_FOLDER + "/globe.png"
    else:
        path = Paths.ASSETS_FOLDER + "/skull_globe.png"
    return get_image(path)

def get_image(path) -> customtkinter.CTkImage:
    img = Image.open(path).convert("RGBA")
    return customtkinter.CTkImage(img, size=(img.width, img.height))


def update_streak_graphics():
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

def time_action_label_create(time : str, label_type : ConfigKey):
    target = datetime.strptime(time, '%H:%M:%S')
    target = target.replace(year=now.year, month=now.month, day=now.day)

    if now > target:
      target = target.replace(day=tomorrow.day)

    shutdown_time_label = customtkinter.CTkLabel(widget_frame, text=target)
    shutdown_time_label.pack(ipadx=10, ipady=10, fill="both")

    if label_type == ConfigKey.SHUTDOWN_TIMES:
        time_action_labels.append(shutdown_data(target, shutdown_time_label))
    elif label_type == ConfigKey.ENFORCED_SHUTDOWN_TIMES:
        time_action_labels.append(enforced_shutdown_data(target, shutdown_time_label))
    else:
        time_action_labels.append(internet_up_data(target, shutdown_time_label))

def set_icon(internet_on : bool):
    if internet_on:
        app.iconbitmap(Paths.ASSETS_FOLDER + "/globe.ico")
        img = tkinter.PhotoImage(file=Paths.ASSETS_FOLDER + "/globex5.png")
    else:
        app.iconbitmap(Paths.ASSETS_FOLDER + "/globe_no.ico")
        img = tkinter.PhotoImage(file=Paths.ASSETS_FOLDER + "/no_globex5.png")
    #custom_img = customtkinter.Ctkim
    app.wm_iconphoto(True, img)

def get_frames(img):
    with Image.open(img) as gif:
        index = 0
        frames = []
        while True:
            try:
                gif.seek(index)
                frame = customtkinter.CTkImage(dark_image=gif.convert("RGBA"), size=(gif.width, gif.height))
                frames.append(frame)
            except EOFError:
                break
            index += 1
        return frames

def _play_gif(label, frames):

    total_delay = 0
    delay_frames = 100

    for frame in frames:
        app.after(total_delay, _next_frame, frame, label, frames)
        total_delay += delay_frames
    app.after(total_delay, _next_frame, frame, label, frames, True)

def _next_frame(frame : customtkinter.CTkImage, label, frames, restart=False):
    if restart:
        app.after(1, _play_gif, label, frames)
        return
    label.configure(image=frame)

# no clue why this works, but it allows the taskbar icon to be custom
myappid = 'mycompany.myproduct.subproduct.version' # arbitrary string
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

sel = selectors.DefaultSelector()

# Reading config
with open(Paths.CLIENT_CONFIG_FILE) as f:
    cfg = yaml.load(f, Loader=yaml.FullLoader)
    host = cfg[ConfigKey.HOST]
    port = cfg[ConfigKey.PORT]

cfg = do_request(Actions.GRAB_CONFIG, "")

json_data = do_request(Actions.GRAB_STORAGE, "")

# Defining last time since internet override, used in streak calc
last_relapse = datetime.strptime(json_data[StorageKey.SINCE_LAST_RELAPSE], '%m/%d/%y %H:%M:%S')
cutoff_time = datetime.strptime(cfg[ConfigKey.STREAK_SHIFT], '%H:%M')
last_relapse = last_relapse.replace(hour=cutoff_time.hour, minute=cutoff_time.minute)

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
widget_frame = customtkinter.CTkFrame(app, fg_color='#697592', corner_radius=0)
widget_frame.pack(side='left', fill="y")

# Top label parent
top_frame = customtkinter.CTkFrame(app, fg_color='#2d3542', corner_radius=0)
top_frame.pack(side='top', fill="x")
top_frame_fg_color = top_frame.cget('fg_color')

# Top left
top_left_frame = customtkinter.CTkFrame(top_frame, fg_color='#2d3542', corner_radius=0)
top_left_frame.pack(side='left', fill='both', expand= True)

# Top right 
top_right_frame = customtkinter.CTkFrame(top_frame, fg_color='#2d3542', corner_radius=0)
top_right_frame.pack(side='right', fill='both', expand= True)

bottom_frame = customtkinter.CTkFrame(app, corner_radius=0, fg_color='#2d3542')
bottom_frame.pack(side='bottom', fill="x")

# Bottom right 
bottom_right_frame = customtkinter.CTkFrame(bottom_frame, corner_radius=0, fg_color='#2d3542')
bottom_right_frame.pack(side='right')

# Making shutdown label color gradient
shutdown_colors = create_gradient(SHUTDOWN_COLORS)
enforced_colors = create_gradient(ENFORCED_COLORS)
up_colors = create_gradient(UP_COLORS)

time_action_labels = []

# Intializing shutdown labels
for shutdown_time in cfg[ConfigKey.SHUTDOWN_TIMES]:
    time_action_label_create(shutdown_time, ConfigKey.SHUTDOWN_TIMES)

# Intializing enforced shutdown labels
for enforced_shutdown_time in cfg[ConfigKey.ENFORCED_SHUTDOWN_TIMES]:
    time_action_label_create(enforced_shutdown_time, ConfigKey.ENFORCED_SHUTDOWN_TIMES)

# Intializing internet up labels
for up_time in cfg[ConfigKey.UP_TIMES]:
    time_action_label_create(up_time, ConfigKey.UP_TIMES)

sort_labels()

# Adding Time
date_label = customtkinter.CTkLabel(top_frame, text="Date", font=("Arial", 20))
time_label = customtkinter.CTkLabel(top_frame, text=string_now(), font=("Arial", 40))

date_label.pack(side='top')
time_label.pack(side='top')

time_until_label = tkinter.Label(top_frame, text='', background=top_frame_fg_color , foreground="gray", font=("Arial", 20))
time_until_label.pack()

status_label = customtkinter.CTkLabel(app, text=f"", text_color="black", image=get_image(Paths.ASSETS_FOLDER + "/ribbon.png"), font=("old english text mt",20), compound='center', anchor='n')
status_label.pack_forget()

# Initial Status
if not do_request(Actions.ADMIN_STATUS, ""):
    show_status("Server is not running in Admin", False)
elif do_request(Actions.INTERNET_STATUS, ""):
    show_status("Internet is On", True)
    set_icon(True)
else:
    show_status("Internet is Off", False)
    set_icon(False)

globe_frames = get_frames(Paths.ASSETS_FOLDER + "/globular.gif")
globe_gif = customtkinter.CTkLabel(top_left_frame, text="", image=globe_frames[1])
globe_gif.pack(side='right', anchor='e', expand=True)
app.after(100, _play_gif, globe_gif, globe_frames)

globe_frames = get_frames(Paths.ASSETS_FOLDER + "/globular.gif")
globe_gif = customtkinter.CTkLabel(top_right_frame, text="", image=globe_frames[1])
globe_gif.pack(side='left', anchor='w', expand=True)
app.after(100, _play_gif, globe_gif, globe_frames)

# Debug turn internet on and off buttons
if cfg[ConfigKey.DEBUG]:
    debug_frame = customtkinter.CTkFrame(app)
    debug_frame.pack(side='bottom', fill="x")

    turn_off = CTkButton(debug_frame, text = 'Turn off Internet',
                            command = lambda : do_request(Actions.INTERNET_OFF, "")) 
    turn_on = CTkButton(debug_frame, text = 'Turn on Internet',
                            command = lambda : do_request(Actions.INTERNET_ON, ""))  
    turn_off.pack(side = 'left', anchor='e', expand=False)
    turn_on.pack(side='left', anchor='w', expand=False)

"""
    streak_inc = CTkButton(debug_frame, text = 'Streak +',
                            command = lambda : streak_mod(30)) 
    streak_dec = CTkButton(debug_frame, text = 'Streak -',
                            command = lambda : streak_mod(-30))  
    streak_inc.pack(side = 'right', anchor='e', expand=False)
    streak_dec.pack(side= 'right', anchor='w', expand=False)
    
    total_shutdown = CTkButton(debug_frame, text = 'Total Shutdown',
                            command = shutdown_threads) 
    total_shutdown.pack(side = 'top', expand=True)
"""

streak = math.floor((now - last_relapse).total_seconds() / 86400)

streak_icon = customtkinter.CTkLabel(bottom_frame, text="")
streak_icon.pack(side='left', anchor='e', expand=True)
streak_label = customtkinter.CTkLabel(bottom_frame, text=f"Streak: {streak}" )
streak_label.pack(side='right', anchor='w', expand=True)
update_streak_graphics()

voucher_amount = json_data[StorageKey.VOUCHER]
voucher_label = customtkinter.CTkLabel(bottom_right_frame, text=f"x{voucher_amount}", 
                                        image=get_image(Paths.ASSETS_FOLDER + "/tiny_voucher.png"),
                                        compound='left', anchor='e', padx = 5)
voucher_label.pack(side='right', anchor='e', expand=True)

# Apparently resizes the window
app.update_idletasks()
app.minsize(app.winfo_width(), app.winfo_height())

# Run time update
update_gui()
t = threading.Thread(target=lambda: every(1, update_gui))
t.daemon = True
t.start()

# Run app
app.mainloop()

#Close selector
sel.close()