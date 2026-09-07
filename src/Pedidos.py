from datetime import datetime
from enum import Enum
import tkinter as tk
from tkinter import messagebox, ttk
import uuid

from DBProxy import DBProxy
from Lanche import Lanche

class EstadoPedido(Enum):
    ABERTO = "Aberto"
    EM_PRODUCAO = "Em Produção"
    EM_CONSUMO = "Em Consumo"
    FECHADO = "Fechado"
    CANCELADO = "Cancelado"

class Pedido:
    def __init__(self, cliente: str):
        self.id = str(uuid.uuid4())
        self.cliente = cliente.strip()
        self.itens = []
        self.estado = EstadoPedido.ABERTO
        self.estoque_baixado = 0
        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = None

    def adicionar_item(self, item: str):
        if self.estado in (EstadoPedido.ABERTO, EstadoPedido.EM_PRODUCAO, EstadoPedido.EM_CONSUMO):
            self.itens.append(item)

    def remover_item(self, item: str):
        if item in self.itens and self.estado in (EstadoPedido.ABERTO, EstadoPedido.EM_PRODUCAO, EstadoPedido.EM_CONSUMO):
            self.itens.remove(item)

    def atualizar_estado(self, novo_estado: EstadoPedido):
        self.estado = novo_estado

    def fechar_pedido(self):
        if self.estado in (EstadoPedido.ABERTO, EstadoPedido.EM_PRODUCAO, EstadoPedido.EM_CONSUMO):
            self.estado = EstadoPedido.FECHADO

    def cancelar_pedido(self):
        if self.estado != EstadoPedido.FECHADO:
            self.estado = EstadoPedido.CANCELADO

    def __str__(self):
        return f"Pedido(ID={self.id}, Cliente={self.cliente}, Estado={self.estado.value}, Itens={self.itens})"

    class Pedidos:
        def __init__(self, db_path: str = "data/SysDB.db", is_admin: bool = False):
            self.db = DBProxy(db_path)
            self.is_admin = is_admin
            self._ensure_tables()

        def _ensure_tables(self):
            Lanche(db_path=self.db.db_path).close()
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS pedidos (
                    id TEXT PRIMARY KEY,
                    cliente TEXT NOT NULL,
                    estado TEXT NOT NULL,
                    estoque_baixado INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                )
                """,
                commit=True,
            )
            pedido_columns = {row["name"] for row in self.db.query_all("PRAGMA table_info(pedidos)")}
            self._pedido_tem_data_criacao = "data_criacao" in pedido_columns
            migrations = {
                "estoque_baixado": "ALTER TABLE pedidos ADD COLUMN estoque_baixado INTEGER NOT NULL DEFAULT 0",
                "created_at": "ALTER TABLE pedidos ADD COLUMN created_at TEXT",
                "updated_at": "ALTER TABLE pedidos ADD COLUMN updated_at TEXT",
            }
            for column, sql in migrations.items():
                if column not in pedido_columns:
                    self.db.execute(sql, commit=True)
            self._pedido_id_inteiro = any(
                row["name"] == "id" and "INT" in (row["type"] or "").upper()
                for row in self.db.query_all("PRAGMA table_info(pedidos)")
            )
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS pedido_itens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pedido_id TEXT NOT NULL,
                    estoque_id INTEGER NOT NULL,
                    nome TEXT NOT NULL,
                    quantidade REAL NOT NULL,
                    unidade TEXT NOT NULL,
                    validade DATE,
                    FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
                    FOREIGN KEY (estoque_id) REFERENCES estoque(id)
                )
                """,
                commit=True,
            )
            item_columns = {row["name"] for row in self.db.query_all("PRAGMA table_info(pedido_itens)")}
            self._item_schema_legado = "nome_item" in item_columns
            if self._item_schema_legado:
                if "nome" not in item_columns:
                    self.db.execute("ALTER TABLE pedido_itens ADD COLUMN nome TEXT", commit=True)
                if "validade" not in item_columns:
                    self.db.execute("ALTER TABLE pedido_itens ADD COLUMN validade DATE", commit=True)
                self.db.execute("UPDATE pedido_itens SET nome = nome_item WHERE nome IS NULL", commit=True)
            else:
                self._item_schema_legado = False

        @staticmethod
        def _estado(estado):
            if isinstance(estado, EstadoPedido):
                return estado
            normalized = str(estado).strip().lower()
            for item in EstadoPedido:
                if normalized in (item.value.lower(), item.name.lower()):
                    return item
            raise ValueError(f"estado de pedido inválido: {estado}")

        def _novo_pedido_id(self):
            if self._pedido_id_inteiro:
                row = self.db.query_one("SELECT COALESCE(MAX(id), 0) + 1 AS proximo_id FROM pedidos")
                return row["proximo_id"]
            return str(uuid.uuid4())

        def _inserir_itens(self, pedido_id, alocados):
            if self._item_schema_legado:
                sql = "INSERT INTO pedido_itens (pedido_id, estoque_id, nome_item, categoria, unidade, quantidade) VALUES (?, ?, ?, ?, ?, ?)"
                values = ((pedido_id, lote["id"], lote["nome"], lote["categoria"], lote["unidade"], quantidade)
                          for lote, quantidade in alocados)
            else:
                sql = "INSERT INTO pedido_itens (pedido_id, estoque_id, nome, quantidade, unidade, validade) VALUES (?, ?, ?, ?, ?, ?)"
                values = ((pedido_id, lote["id"], lote["nome"], quantidade, lote["unidade"], lote["vencimento"])
                          for lote, quantidade in alocados)
            self.db.executemany(sql, values)

        @staticmethod
        def _item_values(item):
            if isinstance(item, dict):
                nome = item.get("nome")
                quantidade = item.get("quantidade", item.get("qtd_disponivel"))
            else:
                nome, quantidade = item
            if not nome or quantidade is None or float(quantidade) <= 0:
                raise ValueError("cada item deve ter nome e quantidade maior que zero")
            return str(nome).strip(), float(quantidade)

        def _alocar_itens(self, itens):
            alocados = []
            for item in itens:
                nome, quantidade = self._item_values(item)
                lotes = self.db.query_all(
                    """
                    SELECT id, nome, categoria, unidade, vencimento, qtd_disponivel
                    FROM estoque
                    WHERE ativo = 1 AND nome = ? AND qtd_disponivel > 0
                    ORDER BY CASE WHEN vencimento IS NULL THEN 1 ELSE 0 END, vencimento ASC, id ASC
                    """,
                    (nome,),
                )
                restante = quantidade
                for lote in lotes:
                    usado = min(restante, float(lote["qtd_disponivel"]))
                    alocados.append((lote, usado))
                    restante -= usado
                    if restante <= 0:
                        break
                if restante > 0:
                    raise ValueError(f"estoque insuficiente para '{nome}'")
            return alocados

        def _expandir_lanches(self, itens):
            expandidos = []
            for item in itens:
                if not isinstance(item, dict) or "lanche_id" not in item:
                    expandidos.append(item)
                    continue
                quantidade = float(item.get("quantidade", 0))
                if quantidade <= 0:
                    raise ValueError("a quantidade do lanche deve ser maior que zero")
                lanche = self.db.query_one(
                    "SELECT id, nome FROM lanches WHERE id = ? AND ativo = 1",
                    (item["lanche_id"],),
                )
                if not lanche:
                    raise ValueError("lanche não encontrado")
                componentes = self.db.query_all(
                    "SELECT item_nome, quantidade FROM lanche_itens WHERE lanche_id = ?",
                    (lanche["id"],),
                )
                if not componentes:
                    raise ValueError(f"o lanche '{lanche['nome']}' não possui receita")
                for componente in componentes:
                    expandidos.append({
                        "nome": componente["item_nome"],
                        "quantidade": float(componente["quantidade"]) * quantidade,
                    })
            return expandidos

        def adicionar(self, cliente, itens):
            if not cliente or not itens:
                raise ValueError("cliente e itens são obrigatórios")
            alocados = self._alocar_itens(self._expandir_lanches(itens))
            pedido_id = self._novo_pedido_id()
            now = datetime.utcnow().isoformat()
            with self.db.transaction():
                if self._pedido_tem_data_criacao:
                    self.db.execute(
                        "INSERT INTO pedidos (id, cliente, estado, data_criacao, created_at) VALUES (?, ?, ?, ?, ?)",
                        (pedido_id, cliente.strip(), EstadoPedido.ABERTO.value, now, now),
                    )
                else:
                    self.db.execute(
                        "INSERT INTO pedidos (id, cliente, estado, created_at) VALUES (?, ?, ?, ?)",
                        (pedido_id, cliente.strip(), EstadoPedido.ABERTO.value, now),
                    )
                self._inserir_itens(pedido_id, alocados)
            return pedido_id

        inserir = adicionar

        def obter(self, pedido_id):
            row = self.db.query_one("SELECT * FROM pedidos WHERE id = ?", (pedido_id,))
            return dict(row) if row else None

        def atualizar_cliente(self, pedido_id, cliente):
            cliente = (cliente or "").strip()
            if not cliente:
                raise ValueError("o nome do cliente é obrigatório")
            cursor = self.db.execute(
                "UPDATE pedidos SET cliente = ?, updated_at = ? WHERE id = ?",
                (cliente, datetime.utcnow().isoformat(), pedido_id),
                commit=True,
            )
            if cursor.rowcount == 0:
                raise ValueError("pedido não encontrado")
            return True

        def listar(self):
            rows = self.db.query_all("SELECT * FROM pedidos ORDER BY created_at ASC, id ASC")
            return [dict(row) for row in rows]

        def listar_itens(self, pedido_id):
            if self._item_schema_legado:
                sql = "SELECT id, pedido_id, estoque_id, nome_item AS nome, quantidade, unidade, validade FROM pedido_itens WHERE pedido_id = ? ORDER BY id"
            else:
                sql = "SELECT * FROM pedido_itens WHERE pedido_id = ? ORDER BY id"
            rows = self.db.query_all(sql, (pedido_id,))
            return [dict(row) for row in rows]

        def _baixar_estoque(self, pedido_id):
            itens = self.listar_itens(pedido_id)
            for item in itens:
                estoque = self.db.query_one(
                    "SELECT qtd_disponivel FROM estoque WHERE id = ? AND ativo = 1", (item["estoque_id"],)
                )
                if not estoque or float(estoque["qtd_disponivel"]) < item["quantidade"]:
                    raise ValueError(f"estoque insuficiente para '{item['nome']}'")
            for item in itens:
                self.db.execute(
                    "UPDATE estoque SET qtd_disponivel = qtd_disponivel - ?, updated_at = ? WHERE id = ?",
                    (item["quantidade"], datetime.utcnow().isoformat(), item["estoque_id"]),
                )

        def atualizar_estado(self, pedido_id, novo_estado):
            novo_estado = self._estado(novo_estado)
            pedido = self.obter(pedido_id)
            if not pedido:
                raise ValueError("pedido não encontrado")
            estado_atual = self._estado(pedido["estado"])
            if estado_atual == novo_estado:
                return True
            if estado_atual in (EstadoPedido.FECHADO, EstadoPedido.CANCELADO):
                raise ValueError("pedido encerrado não pode ser movido")
            with self.db.transaction():
                if novo_estado == EstadoPedido.EM_CONSUMO and not pedido["estoque_baixado"]:
                    self._baixar_estoque(pedido_id)
                    self.db.execute("UPDATE pedidos SET estoque_baixado = 1 WHERE id = ?", (pedido_id,))
                self.db.execute(
                    "UPDATE pedidos SET estado = ?, updated_at = ? WHERE id = ?",
                    (novo_estado.value, datetime.utcnow().isoformat(), pedido_id),
                )
            return True

        def adicionar_itens(self, pedido_id, itens):
            pedido = self.obter(pedido_id)
            if not pedido or self._estado(pedido["estado"]) not in (EstadoPedido.ABERTO, EstadoPedido.EM_PRODUCAO, EstadoPedido.EM_CONSUMO):
                raise ValueError("só é possível editar pedidos em produção ou em consumo")
            alocados = self._alocar_itens(self._expandir_lanches(itens))
            with self.db.transaction():
                if self._estado(pedido["estado"]) == EstadoPedido.EM_CONSUMO:
                    for lote, quantidade in alocados:
                        estoque = self.db.query_one(
                            "SELECT qtd_disponivel FROM estoque WHERE id = ? AND ativo = 1", (lote["id"],)
                        )
                        if not estoque or float(estoque["qtd_disponivel"]) < quantidade:
                            raise ValueError(f"estoque insuficiente para '{lote['nome']}'")
                        self.db.execute(
                            "UPDATE estoque SET qtd_disponivel = qtd_disponivel - ?, updated_at = ? WHERE id = ?",
                            (quantidade, datetime.utcnow().isoformat(), lote["id"]),
                        )
                self._inserir_itens(pedido_id, alocados)
                self.db.execute("UPDATE pedidos SET updated_at = ? WHERE id = ?",
                                (datetime.utcnow().isoformat(), pedido_id))

        def excluir(self, pedido_id):
            if not self.is_admin:
                raise PermissionError("somente administradores podem excluir pedidos")
            pedido = self.obter(pedido_id)
            if not pedido:
                raise ValueError("pedido não encontrado")
            with self.db.transaction():
                if pedido["estoque_baixado"]:
                    for item in self.listar_itens(pedido_id):
                        self.db.execute(
                            "UPDATE estoque SET qtd_disponivel = qtd_disponivel + ?, updated_at = ? WHERE id = ?",
                            (item["quantidade"], datetime.utcnow().isoformat(), item["estoque_id"]),
                        )
                self.db.execute("DELETE FROM pedido_itens WHERE pedido_id = ?", (pedido_id,))
                cursor = self.db.execute("DELETE FROM pedidos WHERE id = ?", (pedido_id,))
            if cursor.rowcount == 0:
                raise ValueError("pedido não encontrado")
            return True

        def remover_itens(self, pedido_id, item_ids):
            item_ids = list(item_ids)
            if not item_ids:
                return
            pedido = self.obter(pedido_id)
            if not pedido:
                raise ValueError("pedido não encontrado")
            if self._estado(pedido["estado"]) in (EstadoPedido.FECHADO, EstadoPedido.CANCELADO):
                raise ValueError("não é possível remover itens de um pedido encerrado")
            items = [item for item in self.listar_itens(pedido_id) if item["id"] in item_ids]
            with self.db.transaction():
                if pedido["estoque_baixado"]:
                    for item in items:
                        self.db.execute(
                            "UPDATE estoque SET qtd_disponivel = qtd_disponivel + ?, updated_at = ? WHERE id = ?",
                            (item["quantidade"], datetime.utcnow().isoformat(), item["estoque_id"]),
                        )
                for item_id in item_ids:
                    self.db.execute(
                        "DELETE FROM pedido_itens WHERE id = ? AND pedido_id = ?",
                        (item_id, pedido_id),
                    )
                self.db.execute(
                    "UPDATE pedidos SET updated_at = ? WHERE id = ?",
                    (datetime.utcnow().isoformat(), pedido_id),
                )

        def close(self):
            self.db.close()

        def abrir_menu(self, app, login_instance, win=None, frame=None):
            if win is None or frame is None:
                win, frame = app._new_menu_window(login_instance, "Gestão de Pedidos")
            else:
                win.title("Gestão de Pedidos")
            self._render_menu(app, login_instance, win, frame)

        def _render_menu(self, app, login_instance, win, frame):
            for widget in frame.winfo_children():
                widget.destroy()
            title = tk.Label(frame, text="Gestão de Pedidos", font=("Segoe UI", 18, "bold"), bg=app.COLORS["canvas"], fg=app.COLORS["ink"])
            title.pack(pady=(4, 8))
            toolbar = tk.Frame(frame, bg=app.COLORS["canvas"])
            toolbar.pack(fill=tk.X, pady=(0, 8))
            board = tk.Frame(frame, bg=app.COLORS["canvas"])
            board.pack(expand=True, fill=tk.BOTH)

            def refresh():
                for child in board.winfo_children():
                    child.destroy()
                grouped = {estado: [] for estado in EstadoPedido}
                for pedido in self.listar():
                    grouped[self._estado(pedido["estado"])].append(pedido)
                for column, estado in enumerate(EstadoPedido):
                    panel = tk.Frame(board, bg=app.COLORS["surface"], bd=1, relief=tk.SOLID)
                    panel.grid(row=0, column=column, sticky="nsew", padx=3)
                    board.columnconfigure(column, weight=1)
                    tk.Label(panel, text=estado.value, font=("Segoe UI", 11, "bold"), bg=app.COLORS["primary"], fg="white", pady=6).pack(fill=tk.X)
                    for pedido in grouped[estado]:
                        card = tk.Frame(panel, bg=app.COLORS["surface"], bd=1, relief=tk.GROOVE, padx=6, pady=6)
                        card.pack(fill=tk.X, padx=5, pady=5)
                        tk.Label(card, text=pedido["cliente"], font=("Segoe UI", 10, "bold"), bg=app.COLORS["surface"], fg=app.COLORS["ink"]).pack(anchor=tk.W)
                        items = self.listar_itens(pedido["id"])
                        tk.Label(card, text="\n".join(f"{item['quantidade']:g} {item['unidade']} - {item['nome']}" for item in items), justify=tk.LEFT, anchor=tk.W, bg=app.COLORS["surface"], fg=app.COLORS["muted"]).pack(anchor=tk.W, pady=(3, 5))
                        actions = tk.Frame(card, bg=app.COLORS["surface"])
                        actions.pack(fill=tk.X, pady=(3, 0))
                        if estado not in (EstadoPedido.FECHADO, EstadoPedido.CANCELADO):
                            edit_button = tk.Button(actions, text="Atualizar", command=lambda p=pedido: open_form(p))
                            app._style_button(edit_button, "primary")
                            edit_button.configure(font=("Segoe UI", 9, "bold"), padx=6, pady=4)
                            edit_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
                        if self.is_admin:
                            def delete_order(current=pedido):
                                if not messagebox.askyesno(
                                    "Excluir pedido",
                                    f"Deseja excluir o pedido de {current['cliente']}?",
                                    parent=win,
                                ):
                                    return
                                try:
                                    self.excluir(current["id"])
                                except (PermissionError, ValueError) as error:
                                    messagebox.showerror("Pedidos", str(error), parent=win)
                                    return
                                refresh()

                            delete_button = tk.Button(actions, text="Excluir", command=delete_order)
                            app._style_button(delete_button, "danger")
                            delete_button.configure(font=("Segoe UI", 9, "bold"), padx=6, pady=4)
                            delete_button.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(4, 0))

            def open_form(pedido=None):
                form = tk.Toplevel(win)
                form.title("Editar pedido" if pedido else "Novo pedido")
                form.transient(win)
                form.grab_set()
                form.configure(bg=app.COLORS["canvas"])
                form.geometry("760x760")
                form.resizable(False, False)
                heading = tk.Label(
                    form,
                    text="Editar pedido" if pedido else "Novo pedido",
                    font=("Segoe UI", 16, "bold"),
                    bg=app.COLORS["canvas"],
                    fg=app.COLORS["ink"],
                )
                heading.pack(anchor=tk.W, padx=24, pady=(18, 8))
                body = tk.Frame(form, padx=24, pady=14, bg=app.COLORS["canvas"])
                body.pack(fill=tk.BOTH, expand=True)
                body.columnconfigure(1, weight=1)
                label_style = {"bg": app.COLORS["canvas"], "fg": app.COLORS["ink"], "font": ("Segoe UI", 10, "bold")}
                entry_style = {"bg": app.COLORS["surface"], "fg": app.COLORS["ink"], "insertbackground": app.COLORS["ink"], "relief": tk.SOLID, "borderwidth": 1}
                tk.Label(body, text="Cliente:", **label_style).grid(row=0, column=0, sticky=tk.W, pady=6)
                cliente = tk.Entry(body, width=48, **entry_style)
                cliente.grid(row=0, column=1, sticky=tk.EW, pady=4)
                if pedido:
                    cliente.insert(0, pedido["cliente"])
                selected_items = {}
                selected_lanches = {}
                existing_items = self.listar_itens(pedido["id"]) if pedido else []
                original_item_ids = {item["id"] for item in existing_items}
                tk.Label(body, text="Categorias:", **label_style).grid(row=1, column=0, sticky=tk.W, pady=(12, 6))
                tk.Label(body, text="Itens da categoria:", **label_style).grid(row=1, column=1, sticky=tk.W, pady=(12, 6))
                list_style = {"bg": app.COLORS["surface"], "fg": app.COLORS["ink"], "selectbackground": app.COLORS["primary"], "selectforeground": "white", "relief": tk.SOLID, "borderwidth": 1, "highlightthickness": 0}
                category_list = tk.Listbox(body, height=7, width=28, exportselection=False, **list_style)
                category_list.grid(row=2, column=0, sticky=tk.EW, padx=(0, 10), pady=4)
                item_list = tk.Listbox(body, height=7, width=38, exportselection=False, **list_style)
                item_list.grid(row=2, column=1, sticky=tk.EW, pady=4)
                quantity_frame = tk.Frame(body, bg=app.COLORS["canvas"])
                quantity_frame.grid(row=3, column=1, sticky=tk.W, pady=(10, 4))
                tk.Label(quantity_frame, text="Quantidade:", **label_style).pack(side=tk.LEFT)
                quantity_entry = tk.Entry(quantity_frame, width=10, **entry_style)
                quantity_entry.pack(side=tk.LEFT, padx=6)
                lanche_options = {}
                lanche_choice = ttk.Combobox(quantity_frame, state="readonly", width=24)
                lanche_choice.pack(side=tk.LEFT, padx=(12, 6))
                selected_label = "Itens a acrescentar:" if pedido else "Itens selecionados:"
                tk.Label(body, text=selected_label, **label_style).grid(row=4, column=0, sticky=tk.W, pady=(12, 6))
                selected_list = tk.Listbox(body, height=5, width=58, **list_style)
                selected_list.grid(row=4, column=1, sticky=tk.EW, pady=4)

                def render_selected_items():
                    selected_list.delete(0, tk.END)
                    for item in existing_items:
                        selected_list.insert(tk.END, f"Atual: {item['nome']} = {item['quantidade']:g}")
                    for name, quantity in selected_items.items():
                        selected_list.insert(tk.END, f"Novo: {name} = {quantity:g}")
                    for name, quantity in selected_lanches.values():
                        selected_list.insert(tk.END, f"Lanche: {name} = {quantity:g}")

                categories = [row["categoria"] or "Sem categoria" for row in self.db.query_all(
                    "SELECT DISTINCT categoria FROM estoque WHERE ativo = 1 ORDER BY categoria"
                )]
                category_list.insert(tk.END, *categories)
                for row in self.db.query_all(
                    "SELECT id, nome FROM lanches WHERE ativo = 1 ORDER BY nome"
                ):
                    lanche_options[row["nome"]] = row["id"]
                lanche_choice["values"] = tuple(lanche_options)

                def load_items(_event=None):
                    selection = category_list.curselection()
                    if not selection:
                        return
                    category = category_list.get(selection[0])
                    item_list.delete(0, tk.END)
                    rows = self.db.query_all(
                        """
                        SELECT DISTINCT nome FROM estoque
                        WHERE ativo = 1 AND (categoria = ? OR (categoria IS NULL AND ? = 'Sem categoria'))
                          AND qtd_disponivel > 0
                        ORDER BY nome
                        """,
                        (category, category),
                    )
                    item_list.insert(tk.END, *(row["nome"] for row in rows))

                def add_selected_item():
                    try:
                        item_selection = item_list.curselection()
                        if not item_selection:
                            raise ValueError("selecione um item")
                        quantity = float(quantity_entry.get().strip())
                        if quantity <= 0:
                            raise ValueError("a quantidade deve ser maior que zero")
                        name = item_list.get(item_selection[0])
                        selected_items[name] = selected_items.get(name, 0) + quantity
                        render_selected_items()
                        quantity_entry.delete(0, tk.END)
                    except (TypeError, ValueError) as error:
                        messagebox.showerror("Itens do pedido", str(error), parent=form)

                def add_selected_lanche():
                    try:
                        name = lanche_choice.get().strip()
                        if not name:
                            raise ValueError("selecione um lanche")
                        quantity = float(quantity_entry.get().strip())
                        if quantity <= 0:
                            raise ValueError("a quantidade deve ser maior que zero")
                        lanche_id = lanche_options[name]
                        current = selected_lanches.get(lanche_id, (name, 0))[1]
                        selected_lanches[lanche_id] = (name, current + quantity)
                        render_selected_items()
                        quantity_entry.delete(0, tk.END)
                    except (KeyError, TypeError, ValueError) as error:
                        messagebox.showerror("Lanches do pedido", str(error), parent=form)

                category_list.bind("<<ListboxSelect>>", load_items)
                add_item_button = tk.Button(quantity_frame, text="Adicionar item", command=add_selected_item)
                app._style_button(add_item_button, "primary")
                add_item_button.pack(side=tk.LEFT)
                add_lanche_button = tk.Button(quantity_frame, text="Adicionar lanche", command=add_selected_lanche)
                app._style_button(add_lanche_button, "success")
                add_lanche_button.pack(side=tk.LEFT, padx=(6, 0))
                render_selected_items()

                def remove_selected_item():
                    selection = selected_list.curselection()
                    if not selection:
                        messagebox.showwarning("Itens do pedido", "Selecione um item para excluir.", parent=form)
                        return
                    selected_index = selection[0]
                    if selected_index < len(existing_items):
                        existing_items.pop(selected_index)
                    elif selected_index < len(existing_items) + len(selected_items):
                        new_items = list(selected_items)
                        selected_items.pop(new_items[selected_index - len(existing_items)])
                    else:
                        lanche_items = list(selected_lanches)
                        selected_lanches.pop(lanche_items[selected_index - len(existing_items) - len(selected_items)])
                    render_selected_items()

                remove_item_button = tk.Button(body, text="Excluir item selecionado", command=remove_selected_item)
                app._style_button(remove_item_button, "danger")
                remove_item_button.grid(row=5, column=1, sticky=tk.W, pady=(4, 8))

                state_row = 6
                tk.Label(body, text="Estado:", **label_style).grid(row=state_row, column=0, sticky=tk.W, pady=6)
                combo_style = ttk.Style(form)
                combo_style.configure("Pedido.TCombobox", fieldbackground=app.COLORS["surface"], foreground=app.COLORS["ink"])
                estado = ttk.Combobox(body, values=[item.value for item in EstadoPedido], state="readonly", width=28, style="Pedido.TCombobox")
                estado.grid(row=state_row, column=1, sticky=tk.W, pady=4)
                estado.set(self._estado(pedido["estado"]).value if pedido else EstadoPedido.ABERTO.value)

                def parse_items():
                    items = [{"nome": name, "quantidade": quantity} for name, quantity in selected_items.items()]
                    items.extend(
                        {"lanche_id": lanche_id, "quantidade": quantity}
                        for lanche_id, (_name, quantity) in selected_lanches.items()
                    )
                    return items

                def save():
                    try:
                        values = parse_items()
                        if pedido:
                            removed_ids = original_item_ids - {item["id"] for item in existing_items}
                            self.remover_itens(pedido["id"], removed_ids)
                            self.atualizar_cliente(pedido["id"], cliente.get())
                            if values:
                                self.adicionar_itens(pedido["id"], values)
                            self.atualizar_estado(pedido["id"], estado.get())
                        else:
                            self.adicionar(cliente.get().strip(), values)
                    except (TypeError, ValueError) as error:
                        messagebox.showerror("Pedidos", str(error), parent=form)
                        return
                    form.destroy()
                    refresh()

                footer = tk.Frame(body, bg=app.COLORS["canvas"])
                footer.grid(row=7, column=0, columnspan=2, pady=(18, 0))
                save_button = tk.Button(footer, text="Salvar", command=save)
                app._style_button(save_button, "success")
                save_button.pack(side=tk.LEFT, padx=4)

            new_order_button = tk.Button(toolbar, text="Novo pedido", command=open_form)
            app._style_button(new_order_button, "success")
            new_order_button.pack(side=tk.LEFT)
            refresh_button = tk.Button(toolbar, text="Atualizar", command=refresh)
            app._style_button(refresh_button, "primary")
            refresh_button.pack(side=tk.LEFT, padx=8)
            refresh()


Pedidos = Pedido.Pedidos
