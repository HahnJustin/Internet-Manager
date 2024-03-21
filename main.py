import tkinter
import customtkinter
import threading
import yaml
import time, traceback
from pytube import YouTube
from datetime import datetime

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

def get_datetime():
    now = datetime.now()
    date = now.strftime("%d/%m/%y")
    time = now.strftime("%H:%M:%S")

    return date, time

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

widget_frame = customtkinter.CTkFrame(app)
widget_frame.pack(side='left')

for shutdown_time in cfg["shutdowntimes"]:
   shutdown_time_label = customtkinter.CTkLabel(widget_frame, text=shutdown_time, bg_color="steel blue")
   shutdown_time_label.pack(ipadx=10, ipady=10, fill="both")

# Adding Time
date_label = customtkinter.CTkLabel(app, text="Date", font=("Times", 20))
time_label = customtkinter.CTkLabel(app, text="Time", font=("Times", 40))

date_label.pack()
time_label.pack()

# Run time update
update_datetime_labels()
t = threading.Thread(target=lambda: every(1, update_datetime_labels))
t.daemon = True
t.start()

# Run app
app.mainloop()