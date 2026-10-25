from datetime import date, datetime
from zoneinfo import ZoneInfo

COLOMBO = ZoneInfo("Asia/Colombo")


def colombo_today() -> date:
    """Return the current business date for the Sri Lankan deployment."""
    return datetime.now(COLOMBO).date()
