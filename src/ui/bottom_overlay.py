from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Callable
from PIL import ImageTk

from assets import Paths
from ui.images import get_canvas_photo, get_round_rect_photo
from tkinter import Canvas

@dataclass
class BottomOverlay:
    canvas: Optional[Canvas] = None

    manual_icon_item: Optional[int] = None
    vouched_icon_item: Optional[int] = None
    retrovouched_icon_item: Optional[int] = None
    relapse_bg_item: Optional[int] = None
    relapse_text_item: Optional[int] = None

    manual_icon_tk: Optional[ImageTk.PhotoImage] = None
    vouched_icon_tk: Optional[ImageTk.PhotoImage] = None
    retrovouched_icon_tk: Optional[ImageTk.PhotoImage] = None
    relapse_bg_tk: Optional[ImageTk.PhotoImage] = None

    manual_visible: bool = False
    vouched_visible: bool = False
    retrovouched_visible: bool = False
    relapse_visible: bool = False

    on_relapse_click: Optional[Callable[[], None]] = None

    def init(self, canvas : Canvas):
        self.canvas = canvas

        self.manual_icon_tk = get_canvas_photo(canvas, Paths.ASSETS_FOLDER + "/embarrased_globe.png")
        self.vouched_icon_tk = get_canvas_photo(canvas, Paths.ASSETS_FOLDER + "/voucher_globe.png")
        self.retrovouched_icon_tk = get_canvas_photo(canvas, Paths.ASSETS_FOLDER + "/retrovoucher_globe.png")

        self.manual_icon_item = canvas.create_image(
            0, 0, anchor="se", image=self.manual_icon_tk, state="hidden", tags=("bottomui",)
        )

        self.vouched_icon_item = canvas.create_image(
            0, 0, anchor="se", image=self.vouched_icon_tk, state="hidden", tags=("bottomui",)
        )
        
        self.retrovouched_icon_item = canvas.create_image(
            0, 0, anchor="se", image=self.retrovouched_icon_tk, state="hidden", tags=("bottomui",)
        )

        self.relapse_bg_tk = get_round_rect_photo(canvas, 240, 34, 10, (181, 27, 32, 210))
        self.relapse_bg_item = canvas.create_image(
            0, 0, anchor="se", image=self.relapse_bg_tk, state="hidden", tags=("relapsebtn", "bottomui")
        )
        self.relapse_text_item = canvas.create_text(
            0, 0, text="Override Turn On Internet", fill="white", font=("Arial", 11),
            anchor="center", state="hidden", tags=("relapsebtn", "bottomui")
        )

        canvas.tag_bind("relapsebtn", "<Button-1>", lambda _e=None: self._handle_relapse_click())
        canvas.tag_bind("relapsebtn", "<Enter>", lambda _e=None: self._handle_relapse_enter())
        canvas.tag_bind("relapsebtn", "<Leave>", lambda _e=None: self._handle_relapse_leave())

    def set_relapse_callback(self, cb: Callable[[], None]):
        self.on_relapse_click = cb

    def _handle_relapse_click(self):
        if self.relapse_visible and self.on_relapse_click:
            self.on_relapse_click()

    def _handle_relapse_enter(self):
        if self.canvas and self.relapse_visible:
            self.canvas.configure(cursor="hand2")

    def _handle_relapse_leave(self):
        if self.canvas:
            self.canvas.configure(cursor="")

    def toggle_manual_icon(self, value: bool):
        self.manual_visible = value
        if self.canvas and self.manual_icon_item is not None:
            self.canvas.itemconfigure(self.manual_icon_item, state=("normal" if value else "hidden"))

    def toggle_vouched_icon(self, value: bool):
        self.vouched_visible = value
        if self.canvas and self.vouched_icon_item is not None:
            self.canvas.itemconfigure(self.vouched_icon_item, state=("normal" if value else "hidden"))

    def toggle_retrovouched_icon(self, value: bool):
        self.retrovouched_visible = value
        if self.canvas and self.retrovouched_icon_item is not None:
            self.canvas.itemconfigure(self.retrovouched_icon_item, state=("normal" if value else "hidden"))

    def toggle_relapse_button(self, value: bool):
        self.relapse_visible = value
        if not self.canvas:
            return
        st = "normal" if value else "hidden"
        if self.relapse_bg_item is not None:
            self.canvas.itemconfigure(self.relapse_bg_item, state=st)
        if self.relapse_text_item is not None:
            self.canvas.itemconfigure(self.relapse_text_item, state=st)

    def layout(self, w: int, h: int):
        if self.canvas is None:
            return

        PAD = 0
        GAP = 8

        x_right = w - 1 - PAD
        y_bottom = h - 1 - PAD

        btn_w, btn_h = 240, 34
        icon_w, icon_h = 40, 40

        try:
            if self.relapse_bg_tk is not None:
                btn_w = self.relapse_bg_tk.width()
                btn_h = self.relapse_bg_tk.height()
        except Exception:
            pass

        try:
            if self.manual_icon_tk is not None:
                icon_w = self.manual_icon_tk.width()
                icon_h = self.manual_icon_tk.height()
        except Exception:
            pass

        # -----------------------------
        # Center the relapse button
        # -----------------------------
        btn_center_x = w / 2.0
        btn_right_x  = btn_center_x + (btn_w / 2.0)   # because bg uses anchor="se"

        if self.relapse_bg_item is not None:
            self.canvas.coords(self.relapse_bg_item, btn_right_x, y_bottom)

        if self.relapse_text_item is not None:
            # Text anchored "center"
            self.canvas.coords(self.relapse_text_item, btn_center_x, y_bottom - (btn_h / 2.0))

        # -----------------------------
        # Align icons vertically with the button
        # (same vertical level as the button center)
        # -----------------------------
        if self.relapse_visible:
            btn_center_y = y_bottom - (btn_h / 2.0)
            icons_bottom_y = btn_center_y + (icon_h / 2.0)  # because icons use anchor="se"
        else:
            # fallback: old behavior if button hidden
            icons_bottom_y = y_bottom

        icons_in_order = [
            (self.manual_icon_item, self.manual_visible),
            (self.vouched_icon_item, self.vouched_visible),
            (self.retrovouched_icon_item, self.retrovouched_visible),
        ]

        x = x_right
        for item, visible in icons_in_order:
            if item is None or not visible:
                continue
            self.canvas.coords(item, x, icons_bottom_y)
            x -= (icon_w + GAP)