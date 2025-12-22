# domain/models.py
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto

class TimeActionKind(Enum):
    SHUTDOWN = auto()
    ENFORCED_SHUTDOWN = auto()
    INTERNET_UP = auto()
    VOUCHER = auto()
    RETROVOUCHER = auto()

@dataclass
class TimeAction:
    when: datetime
    kind: TimeActionKind
    vouched: bool = False
