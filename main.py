import tkinter
import customtkinter
import threading
import yaml
import time, traceback
import subprocess
from colour import Color
from pytube import YouTube
from datetime import datetime, timedelta

# from https://github.com/abagh0703/turn-off-wifi
SECONDS_WITH_WIFI_DISABLED = 60
# Constants for the command prompt
CMD_BASE = 'cmd /c "{}"'  # first is remain/terminate, then is enable/disable
WIFI_CMD_BASE = 'wmic path win32_networkadapter where NetConnectionID="Wi-fI" call {}'
ETHERNET_CMD_BASE = 'netsh interface set interface {}'
WIFI_CMD_ENABLE = WIFI_CMD_BASE.format('enable')
WIFI_CMD_DISABLE = WIFI_CMD_BASE.format('disable')

COLOR_AMOUNT = 1000

class shutdown_data():
    def __init__(self, time, label):
        self.datetime = time
        self.label = label

    def update(self):
        delta = self.datetime - now
        hour_delta = int((delta.total_seconds() / 60 / 24))
        color_index = clamp(int(hour_delta * (COLOR_AMOUNT / 100)), 0, COLOR_AMOUNT-1)
        bg_color = Color(colors[color_index])
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
      # in production code you might want to have this instead of course:
      # logger.exception("Problem while executing repetitive task.")
    # skip tasks if we are behind schedule:
    next_time += (time.time() - next_time) // delay * delay + delay

def update_datetime_labels():
    (date, time) = get_datetime()
    date_label.configure(text=date)
    time_label.configure(text=time)

    now = datetime.now()

    for data in shutdown_labels:
        data.update()

        if data.datetime <= now:
           recalculate_time(data)
           turn_off_wifi()
           turn_off_ethernet()

def recalculate_time(data: shutdown_data):
   data.datetime = data.datetime.replace(day=tomorrow.day)
   data.update()

def get_datetime():
    now = datetime.now()
    date = now.strftime("%d/%m/%y")
    time = now.strftime("%H:%M:%S")

    return date, time

def execute_cmd(cmd):
    print(cmd)
    subprocess.call(cmd, shell=True)

def turn_on_wifi():
    execute_cmd(CMD_BASE.format(WIFI_CMD_ENABLE))

def turn_off_wifi():
    execute_cmd(CMD_BASE.format(WIFI_CMD_DISABLE))

def turn_on_ethernet():
    for ethernet in cfg["ethernet"]:
        execute_cmd(CMD_BASE.format(ETHERNET_CMD_BASE.format(ethernet) + " enabled"))

def turn_off_ethernet():
    for ethernet in cfg["ethernet"]:
        execute_cmd(CMD_BASE.format(ETHERNET_CMD_BASE.format(ethernet) + " disabled"))

# Reading config
with open("config.yaml") as f:
    cfg = yaml.load(f, Loader=yaml.FullLoader)

# System Settings
customtkinter.set_appearance_mode("System")
customtkinter.set_default_color_theme("blue")

# Our app frame
app = customtkinter.CTk()
app.geometry("720x480")
app.title("Internet Manager")

widget_frame = customtkinter.CTkFrame(app, bg_color="steel blue")
widget_frame.pack(side='left')

now = datetime.now()
tomorrow = now + timedelta(days=1)

blue = Color("darkslateblue")
colors = list(blue.range_to(Color("red"), COLOR_AMOUNT))

shutdown_labels = []

for shutdown_time in cfg["shutdowntimes"]:
    target = datetime.strptime(shutdown_time, '%H:%M:%S')
    target = target.replace(year=now.year, month=now.month, day=now.day)

    if now > target:
      target = target.replace(day=tomorrow.day)

    shutdown_time_label = customtkinter.CTkLabel(widget_frame, text=target)
    shutdown_time_label.pack(ipadx=10, ipady=10, fill="both")

    shutdown_labels.append(shutdown_data(target, shutdown_time_label))

# Adding Time
date_label = customtkinter.CTkLabel(app, text="Date", font=("Times", 20))
time_label = customtkinter.CTkLabel(app, text="Time", font=("Times", 40))

date_label.pack()
time_label.pack()

turn_off = customtkinter.CTkButton(app, text = 'Turn off Internet',
                          command = turn_off_ethernet) 
turn_on = customtkinter.CTkButton(app, text = 'Turn on Internet',
                          command = turn_on_ethernet) 

# Set the position of button on the top of window.   
turn_off.pack(side = 'top')
turn_on.pack()

# Run time update
update_datetime_labels()
t = threading.Thread(target=lambda: every(1, update_datetime_labels))
t.daemon = True
t.start()

# Run app
app.mainloop()