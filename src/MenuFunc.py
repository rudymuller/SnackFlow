import tkinter as tk
from tkinter import messagebox


class MenuFunc:
    """Tela principal do menu de atendimento."""

    def __init__(self, app, login_instance):
        self.app = app
        self.login_instance = login_instance
        self.win, self.frame = app._new_menu_window(login_instance, "Menu de Atendimento")
        self.render()

    def render(self):
        self.win.title("Home - Gestão de Atendimento")
        self.app._render_home(self.frame, self.win, self.login_instance, "atend")
        self.app._maximize_window(self.win)

    def open_placeholder(self, title):
        messagebox.showinfo(title, f"Abrindo {title} (placeholder)")

    def open_estoque(self):
        from Estoque import Estoque
        Estoque().abrir_menu(self.app, self.login_instance, self.win, self.frame)