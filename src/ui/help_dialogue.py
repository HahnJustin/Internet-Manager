from typing import Callable, Optional
import webbrowser
from customtkinter import CTkFrame, CTkLabel, CTkToplevel, CTkButton
from assets import Paths, resource_path
from ui.images import get_image
from client.app_context import AppContext

_ctx: Optional[AppContext] = None

_version = ""

def init(
    ctx: AppContext,
    version
) -> None:
    """Call once from gui.py after app/context exist."""
    global _ctx, _version
    _ctx = ctx
    _version = version

def help_dialogue():
    top = CTkToplevel(_ctx.app)
    
    # Center the popup on the main window
    x = _ctx.app.winfo_rootx()
    y = _ctx.app.winfo_rooty()
    height = _ctx.app.winfo_height() - 200
    width = _ctx.app.winfo_width() - 350
    top.geometry("+%d+%d" % (x + width / 2, y - 50 + height / 2))
    top.minsize(500, 700)
    top.maxsize(500, 700)
    top.attributes('-topmost', True)
    top.title("Info")

    # Title Label
    info_title_label = CTkLabel(top, text="Info", font=("DreiFraktur", 32), pady=10)
    info_title_label.pack(side='top')

    # Software Version Label
    info_string = f"Internet Manager {get_version()}"
    software_v_label = CTkLabel(top, text=info_string, font=('arial', 18), pady=2.5)
    software_v_label.pack(side='top', fill='x', padx=20)

    # Description Label
    desc_string = "Made by Dalichrome '25 \n "
    desc_label = CTkLabel(top, text=desc_string, font=('arial', 16), pady=2.5)
    desc_label.pack(side='top', fill='x', padx=20)

    # FAQ Label
    faq_title_label = CTkLabel(top, text="~Faq~", font=("DreiFraktur", 26), pady=10)
    faq_title_label.pack(side='top')

    # FAQ Desc Label
    faq_desc_string = ("How do I re-configure the manager? \n"
                   "    - Reinstall the manager using the installer or modify the config.json file. The installer actually reads your config file if it exists, so you won't need to re-enter any data. \n \n"
                   "How do loot boxes drop? \n"
                   "    - There are two types of loot boxes, one drops at shutdown, one if you turn off your computer before shutdown \n \n"
                   "How do I use vouchers? \n"
                   "    - Right click on the configured times \n \n "
                   "How do I use my stored loot boxes?  \n"
                   "    - Click on the loot box icon \n \n"
                   "My internet isn't shutting off, why? \n"
                   "    - Most likely your networks aren't configured correctly, find your network name and add it to then config when you re-configure it. \n \n"
                   "If I reinstall, will I lose my streak?  \n"
                   "    - No if you reinstall or upgrade, your streak is safe. That data is in the storage.json file, feel free to make an extra copy \n \n"
                   "What if none of these address my question? \n"
                   "    - If that doesn't work, email support@dalichro.me \n \n")
    faq_desc_string = CTkLabel(top, justify='left', wraplength=400, text=faq_desc_string, font=('arial', 10), pady=2.5)
    faq_desc_string.pack(side='top', fill='x', padx=20)

    # Links Section Title
    label = CTkLabel(top, text="Links", font=("DreiFraktur", 22), pady=10)
    label.pack(side='top')

    # Social Media Links Frame
    social_frame = CTkFrame(top)
    social_frame.pack()

    # Dictionary of social media platforms and their URLs
    social_medias = {
        "website": "https://www.dalichro.me",
        "bluesky": "https://bsky.app/profile/dalichrome.bsky.social",
        "itch": "https://dalichrome.itch.io/"
    }

    # Dictionary to hold image references
    social_images = {}

    for platform, url in social_medias.items():
        image_path = resource_path(f"{Paths.ASSETS_FOLDER}/{platform}_link.png")
        try:
            social_image = get_image(image_path)
        except Exception as e:
            print(f"Error loading image for {platform}: {e}")
            continue
        social_images[platform] = social_image  # Keep a reference to prevent garbage collection

        # Create a button for each social media link
        btn = CTkButton(
            social_frame,
            image=social_image,
            text="",
            width=50,
            height=50,
            fg_color="transparent",
            hover_color="#404040",
            cursor="hand2",
            command=lambda url=url: open_url(url)
        )
        btn.pack(side='left', padx=10)

    # Store the image references to prevent garbage collection
    top.social_images = social_images

    # Set the icon twice to ensure it persists
    icon_path = resource_path(f"{Paths.ASSETS_FOLDER}/info_icon.ico")
    try:
        top.wm_iconbitmap(icon_path)
    except Exception as e:
        print(f"Error setting icon: {e}")
    top.update_idletasks()     # Force any pending updates
    top.after(201, lambda: top.iconbitmap(icon_path))

    # Add widgets and focus
    top.focus_set()
    top.grab_set()

    def on_close():
        top.grab_release()
        top.destroy()

    top.protocol("WM_DELETE_WINDOW", on_close)

def open_url(url):
    webbrowser.open_new(url)