from __future__ import annotations
from typing import Callable, Optional

from customtkinter import CTkButton, CTkLabel, CTkToplevel

from assets import Paths, resource_path
from client.app_context import AppContext

_ctx: Optional[AppContext] = None
_get_streak: Optional[Callable[[], int]] = None
_on_relapse: Optional[Callable[[CTkToplevel], None]] = None


def init(
    ctx: AppContext,
    get_streak: Callable[[], int],
    on_relapse: Callable[[CTkToplevel], None],
) -> None:
    """Call once from gui.py after app/context exist."""
    global _ctx, _get_streak, _on_relapse
    _ctx = ctx
    _get_streak = get_streak
    _on_relapse = on_relapse


def manual_override() -> None:
    if _ctx is None or _get_streak is None or _on_relapse is None:
        raise RuntimeError("manual_override_dialogue.init(...) must be called before manual_override().")

    top = CTkToplevel(_ctx.app)

    # icon
    icon_path = resource_path(Paths.ASSETS_FOLDER + "/sad_emoji.ico")
    try:
        top.iconbitmap(icon_path)
    except Exception:
        # Some environments need this pattern
        top.after(200, lambda: top.iconbitmap(icon_path))

    # center-ish over parent
    x = _ctx.app.winfo_rootx()
    y = _ctx.app.winfo_rooty()
    height = _ctx.app.winfo_height()
    width = _ctx.app.winfo_width()
    top.geometry("+%d+%d" % (x - 125 + width / 2, y - 50 + height / 2))

    top.minsize(400, 250)
    top.maxsize(400, 250)
    top.attributes("-topmost", True)
    top.title("Pathetic")

    streak = _get_streak()
    label = CTkLabel(
        top,
        text=f"Are you really sure that you want to end \n"
             f"your streak of {streak} and turn on the internet?",
        font=("Mistral 18 bold", 20),
        pady=10,
    )
    label.pack(side="top")

    btn = CTkButton(
        top,
        text="Forsake your Honor",
        command=lambda: _on_relapse(top),
        hover_color="#691114",
        font=("Mistral 18 bold", 20),
        fg_color="#b51b20",
    )
    btn.place(relx=0.5, rely=0.5, anchor="center")

    top.grab_set()
