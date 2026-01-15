# controllers/time_controller.py
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Callable, Optional

from domain.models import TimeAction, TimeActionKind
from domain.rules import compute_cutoff, compute_streak
from domain.state import AppState
from libuniversal import Actions
from configreader import str_to_datetime, datetime_to_str

class TimeController:
    def __init__(self, state, api, shift_hhmm: str, on_event: Optional[Callable[[str, Optional[TimeAction]], None]] = None):
        self.state: AppState = state
        self.api = api
        self.shift_hhmm = shift_hhmm
        self.on_event = on_event
        self.actions: list[TimeAction] = []

    def set_actions(self, actions: list[TimeAction]):
        self.actions = actions
        self.actions.sort(key=lambda a: a.when)

    def tick(self):
        self.state.now = datetime.now()

        # rollover
        if self.state.now > self.state.cutoff_time:
            self.state.streak = compute_streak(self.state.now, self.state.last_relapse)
            self.state.cutoff_time = compute_cutoff(self.state.now, self.shift_hhmm)
            self.state.vouchers.used_today = False
            self.state.used_manual_override = False
            if self.on_event:
                self.on_event("day_rollover", None)

        # trigger due actions (like your old update_gui loop)
        now = self.state.now
        for action in self.actions:
            if action.when > now:
                continue
            # internet up
            if action.kind == TimeActionKind.INTERNET_UP:
                self.state.internet_on = True
                if self.on_event:
                    self.on_event("internet_up_triggered", action)
            # retroactivate
            elif self.state.vouchers.retro_scheduled:
                if self.on_event:
                    self.on_event("retro_consumed", None)
            # voucher consumed at trigger time
            elif action.vouched:
                self.state.vouchers.used_today = True
                self.state.vouchers.used_count = max(0, self.state.vouchers.used_count - 1)
                action.vouched = False
                if self.on_event:
                    self.on_event("voucher_consumed", action)
            # normal action
            elif action.kind in (TimeActionKind.SHUTDOWN, TimeActionKind.ENFORCED_SHUTDOWN):
                    self.state.internet_on = False
                    if self.on_event:
                        self.on_event("shutdown_triggered", action)

            # roll to tomorrow (same as your recalculate_time)
            action.when = action.when + timedelta(days=1)

        self.actions.sort(key=lambda a: a.when)

    def on_action_clicked(self, index: int):
        if index < 0 or index >= len(self.actions):
            return
        action = self.actions[index]

        # Only shutdown entries are vouchable (like before)
        if action.kind != TimeActionKind.SHUTDOWN:
            return

        # "can_vouch" rule: all previous non-INTERNET_UP actions must be vouched
        can_vouch = True
        for prev in self.actions[:index]:
            if prev.kind != TimeActionKind.INTERNET_UP and not prev.vouched:
                can_vouch = False
                break

        if (not action.vouched and self.state.vouchers.local > 0 and self.state.internet_on and can_vouch):
            action.vouched = True
            self.state.vouchers.local -= 1
            self.state.vouchers.used_count += 1
            self.api.request_async(Actions.USED_VOUCHER, datetime_to_str(action.when))
        elif action.vouched:
            # unvouch this and all subsequent vouched actions (your old behavior)
            for a in self.actions[index:]:
                if a.vouched:
                    a.vouched = False
                    self.state.vouchers.local += 1
                    self.state.vouchers.used_count = max(0, self.state.vouchers.used_count - 1)
                    self.api.request_async(Actions.UNUSED_VOUCHER, datetime_to_str(a.when))

        self.actions.sort(key=lambda a: a.when)