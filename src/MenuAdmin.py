import tkinter as tk
from tkinter import messagebox


class MenuAdmin:
    """Tela principal do menu administrativo."""

    def __init__(self, app, login_instance):
        self.app = app
        self.login_instance = login_instance
        self.win, self.frame = app._new_menu_window(login_instance, "Menu Administrativo")
        self.render()

    def render(self):
        self.win.title("Home - Gestão Administrativa")
        self.app._render_home(self.frame, self.win, self.login_instance, "admin")
        self.app._maximize_window(self.win)

    def open_pedidos(self):
        try:
            from Pedidos import Pedidos
            Pedidos()
            messagebox.showinfo("Pedidos", "Abrindo módulo Pedidos (placeholder)")
        except Exception:
            messagebox.showinfo("Pedidos", "Módulo Pedidos não implementado - placeholder.")