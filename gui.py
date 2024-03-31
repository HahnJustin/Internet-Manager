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
import random
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

MILITARY_TIME = "%H:%M:%S"
NORMAL_TIME = "%#I:%M:%S %p"

time_format = MILITARY_TIME

VOUCHED_COLOR = '#1f61a3'

LOOT_BOX_ODDS = 80
VOUCHER_ODDS = 60

internet_on = True
admin_on = True
stop_gifs = False

used_voucher_today = False
local_vouchers = 0
status_timer = None

global now
global colors
global time_action_buttons
global json_data
global date_label
global time_label
global sel

class time_action_data():
    def __init__(self, time, button):
        self.datetime = time
        self.button = button
        self.vouched = False
        self.button.configure(image=get_button_icon(self),
                              compound="right",
                              anchor='e', 
                              corner_radius=0, 
                              command= self.click,
                              text_color_disabled="white")

    def click(self):
        global local_vouchers
        global internet_on
        global time_action_buttons

        index = time_action_buttons.index(self)
        can_vouch = True
        for i in reversed(range(index)):
            button = time_action_buttons[i] 
            if not button.vouched and type(button) != internet_up_data:
                can_vouch = False
                break

        if not self.vouched and local_vouchers > 0 and internet_on and can_vouch:
            self.make_vouched()
            local_vouchers -= 1
            do_request(Actions.USED_VOUCHER, str(self))
        elif self.vouched:
            for i in range(index,len(time_action_buttons)):
                button = time_action_buttons[i] 
                if button.vouched:
                    button.make_unvouched()
                    local_vouchers += 1
                    do_request(Actions.UNUSED_VOUCHER, str(button))
        update_voucher_label()

    def make_vouched(self):
        date_time = self.datetime.strftime(time_format)
        vouched_color = Color(VOUCHED_COLOR)
        hvr_color = Color(rgb=(clamp(vouched_color.red/1.4,0,1), clamp(vouched_color.green/1.4,0,1), clamp(vouched_color.blue/1.2,0,1)))
        self.button.configure(text=f"{date_time} | -:--", fg_color=VOUCHED_COLOR, hover_color=str(hvr_color), image=get_image(Paths.ASSETS_FOLDER + "/mini_voucher.png"))
        self.vouched = True

    def make_unvouched(self):
        self.button.configure(image=get_button_icon(self), compound="right", anchor='e', corner_radius=0, command= self.click)
        self.update_gui()
        self.update_color()
        self.vouched = False

    def update_gui(self):
        global now

        delta = self.datetime - now
        time_left = ':'.join(str(delta).split(':')[:2])
        date_time = self.datetime.strftime(time_format)
        self.button.configure(text=f"{date_time} | {time_left}")

    def update_color(self):
        color = self.get_color()
        hvr_color = Color(rgb=(color.red/1.4, color.green/1.4, color.blue/1.2))
        self.button.configure(fg_color=str(self.get_color()), hover_color=str(hvr_color))

    def get_color(self) -> Color:
        delta = self.datetime - now
        if self.datetime <= now:
            color_index = 0
        else:
            delta_scaled = int(delta.total_seconds() ** 1.4) / int(60 * 60)
            color_index = clamp(int(delta_scaled * (COLOR_AMOUNT / 100)), 0, COLOR_AMOUNT-1)
        return Color('#%02x%02x%02x' % tuple(map(round, self.color_list[color_index])))

    def __str__(self) -> str:
        return datetime.strftime(self.datetime, '%m/%d/%y %H:%M:%S')
    
class shutdown_data(time_action_data):
    def __init__(self, time, button):
        self.color_list = shutdown_colors
        super(shutdown_data, self).__init__(time, button)

class enforced_shutdown_data(time_action_data):
    def __init__(self, time, button):
        self.color_list = enforced_colors
        super(enforced_shutdown_data, self).__init__(time, button)

class internet_up_data(time_action_data):
    def __init__(self, time, button):
        self.color_list = up_colors
        super(internet_up_data, self).__init__(time, button)

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
    if action == Actions.SEARCH or Actions.USED_VOUCHER or Actions.UNUSED_VOUCHER:
        return dict(
            type="text/json",
            encoding="utf-8",
            content=dict(action=action, value=value),
        )
    elif( action == Actions.INTERNET_ON or action == Actions.INTERNET_OFF or 
          action == Actions.GRAB_CONFIG or action == Actions.ADMIN_STATUS or
          action == Actions.INTERNET_STATUS or action == Actions.GRAB_STORAGE or
          action == Actions.RELAPSE or action == Actions.ADD_VOUCHER):
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
    global used_voucher_today
    global time_action_buttons
    global json_data
    global now
    global cutoff_time
    global date_label
    global time_label
    global internet_on

    (date, time) = get_datetime()
    date_label.configure(text=date)
    time_label.configure(text=time)

    # Soonest time delta 
    for data in time_action_buttons:
        if not data.vouched:
            soonest_data = data
            break
    soonest_time_delta = soonest_data.datetime  - now
    color = soonest_data.get_color()
    hvr_color = Color(rgb=(clamp(color.red*1.4,0,1), clamp(color.green*1.4,0,1), clamp(color.blue*1.4,0,1)))
    time_until_label.configure(text=':'.join(str(soonest_time_delta).split(':')[:2]), text_color=str(hvr_color))

    now = datetime.now()

    if now > cutoff_time:
        recalculate_cutoff_time()
        used_voucher_today = False

    # shutdown label maintenance
    for data in time_action_buttons:
        if not data.vouched:
            data.update_gui()

        # actual shutdown
        if data.datetime > now:
            continue
        if data.vouched:
            show_status("Voucher Consumed", True)
            used_voucher_today = True
        elif type(data) == shutdown_data or type(data) == enforced_shutdown_data:
            set_icon(False)
            show_status("Internet Shutdown Triggered", False)
            toggle_relapse_button(True)
            toggle_globe_animation(False)
            internet_on = False
            if random.randint(0,99) < LOOT_BOX_ODDS and not used_voucher_today:
                toggle_loot_box(True)
        elif type(data) == internet_up_data:
            set_icon(True)
            show_status("Internet Reboot Triggered", True)
            toggle_relapse_button(False)
            toggle_globe_animation(True)
            internet_on = True
        recalculate_time(data)
        sort_labels()

def update_button_color():
    for data in time_action_buttons:
        if not data.vouched:
            data.update_color()

def recalculate_time(data: time_action_data):
   global tomorrow
   tomorrow = now + timedelta(days=1)
   data.datetime = data.datetime.replace(day=tomorrow.day)
   data.make_unvouched()

def recalculate_cutoff_time():
    global cutoff_time
    global now

    cutoff_time = datetime.strptime(cfg[ConfigKey.STREAK_SHIFT], '%H:%M')
    cutoff_time = cutoff_time.replace(year=now.year, month=now.month, day=now.day)

    if now > cutoff_time:
        cutoff_time = cutoff_time.replace(year=tomorrow.year, month=tomorrow.month, day=tomorrow.day)

def get_datetime():
    now = datetime.now()
    date = now.strftime("%#m.%#d.%Y")
    time = now.strftime(time_format)
    return date, time

def show_status(status : str, positive : bool):
    global status_timer

    if not positive:
        status_label.configure(text=status, image=get_image(Paths.ASSETS_FOLDER + "/red_ribbon.png"))
    else:
        status_label.configure(text=status, image=get_image(Paths.ASSETS_FOLDER + "/blue_ribbon.png"))
    status_label.pack()

    if status_timer is not None:
        status_timer.cancel()
    status_timer = run_function_in_minute(lambda: status_label.pack_forget())

def run_function_in_minute(func) -> threading.Timer:
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
    global time_action_buttons
    time_action_buttons = sorted(time_action_buttons, key=lambda x: x.datetime)
    for data in time_action_buttons:
        data.button.pack_forget()

    for data in time_action_buttons:
        data.button.pack(ipadx=10, ipady=10, fill="both")

def get_streak_icon(streak : int) -> customtkinter.CTkImage:
    path = ""
    if streak >= 60:
        path = Paths.ASSETS_FOLDER + "/streak3.png"
    elif streak >= 30:
        path = Paths.ASSETS_FOLDER + "/streak2.png"
    else:
        path = Paths.ASSETS_FOLDER + "/streak.png"
    return get_image(path)

def get_button_icon(label_data : time_action_data) -> customtkinter.CTkImage:
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

def update_voucher_label():
    voucher_label.configure(text=f"x{local_vouchers}")

def time_action_button_create(time : str, label_type : ConfigKey) -> time_action_data:
    global tomorrow
    global now

    target = datetime.strptime(time, '%H:%M:%S')
    target = target.replace(year=now.year, month=now.month, day=now.day)

    if now > target:
       target = target.replace(year=tomorrow.year, month=tomorrow.month, day=tomorrow.day)

    action_time_button = customtkinter.CTkButton(widget_frame, text=target)
    action_time_button.pack(ipadx=10, ipady=10, fill="both")

    if label_type == ConfigKey.SHUTDOWN_TIMES:
        data = shutdown_data(target, action_time_button)
    elif label_type == ConfigKey.ENFORCED_SHUTDOWN_TIMES:
        data = enforced_shutdown_data(target, action_time_button)
        action_time_button.configure(state="disabled")
    else:
        data = internet_up_data(target, action_time_button)
        action_time_button.configure(state="disabled")
    time_action_buttons.append(data)
    if str(data) in json_data[StorageKey.VOUCHERS_USED]:
        data.make_vouched()

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

def _play_gif_once(label, frames):

    total_delay = 0
    delay_frames = 100

    for frame in frames:
        app.after(total_delay, _next_frame, frame, label, frames)
        total_delay += delay_frames

def _play_gif(label, frames):
    if stop_gifs:
        return
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

def manual_override():
    top= customtkinter.CTkToplevel(app)
   
    x = app.winfo_rootx()
    y = app.winfo_rooty()
    height = app.winfo_height()
    width = app.winfo_width()
    top.geometry("+%d+%d" % (x-125+width/2,y-50+height/2))
    top.minsize(400, 250)
    top.maxsize(400, 250)
    top.attributes('-topmost',True)
    top.title("Pathetic")
    label = customtkinter.CTkLabel(top, text= f"Are you really sure that you want to end \n your streak of {streak} and turn on the internet?", font=('Mistral 18 bold', 20), pady=10)
    label.pack(side='top')
    internet_on = CTkButton(top, text = 'Forsake your Honor',
                        command= lambda : relapse(top),
                        hover_color='#691114',
                        font=('Mistral 18 bold', 20),
                        fg_color="#b51b20")  
    internet_on.place(relx=0.5, rely=0.5, anchor="center")

    top.grab_set()

def relapse(top : customtkinter.CTkToplevel):
    global streak
    global last_relapse
    global json_data
    global internet_on

    top.destroy()
    streak = 0
    show_status("User succumbed to temptation", True)
    do_request(Actions.RELAPSE, "")

    json_data[StorageKey.SINCE_LAST_RELAPSE] = datetime.strftime(datetime.now(), '%m/%d/%y %H:%M:%S')
    last_relapse = get_last_relapse()
    update_streak_graphics()
    toggle_relapse_button(False)
    toggle_globe_animation(True)
    set_icon(True)
    internet_on = True

def get_last_relapse() -> datetime:
    global json_data
    global cfg
    global cutoff_time

    last_relapse = datetime.strptime(json_data[StorageKey.SINCE_LAST_RELAPSE], '%m/%d/%y %H:%M:%S')
    return last_relapse.replace(hour=cutoff_time.hour, minute=cutoff_time.minute)

def toggle_relapse_button(on : bool):
    if on:
        relapse_button.pack(side='bottom', anchor='s', expand=False)
    else:
        relapse_button.pack_forget()

def toggle_loot_box(on : bool):
    if on:
        internet_box_button.configure(text = 'You found an internet box!',
                        image=get_image(Paths.ASSETS_FOLDER + "/internet_box.png")) 
        internet_box_button.pack(fill="both", expand=True, padx=20, pady=20)
        internet_box_button.bind("<Enter>", lambda e: internet_box_button.configure(text="Click to open!"))
        internet_box_button.bind("<Leave>", lambda e: internet_box_button.configure(text='You found an internet box!'))
    else:
        internet_box_button.pack_forget()

def loot_box():
    internet_box_button.unbind("<Enter>")
    internet_box_button.unbind("<Leave>")
    internet_box_button.configure(text='You opened the box...', state="disabled", image=get_image(Paths.ASSETS_FOLDER + "\internet_box_open.png"))

    thread = threading.Timer(random.randint(2, 10), get_loot)
    thread.daemon = True
    thread.start()

def get_loot():
    global local_vouchers
    result = random.randint(0,99)
    if result > VOUCHER_ODDS:
        internet_box_button.configure(text='There was nothing inside :(')
    elif local_vouchers < voucher_limit:
        internet_box_button.configure(text='You found a voucher!!!', image=get_image(Paths.ASSETS_FOLDER + "\\voucher.png"))
        local_vouchers += 1
        update_voucher_label()
        do_request(Actions.ADD_VOUCHER, "")
    else:
        internet_box_button.configure(text="You found a voucher, but don't have room... ", image=get_image(Paths.ASSETS_FOLDER + "\\voucher.png"))
    
    run_function_in_minute(lambda : toggle_loot_box(False))
    
def toggle_globe_animation(enabled : bool):
    global globe_frames
    global stop_gifs

    stop_gifs = not enabled
    if enabled:
        globe_enable_left_frames = get_frames(Paths.ASSETS_FOLDER + "/globular_on_left.gif")
        globe_enable_right_frames = get_frames(Paths.ASSETS_FOLDER + "/globular_on_right.gif")
        app.after(1, _play_gif_once, left_globe_gif, globe_enable_left_frames)
        app.after(1, _play_gif_once, right_globe_gif, globe_enable_right_frames)
        app.after(2000, _play_gif, left_globe_gif, globe_frames)
        app.after(2000, _play_gif, right_globe_gif, globe_frames)
    else:
        globe_disable_left_frames = get_frames(Paths.ASSETS_FOLDER + "/globular_off_left.gif")
        globe_disable_right_frames = get_frames(Paths.ASSETS_FOLDER + "/globular_off_right.gif")
        app.after(1, _play_gif_once, left_globe_gif, globe_disable_left_frames)
        app.after(1, _play_gif_once, right_globe_gif, globe_disable_right_frames)


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

# Defining local vouchers amount
local_vouchers = json_data[StorageKey.VOUCHER]
voucher_limit = json_data[StorageKey.VOUCHER_LIMIT]

# Defining basic time variables
now = datetime.now()
tomorrow = now + timedelta(days=1)
recalculate_cutoff_time()

# Defining last time since internet override, used in streak calc
last_relapse = get_last_relapse()

# Set military time or not
if ConfigKey.MILITARY_TIME in cfg and not cfg[ConfigKey.MILITARY_TIME]:
    print("not military time")
    time_format = NORMAL_TIME

if StorageKey.VOUCHERS_USED in json_data:
    for time in json_data[StorageKey.VOUCHERS_USED]:
        used_time = datetime.strptime(time, '%m/%d/%y %H:%M:%S')
        if now > used_time:
            used_voucher_today = True
            print('Used voucher since last cutoff detected')
            break

# System Settings
customtkinter.set_appearance_mode("System")
customtkinter.set_default_color_theme("blue")

# Our app frame
app = customtkinter.CTk()
app.geometry("720x480")
app.minsize(600, 350)
app.title("Internet Manager")
app_bg_color = app.cget('bg')

# Shutdown label parent
widget_frame = customtkinter.CTkFrame(app, fg_color='#404654', corner_radius=0)
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

# Bottom Frame
bottom_frame = customtkinter.CTkFrame(app, corner_radius=0, fg_color='#2d3542')
bottom_frame.pack(side='bottom', fill="x")

# Bottom right 
bottom_right_frame = customtkinter.CTkFrame(bottom_frame, corner_radius=0, fg_color='#2d3542')
bottom_right_frame.pack(side='right')

# Bottom left 
bottom_left_frame = customtkinter.CTkFrame(bottom_frame, corner_radius=0, fg_color='#2d3542')
bottom_left_frame.pack(side='left')

# Making shutdown label color gradient
shutdown_colors = create_gradient(SHUTDOWN_COLORS)
enforced_colors = create_gradient(ENFORCED_COLORS)
up_colors = create_gradient(UP_COLORS)

time_action_buttons = []

# Intializing shutdown labels
for shutdown_time in cfg[ConfigKey.SHUTDOWN_TIMES]:
    time_action_button_create(shutdown_time, ConfigKey.SHUTDOWN_TIMES)

# Intializing enforced shutdown labels
for enforced_shutdown_time in cfg[ConfigKey.ENFORCED_SHUTDOWN_TIMES]:
    time_action_button_create(enforced_shutdown_time, ConfigKey.ENFORCED_SHUTDOWN_TIMES)

# Intializing internet up labels
for up_time in cfg[ConfigKey.UP_TIMES]:
    time_action_button_create(up_time, ConfigKey.UP_TIMES)

sort_labels()

# Adding Time
date_label = customtkinter.CTkLabel(top_frame, text_color="#666e7a", text="Date", font=("Arial", 20), pady=0)
time_label = customtkinter.CTkLabel(top_frame, text=string_now(), font=("old english text mt", 40), padx=10)

date_label.pack(side='top')
time_label.pack(side='top')

time_until_label = customtkinter.CTkLabel(top_frame, text='', font=("Arial", 20))
time_until_label.pack()

status_label = customtkinter.CTkLabel(app, text=f"", text_color="white", font=("old english text mt",20), compound='center', anchor='n')
status_label.pack_forget()

# Initial Status
if do_request(Actions.INTERNET_STATUS, ""):
    internet_on = True
    show_status("Internet is On", True)
    set_icon(True)
else:
    internet_on = False
    show_status("Internet is Off", False)
    set_icon(False)

# Admin Check
if not do_request(Actions.ADMIN_STATUS, ""):
    show_status("Server is not running in Admin", False)
    admin_on = False


if admin_on:
    # left globe
    globe_frames = get_frames(Paths.ASSETS_FOLDER + "/globular.gif")
    left_globe_gif = customtkinter.CTkLabel(top_left_frame, text="", image=globe_frames[1])
    left_globe_gif.pack(side='right', anchor='e', expand=True)

    # right globe
    right_globe_gif = customtkinter.CTkLabel(top_right_frame, text="", image=globe_frames[1])
    right_globe_gif.pack(side='left', anchor='w', expand=True)

    toggle_globe_animation(internet_on)

else:
    # left caution
    caution_right = customtkinter.CTkLabel(top_left_frame, text="", image=get_image(Paths.ASSETS_FOLDER + "/caution.png"))
    caution_right.pack(side='right', anchor='e', expand=True)

    # right caution
    caution_left = customtkinter.CTkLabel(top_right_frame, text="", image=get_image(Paths.ASSETS_FOLDER + "/caution.png"))
    caution_left.pack(side='left', anchor='w', expand=True)

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

    test_gif = CTkButton(debug_frame, text = 'Gif Toggle Off',
                            command = lambda : toggle_globe_animation(False))  
    test_gif.pack(side='right', anchor='w', expand=False)

    test_gif_on = CTkButton(debug_frame, text = 'Gif Toggle On',
                            command = lambda : toggle_globe_animation(True))  
    test_gif_on.pack(side='right', anchor='w', expand=False)
    """
    test_loot_box = CTkButton(debug_frame, text = 'Test Lootbox',
                            command = lambda : toggle_loot_box(True))  
    test_loot_box.pack(side='right', anchor='w', expand=False)
    """

# manual on button
relapse_button = CTkButton(app, text = 'Override Turn On Internet',
                        command = manual_override,
                        hover_color='#691114',
                        fg_color="#b51b20")
toggle_relapse_button(not internet_on)

internet_box_button = CTkButton(app, text = 'You found an internet box!',
                        hover_color='#1b1d21',
                        fg_color= app_bg_color,
                        image=get_image(Paths.ASSETS_FOLDER + "/internet_box.png"),
                        compound="top",
                        anchor='center', 
                        corner_radius=0, 
                        hover= True,
                        command= loot_box,
                        text_color_disabled="white")
toggle_loot_box(False)

streak = math.floor((now - last_relapse).total_seconds() / 86400)

streak_icon = customtkinter.CTkLabel(bottom_frame, text="")
streak_icon.pack(side='left', anchor='e', expand=True)
streak_label = customtkinter.CTkLabel(bottom_frame, text=f"Streak: {streak}" )
streak_label.pack(side='right', anchor='w', expand=True)
update_streak_graphics()

voucher_label = customtkinter.CTkLabel(bottom_right_frame, text=f"x{local_vouchers}", 
                                        image=get_image(Paths.ASSETS_FOLDER + "/tiny_voucher.png"),
                                        compound='left', anchor='e', padx = 5)
voucher_label.pack(side='right', anchor='e', expand=True)

red_voucher_label = customtkinter.CTkLabel(bottom_left_frame, text=f"x{voucher_limit}", 
                                        image=get_image(Paths.ASSETS_FOLDER + "/tiny_red_voucher.png"),
                                        compound='left', anchor='e', padx = 5)
red_voucher_label.pack(side='right', anchor='e', expand=True)


# Run time update
update_gui()
t = threading.Thread(target=lambda: every(1, update_gui))
t.daemon = True
t.start()

# Run time update
update_button_color()
t = threading.Thread(target=lambda: every(60, update_button_color))
t.daemon = True
t.start()

# Run app
app.mainloop()

#Close selector
sel.close()