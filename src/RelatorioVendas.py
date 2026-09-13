from datetime import date
import tkinter as tk
from tkinter import messagebox, ttk

from const import DB_PATH
from DBProxy import DBProxy
from DatePicker import create_date_entry


class RelatorioVendasRepository:
    """Consulta os pedidos fechados e os itens vendidos em uma data."""

    def __init__(self, db: DBProxy):
        self.db = db

    def consultar(self, data_consulta: date) -> dict:
        data_iso = data_consulta.isoformat()
        pedidos = self.db.query_all(
            """
            SELECT id, cliente, data_fechamento
            FROM pedidos
            WHERE estado = 'Fechado' AND date(data_fechamento) = ?
            ORDER BY data_fechamento, id
            """,
            (data_iso,),
        )
        itens_vendidos = self.db.query_one(
            """
            SELECT COALESCE(SUM(item.quantidade), 0) AS total
            FROM pedido_itens item
            JOIN pedidos pedido ON pedido.id = item.pedido_id
            WHERE pedido.estado = 'Fechado'
              AND date(pedido.data_fechamento) = ?
            """,
            (data_iso,),
        )
        valor_vendido = self.db.query_one(
            """
            SELECT COALESCE(SUM(valor_total), 0) AS total
            FROM pedidos
            WHERE estado = 'Fechado' AND date(data_fechamento) = ?
            """,
            (data_iso,),
        )
        return {
            "data": data_iso,
            "pedidos": [dict(pedido) for pedido in pedidos],
            "quantidade_pedidos": len(pedidos),
            "quantidade_itens": float(itens_vendidos["total"]),
            "valor_vendido": float(valor_vendido["total"]),
        }


class RelatorioVendasView:
    """Tela do fechamento quantitativo das vendas de um dia."""

    def __init__(self, db_path: str = DB_PATH):
        self.db = DBProxy(db_path)
        self.repository = RelatorioVendasRepository(self.db)

    def close(self):
        self.db.close()

    def abrir(self, app, login_instance, win=None, frame=None):
        if win is None or frame is None:
            win, frame = app._new_menu_window(login_instance, "Fechamento diário")
        else:
            win.title("Fechamento diário")

        for widget in frame.winfo_children():
            widget.destroy()

        title = tk.Label(
            frame, text="Fechamento diário de vendas", font=("Segoe UI", 18, "bold"),
            bg=app.COLORS["canvas"], fg=app.COLORS["ink"],
        )
        title.pack(pady=(4, 10))

        controls = tk.Frame(frame, bg=app.COLORS["canvas"])
        controls.pack(fill=tk.X, pady=(0, 12))
        tk.Label(
            controls, text="Data da consulta:", bg=app.COLORS["canvas"],
            fg=app.COLORS["ink"],
        ).pack(side=tk.LEFT)
        date_entry = create_date_entry(controls, width=14)
        date_entry.pack(side=tk.LEFT, padx=8)

        summary = tk.Label(
            frame, text="Selecione uma data para consultar.",
            bg=app.COLORS["canvas"], fg=app.COLORS["muted"],
        )
        summary.pack(anchor=tk.W, pady=(0, 8))

        table = ttk.Treeview(
            frame, columns=("id", "cliente", "fechamento"),
            show="headings", height=12,
        )
        for column, heading, width in (
            ("id", "Pedido", 180),
            ("cliente", "Cliente", 220),
            ("fechamento", "Fechado em", 180),
        ):
            table.heading(column, text=heading)
            table.column(column, width=width, anchor=tk.CENTER)
        table.pack(expand=True, fill=tk.BOTH, pady=(0, 8))

        def consultar():
            try:
                data_consulta = date_entry.get_date()
                relatorio = self.repository.consultar(data_consulta)
            except (TypeError, ValueError) as error:
                messagebox.showerror("Fechamento diário", str(error), parent=win)
                return

            for row_id in table.get_children():
                table.delete(row_id)
            for pedido in relatorio["pedidos"]:
                fechamento = (pedido["data_fechamento"] or "").replace("T", " ")[:19]
                table.insert(
                    "", tk.END,
                    values=(pedido["id"], pedido["cliente"], fechamento),
                )
            summary.configure(
                text=(
                    f"Data: {relatorio['data']} | "
                    f"Pedidos fechados: {relatorio['quantidade_pedidos']} | "
                    f"Itens vendidos: {relatorio['quantidade_itens']:g} | "
                    f"Vendas: R$ {relatorio['valor_vendido']:.2f}"
                ),
                fg=app.COLORS["ink"],
            )

        consult_button = tk.Button(controls, text="Consultar", command=consultar)
        app._style_button(consult_button, "primary")
        consult_button.pack(side=tk.LEFT)
        app._maximize_window(win)
