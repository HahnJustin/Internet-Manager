# ui/action_list_view.py
from __future__ import annotations

import customtkinter as ctk
from datetime import datetime
from typing import Callable, Optional

from domain.models import TimeAction, TimeActionKind
from domain.rules import clamp
from ui.images import get_time_action_icon


COLOR_AMOUNT = 100

def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def _darken_hex_like_old(hex_color: str) -> str:
    # Matches: Color(rgb=(r/1.4, g/1.4, b/1.2))
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    r = int(clamp(r / 1.4, 0, 255))
    g = int(clamp(g / 1.4, 0, 255))
    b = int(clamp(b / 1.2, 0, 255))
    return f"#{r:02x}{g:02x}{b:02x}"

class ActionListView(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        actions: list[TimeAction],
        time_format: Callable[[], str] | str,
        voucher_color: str,
        shutdown_colors: list[tuple[int, int, int]],
        enforced_colors: list[tuple[int, int, int]],
        up_colors: list[tuple[int, int, int]],
        on_click: Optional[Callable[[TimeAction], None]] = None,
    ):
        super().__init__(parent, corner_radius=0)

        self.actions = actions
        self.time_format = time_format
        self.voucher_color = voucher_color

        self.shutdown_colors = shutdown_colors
        self.enforced_colors = enforced_colors
        self.up_colors = up_colors

        self.on_click = on_click

        self._vouchers = None

        self.buttons: list[ctk.CTkButton] = []
        self._last_now = datetime.now()

        # Make the list background match the "far away" button gray
        far_rgb = (69, 75, 92)
        self.configure(fg_color=_rgb_to_hex(far_rgb))

        # Track hover by *button object* so reorder won't break hover handling.
        self._hovered_btn: Optional[ctk.CTkButton] = None

        self._rebuild_buttons()
        self.refresh(now=self._last_now, vouchers=None)

    # -------- public API (used by gui.py) --------

    def refresh(self, now: datetime, vouchers=None):
        self._last_now = now
        self._vouchers = vouchers  # <-- add this
        self.actions.sort(key=lambda a: a.when)

        if len(self.buttons) != len(self.actions):
            self._rebuild_buttons()

        for i, (btn, action) in enumerate(zip(self.buttons, self.actions)):
            self._render(btn, action, i)

    def recolor(self):
        # leave hover intact; we guard fg_color updates while hovered
        self.refresh(self._last_now, vouchers=self._vouchers)

    def get_colors(self, action: TimeAction, now: datetime):
        fg = self._fg(action, now)
        hv = _darken_hex_like_old(fg)
        return fg, hv

    def first_action(self) -> TimeAction | None:
        if not self.actions:
            return None
        # soonest non-vouched preferred (matches your old "soonest non-vouched")
        for a in self.actions:
            if not getattr(a, "vouched", False):
                return a
        return self.actions[0]

    def first_button_action(self) -> TimeAction | None:
        if not self.actions:
            return None
        return self.actions[0]

    # -------- internal --------

    def _rebuild_buttons(self):
        for b in self.buttons:
            b.destroy()
        self.buttons = []

        # Reset hover tracking when rebuilding
        self._hovered_btn = None

        for i in range(len(self.actions)):
            btn = ctk.CTkButton(
                self,
                text="",
                corner_radius=0,
                height=60,                 # <-- pick your old feel: try 52/56/60
                width=170,
                command=lambda i=i: self._handle_click(i),
            )
            btn.pack(fill="x", padx=0, pady=0)

            # Optional: fixed height helps consistency
            # btn.configure(height=44)

            # Per-button render cache
            btn._last = {}      # type: ignore[attr-defined]
            btn._icon_ref = None  # type: ignore[attr-defined]

            # Hover tracking
            btn.bind("<Enter>", lambda _e, b=btn: self._on_enter(b))
            btn.bind("<Leave>", lambda _e, b=btn: self._on_leave(b))

            self.buttons.append(btn)

    def _on_enter(self, btn: ctk.CTkButton):
        self._hovered_btn = btn

    def _on_leave(self, btn: ctk.CTkButton):
        if self._hovered_btn is btn:
            self._hovered_btn = None

    def _handle_click(self, index: int):
        # Disallow clicks past voucher capacity (sorted index rule)
        if self._vouchers is not None:
            total = int(getattr(self._vouchers, "local", 0)) + int(getattr(self._vouchers, "used_count", 0))
            if index >= total:
                return  # <-- unclickable

        if self.on_click:
            self.on_click(index)

    def _format_time(self, action: TimeAction) -> str:
        fmt = self.time_format() if callable(self.time_format) else str(self.time_format)
        return action.when.strftime(fmt)

    def _format_remaining(self, action: TimeAction, now: datetime) -> str:
        delta = action.when - now
        if delta.total_seconds() <= 0:
            return "00:00"
        return ":".join(str(delta).split(":")[:2])  # HH:MM

    def _fg(self, action: TimeAction, now: datetime) -> str:
        # Old behavior: vouched shutdown turns voucher color
        if action.kind == TimeActionKind.SHUTDOWN and action.vouched:
            return self.voucher_color
        return self._gradient_color(action, now)

    def _text_color(self, action: TimeAction) -> str:
        # Non-shutdown times use pearly white
        if action.kind != TimeActionKind.SHUTDOWN:
            return "#ffffff"
        return "white"  # keep shutdown as-is (or also "#ffffff" if you want identical)

    def _disabled(self, action: TimeAction) -> bool:
        # match your old UI: enforced + up were disabled
        # (Voucher/Retrovoucher are UI icons, not actual buttons)
        return action.kind != TimeActionKind.SHUTDOWN

    def _gradient_color(self, action: TimeAction, now: datetime) -> str:
        if action.kind == TimeActionKind.SHUTDOWN:
            grad = self.shutdown_colors
        elif action.kind == TimeActionKind.ENFORCED_SHUTDOWN:
            grad = self.enforced_colors
        else:
            # INTERNET_UP + any other kinds fallback to up
            grad = self.up_colors

        if not grad:
            return "#404654"

        # OLD BEHAVIOR:
        # - only indices 0..COLOR_AMOUNT-1 used
        # - power curve makes far=grey-ish, near=bright
        delta_s = (action.when - now).total_seconds()

        if action.when <= now:
            idx = 0
        else:
            delta_scaled = int(delta_s**1.4) / (60 * 60)
            idx = int(delta_scaled * (COLOR_AMOUNT / 100.0))
            idx = int(clamp(idx, 0, COLOR_AMOUNT - 1))

        rgb = grad[idx]
        return _rgb_to_hex(rgb)

    def _hover(self, action: TimeAction, now: datetime) -> str:
        fg = self._fg(action, now)
        return _darken_hex_like_old(fg)

    def _choose_icon(self, action: TimeAction) -> object:
        """
        Icon rules:
        - If SHUTDOWN is vouched => show VOUCHER icon
        - Otherwise show icon for action.kind
        """
        if action.kind == TimeActionKind.SHUTDOWN and getattr(action, "vouched", False):
            return get_time_action_icon(TimeActionKind.VOUCHER)
        return get_time_action_icon(action.kind)

    def _render(self, btn: ctk.CTkButton, action: TimeAction, index: int):
        now = self._last_now

        fg = self._fg(action, now)
        hv = self._hover(action, now)

        icon = self._choose_icon(action)
        text = f"{self._format_time(action)} | {self._format_remaining(action, now)}"
        state = "disabled" if self._disabled(action) else "normal"

        # --- NEW: disable hover past voucher threshold ---
        hover_enabled = True
        if self._vouchers is not None:
            total = int(getattr(self._vouchers, "local", 0)) + int(getattr(self._vouchers, "used_count", 0))
            if index >= total:
                hover_enabled = False

        # If hover disabled, make hover_color identical to fg (no visual change)
        hover_color = hv if hover_enabled else fg

        sig = (action.kind, action.when, bool(getattr(action, "vouched", False)))

        tc = self._text_color(action)

        desired = {
            "text": text,
            "image": icon,
            "hover_color": hover_color,
            "state": state,
            "hover": hover_enabled,

            # IMPORTANT: disabled buttons use text_color_disabled, not text_color
            "text_color": tc,
            "text_color_disabled": tc,
        }

        desired_static = {
            "compound": "right",
            "anchor": "e",
            "corner_radius": 0,
            "border_width": 0,
        }

        last = getattr(btn, "_last", {})
        updates = {}

        force_fg = last.get("__sig") != sig
        desired["__sig"] = sig   # store into cache (we'll filter it out of configure below)

        if force_fg or (not hover_enabled) or (self._hovered_btn is not btn):
            desired["fg_color"] = fg

        for k, v in desired_static.items():
            if k.startswith("__"):
                continue
            if last.get(k) != v:
                updates[k] = v

        for k, v in desired.items():
            if k.startswith("__"):
                continue
            if last.get(k) != v:
                updates[k] = v

        if updates:
            btn.configure(**updates)
            last.update(updates)
            last["__sig"] = sig
            btn._last = last  # type: ignore[attr-defined]

        btn._icon_ref = icon  # type: ignore[attr-defined]
