from pathlib import Path
from datetime import datetime
import sys


if getattr(sys, "frozen", False):
	PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
	PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = str(PROJECT_ROOT / "data" / "SysDB.db")

WIN_HEIGHT = 320
WIN_WIDTH = 600


def now_iso():
	"""Retorna o horario local atual no formato ISO usado pelo banco."""
	local_now = datetime.now().astimezone().replace(tzinfo=None)
	return local_now.isoformat()

