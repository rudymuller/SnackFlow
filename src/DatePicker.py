from datetime import date, datetime
import tkinter as tk

from tkcalendar import DateEntry


def _parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        value = value.strip()
        for pattern in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(value[:10], pattern).date()
            except ValueError:
                continue
    raise ValueError(f"Formato de data inválido: {value!r}")


def create_date_entry(parent, value=None, width=32):
    """Cria um campo de data com calendario e formato brasileiros."""
    entry = DateEntry(
        parent,
        width=width,
        locale="pt_BR",
        date_pattern="dd/mm/yyyy",
        showweeknumbers=False,
    )
    if value:
        entry.set_date(_parse_date(value))
    else:
        entry.delete(0, tk.END)
    return entry