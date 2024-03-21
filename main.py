import tkinter
import customtkinter
import threading
import yaml
from pytube import YouTube
from datetime import datetime

def start_download():
    progressBar.set(0)
    pPercentage.configure(text="0%")

    try:
        ytLink = link.get()
        ytObject = YouTube(ytLink, on_progress_callback=on_progress)
        video = ytObject.streams.get_highest_resolution()
        title.configure(text=ytObject.title, text_color="white")
        finishLabel.configure(text="")
        video.download()
        finishLabel.configure(text="Download Complete!", text_color="white")
    except:
        finishLabel.configure(text="Download Error", text_color="red")

class updateTime(threading.Thread):

    def __init__(self):
        super(updateTime, self).__init__()
        self.daemon = True
        self.recognized_text = "initial"

    def run(self):
        global date_label, time_label
        while True:
            (date, time) = get_datetime()
            date_label.configure(text=date)
            time_label.configure(text=time)

def on_progress(stream, chunk, bytes_remaining):
    total_size = stream.filesize
    bytes_downloaded = total_size - bytes_remaining
    percentage_of_compeletion = bytes_downloaded / total_size * 100
    per = str(int(percentage_of_compeletion))
    pPercentage.configure(text=per + '%')
    pPercentage.update()

    # Update progress bar
    progressBar.set(float(percentage_of_compeletion) / 100)

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
app.title("Youtube Downloader")

# Adding UI Elements
title = customtkinter.CTkLabel(app, text="Insert a YouTube Link")
title.pack(padx=10, pady=10)

# Adding Time
date_label = customtkinter.CTkLabel(app, text="Date", font=("Times", 20))
time_label = customtkinter.CTkLabel(app, text="Time", font=("Times", 40))

date_label.pack(padx=10, pady=10)
time_label.pack(padx=10, pady=10)
#date_label.grid(row=0, column=0)
#time_label.grid(row=1, column=0)

# Config Label
configLabel = customtkinter.CTkLabel(app, text=cfg)
configLabel.pack()

# Link input
url_var = tkinter.StringVar()
link = customtkinter.CTkEntry(app, width=350, height=40, textvariable=url_var)
link.pack()

# Finished Downloading
finishLabel = customtkinter.CTkLabel(app, text="")
finishLabel.pack()

# Progress percentage
pPercentage = customtkinter.CTkLabel(app, text="0%")
pPercentage.pack()

progressBar = customtkinter.CTkProgressBar(app, width=400)
progressBar.set(0)
progressBar.pack(padx=10, pady=10)

# Download Button
download = customtkinter.CTkButton(app, text="Download", command=start_download)
download.pack(padx=10, pady=10)

# Run time update
update = updateTime()
update.start()

# Run app
app.mainloop()