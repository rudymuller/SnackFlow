from datetime import date, datetime
import tkinter as tk

from tkcalendar import DateEntry


def create_date_entry(parent, value=None, width=32):
    """Cria um campo de data com calendário e valor ISO opcional."""
    entry = DateEntry(
        parent,
        width=width,
        date_pattern="dd-mm-yyyy",
        showweeknumbers=False,
    )
    if value:
        if isinstance(value, datetime):
            value = value.date()
        elif isinstance(value, str):
            value = date.fromisoformat(value[:10])
        entry.set_date(value)
    else:
        entry.delete(0, tk.END)
    return entry