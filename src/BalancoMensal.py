from datetime import date, datetime
import tkinter as tk
from tkinter import messagebox, ttk

from const import DB_PATH
from DBProxy import DBProxy
from DatePicker import create_date_entry


class BalancoMensalRepository:
    """Consolida entradas e saidas por mes e por dia."""

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

    @staticmethod
    def _proximo_mes(mes):
        inicio = datetime.strptime(mes, "%Y-%m").date().replace(day=1)
        if inicio.month == 12:
            inicio = inicio.replace(year=inicio.year + 1, month=1)
        else:
            inicio = inicio.replace(month=inicio.month + 1)
        return inicio.strftime("%Y-%m")

    def consultar_periodo(self, mes_inicio, mes_fim):
        try:
            inicio_date = datetime.strptime(mes_inicio.strip(), "%Y-%m").date().replace(day=1)
            fim_date = datetime.strptime(mes_fim.strip(), "%Y-%m").date().replace(day=1)
        except (AttributeError, ValueError) as error:
            raise ValueError("informe os meses no formato AAAA-MM") from error
        if inicio_date > fim_date:
            raise ValueError("o mês inicial deve ser anterior ou igual ao mês final")
        inicio = inicio_date.isoformat()
        fim = self._periodo(self._proximo_mes(mes_fim.strip()))[0]
        periodo_params = (inicio, fim)
        vendas = self.db.query_one(
            """
            SELECT COALESCE(SUM(valor_total), 0) AS total,
                   COUNT(*) AS quantidade
            FROM pedidos
            WHERE estado = 'Fechado'
              AND date(data_fechamento) >= ?
              AND date(data_fechamento) < ?
            """,
            periodo_params,
        )
        gastos = self.db.query_one(
            """
            SELECT COALESCE(SUM(valor), 0) AS total
            FROM contas_pagar
            WHERE ativo = 1 AND date(vencimento) >= ? AND date(vencimento) < ?
            """,
            periodo_params,
        )
        movimentos = self.db.query_all(
            """
            SELECT mes, SUM(ganhos) AS ganhos, SUM(gastos) AS gastos
            FROM (
                SELECT strftime('%Y-%m', data_fechamento) AS mes, SUM(valor_total) AS ganhos, 0 AS gastos
                FROM pedidos
                WHERE estado = 'Fechado'
                  AND date(data_fechamento) >= ? AND date(data_fechamento) < ?
                GROUP BY strftime('%Y-%m', data_fechamento)
                UNION ALL
                SELECT strftime('%Y-%m', vencimento) AS mes, 0 AS ganhos, SUM(valor) AS gastos
                FROM contas_pagar
                WHERE ativo = 1 AND date(vencimento) >= ? AND date(vencimento) < ?
                GROUP BY strftime('%Y-%m', vencimento)
            )
            GROUP BY mes ORDER BY mes
            """,
            (inicio, fim, inicio, fim),
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
        por_mes = {
            row["mes"]: {
                "mes": row["mes"],
                "ganhos": float(row["ganhos"]),
                "gastos": float(row["gastos"]),
                "saldo": float(row["ganhos"]) - float(row["gastos"]),
            }
            for row in movimentos
        }
        for mes in self._meses_no_periodo(mes_inicio.strip(), mes_fim.strip()):
            por_mes.setdefault(mes, {"mes": mes, "ganhos": 0.0, "gastos": 0.0, "saldo": 0.0})
        return {
            "mes_inicio": mes_inicio.strip(),
            "mes_fim": mes_fim.strip(),
            "quantidade_pedidos": int(vendas["quantidade"]),
            "ganhos": total_ganhos,
            "gastos": total_gastos,
            "saldo": total_ganhos - total_gastos,
            "meses": [por_mes[mes] for mes in sorted(por_mes)],
            "dias": [dict(dia) for dia in dias],
        }

    @classmethod
    def _meses_no_periodo(cls, mes_inicio, mes_fim):
        meses = []
        atual = mes_inicio
        while atual <= mes_fim:
            meses.append(atual)
            atual = cls._proximo_mes(atual)
        return meses

    def consultar(self, mes):
        return self.consultar_periodo(mes, mes)


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
        tk.Label(controls, text="De:", bg=app.COLORS["canvas"], fg=app.COLORS["ink"]).pack(side=tk.LEFT)
        start_entry = create_date_entry(controls, date.today(), width=12)
        start_entry.pack(side=tk.LEFT, padx=(8, 12))
        tk.Label(controls, text="Até:", bg=app.COLORS["canvas"], fg=app.COLORS["ink"]).pack(side=tk.LEFT)
        end_entry = create_date_entry(controls, date.today(), width=12)
        end_entry.pack(side=tk.LEFT, padx=8)
        summary = tk.Label(controls, text="", bg=app.COLORS["canvas"], fg=app.COLORS["ink"])
        summary.pack(side=tk.LEFT, padx=12)
        graph = tk.Canvas(frame, height=240, bg=app.COLORS["surface"], highlightthickness=0)
        graph.pack(fill=tk.X, pady=(0, 10))
        table = ttk.Treeview(frame, columns=("dia", "ganhos", "gastos", "saldo"), show="headings", height=8)
        for column, heading, width in (("dia", "Data", 120), ("ganhos", "Entradas", 120), ("gastos", "Saídas", 120), ("saldo", "Saldo", 120)):
            table.heading(column, text=heading)
            table.column(column, width=width, anchor=tk.CENTER)
        table.pack(expand=True, fill=tk.BOTH)

        selected_month = {"value": None}

        def show_daily_report(report, mes):
            selected_month["value"] = mes
            for item in table.get_children():
                table.delete(item)
            daily_items = [item for item in report["dias"] if item["dia"].startswith(mes)] if mes else []
            for item in daily_items:
                ganhos = float(item["ganhos"])
                gastos = float(item["gastos"])
                table.insert(
                    "", tk.END,
                    values=(
                        datetime.strptime(item["dia"], "%Y-%m-%d").strftime("%d/%m/%Y"),
                        f"R$ {ganhos:.2f}",
                        f"R$ {gastos:.2f}",
                        f"R$ {ganhos - gastos:.2f}",
                    ),
                )

        def draw_graph(months, report):
            graph.delete("all")
            if not months:
                graph.create_text(300, 100, text="Sem movimentações no período", fill=app.COLORS["muted"])
                return
            max_value = max(
                max(float(item["ganhos"]), float(item["gastos"]), abs(float(item["saldo"])))
                for item in months
            ) or 1
            width = max(graph.winfo_width(), 600)
            slot = max(width / len(months), 90)
            baseline = 130
            max_bar_height = 88
            graph.create_line(0, baseline, width, baseline, fill=app.COLORS["line"], width=1)
            graph.create_text(8, baseline - 4, text="0", fill=app.COLORS["muted"], anchor=tk.E)

            def format_currency(value):
                return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            for index, item in enumerate(months):
                x = index * slot + slot / 2
                tag = f"mes_{item['mes']}"
                for offset, key, color in ((-22, "ganhos", "#2E8B57"), (0, "gastos", "#D64545"), (22, "saldo", "#2F6FA3")):
                    value = float(item[key])
                    height = abs(value) / max_value * max_bar_height
                    top = baseline - height if value >= 0 else baseline
                    bottom = baseline if value >= 0 else baseline + height
                    graph.create_rectangle(
                        x + offset - 9, top, x + offset + 9, bottom,
                        fill=color, outline="", tags=(tag,),
                    )
                    label_y = top - 4 if value >= 0 else bottom + 4
                    graph.create_text(
                        x + offset,
                        label_y,
                        text=format_currency(value),
                        fill=color,
                        font=("Segoe UI", 8, "bold"),
                        anchor=tk.S if value >= 0 else tk.N,
                        tags=(tag,),
                    )
                graph.create_text(x, baseline + 18, text=item["mes"], fill=app.COLORS["ink"], tags=(tag,))
                graph.create_text(x, baseline + 38, text="clique para detalhes", fill=app.COLORS["muted"], font=("Segoe UI", 8), tags=(tag,))
                graph.tag_bind(tag, "<Button-1>", lambda _event, mes=item["mes"]: show_daily_report(report, mes))
            graph.create_text(45, 18, text="Entradas", fill="#2E8B57", anchor=tk.W)
            graph.create_text(125, 18, text="Saídas", fill="#D64545", anchor=tk.W)
            graph.create_text(195, 18, text="Saldo", fill="#2F6FA3", anchor=tk.W)
            graph.create_text(45, 42, text="Clique nas barras de um mês para ver o relatório diário", fill=app.COLORS["muted"], anchor=tk.W)

        def consult():
            try:
                mes_inicio = start_entry.get_date().strftime("%Y-%m")
                mes_fim = end_entry.get_date().strftime("%Y-%m")
                report = self.repository.consultar_periodo(mes_inicio, mes_fim)
            except ValueError as error:
                messagebox.showerror("Balanço mensal", str(error), parent=win)
                return
            summary.configure(text=(
                f"Período: {report['mes_inicio']} a {report['mes_fim']} | "
                f"Pedidos: {report['quantidade_pedidos']} | "
                f"Ganhos: R$ {report['ganhos']:.2f} | "
                f"Gastos: R$ {report['gastos']:.2f} | "
                f"Saldo: R$ {report['saldo']:.2f}"
            ))
            draw_graph(report["meses"], report)
            show_daily_report(report, report["meses"][0]["mes"] if report["meses"] else None)

        button = tk.Button(controls, text="Consultar", command=consult)
        app._style_button(button, "primary")
        button.pack(side=tk.LEFT)
        app._maximize_window(win)
