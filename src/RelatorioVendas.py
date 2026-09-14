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

    def pedidos_do_dia(self, data_consulta: str) -> list[dict]:
        rows = self.db.query_all(
            """
            SELECT id, cliente, data_fechamento, valor_total
            FROM pedidos
            WHERE estado = 'Fechado' AND date(data_fechamento) = ?
            ORDER BY data_fechamento, id
            """,
            (data_consulta,),
        )
        return [dict(row) for row in rows]

    def detalhes_pedido(self, pedido_id: str) -> dict | None:
        pedido = self.db.query_one(
            "SELECT id, cliente, estado, data_fechamento, valor_total, observacao FROM pedidos WHERE id = ?",
            (pedido_id,),
        )
        if not pedido:
            return None
        itens = self.db.query_all(
            """
            SELECT nome, quantidade, unidade, preco_unitario, valor_total, lanche_nome
            FROM pedido_itens
            WHERE pedido_id = ?
            ORDER BY id
            """,
            (pedido_id,),
        )
        lanches = self.db.query_all(
            """
            SELECT nome, quantidade
            FROM pedido_lanches
            WHERE pedido_id = ?
            ORDER BY id
            """,
            (pedido_id,),
        )
        return {
            "pedido": dict(pedido),
            "itens": [dict(item) for item in itens],
            "lanches": [dict(lanche) for lanche in lanches],
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

        def mostrar_pedidos_do_dia():
            selection = table.selection()
            if not selection:
                messagebox.showinfo(
                    "Faturamento",
                    "Selecione um dia na tabela para ver os pedidos.",
                    parent=win,
                )
                return
            values = table.item(selection[0], "values")
            data_consulta = datetime.strptime(values[0], "%d/%m/%Y").strftime("%Y-%m-%d")
            pedidos = self.repository.pedidos_do_dia(data_consulta)
            popup = tk.Toplevel(win)
            popup.title(f"Pedidos de {values[0]}")
            popup.transient(win)
            popup.geometry("720x360")
            popup.configure(bg=app.COLORS["canvas"])
            tk.Label(
                popup,
                text=f"Pedidos fechados em {values[0]}",
                font=("Segoe UI", 14, "bold"),
                bg=app.COLORS["canvas"],
                fg=app.COLORS["ink"],
            ).pack(pady=(12, 8))
            orders_table = ttk.Treeview(
                popup,
                columns=("id", "cliente", "horario", "valor"),
                show="headings",
                height=10,
            )
            for column, heading, width in (
                ("id", "Pedido", 220),
                ("cliente", "Cliente", 180),
                ("horario", "Fechado em", 140),
                ("valor", "Valor", 120),
            ):
                orders_table.heading(column, text=heading)
                orders_table.column(column, width=width, anchor=tk.CENTER)
            orders_table.pack(expand=True, fill=tk.BOTH, padx=12, pady=(0, 8))
            for pedido in pedidos:
                fechamento = (pedido["data_fechamento"] or "").replace("T", " ")[:19]
                orders_table.insert(
                    "", tk.END,
                    values=(
                        pedido["id"],
                        pedido["cliente"],
                        fechamento,
                        f"R$ {float(pedido['valor_total'] or 0):.2f}",
                    ),
                )

            def mostrar_detalhes_pedido():
                selection = orders_table.selection()
                if not selection:
                    messagebox.showinfo(
                        "Pedidos",
                        "Selecione um pedido para ver os detalhes.",
                        parent=popup,
                    )
                    return
                pedido_id = orders_table.item(selection[0], "values")[0]
                detalhes = self.repository.detalhes_pedido(pedido_id)
                if not detalhes:
                    messagebox.showerror("Pedidos", "Pedido não encontrado.", parent=popup)
                    return
                pedido = detalhes["pedido"]
                card_popup = tk.Toplevel(popup)
                card_popup.title(f"Detalhes do pedido {pedido['id']}")
                card_popup.transient(popup)
                card_popup.geometry("620x520")
                card_popup.configure(bg=app.COLORS["canvas"])
                card = tk.Frame(
                    card_popup,
                    bg=app.COLORS["surface"],
                    bd=1,
                    relief=tk.GROOVE,
                    padx=18,
                    pady=14,
                )
                card.pack(expand=True, fill=tk.BOTH, padx=18, pady=18)
                tk.Label(
                    card,
                    text=f"Pedido de {pedido['cliente']}",
                    font=("Segoe UI", 15, "bold"),
                    bg=app.COLORS["surface"],
                    fg=app.COLORS["ink"],
                ).pack(anchor=tk.W)
                fechamento = (pedido["data_fechamento"] or "").replace("T", " ")[:19]
                tk.Label(
                    card,
                    text=f"Status: {pedido['estado']}   |   Fechado em: {fechamento}",
                    font=("Segoe UI", 10),
                    bg=app.COLORS["surface"],
                    fg=app.COLORS["muted"],
                ).pack(anchor=tk.W, pady=(3, 12))
                items_frame = tk.Frame(card, bg=app.COLORS["surface"])
                items_frame.pack(fill=tk.BOTH, expand=True)
                for column, heading, width in (
                    (0, "ITEM", 30),
                    (1, "QTD", 8),
                    (2, "PREÇO UN.", 12),
                    (3, "TOTAL", 12),
                ):
                    tk.Label(
                        items_frame,
                        text=heading,
                        width=width,
                        font=("Segoe UI", 9, "bold"),
                        bg=app.COLORS["surface"],
                        fg=app.COLORS["ink"],
                        anchor=tk.W if column == 0 else tk.E,
                    ).grid(row=0, column=column, sticky=tk.EW, padx=2, pady=(0, 5))
                row_index = 1
                for item in detalhes["itens"]:
                    quantidade = float(item["quantidade"] or 0)
                    unitario = float(item["preco_unitario"] or 0)
                    total_item = float(item["valor_total"] or 0)
                    tk.Label(items_frame, text=item["nome"], bg=app.COLORS["surface"], fg=app.COLORS["muted"], anchor=tk.W).grid(row=row_index, column=0, sticky=tk.EW, padx=2)
                    tk.Label(items_frame, text=f"{quantidade:g}", bg=app.COLORS["surface"], fg=app.COLORS["muted"], anchor=tk.E).grid(row=row_index, column=1, sticky=tk.EW, padx=2)
                    tk.Label(items_frame, text=f"R$ {unitario:.2f}", bg=app.COLORS["surface"], fg=app.COLORS["muted"], anchor=tk.E).grid(row=row_index, column=2, sticky=tk.EW, padx=2)
                    tk.Label(items_frame, text=f"R$ {total_item:.2f}", bg=app.COLORS["surface"], fg=app.COLORS["muted"], anchor=tk.E).grid(row=row_index, column=3, sticky=tk.EW, padx=2)
                    row_index += 1
                for lanche in detalhes["lanches"]:
                    quantidade = float(lanche["quantidade"] or 0)
                    tk.Label(items_frame, text=lanche["nome"], bg=app.COLORS["surface"], fg=app.COLORS["muted"], anchor=tk.W).grid(row=row_index, column=0, sticky=tk.EW, padx=2)
                    tk.Label(items_frame, text=f"{quantidade:g}", bg=app.COLORS["surface"], fg=app.COLORS["muted"], anchor=tk.E).grid(row=row_index, column=1, sticky=tk.EW, padx=2)
                    row_index += 1
                if pedido.get("observacao"):
                    tk.Label(card, text=f"Observação: {pedido['observacao']}", bg=app.COLORS["surface"], fg=app.COLORS["muted"], wraplength=540, justify=tk.LEFT).pack(anchor=tk.W, pady=(10, 0))
                tk.Label(
                    card,
                    text=f"TOTAL: R$ {float(pedido['valor_total'] or 0):.2f}",
                    font=("Segoe UI", 12, "bold"),
                    bg=app.COLORS["surface"],
                    fg=app.COLORS["primary"],
                ).pack(anchor=tk.W, pady=(12, 8))
                close_card_button = tk.Button(card, text="Fechar", command=card_popup.destroy)
                app._style_button(close_card_button, "primary")
                close_card_button.pack(anchor=tk.W)

            details_button = tk.Button(
                popup,
                text="Mostrar detalhes do pedido selecionado",
                command=mostrar_detalhes_pedido,
            )
            app._style_button(details_button, "primary")
            details_button.pack(pady=(0, 8))
            close_button = tk.Button(popup, text="Fechar", command=popup.destroy)
            app._style_button(close_button, "primary")
            close_button.pack(pady=(0, 12))

        show_orders_button = tk.Button(
            frame,
            text="Ver pedidos do dia selecionado",
            command=mostrar_pedidos_do_dia,
        )
        app._style_button(show_orders_button, "primary")
        show_orders_button.pack(anchor=tk.W, pady=(0, 8))

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
