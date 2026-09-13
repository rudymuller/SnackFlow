from datetime import date, datetime
import tkinter as tk
from tkinter import messagebox, ttk

from const import DB_PATH
from DBProxy import DBProxy


class BalancoMensalRepository:
    """Consolida vendas fechadas e contas a pagar por mes."""

    def __init__(self, db: DBProxy):
        self.db = db

    @staticmethod
    def _periodo(mes):
        try:
            inicio = datetime.strptime(mes, "%Y-%m").date().replace(day=1)
        except ValueError as error:
            raise ValueError("informe o mes no formato AAAA-MM") from error
        if inicio.month == 12:
            fim = inicio.replace(year=inicio.year + 1, month=1)
        else:
            fim = inicio.replace(month=inicio.month + 1)
        return inicio.isoformat(), fim.isoformat()

    def consultar(self, mes):
        inicio, fim = self._periodo(mes)
        vendas = self.db.query_one(
            """
            SELECT COALESCE(SUM(valor_total), 0) AS total,
                   COUNT(*) AS quantidade
            FROM pedidos
            WHERE estado = 'Fechado'
              AND date(data_fechamento) >= ?
              AND date(data_fechamento) < ?
            """,
            (inicio, fim),
        )
        gastos = self.db.query_one(
            """
            SELECT COALESCE(SUM(valor), 0) AS total
            FROM contas_pagar
            WHERE ativo = 1 AND date(vencimento) >= ? AND date(vencimento) < ?
            """,
            (inicio, fim),
        )
        dias = self.db.query_all(
            """
            SELECT dia, SUM(ganhos) AS ganhos, SUM(gastos) AS gastos
            FROM (
                SELECT date(data_fechamento) AS dia, SUM(valor_total) AS ganhos, 0 AS gastos
                FROM pedidos
                WHERE estado = 'Fechado'
                  AND date(data_fechamento) >= ? AND date(data_fechamento) < ?
                GROUP BY date(data_fechamento)
                UNION ALL
                SELECT date(vencimento) AS dia, 0 AS ganhos, SUM(valor) AS gastos
                FROM contas_pagar
                WHERE ativo = 1 AND date(vencimento) >= ? AND date(vencimento) < ?
                GROUP BY date(vencimento)
            )
            GROUP BY dia ORDER BY dia
            """,
            (inicio, fim, inicio, fim),
        )
        total_ganhos = float(vendas["total"])
        total_gastos = float(gastos["total"])
        return {
            "mes": mes,
            "quantidade_pedidos": int(vendas["quantidade"]),
            "ganhos": total_ganhos,
            "gastos": total_gastos,
            "saldo": total_ganhos - total_gastos,
            "dias": [dict(dia) for dia in dias],
        }


class BalancoMensalView:
    """Tela do UC10 com resumo e grafico diario do fluxo de caixa."""

    def __init__(self, db_path=DB_PATH):
        self.db = DBProxy(db_path)
        self.repository = BalancoMensalRepository(self.db)

    def close(self):
        self.db.close()

    def abrir(self, app, login_instance, win=None, frame=None):
        if win is None or frame is None:
            win, frame = app._new_menu_window(login_instance, "Balanço mensal")
        else:
            win.title("Balanço mensal")
        for widget in frame.winfo_children():
            widget.destroy()

        tk.Label(
            frame, text="Balanço mensal", font=("Segoe UI", 18, "bold"),
            bg=app.COLORS["canvas"], fg=app.COLORS["ink"],
        ).pack(pady=(4, 10))
        controls = tk.Frame(frame, bg=app.COLORS["canvas"])
        controls.pack(fill=tk.X, pady=(0, 10))
        tk.Label(controls, text="Mês (AAAA-MM):", bg=app.COLORS["canvas"], fg=app.COLORS["ink"]).pack(side=tk.LEFT)
        month_entry = tk.Entry(controls, width=10)
        month_entry.insert(0, date.today().strftime("%Y-%m"))
        month_entry.pack(side=tk.LEFT, padx=8)
        summary = tk.Label(controls, text="", bg=app.COLORS["canvas"], fg=app.COLORS["ink"])
        summary.pack(side=tk.LEFT, padx=12)
        graph = tk.Canvas(frame, height=180, bg=app.COLORS["surface"], highlightthickness=0)
        graph.pack(fill=tk.X, pady=(0, 10))
        table = ttk.Treeview(frame, columns=("dia", "ganhos", "gastos", "saldo"), show="headings", height=8)
        for column, heading, width in (("dia", "Dia", 120), ("ganhos", "Ganhos", 120), ("gastos", "Gastos", 120), ("saldo", "Saldo", 120)):
            table.heading(column, text=heading)
            table.column(column, width=width, anchor=tk.CENTER)
        table.pack(expand=True, fill=tk.BOTH)

        def draw_graph(days):
            graph.delete("all")
            if not days:
                graph.create_text(300, 80, text="Sem movimentações no período", fill=app.COLORS["muted"])
                return
            max_value = max(max(float(item["ganhos"]), float(item["gastos"])) for item in days) or 1
            width = max(graph.winfo_width(), 600)
            slot = max(width / len(days), 45)
            for index, item in enumerate(days):
                x = index * slot + slot / 2
                ganhos_height = float(item["ganhos"]) / max_value * 120
                gastos_height = float(item["gastos"]) / max_value * 120
                graph.create_rectangle(x - 16, 145 - ganhos_height, x - 2, 145, fill=app.COLORS["success"], outline="")
                graph.create_rectangle(x + 2, 145 - gastos_height, x + 16, 145, fill=app.COLORS["danger"], outline="")
                graph.create_text(x, 160, text=item["dia"][5:], fill=app.COLORS["ink"])
            graph.create_text(35, 15, text="Ganhos", fill=app.COLORS["success"])
            graph.create_text(90, 15, text="Gastos", fill=app.COLORS["danger"])

        def consult():
            try:
                report = self.repository.consultar(month_entry.get().strip())
            except ValueError as error:
                messagebox.showerror("Balanço mensal", str(error), parent=win)
                return
            summary.configure(text=(
                f"Pedidos: {report['quantidade_pedidos']} | "
                f"Ganhos: R$ {report['ganhos']:.2f} | "
                f"Gastos: R$ {report['gastos']:.2f} | "
                f"Saldo: R$ {report['saldo']:.2f}"
            ))
            for item in table.get_children():
                table.delete(item)
            for item in report["dias"]:
                ganhos = float(item["ganhos"])
                gastos = float(item["gastos"])
                table.insert("", tk.END, values=(item["dia"], f"R$ {ganhos:.2f}", f"R$ {gastos:.2f}", f"R$ {ganhos - gastos:.2f}"))
            draw_graph(report["dias"])

        button = tk.Button(controls, text="Consultar", command=consult)
        app._style_button(button, "primary")
        button.pack(side=tk.LEFT)
        app._maximize_window(win)
