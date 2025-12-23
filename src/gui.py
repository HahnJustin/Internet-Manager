import tkinter
import customtkinter
import yaml
import math
import ctypes
import random
import sys
from client.app_context import AppContext
from libuniversal import *
from assets import *
from ui.images import *
from ui import gui_text, help_dialogue, manual_override_dialogue
from customtkinter import CTkButton
from client import client_api
from datetime import datetime, timedelta
from PIL import Image
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
from controllers.loot_controller import LootController
from client.api_service import ApiService
from ui.action_list_view import ActionListView
from configreader import str_to_datetime, datetime_to_str

SOFTWARE_VERSION_V_LESS = '1.2.1'
SOFTWARE_VERSION = "v" + SOFTWARE_VERSION_V_LESS

COLOR_AMOUNT = 100
SHUTDOWN_COLORS = [(224, 0, 0), (69, 75, 92),(0, 0, 255),(0, 0, 0)]
ENFORCED_COLORS = [(48, 0, 9), (69, 75, 92),(0, 0, 255),(0, 0, 0)]
UP_COLORS = [(0, 144, 227), (69, 75, 92),(0, 0, 255),(0, 0, 0)]

LOOT_FONT = ("Arial", 10)

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

stop_gifs = False

status_timer = None
lootbox_timer = None

_icon_img_ref = None

loot_ctrl = None

global json_data
global date_label
global time_label

RELAPSE_FMT = "%m/%d/%y %H:%M:%S"

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
    delta = state.now - state.last_relapse
    if delta.total_seconds() / 86400 <= 1:
        streak_icon.pack_forget()
        streak_label.pack(side='top', anchor='center', expand=False)
    else:
        streak_icon.pack(side='left', anchor='e', expand=True)
        streak_label.pack(side='right', anchor='w', expand=True)

    streak_icon.configure(image=get_streak_icon(state.streak))
    streak_label.configure(text=f"Streak: {state.streak}")

def update_voucher_label():
    voucher_label.configure(text=f"x{state.vouchers.local}")

    if state.vouchers.local + state.vouchers.used_count >= state.vouchers.limit:
        voucher_label.configure(text_color=FULL_COLOR)
    else:
        voucher_label.configure(text_color="#ffffff")

def set_icon(internet_on : bool):
    global _icon_img_ref
    if internet_on:
        app.iconbitmap(resource_path(Paths.ASSETS_FOLDER + "/globe.ico"))
        _icon_img_ref = tkinter.PhotoImage(file=resource_path(Paths.ASSETS_FOLDER + "/globex5.png"))
    else:
        app.iconbitmap(resource_path(Paths.ASSETS_FOLDER + "/globe_no.ico"))
        _icon_img_ref = tkinter.PhotoImage(file=resource_path(Paths.ASSETS_FOLDER + "/no_globex5.png"))
    #custom_img = customtkinter.Ctkim
    app.wm_iconphoto(True, _icon_img_ref)

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
    top.destroy()
    state.streak = 0
    show_status("User succumbed to temptation", True)
    client_api.do_request_async(Actions.RELAPSE, "")

    state.used_manual_override = True
    json_data[StorageKey.SINCE_LAST_RELAPSE] = datetime.strftime(datetime.now(), "%m/%d/%y %H:%M:%S")
    state.last_relapse = get_last_relapse(json_data, state.cutoff_time)
    state.streak = compute_streak(datetime.now(), state.last_relapse)
    update_streak_graphics()
    bottom.toggle_relapse_button(False)
    toggle_globe_animation(True)
    set_icon(True)
    bottom.toggle_manual_icon(state.used_manual_override)
    state.internet_on = True

def get_streak() -> int:
    return state.streak

def get_last_relapse(storage: dict, cutoff_time: datetime) -> datetime:
    raw = storage[StorageKey.SINCE_LAST_RELAPSE]  # or .value depending on your enum
    dt = datetime.strptime(raw, "%m/%d/%y %H:%M:%S")
    return dt.replace(hour=cutoff_time.hour, minute=cutoff_time.minute, second=0, microsecond=0)

def toggle_globe_animation(enabled : bool):
    global globe_frames
    global stop_gifs

    if enabled == state.globe_on or not state.admin_on:
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
    state.globe_on = enabled

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
        if loot_ctrl:
            app.after(100, loot_ctrl.check_new_loot)

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

def was_relapse_since_last_cutoff(now: datetime, cutoff_time: datetime, storage: dict) -> bool:
    raw = storage.get(StorageKey.SINCE_LAST_RELAPSE)
    if not raw:
        return False

    relapse_dt = datetime.strptime(raw, RELAPSE_FMT)

    # compute most recent cutoff boundary
    last_cutoff = cutoff_time if cutoff_time <= now else (cutoff_time - timedelta(days=1))

    return relapse_dt >= last_cutoff

def debug_force_offline_ui():
    """
    DEBUG: Make the UI *look* like we're offline, without touching the server.
    Safe to call after widgets exist (status/bottom/globes).
    """

    # Icon + status banner
    set_icon(False)
    show_status("Internet is Off (DEBUG)", False)

    # Bottom relapse button should be visible when offline
    bottom.toggle_relapse_button(True)

    # Stop globe animation + switch it off visually
    toggle_globe_animation(False)
    state.globe_on = False

    # Make sure labels refresh immediately
    try:
        state.internet_on = False
    except Exception:
        pass

    # Force a redraw tick so action colors/time-until are consistent
    try:
        state.now = datetime.now()
        action_list.refresh(now=state.now, vouchers=state.vouchers)
        update_help_colors_from_action(action_list.first_button_action())
        _refresh_time_until_label()
    except Exception:
        pass

def debug_render_all_overlays():
    """
    DEBUG: Force-show all canvas overlays (bottom icons, relapse, status ribbon, loot box)
    so you can visually confirm they render/position correctly.
    UI-only: does NOT call server.
    """

    # ---- Bottom overlay icons (force visible) ----
    try:
        bottom.toggle_manual_icon(True)
        bottom.toggle_vouched_icon(True)
        bottom.toggle_relapse_button(True)
    except Exception:
        pass

    # ---- Status ribbon (ensure something visible) ----
    try:
        show_status("DEBUG: overlay render check", False)
    except Exception:
        pass

    # ---- Re-layout everything now that we've forced elements visible ----
    try:
        scene.layout()
    except Exception:
        pass

# no clue why this works, but it allows the taskbar icon to be custom
myappid = 'dalichrome.internetmanager.' + SOFTWARE_VERSION_V_LESS # arbitrary string
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

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
    host = cfg.get(ConfigKey.HOST.value, cfg.get(ConfigKey.HOST, "127.0.0.1"))
    port = int(cfg.get(ConfigKey.PORT.value, cfg.get(ConfigKey.PORT, 65432)))

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

# Set military time or not
if ConfigKey.MILITARY_TIME in cfg and not cfg[ConfigKey.MILITARY_TIME]:
    print("Not using military time")
    time_format = NORMAL_TIME

used_voucher_today = False
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

last_relapse = get_last_relapse(json_data, cutoff_time)
streak = compute_streak(now, last_relapse)

# Prefer deriving it from relapse time (survives server reboot), OR fall back to stored flag if you keep it
stored_flag = bool(json_data.get(StorageKey.MANUAL_USED, False))
cutoff_time = compute_cutoff(now, cfg[ConfigKey.STREAK_SHIFT])

used_manual_override = stored_flag or was_relapse_since_last_cutoff(now, cutoff_time, json_data)

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
state.admin_on =  bool(client_api.do_request(Actions.ADMIN_STATUS, ""))

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

background.init(center_canvas)
watermark.init(center_canvas)

# Bind LAST so nobody overwrites it
center_canvas.bind("<Configure>", scene.layout)

if not state.admin_on:
    show_status("Server is not running as Admin", False)

# Also force one recenter after layout settles (belt + suspenders)
app.after(50, scene.layout)

bottom.toggle_manual_icon(state.used_manual_override)
bottom.toggle_vouched_icon(used_voucher_today)

# Initial Status (supports DEBUG: start offline UI)
debug_start_offline = bool(cfg.get("debug_start_offline", False))

if debug_start_offline:
    debug_force_offline_ui()
    state.internet_on = False
    # Delay slightly so canvas has a size and layout math is stable
    app.after(100, debug_render_all_overlays)
else:
    if client_api.do_request(Actions.INTERNET_STATUS, ""):
        state.internet_on = True
        status.show("Internet is On", True)
        set_icon(True)
        bottom.toggle_relapse_button(False)
    else:
        state.internet_on = False
        status.show("Internet is Off", False)
        set_icon(False)
        bottom.toggle_relapse_button(True)

# Globes or admin cautions
if state.admin_on:
    # left globe
    globe_frames = get_frames(Paths.ASSETS_FOLDER + "/globular.gif")
    left_globe_gif = customtkinter.CTkLabel(top_left_frame, text="", image=globe_frames[1])
    left_globe_gif.pack(side='right', anchor='e', expand=True)

    # right globe
    right_globe_gif = customtkinter.CTkLabel(top_right_frame, text="", image=globe_frames[1])
    right_globe_gif.pack(side='left', anchor='w', expand=True)

    if state.internet_on:
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

streak_icon = customtkinter.CTkLabel(bottom_frame, text="")
streak_icon.pack(side='left', anchor='e', expand=True)
streak_label = customtkinter.CTkLabel(bottom_frame, text=f"Streak: {state.streak}", text_color="white" )
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
                                        corner_radius=0)
loot_button.pack(side='right', anchor='e', expand=True)

loot_ctrl = LootController(
    app=app,
    state=state,
    loot_overlay=loot,
    status_overlay=status,
    scene=scene,
    loot_button=loot_button,
    loot_limit=loot_limit,
    local_loot_boxes=local_loot_boxes,
    on_vouchers_changed=update_voucher_label,
)
loot_button.configure(command=loot_ctrl.pull_box_from_storage)


loot_ctrl.check_new_loot()
loot_ctrl.refresh_loot_count_async()

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