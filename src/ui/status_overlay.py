from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from PIL import ImageTk

from assets import Paths
from ui.images import get_canvas_photo

@dataclass
class StatusOverlay:
    canvas: Optional[object] = None
    item: Optional[int] = None
    text_item: Optional[int] = None
    img_tk: Optional[ImageTk.PhotoImage] = None

    visible: bool = False
    current_text: str = ""
    positive: bool = True

    def init(self, canvas):
        self.canvas = canvas
        self.item = canvas.create_image(0, 0, anchor="n", state="hidden", tags=("status",))
        self.text_item = canvas.create_text(
            0, 0,
            text="",
            fill="white",
            font=("DreiFraktur", 12),
            anchor="n",
            state="hidden",
            tags=("status",)
        )

    def show(self, text: str, positive: bool):
        if self.canvas is None or self.item is None or self.text_item is None:
            return

        self.visible = True
        self.current_text = text
        self.positive = positive

        ribbon_path = Paths.ASSETS_FOLDER + ("/blue_ribbon.png" if positive else "/red_ribbon.png")
        self.img_tk = get_canvas_photo(self.canvas, ribbon_path)

        self.canvas.itemconfigure(self.item, image=self.img_tk, state="normal")
        self.canvas.itemconfigure(self.text_item, text=text, state="normal")

    def hide(self):
        self.visible = False
        if self.canvas is None or self.item is None or self.text_item is None:
            return
        self.canvas.itemconfigure(self.item, state="hidden")
        self.canvas.itemconfigure(self.text_item, state="hidden")

    def layout(self, w: int, h: int):
        if not self.visible:
            return
        if self.canvas is None or self.item is None or self.text_item is None:
            return

        top_pad = -4
        self.canvas.coords(self.item, w / 2, top_pad)

        rh = 40
        try:
            if self.img_tk is not None:
                rh = self.img_tk.height() / 1.5
        except Exception:
            pass

        self.canvas.coords(self.text_item, w / 2, top_pad + rh * 0.42)
