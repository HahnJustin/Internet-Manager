# domain/state.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class VoucherState:
    local: int = 0
    used_today: bool = False
    used_count: int = 0
    limit: int = 0
    retrolocal: int = 0
    retrolimit: int = 0
    retro_scheduled: bool = False
    retro_used: bool = False
    retro_pending: bool = False

@dataclass
class LootUIState:
    openable: bool = True
    origin: Optional[str] = None          # None | "storage" | "found" | "debug"
    consumed: bool = False
    state: str = "hidden"                # "hidden" | "idle" | "opening" | "opened"
    click_enabled: bool = False
    idle_text: str = ""
    current_lootbox: Optional[str] = None
    hide_after_id: Optional[str] = None  # store tk after id as str/int

@dataclass
class AppState:
    now: datetime
    cutoff_time: datetime
    internet_on: bool = True
    admin_on: bool = True
    globe_on: bool = True

    streak: int = 0
    last_relapse: datetime = field(default_factory=datetime.now)

    vouchers: VoucherState = field(default_factory=VoucherState)
    loot: LootUIState = field(default_factory=LootUIState)

    used_manual_override: bool = False
