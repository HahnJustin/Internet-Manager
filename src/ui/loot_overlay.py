# ui/loot_overlay.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Callable
from PIL import ImageTk

from ui.gui_text import create_outlined_text
from ui.images import get_canvas_photo


@dataclass
class LootOverlay:
    canvas: Optional[object] = None

    loot_item: Optional[int] = None
    loot_img_tk: Optional[ImageTk.PhotoImage] = None

    loot_text: object = None  # outlined text helper
    idle_text: str = ""
    state: str = "hidden"     # "hidden" | "idle" | "opening" | "opened"

    on_click: Optional[Callable[[], None]] = None
    on_hover_enter: Optional[Callable[[], None]] = None
    on_hover_leave: Optional[Callable[[], None]] = None

    def init(self, canvas):
        self.canvas = canvas

        self.loot_item = canvas.create_image(0, 0, anchor="center", state="hidden", tags=("loot",))

        self.loot_text = create_outlined_text(
            canvas, 0, 0,
            text="",
            font=("Arial", 12),
            anchor="s",
            fill="white",
            outline="black",
            thickness=2,
            state="hidden",
            tags=("loot", "loot_text")
        )

        canvas.tag_bind(self.loot_item, "<Button-1>", lambda _e=None: self._click())
        canvas.tag_bind(self.loot_item, "<Enter>", lambda _e=None: self._enter())
        canvas.tag_bind(self.loot_item, "<Leave>", lambda _e=None: self._leave())

    def set_handlers(self, on_click=None, on_hover_enter=None, on_hover_leave=None):
        self.on_click = on_click
        self.on_hover_enter = on_hover_enter
        self.on_hover_leave = on_hover_leave

    def show_box(self, asset_rel_path: str, idle_text: str):
        self.idle_text = idle_text
        self.state = "idle"
        self.show_image(asset_rel_path)
        self.set_text(self.idle_text)

    def show_image(self, asset_rel_path: str):
        if not self.canvas or self.loot_item is None:
            return
        self.loot_img_tk = get_canvas_photo(self.canvas, asset_rel_path)
        self.canvas.itemconfigure(self.loot_item, image=self.loot_img_tk, state="normal")
        if self.loot_text:
            self.loot_text.set_state("normal")

    def set_image(self, asset_rel_path: str):
        # semantic alias; doesn’t change state
        self.show_image(asset_rel_path)

    def set_text(self, text: str):
        if self.loot_text:
            self.loot_text.set_text(text)

    def hide(self):
        self.state = "hidden"
        if not self.canvas:
            return
        if self.loot_item is not None:
            self.canvas.itemconfigure(self.loot_item, state="hidden")
        if self.loot_text:
            self.loot_text.set_state("hidden")
        self.canvas.configure(cursor="")

    def visible(self) -> bool:
        return self.state != "hidden"

    def _click(self):
        if self.state == "idle" and self.on_click:
            self.on_click()

    def _enter(self):
        if not self.canvas:
            return
        if self.state == "idle":
            self.canvas.configure(cursor="hand2")
            if self.on_hover_enter:
                self.on_hover_enter()
            else:
                self.set_text("Click to open!")

    def _leave(self):
        if not self.canvas:
            return
        self.canvas.configure(cursor="")
        if self.on_hover_leave:
            self.on_hover_leave()
        elif self.state == "idle":
            self.set_text(self.idle_text)

    def layout(self, w: int, h: int):
        if self.canvas is None or self.state == "hidden":
            return
        if self.loot_item is None or self.loot_text is None:
            return

        self.canvas.coords(self.loot_item, w / 2, h / 2)

        img_h = 280
        try:
            if self.loot_img_tk is not None:
                img_h = self.loot_img_tk.height()
        except Exception:
            pass

        text_y = (h / 2) - (img_h / 2) - 10
        self.loot_text.coords(w / 2, text_y)

