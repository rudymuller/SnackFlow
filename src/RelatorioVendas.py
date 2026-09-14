from datetime import date, datetime
import tkinter as tk
from tkinter import messagebox, ttk

from const import DB_PATH
from DBProxy import DBProxy
from DatePicker import create_date_entry


class RelatorioVendasRepository:
    """Consulta o faturamento diario consolidado de um mes."""

    def __init__(self, db: DBProxy):
        self.db = db

    def consultar(self, mes: str) -> dict:
        try:
            inicio = datetime.strptime(mes.strip(), "%Y-%m").date().replace(day=1)
        except (AttributeError, ValueError) as error:
            raise ValueError("informe o mes no formato AAAA-MM") from error
        if inicio.month == 12:
            fim = inicio.replace(year=inicio.year + 1, month=1)
        else:
            fim = inicio.replace(month=inicio.month + 1)
        inicio_iso = inicio.isoformat()
        fim_iso = fim.isoformat()
        dias = self.db.query_all(
            """
            SELECT date(data_fechamento) AS data,
                   COUNT(*) AS total_pedidos,
                   COALESCE(SUM(valor_total), 0) AS valor_total
            FROM pedidos
            WHERE estado = 'Fechado'
              AND date(data_fechamento) >= ?
              AND date(data_fechamento) < ?
            GROUP BY date(data_fechamento)
            ORDER BY data
            """,
            (inicio_iso, fim_iso),
        )
        valores = []
        total_pedidos = 0
        valor_total = 0.0
        for dia in dias:
            quantidade = int(dia["total_pedidos"])
            valor = float(dia["valor_total"])
            total_pedidos += quantidade
            valor_total += valor
            valores.append({
                "data": dia["data"],
                "total_pedidos": quantidade,
                "valor_total": valor,
                "ticket_medio": valor / quantidade if quantidade else 0.0,
            })
        return {
            "mes": mes.strip(),
            "dias": valores,
            "quantidade_pedidos": total_pedidos,
            "valor_vendido": valor_total,
            "ticket_medio": valor_total / total_pedidos if total_pedidos else 0.0,
        }


class RelatorioVendasView:
    """Tela do faturamento diario consolidado por mes."""

    def __init__(self, db_path: str = DB_PATH):
        self.db = DBProxy(db_path)
        self.repository = RelatorioVendasRepository(self.db)

    def close(self):
        self.db.close()

    def abrir(self, app, login_instance, win=None, frame=None):
        if win is None or frame is None:
            win, frame = app._new_menu_window(login_instance, "Faturamento")
        else:
            win.title("Faturamento")

        for widget in frame.winfo_children():
            widget.destroy()

        title = tk.Label(
            frame, text="Faturamento diário", font=("Segoe UI", 18, "bold"),
            bg=app.COLORS["canvas"], fg=app.COLORS["ink"],
        )
        title.pack(pady=(4, 10))

        controls = tk.Frame(frame, bg=app.COLORS["canvas"])
        controls.pack(fill=tk.X, pady=(0, 12))
        tk.Label(
            controls, text="Data do mês:", bg=app.COLORS["canvas"],
            fg=app.COLORS["ink"],
        ).pack(side=tk.LEFT)
        month_entry = create_date_entry(controls, date.today(), width=12)
        month_entry.pack(side=tk.LEFT, padx=8)

        summary = tk.Label(
            frame, text="Selecione um mês para consultar.",
            bg=app.COLORS["canvas"], fg=app.COLORS["muted"],
        )
        summary.pack(anchor=tk.W, pady=(0, 8))

        table = ttk.Treeview(
            frame, columns=("data", "total_pedidos", "valor_total", "ticket_medio"),
            show="headings", height=12,
        )
        for column, heading, width in (
            ("data", "Data", 140),
            ("total_pedidos", "Total de pedidos", 180),
            ("valor_total", "Valor total de pedidos vendidos", 280),
            ("ticket_medio", "Ticket médio", 160),
        ):
            table.heading(column, text=heading)
            table.column(column, width=width, anchor=tk.CENTER)
        table.pack(expand=True, fill=tk.BOTH, pady=(0, 8))

        def consultar():
            try:
                mes = month_entry.get_date().strftime("%Y-%m")
                relatorio = self.repository.consultar(mes)
            except (TypeError, ValueError) as error:
                messagebox.showerror("Faturamento", str(error), parent=win)
                return

            for row_id in table.get_children():
                table.delete(row_id)
            for dia in relatorio["dias"]:
                table.insert(
                    "", tk.END,
                    values=(
                        datetime.strptime(dia["data"], "%Y-%m-%d").strftime("%d/%m/%Y"),
                        dia["total_pedidos"],
                        f"R$ {dia['valor_total']:.2f}",
                        f"R$ {dia['ticket_medio']:.2f}",
                    ),
                )
            summary.configure(
                text=(
                    f"Mês: {relatorio['mes']} | "
                    f"Pedidos: {relatorio['quantidade_pedidos']} | "
                    f"Vendas: R$ {relatorio['valor_vendido']:.2f} | "
                    f"Ticket médio: R$ {relatorio['ticket_medio']:.2f}"
                ),
                fg=app.COLORS["ink"],
            )

        consult_button = tk.Button(controls, text="Consultar", command=consultar)
        app._style_button(consult_button, "primary")
        consult_button.pack(side=tk.LEFT)
        app._maximize_window(win)
