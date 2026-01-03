# controllers/loot_controller.py
from __future__ import annotations
from dataclasses import dataclass
import random
from typing import Optional

from domain.rules import clamp
from client import client_api
from libuniversal import Paths, Actions, MessageKey, StorageKey
from domain.state import AppState

from typing import Optional, Callable

@dataclass
class LootController:
    app: object
    state: AppState
    loot_overlay: object
    status_overlay: object
    scene: object
    loot_button: object
    loot_limit: int
    local_loot_boxes: int = 0
    box_origin = None
    loot_box_openable = True
    
    # --- controller state (MUST be annotated to become instance fields) ---
    box_origin: Optional[str] = None
    loot_box_openable: bool = True
    hide_after_id: Optional[str] = None
    box_consumed: bool = False
    current_lootbox: Optional[str] = None

    on_vouchers_changed: Optional[Callable[[], None]] = None 

    def on_loot_button_clicked(self):
        """
        Loot button behavior:
            - No overlay showing: pull a box from storage
            - Overlay idle (closed box): HIDE it (don't open)
            - Overlay showing result (voucher/retrovoucher/empty): deploy next box (if any), else hide
            - Overlay opening: ignore
        """
        if self.loot_overlay.visible():
            st = getattr(self.loot_overlay, "state", None)

            # If a closed box is showing, loot button should dismiss it (box click opens)
            if st == "idle":
                self.hide_loot_box()
                return

            # If we’re in the opening animation/delay, ignore.
            if st == "opening":
                return

            # Result view: chain if possible, else hide.
            if self.local_loot_boxes > 0:
                self._deploy_next_box_from_storage()
            else:
                self.hide_loot_box()
            return

        # No overlay -> normal behavior
        self.pull_box_from_storage()

    def _schedule_hide(self):
        # be robust even if something weird happens
        if getattr(self, "hide_after_id", None) is not None:
            self.app.after_cancel(self.hide_after_id)

        self.hide_after_id = self.app.after(60_000, self.hide_loot_box)

    def update_loot_button(self):
        # keep it safe
        self.local_loot_boxes = clamp(self.local_loot_boxes, 0, self.loot_limit)

        self.loot_button.configure(text=f"x{self.local_loot_boxes}")

        if self.local_loot_boxes >= self.loot_limit:
            self.loot_button.configure(text_color="#2d74bc")
        else:
            self.loot_button.configure(text_color="#ffffff")

    def refresh_loot_count_async(self):
        def on_count(result):
            if isinstance(result, Exception):
                return

            server_count = int(result or 0)

            # If user pulled a box from storage, server still counts it as stored
            # until it is opened/consumed. Don't let refresh snap UI back.
            if (
                self.box_origin == "storage"
                and not self.box_consumed
                and not self.loot_box_openable
                and self.loot_overlay.visible()
            ):
                return

            self.local_loot_boxes = clamp(server_count, 0, self.loot_limit)
            self.update_loot_button()

        client_api.do_request_async(Actions.LOOT_CHECK, MessageKey.ALL_LOOT_BOXES, on_count)

    def pull_box_from_storage(self):
        if not self.loot_box_openable or self.local_loot_boxes <= 0:
            return

        self.local_loot_boxes -= 1
        self.update_loot_button()
        self.show_loot_box(origin="storage")

    def check_new_loot(self):
        def on_new_amount(result):
            if isinstance(result, Exception):
                return

            new_amount = int(result or 0)
            if new_amount <= 0:
                return

            if self.loot_box_openable:
                self.show_loot_box("found", found_count=new_amount)
            elif self.loot_overlay.visible():
                self.loot_overlay.set_text(f"{self.loot_overlay.idle_text}\n(+{new_amount} stored)")

            self.refresh_loot_count_async()

        client_api.do_request_async(Actions.NEW_LOOT, "", on_new_amount)

    def show_loot_box(self, origin: str, found_count: int = 0):
        if not self.loot_box_openable:
            return

        self.box_origin = origin
        self.box_consumed = False
        self.loot_box_openable = False

        idle_text = "You pulled a box out of storage"
        if found_count > 1:
            idle_text = f"You found {found_count} internet boxes!"
        elif found_count == 1:
            idle_text = "You found an internet box!"

        def on_type(result):
            if isinstance(result, Exception):
                self.status_overlay.show("Server error getting loot box", False)
                self.hide_loot_box()
                return

            self.current_lootbox = result
            if self.current_lootbox == MessageKey.NO_LOOT_BOX:
                self.hide_loot_box()
                return

            img_path = Paths.ASSETS_FOLDER + (
                "/internet_box.png"
                if self.current_lootbox == MessageKey.NORMAL_LOOT_BOX
                else "/shutdown_internet_box.png"
            )

            self.loot_overlay.show_box(img_path, idle_text=idle_text)
            self.loot_overlay.state = "idle"
            self.loot_overlay.set_handlers(on_click=self.open_loot_box)

            self.scene.layout()
            self._schedule_hide()
            self.refresh_loot_count_async()

        client_api.do_request_async(Actions.GET_LOOT, "", on_type)

    def open_loot_box(self):
        # Only respond when overlay says it’s clickable
        if self.loot_overlay.state != "idle":
            return

        self.box_consumed = True
        self.loot_overlay.state = "opening"

        open_path = Paths.ASSETS_FOLDER + (
            "/internet_box_open.png"
            if self.current_lootbox == MessageKey.NORMAL_LOOT_BOX
            else "/shutdown_internet_box_open.png"
        )
        self.loot_overlay.set_image(open_path)
        self.loot_overlay.set_text("You opened the box...")

        delay_ms = random.randint(2, 10) * 1000
        self.app.after(delay_ms, self._get_loot_result)

    def _try_add_vouchers(self, amount: int) -> bool:
        if amount <= 0:
            return False

        max_local = max(0, self.state.vouchers.limit - self.state.vouchers.used_count)
        if self.state.vouchers.local >= max_local:
            return False

        new_local = min(max_local, self.state.vouchers.local + amount)
        if new_local == self.state.vouchers.local:
            return False

        self.state.vouchers.local = new_local
        return True
    
    def _try_add_retrovouchers(self, amount: int) -> bool:
        if amount <= 0:
            return False

        max_local = max(0, int(getattr(self.state.vouchers, "retrolimit", 0)))
        cur = int(getattr(self.state.vouchers, "retrolocal", 0))

        if cur >= max_local:
            return False

        new_val = min(max_local, cur + amount)
        if new_val == cur:
            return False

        self.state.vouchers.retrolocal = new_val
        return True

    def _get_loot_result(self):
        def on_opened(result):
            if isinstance(result, Exception):
                self.loot_overlay.set_text("Server error opening box :(")
                self._schedule_hide()
                return

            # Robust payload parsing:
            # - if server returns int: treat as vouchers
            # - if server returns dict: look for voucher + retrovoucher
            new_vouchers = 0
            new_retrovouchers = 0

            self.loot_overlay.state = "result"

            if isinstance(result, dict):
                # Option A: server returns { "voucher": 1, "retrovoucher": 0 }
                new_vouchers = int(result.get(StorageKey.VOUCHER.value, 0))
                new_retrovouchers = int(result.get(getattr(StorageKey, "RETROVOUCHER").value, 0))
            else:
                # Option B: old server behavior: integer vouchers only
                try:
                    new_vouchers = int(result or 0)
                except Exception:
                    new_vouchers = 0

            if new_vouchers <= 0 and new_retrovouchers <= 0:
                self.loot_overlay.set_text("There was nothing inside :(")

            elif new_vouchers > 0:
                added = self._try_add_vouchers(new_vouchers)
                self.loot_overlay.set_image(Paths.ASSETS_FOLDER + "/voucher.png")
                self.loot_overlay.set_text(
                    "You found a voucher!!!" if added else "You found a voucher, but don't have room..."
                )
                if self.on_vouchers_changed:
                    self.app.after(0, self.on_vouchers_changed)

            else:
                added = self._try_add_retrovouchers(new_retrovouchers)
                self.loot_overlay.set_image(Paths.ASSETS_FOLDER + "/retrovoucher.png")
                self.loot_overlay.set_text(
                    "You found a retrovoucher!!!" if added else "You found a retrovoucher, but don't have room..."
                )
                if self.on_vouchers_changed:
                    self.app.after(0, self.on_vouchers_changed)

            self._schedule_hide()
            self.refresh_loot_count_async()

        client_api.do_request_async(Actions.LOOT_OPEN, self.current_lootbox, on_opened)

    def _deploy_next_box_from_storage(self):
        # Don’t chain while opening
        if getattr(self.loot_overlay, "state", None) == "opening":
            return

        if self.local_loot_boxes <= 0:
            return

        # Cancel any pending hide on current overlay so it doesn't race.
        if self.hide_after_id is not None:
            self.app.after_cancel(self.hide_after_id)
            self.hide_after_id = None

        # Hide current result overlay immediately
        self.loot_overlay.hide()

        # Pull next box
        self.local_loot_boxes -= 1
        self.update_loot_button()

        # Reset state and show next
        self.loot_box_openable = True
        self.box_origin = None
        self.box_consumed = False
        self.current_lootbox = None

        self.show_loot_box(origin="storage")

    def hide_loot_box(self):
        if self.hide_after_id is not None:
            self.app.after_cancel(self.hide_after_id)
            self.hide_after_id = None

        self.loot_box_openable = True
        self.box_origin = None
        self.box_consumed = False

        self.loot_overlay.hide()
        self.refresh_loot_count_async()
