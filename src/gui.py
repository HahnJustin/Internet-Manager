import tkinter
import customtkinter
import threading
import yaml
import json
import socket
import sys
import selectors
import traceback
import os.path
import time
import math
import ctypes
import webbrowser
import random
from client.app_context import AppContext
from libuniversal import *
from assets import *
from ui.images import *
from ui import gui_text, help_dialogue, manual_override_dialogue
from customtkinter import CTkButton, CTkFont
from colour import Color
from client import message, client_api
from datetime import datetime, timedelta
from PIL import Image, ImageTk, ImageDraw
from ui.canvas_scene import CanvasScene
from ui.background_overlay import BackgroundOverlay
from ui.watermark_overlay import WatermarkOverlay
from ui.loot_overlay import LootOverlay
from ui.status_overlay import StatusOverlay
from ui.bottom_overlay import BottomOverlay
from domain.models import TimeAction, TimeActionKind
from domain.state import AppState, VoucherState, LootUIState
from domain.rules import compute_cutoff, compute_streak, clamp  # or keep your clamp if you prefer
from controllers.time_controller import TimeController
from controllers.ui_scheduler import Repeater
from client.api_service import ApiService
from ui.action_list_view import ActionListView
from configreader import str_to_datetime, datetime_to_str

SOFTWARE_VERSION_V_LESS = '1.2.1'
SOFTWARE_VERSION = "v" + SOFTWARE_VERSION_V_LESS

COLOR_AMOUNT = 100
SHUTDOWN_COLORS = [(224, 0, 0), (69, 75, 92),(0, 0, 255),(0, 0, 0)]
ENFORCED_COLORS = [(48, 0, 9), (69, 75, 92),(0, 0, 255),(0, 0, 0)]
UP_COLORS = [(0, 144, 227), (69, 75, 92),(0, 0, 255),(0, 0, 0)]

MILITARY_TIME = "%H:%M:%S"
NORMAL_TIME = "%#I:%M:%S %p"

time_format = MILITARY_TIME

VOUCHED_COLOR = '#1f61a3'
FULL_COLOR = '#2d74bc'

SECONDARY_COLOR = '#2d3542'

watermark_parent = None
watermark_label = None
watermark_base_img = None
watermark_img_ref = None
watermark_after_id = None

background_parent = None
background_tile_base_img = None   # PIL RGBA tile
background_item = None            # canvas item id
background_img_tk = None          # ImageTk.PhotoImage (keep ref!)
background_last_size = (0, 0)

LOOT_FONT = ("Arial", 10)     # or ("Cloister Black", 18)

loot_img_tk = None
loot_item = None
loot_text_item = None
loot_text = None
loot_idle_text = ""

# -------- Canvas loot UI state --------
loot_state = "hidden"          # "hidden" | "idle" | "opening" | "opened"
loot_click_enabled = False

# -------- Canvas overlay: status ribbon --------
status_item = None
status_text_item = None
status_img_tk = None
status_after_id = None

# -------- Canvas overlay: bottom (manual/vouched + relapse) --------
manual_icon_item = None
vouched_icon_item = None
relapse_bg_item = None
relapse_text_item = None

manual_icon_tk = None
vouched_icon_tk = None
relapse_bg_tk = None

internet_on = True
loot_box_openable = True
globe_on = True
box_origin = None        # None | "storage" | "found"
box_consumed = False     # set True when user opens it
hide_after_id = None     # app.after id so we can cancel

admin_on = True
stop_gifs = False

used_voucher_today = False
used_manual_override = False
local_vouchers = 0
local_vouchers_used = 0
status_timer = None
lootbox_timer = None
current_lootbox = None
internet_box_button = None

global now
global colors
global time_action_buttons
global json_data
global date_label
global time_label
global sel

def build_time_actions(cfg, now: datetime) -> list[TimeAction]:
    tomorrow = now + timedelta(days=1)

    def parse_target(hhmmss: str) -> datetime:
        t = datetime.strptime(hhmmss, "%H:%M:%S").replace(year=now.year, month=now.month, day=now.day)
        if now > t:
            t = t.replace(year=tomorrow.year, month=tomorrow.month, day=tomorrow.day)
        return t

    actions: list[TimeAction] = []

    for t in cfg[ConfigKey.SHUTDOWN_TIMES]:
        actions.append(TimeAction(when=parse_target(t), kind=TimeActionKind.SHUTDOWN))

    for t in cfg[ConfigKey.ENFORCED_SHUTDOWN_TIMES]:
        actions.append(TimeAction(when=parse_target(t), kind=TimeActionKind.ENFORCED_SHUTDOWN))

    for t in cfg[ConfigKey.UP_TIMES]:
        actions.append(TimeAction(when=parse_target(t), kind=TimeActionKind.INTERNET_UP))

    return sorted(actions, key=lambda a: a.when)

def apply_vouched_from_storage(actions: list[TimeAction], json_data) -> None:
    used = set(json_data.get(StorageKey.VOUCHERS_USED, []))
    for a in actions:
        if a.kind == TimeActionKind.SHUTDOWN and datetime_to_str(a.when) in used:
            a.vouched = True
            
def every(delay, task):
    next_time = time.time() + delay
    while True:
        time.sleep(max(0, next_time - time.time()))
        try:
            task()
        except Exception:
            traceback.print_exc()
        next_time += (time.time() - next_time) // delay * delay + delay

def update_help_colors_from_action(action: TimeAction | None):
    if action is None:
        return
    fg, hv = action_list.get_colors(action, now=state.now)
    help_frame.configure(fg_color=fg)
    help_icon.configure(fg_color=fg, hover_color=hv)

def update_gui():
    time_controller.tick()  # updates state.now, handles rollover, triggers events

    _date, _time = get_datetime()
    date_label.configure(text=_date)
    time_label.configure(text=_time)

    # update "time until next"
    # easiest: compute from controller actions after tick
    now = state.now
    next_action = next((a for a in time_controller.actions if a.when > now and not getattr(a, "vouched", False)), None)
    if next_action is None:
        time_until_label.configure(text="--:--")
    else:
        delta = next_action.when - now
        time_until_label.configure(text=":".join(str(delta).split(":")[:2]))

    action_list.refresh(now=state.now, vouchers=state.vouchers)
    update_help_colors_from_action(action_list.first_button_action())

def recalculate_cutoff_time():
    global cutoff_time
    global now

    cutoff_time = datetime.strptime(cfg[ConfigKey.STREAK_SHIFT], '%H:%M')
    cutoff_time = cutoff_time.replace(year=now.year, month=now.month, day=now.day)

    if now > cutoff_time:
        cutoff_time = cutoff_time.replace(year=tomorrow.year, month=tomorrow.month, day=tomorrow.day)

def recalculate_streak():
    global streak
    global now
    global last_relapse

    streak = clamp(math.floor((now - last_relapse).total_seconds() / 86400), 0, 999999)
    update_streak_graphics()

def get_datetime():
    now = datetime.now()
    date = now.strftime("%#m.%#d.%Y")
    time = now.strftime(time_format)
    return date, time

def show_status(text: str, positive: bool):
    global status_after_id

    status.show(text, positive)
    scene.layout()

    if status_after_id is not None:
        app.after_cancel(status_after_id)

    def _hide():
        status.hide()
        scene.layout()

    status_after_id = app.after(60_000, _hide)

def run_function_in_minute(func) -> threading.Timer:
    thread = threading.Timer(60.0, func)
    thread.daemon = True
    thread.start()
    return thread

def run_function_in_five_secs(func) -> threading.Timer:
    thread = threading.Timer(5.0, func)
    thread.daemon = True
    thread.start()
    return thread

def write_data_to_json():
    with open(Paths.JSON_FILE, 'w') as f:
        json.dump(json_data, f)

def string_now():
    return  datetime.strftime(datetime.now(), '%m/%d/%y %H:%M:%S')

def lerp_color(c1,c2,t):
    return (c1[0]+(c2[0]-c1[0])*t, c1[1]+(c2[1]-c1[1])*t, c1[2]+(c2[2]-c1[2])*t)

def create_gradient(colors):
    gradient = []
    for i in range(len(colors) - 1):
        for j in range(COLOR_AMOUNT):
            gradient.append(lerp_color(colors[i], colors[i+1], j / COLOR_AMOUNT))
    return gradient

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
    voucher_label.configure(text=f"x{state.vouchers.local}")

    if state.vouchers.local + state.vouchers.used_count >= state.vouchers.limit:
        voucher_label.configure(text_color=FULL_COLOR)
    else:
        voucher_label.configure(text_color="#ffffff")

def update_loot_button():
    global loot_button
    global loot_box_openable
    loot_button.configure(text=f"x{local_loot_boxes}")

    limit_offset = 0
    if not loot_box_openable: limit_offset += 1

    if local_loot_boxes >= loot_limit - limit_offset:
        loot_button.configure(text_color=FULL_COLOR)
    else:
        loot_button.configure(text_color="#ffffff")

def refresh_loot_count_async():
    def on_count(result):
        if isinstance(result, Exception):
            return

        server_count = int(result or 0)

        # If user pulled a box from storage, server still counts it as stored
        # until it is opened/consumed. Don't let refresh snap UI back.
        if (
            box_origin == "storage"
            and not box_consumed
            and not loot_box_openable          # a box is currently "out"
            and loot.visible()
        ):
            return

        global local_loot_boxes
        local_loot_boxes = clamp(server_count, 0, loot_limit)
        update_loot_button()

    client_api.do_request_async(Actions.LOOT_CHECK, MessageKey.ALL_LOOT_BOXES, on_count)

def set_icon(internet_on : bool):
    if internet_on:
        app.iconbitmap(resource_path(Paths.ASSETS_FOLDER + "/globe.ico"))
        img = tkinter.PhotoImage(file=resource_path(Paths.ASSETS_FOLDER + "/globex5.png"))
    else:
        app.iconbitmap(resource_path(Paths.ASSETS_FOLDER + "/globe_no.ico"))
        img = tkinter.PhotoImage(file=resource_path(Paths.ASSETS_FOLDER + "/no_globex5.png"))
    #custom_img = customtkinter.Ctkim
    app.wm_iconphoto(True, img)

def get_frames(img):
    img = resource_path(img)
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

def relapse(top : customtkinter.CTkToplevel):
    global streak
    global last_relapse
    global json_data
    global internet_on
    global used_manual_override

    top.destroy()
    streak = 0
    show_status("User succumbed to temptation", True)
    client_api.do_request_async(Actions.RELAPSE, "")

    used_manual_override = True
    json_data[StorageKey.SINCE_LAST_RELAPSE] = datetime.strftime(datetime.now(), '%m/%d/%y %H:%M:%S')
    last_relapse = get_last_relapse()
    update_streak_graphics()
    bottom.toggle_relapse_button(False)
    toggle_globe_animation(True)
    set_icon(True)
    bottom.toggle_manual_icon(used_manual_override)
    internet_on = True

def get_streak() -> int:
    return streak

def get_version() -> str:
    return SOFTWARE_VERSION

def get_last_relapse() -> datetime:
    global json_data
    global cfg
    global cutoff_time

    last_relapse = datetime.strptime(json_data[StorageKey.SINCE_LAST_RELAPSE], '%m/%d/%y %H:%M:%S')
    return last_relapse.replace(hour=cutoff_time.hour, minute=cutoff_time.minute)

def loot_box():
    global box_consumed, box_origin

    # Only respond when overlay says it’s clickable
    if loot.state != "idle":
        return

    box_consumed = True
    loot.state = "opening"

    open_path = Paths.ASSETS_FOLDER + (
        "/internet_box_open.png"
        if current_lootbox == MessageKey.NORMAL_LOOT_BOX
        else "/shutdown_internet_box_open.png"
    )

    loot.set_image(open_path)
    loot.set_text("You opened the box...")

    delay_ms = random.randint(2, 10) * 1000
    if box_origin == "debug":
        app.after(delay_ms, debug_get_loot_result)
    else:
        app.after(delay_ms, get_loot)

def _try_add_vouchers(amount: int) -> bool:
    """Returns True if vouchers were added locally."""
    if amount <= 0:
        return False

    # Your UI logic treats limit as (local + used_count) <= limit
    max_local = max(0, state.vouchers.limit - state.vouchers.used_count)
    if state.vouchers.local >= max_local:
        return False

    new_local = min(max_local, state.vouchers.local + amount)
    if new_local == state.vouchers.local:
        return False

    state.vouchers.local = new_local
    update_voucher_label()
    return True

def get_loot():
    def on_opened(result):
        global hide_after_id

        if isinstance(result, Exception):
            loot.set_text("Server error opening box :(")
            if hide_after_id is not None:
                app.after_cancel(hide_after_id)
            hide_after_id = app.after(60_000, hide_loot_box)
            return

        voucher_amount = int(result or 0)
        loot.state = "opened"

        if voucher_amount <= 0:
            loot.set_text("There was nothing inside :(")
        else:
            added = _try_add_vouchers(voucher_amount)
            loot.set_image(Paths.ASSETS_FOLDER + "/voucher.png")
            if added:
                loot.set_text("You found a voucher!!!")
            else:
                loot.set_text("You found a voucher, but don't have room...")

        if hide_after_id is not None:
            app.after_cancel(hide_after_id)
        hide_after_id = app.after(60_000, hide_loot_box)

        refresh_loot_count_async()

    client_api.do_request_async(Actions.LOOT_OPEN, current_lootbox, on_opened)

def hide_loot_box():
    global loot_box_openable, box_origin, box_consumed, hide_after_id

    if hide_after_id is not None:
        app.after_cancel(hide_after_id)
        hide_after_id = None

    loot_box_openable = True
    box_origin = None
    box_consumed = False

    loot.hide()

    refresh_loot_count_async()

def show_loot_box(origin: str, found_count: int = 0):
    global loot_box_openable, box_origin, box_consumed, hide_after_id
    global current_lootbox

    if not loot_box_openable:
        return

    box_origin = origin
    box_consumed = False
    loot_box_openable = False

    idle_text = "You pulled a box out of storage"
    if found_count > 1:
        idle_text = f"You found {found_count} internet boxes!"
    elif found_count == 1:
        idle_text = "You found an internet box!"

    def on_type(result):
        global current_lootbox, hide_after_id

        if isinstance(result, Exception):
            status.show("Server error getting loot box", False)
            hide_loot_box()
            return

        current_lootbox = result

        if current_lootbox == MessageKey.NO_LOOT_BOX:
            hide_loot_box()
            return

        img_path = Paths.ASSETS_FOLDER + (
            "/internet_box.png"
            if current_lootbox == MessageKey.NORMAL_LOOT_BOX
            else "/shutdown_internet_box.png"
        )

        loot.show_box(img_path, idle_text=idle_text)
        loot.set_handlers(on_click=loot_box)

        scene.layout()

        if hide_after_id is not None:
            app.after_cancel(hide_after_id)
        hide_after_id = app.after(60_000, hide_loot_box)

        refresh_loot_count_async()

    client_api.do_request_async(Actions.GET_LOOT, "", on_type)

def debug_show_loot_box(found_count: int = 1):
    global loot_box_openable, box_origin, box_consumed, hide_after_id
    global current_lootbox

    if not loot_box_openable:
        return

    box_origin = "debug"
    box_consumed = False
    loot_box_openable = False

    current_lootbox = MessageKey.NORMAL_LOOT_BOX

    idle_text = "(DEBUG) Click to open!"
    if found_count > 1:
        idle_text = f"(DEBUG) You found {found_count} internet boxes!\nClick to open!"
    elif found_count == 1:
        idle_text = "(DEBUG) You found an internet box!\nClick to open!"

    loot.show_box(Paths.ASSETS_FOLDER + "/internet_box.png", idle_text=idle_text)
    loot.set_handlers(on_click=loot_box)

    scene.layout()

    if hide_after_id is not None:
        app.after_cancel(hide_after_id)
    hide_after_id = app.after(60_000, hide_loot_box)

def debug_get_loot_result():
    global hide_after_id

    voucher_amount = 1 if random.random() < 0.60 else 0

    loot.state = "opened"

    if voucher_amount <= 0:
        loot.set_text("There was nothing inside :(")
    elif local_vouchers + voucher_amount + local_vouchers_used <= voucher_limit:
        loot.set_text("You found a voucher!!!")
        loot.set_image(Paths.ASSETS_FOLDER + "/voucher.png")
    else:
        loot.set_text("You found a voucher, but don't have room...")
        loot.set_image(Paths.ASSETS_FOLDER + "/voucher.png")

    if hide_after_id is not None:
        app.after_cancel(hide_after_id)
    hide_after_id = app.after(60_000, hide_loot_box)

    scene.layout()

def pull_box_from_storage():
    global local_loot_boxes
    if not loot_box_openable or local_loot_boxes <= 0:
        return

    local_loot_boxes -= 1
    update_loot_button()

    show_loot_box("storage")

def check_new_loot():
    def on_new_amount(result):
        if isinstance(result, Exception):
            return

        new_amount = int(result or 0)
        if new_amount <= 0:
            return

        if loot_box_openable:
            show_loot_box("found", found_count=new_amount)
        elif loot.visible():
            # append "(+N stored)" message while box is already visible
            loot.set_text(f"{loot.idle_text}\n(+{new_amount} stored)")

        refresh_loot_count_async()

    client_api.do_request_async(Actions.NEW_LOOT, "", on_new_amount)

def toggle_globe_animation(enabled : bool):
    global globe_frames
    global stop_gifs
    global internet_on
    global globe_on

    if enabled == globe_on or not admin_on:
        return

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
    globe_on = enabled

def register_font(font_path):
    if sys.platform == "win32":
        FR_PRIVATE = 0x10
        FR_NOT_ENUM = 0x20
        AddFontResourceEx = ctypes.windll.gdi32.AddFontResourceExW
        if AddFontResourceEx(font_path, FR_PRIVATE, 0) == 0:
            print("Failed to add font.")
        else:
            print("Font added successfully.")
        # Notify system about the font change
        #ctypes.windll.user32.SendMessageW(0xFFFF, 0x001D, 0, 0)

def loot_visible() -> bool:
    return loot_item is not None and center_canvas.itemcget(loot_item, "state") != "hidden"

def _ensure_loot_canvas_items():
    global loot_item, loot_text
    if loot_item is not None:
        return

    loot_item = center_canvas.create_image(0, 0, anchor="center", state="hidden", tags=("loot",))

    loot_text = gui_text.create_outlined_text(
        center_canvas, 0, 0,
        text="",
        font=LOOT_FONT,
        anchor="s",
        fill="white",
        outline="black",
        thickness=2,
        state="hidden",
        tags=("loot", "loot_text")
    )

    def on_click(_e=None): loot_box()

    def on_enter(_e=None):
        if loot_state == "idle":
            center_canvas.configure(cursor="hand2")
            loot_text.set_text("Click to open!")

    def on_leave(_e=None):
        center_canvas.configure(cursor="")
        if loot_state == "idle":
            loot_text.set_text(loot_idle_text)

    center_canvas.tag_bind(loot_item, "<Button-1>", on_click)
    center_canvas.tag_bind(loot_item, "<Enter>", on_enter)
    center_canvas.tag_bind(loot_item, "<Leave>", on_leave)

    scene.layout()

def handle_time_event(evt: str, action: TimeAction | None):
    if evt == "day_rollover":
        bottom.toggle_manual_icon(state.used_manual_override)
        bottom.toggle_vouched_icon(state.vouchers.used_today)
        update_streak_graphics()

    elif evt == "voucher_consumed":
        show_status("Voucher Consumed", True)
        bottom.toggle_vouched_icon(True)
        update_voucher_label()

    elif evt == "shutdown_triggered":
        set_icon(False)
        show_status("Internet Shutdown Triggered", False)
        bottom.toggle_relapse_button(True)
        toggle_globe_animation(False)
        run_function_in_five_secs(lambda: check_new_loot())

    elif evt == "internet_up_triggered":
        set_icon(True)
        show_status("Internet Reboot Triggered", True)
        bottom.toggle_relapse_button(False)
        toggle_globe_animation(True)

def _refresh_time_until_label():
    now = state.now
    next_action = next(
        (a for a in time_controller.actions if a.when > now and not getattr(a, "vouched", False)),
        None
    )
    if next_action is None:
        time_until_label.configure(text="--:--")
    else:
        delta = next_action.when - now
        time_until_label.configure(text=":".join(str(delta).split(":")[:2]))

def on_action_clicked(index: int):
    before = state.vouchers.local

    # apply voucher logic immediately
    time_controller.on_action_clicked(index)

    # update voucher label immediately if changed
    if state.vouchers.local != before:
        update_voucher_label()

    # IMPORTANT: immediate UI refresh (no 1-second wait)
    state.now = datetime.now()
    action_list.refresh(now=state.now, vouchers=state.vouchers)
    update_help_colors_from_action(action_list.first_button_action())
    _refresh_time_until_label()

# no clue why this works, but it allows the taskbar icon to be custom
myappid = 'dalichrome.internetmanager.' + SOFTWARE_VERSION_V_LESS # arbitrary string
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

sel = selectors.DefaultSelector()

# Path to the drei font
drei_path = resource_path(Paths.FONTS_FOLDER + '/DreiFraktur.ttf')
register_font(drei_path)

cloyster_path = resource_path(Paths.FONTS_FOLDER + '/CloisterBlack.ttf')
register_font(cloyster_path)

# Reading config
try:
    f = open(Paths.CLIENT_CONFIG_FILE)
except OSError:
    cfg = {ConfigKey.HOST.value: str("127.0.0.1"), ConfigKey.PORT.value : 65432}
    with open(Paths.CLIENT_CONFIG_FILE, 'w') as yaml_file:
        yaml.dump(cfg, yaml_file)
    f = open(Paths.CLIENT_CONFIG_FILE)
with f:
    cfg = yaml.load(f, Loader=yaml.FullLoader)
    host = cfg[ConfigKey.HOST]
    port = cfg[ConfigKey.PORT]

client_api.init(host, port)

cfg = client_api.do_request(Actions.GRAB_CONFIG, "")

json_data = client_api.do_request(Actions.GRAB_STORAGE, "")

if cfg is None or json_data is None:
     raise Exception("Internet Manager cannot find a running server")

# Defining local vouchers amount
local_vouchers = json_data[StorageKey.VOUCHER]
voucher_limit = json_data[StorageKey.VOUCHER_LIMIT]

# Defining local loot boxes
local_loot_boxes = 0
if StorageKey.LOOT_BOXES in json_data:
    local_loot_boxes += json_data[StorageKey.LOOT_BOXES]
if StorageKey.SHUTDOWN_LOOT_BOXES in json_data:
    local_loot_boxes += json_data[StorageKey.SHUTDOWN_LOOT_BOXES]

loot_limit = 5
if StorageKey.LOOT_BOX_LIMIT in json_data:
    loot_limit = json_data[StorageKey.LOOT_BOX_LIMIT]

# Defining basic time variables
now = datetime.now()
tomorrow = now + timedelta(days=1)
recalculate_cutoff_time()

# Defining last time since internet override, used in streak calc
last_relapse = get_last_relapse()

# Set military time or not
if ConfigKey.MILITARY_TIME in cfg and not cfg[ConfigKey.MILITARY_TIME]:
    print("Not using military time")
    time_format = NORMAL_TIME

if StorageKey.VOUCHERS_USED in json_data:
    for _time in json_data[StorageKey.VOUCHERS_USED]:
        used_time = datetime.strptime(_time, '%m/%d/%y %H:%M:%S')
        if now > used_time:
            used_voucher_today = True
            print('Used voucher since last cutoff detected')
            break

local_vouchers_used = 0
used_list = json_data.get(StorageKey.VOUCHERS_USED, [])
if isinstance(used_list, list):
    local_vouchers_used = len(used_list)

# Find if manual override
used_manual_override = json_data[StorageKey.MANUAL_USED]

# System Settings
customtkinter.set_appearance_mode("System")
customtkinter.set_default_color_theme("blue")

# Our app frame
app = customtkinter.CTk(fg_color='#25292e')
app.geometry("720x480")
app.minsize(600, 375)
app.title("Internet Manager")
app_bg_color = app.cget('bg')
widget_bg_color = '#404654'

ctx = AppContext(app=app) 
client_api.set_app(ctx)

api = ApiService(ctx)  # wrapper around client_api

now = datetime.now()
cutoff_time = compute_cutoff(now, cfg[ConfigKey.STREAK_SHIFT])

last_relapse = get_last_relapse()  # you can keep your existing helper for now
streak = compute_streak(now, last_relapse)

state = AppState(
    now=now,
    cutoff_time=cutoff_time,
    internet_on=True,
    admin_on=True,
    globe_on=True,
    streak=streak,
    last_relapse=last_relapse,
    vouchers=VoucherState(
        local=local_vouchers,
        used_today=used_voucher_today,
        used_count=local_vouchers_used,
        limit=voucher_limit
    ),
    loot=LootUIState(),
    used_manual_override=used_manual_override
)

# Shutdown label parent
widget_frame = customtkinter.CTkFrame(app, fg_color=widget_bg_color, corner_radius=0)
widget_frame.pack(side='left', fill="y")

# Help label
help_frame = customtkinter.CTkFrame(widget_frame, fg_color=widget_bg_color, corner_radius=0)
help_frame.pack(side='top', fill="x")

# Top label parent
top_frame = customtkinter.CTkFrame(app, fg_color=SECONDARY_COLOR, corner_radius=0)
top_frame.pack(side='top', fill="x")
top_frame_fg_color = top_frame.cget('fg_color')

# Top left
top_left_frame = customtkinter.CTkFrame(top_frame, fg_color=SECONDARY_COLOR, corner_radius=0)
top_left_frame.pack(side='left', fill='both', expand= True)

# Top right 
top_right_frame = customtkinter.CTkFrame(top_frame, fg_color=SECONDARY_COLOR, corner_radius=0)
top_right_frame.pack(side='right', fill='both', expand= True)

# Bottom Frame
bottom_frame = customtkinter.CTkFrame(app, corner_radius=0, fg_color=SECONDARY_COLOR)
bottom_frame.pack(side='bottom', fill="x")

# Bottom right 
bottom_right_frame = customtkinter.CTkFrame(bottom_frame, corner_radius=0, fg_color=SECONDARY_COLOR)
bottom_right_frame.pack(side='right')

# Bottom left 
bottom_left_frame = customtkinter.CTkFrame(bottom_frame, corner_radius=0, fg_color=SECONDARY_COLOR)
bottom_left_frame.pack(side='left')

# Making shutdown label color gradient
shutdown_colors = create_gradient(SHUTDOWN_COLORS)
enforced_colors = create_gradient(ENFORCED_COLORS)
up_colors = create_gradient(UP_COLORS)

time_action_buttons = []

# Build domain actions
now = datetime.now()
actions = build_time_actions(cfg, now)
apply_vouched_from_storage(actions, json_data)

time_controller = TimeController(
    state=state,
    api=api,
    shift_hhmm=cfg[ConfigKey.STREAK_SHIFT],
    on_event=handle_time_event,   # define below
)
time_controller.set_actions(actions)

action_list = ActionListView(
    parent=widget_frame,
    actions=actions,
    time_format=lambda: time_format,
    voucher_color=VOUCHED_COLOR,
    shutdown_colors=shutdown_colors,
    enforced_colors=enforced_colors,
    up_colors=up_colors,
    on_click=on_action_clicked,
)

action_list.pack(side="top", fill="both", expand=True)  # <-- REQUIRED

# Adding Time
date_label = customtkinter.CTkLabel(top_frame, text_color="#666e7a", text="Date", font=("Cloister Black", 25), pady=0)
time_label = customtkinter.CTkLabel(top_frame, text=string_now(), font=("Cloister Black", 45), padx=10, text_color="white")

date_label.pack(side='top')
time_label.pack(side='top')

time_until_label = customtkinter.CTkLabel(top_frame, text='', font=("Cloister Black", 25))
time_until_label.pack()

status_label = customtkinter.CTkLabel(app, text=f"", text_color="white", font=("DreiFraktur", 15), compound='center', anchor='n')
status_label.pack_forget()

# Admin Check
admin_on = client_api.do_request(Actions.ADMIN_STATUS, "")

if admin_on:
    # left globe
    globe_frames = get_frames(Paths.ASSETS_FOLDER + "/globular.gif")
    left_globe_gif = customtkinter.CTkLabel(top_left_frame, text="", image=globe_frames[1])
    left_globe_gif.pack(side='right', anchor='e', expand=True)

    # right globe
    right_globe_gif = customtkinter.CTkLabel(top_right_frame, text="", image=globe_frames[1])
    right_globe_gif.pack(side='left', anchor='w', expand=True)

    if internet_on:
        app.after(100, _play_gif, left_globe_gif, globe_frames)
        app.after(100, _play_gif, right_globe_gif, globe_frames)
    else:
        toggle_globe_animation(False)

else:
    # left caution
    caution_right = customtkinter.CTkLabel(top_left_frame, text="", image=get_image(Paths.ASSETS_FOLDER + "/caution.png"))
    caution_right.pack(side='right', anchor='e', expand=True)

    # right caution
    caution_left = customtkinter.CTkLabel(top_right_frame, text="", image=get_image(Paths.ASSETS_FOLDER + "/caution.png"))
    caution_left.pack(side='left', anchor='w', expand=True)

# Debug turn internet on and off buttons
if ConfigKey.DEBUG in cfg and cfg[ConfigKey.DEBUG]:
    debug_frame = customtkinter.CTkFrame(app)
    debug_frame.pack(side='bottom', fill="x")

    turn_off = CTkButton(debug_frame, text = 'Turn off Internet',
                            command = lambda : client_api.do_request_async(Actions.INTERNET_OFF, "")) 
    turn_on = CTkButton(debug_frame, text = 'Turn on Internet',
                            command = lambda : client_api.do_request_async(Actions.INTERNET_ON, ""))  
    turn_off.pack(side = 'left', anchor='e', expand=False)
    turn_on.pack(side='left', anchor='w', expand=False)

    add_voucher = CTkButton(debug_frame, text = 'Add Voucher',
                            command = lambda : client_api.do_request_async(Actions.ADD_VOUCHER, ""))  
    add_voucher.pack(side = 'left', anchor='e', expand=False)

    test_gif = CTkButton(debug_frame, text = 'Gif Toggle Off',
                            command = lambda : toggle_globe_animation(False))  
    test_gif.pack(side='right', anchor='w', expand=False)

    test_gif_on = CTkButton(debug_frame, text = 'Gif Toggle On',
                            command = lambda : toggle_globe_animation(True))  
    test_gif_on.pack(side='right', anchor='w', expand=False)
    
    test_loot_box = CTkButton(debug_frame, text='Test Lootbox',
                            command=lambda: debug_show_loot_box(found_count=1))
    test_loot_box.pack(side='right', anchor='w', expand=False)


# Center (main) area: use Canvas so background + watermark are real pixels
center_canvas = tkinter.Canvas(app, bg=app_bg_color, highlightthickness=0, bd=0)
center_canvas.pack(side="top", fill="both", expand=True)

background = BackgroundOverlay(user_filename="background.png")
watermark = WatermarkOverlay(user_filename="watermark.png")
loot = LootOverlay()
status = StatusOverlay()
bottom = BottomOverlay()

manual_override_dialogue.init(
    ctx=ctx,
    get_streak=get_streak,
    on_relapse=relapse,
)

help_dialogue.init(ctx, SOFTWARE_VERSION)

bottom.set_relapse_callback(manual_override_dialogue.manual_override)

scene = CanvasScene(
    canvas=center_canvas,
    background=background,
    watermark=watermark,
    loot=loot,
    status=status,
    bottom=bottom
)
scene.init()

# Bind FIRST so we never miss the first real resize
center_canvas.bind("<Configure>", scene.layout)

background.init(center_canvas)
watermark.init(center_canvas)

show_status("Server is not running in Admin", not admin_on)

# Also force one recenter after layout settles (belt + suspenders)
app.after(50, scene.layout)

bottom.toggle_manual_icon(used_manual_override)
bottom.toggle_vouched_icon(used_voucher_today)

# Initial Status
if client_api.do_request(Actions.INTERNET_STATUS, ""):
    internet_on = True
    status.show("Internet is On", True)
    set_icon(True)
else:
    internet_on = False
    status.show("Internet is On", False)
    set_icon(False)

bottom.toggle_relapse_button(not internet_on)

streak = clamp(math.floor((now - last_relapse).total_seconds() / 86400),0,999999)

streak_icon = customtkinter.CTkLabel(bottom_frame, text="")
streak_icon.pack(side='left', anchor='e', expand=True)
streak_label = customtkinter.CTkLabel(bottom_frame, text=f"Streak: {streak}", text_color="white" )
streak_label.pack(side='right', anchor='w', expand=True)
update_streak_graphics()

voucher_label = customtkinter.CTkLabel(bottom_right_frame, text=f"x{local_vouchers}", 
                                        image=get_image(Paths.ASSETS_FOLDER + "/tiny_voucher.png"),
                                        compound='left', anchor='e', padx = 5, text_color="white")
voucher_label.pack(side='right', anchor='e', expand=True)
update_voucher_label()

loot_button = customtkinter.CTkButton(bottom_left_frame, text=f"x{local_loot_boxes}", 
                                        image=get_image(Paths.ASSETS_FOLDER + "/tiny_box.png"),
                                        compound='left', anchor='e', width = 5, text_color="white",
                                        fg_color= SECONDARY_COLOR,
                                        hover_color=app_bg_color,
                                        corner_radius=0,
                                        command= lambda : pull_box_from_storage())
loot_button.pack(side='right', anchor='e', expand=True)
update_loot_button()

check_new_loot()
refresh_loot_count_async()

help_icon = CTkButton(help_frame,
                        hover_color=app_bg_color,
                        text="",
                        command= help_dialogue.help_dialogue,
                        fg_color= widget_bg_color,
                        image=get_image(Paths.ASSETS_FOLDER + "/info_icon.png"),
                        anchor='w', 
                        corner_radius=0,
                        width=2,
                        hover= True)
help_icon.pack(anchor='w', expand=True)


# Run time update
ui_tick = Repeater(app)
ui_tick.every(1000, update_gui)         # every second
ui_tick.every(60_000, action_list.recolor)  # if you want a separate recolor pass

# Run app
app.mainloop()

#Close selector
sel.close()