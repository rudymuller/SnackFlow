from datetime import datetime
from enum import Enum
import tkinter as tk
from tkinter import messagebox, ttk
import uuid

from const import DB_PATH
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
        def __init__(self, db_path: str = DB_PATH, is_admin: bool = False):
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
                    valor_total REAL NOT NULL DEFAULT 0,
                    observacao TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    data_fechamento TEXT
                )
                """,
                commit=True,
            )
            pedido_columns = {row["name"] for row in self.db.query_all("PRAGMA table_info(pedidos)")}
            self._pedido_tem_data_criacao = "data_criacao" in pedido_columns
            migrations = {
                "estoque_baixado": "ALTER TABLE pedidos ADD COLUMN estoque_baixado INTEGER NOT NULL DEFAULT 0",
                "valor_total": "ALTER TABLE pedidos ADD COLUMN valor_total REAL NOT NULL DEFAULT 0",
                "observacao": "ALTER TABLE pedidos ADD COLUMN observacao TEXT",
                "created_at": "ALTER TABLE pedidos ADD COLUMN created_at TEXT",
                "updated_at": "ALTER TABLE pedidos ADD COLUMN updated_at TEXT",
                "data_fechamento": "ALTER TABLE pedidos ADD COLUMN data_fechamento TEXT",
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
                    preco_unitario REAL NOT NULL DEFAULT 0,
                    valor_total REAL NOT NULL DEFAULT 0,
                    lanche_nome TEXT,
                    lanche_quantidade REAL,
                    validade DATE,
                    FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
                    FOREIGN KEY (estoque_id) REFERENCES estoque(id)
                )
                """,
                commit=True,
            )
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS pedido_lanches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pedido_id TEXT NOT NULL,
                    lanche_id INTEGER NOT NULL,
                    nome TEXT NOT NULL,
                    quantidade REAL NOT NULL,
                    FOREIGN KEY (pedido_id) REFERENCES pedidos(id)
                )
                """,
                commit=True,
            )
            item_columns = {row["name"] for row in self.db.query_all("PRAGMA table_info(pedido_itens)")}
            for column, sql in {
                "preco_unitario": "ALTER TABLE pedido_itens ADD COLUMN preco_unitario REAL NOT NULL DEFAULT 0",
                "valor_total": "ALTER TABLE pedido_itens ADD COLUMN valor_total REAL NOT NULL DEFAULT 0",
                "lanche_nome": "ALTER TABLE pedido_itens ADD COLUMN lanche_nome TEXT",
                "lanche_quantidade": "ALTER TABLE pedido_itens ADD COLUMN lanche_quantidade REAL",
            }.items():
                if column not in item_columns:
                    self.db.execute(sql, commit=True)
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
            def item_price(lote):
                if (lote["categoria"] or "").strip().lower() == "ingredientes":
                    return 0.0
                return float(lote["preco_venda"] or 0)

            if self._item_schema_legado:
                sql = "INSERT INTO pedido_itens (pedido_id, estoque_id, nome_item, categoria, unidade, quantidade, preco_unitario, valor_total, lanche_nome, lanche_quantidade) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                values = ((pedido_id, lote["id"], lote["nome"], lote["categoria"], lote["unidade"], quantidade,
                           item_price(lote), quantidade * item_price(lote), lanche_nome, lanche_quantidade)
                          for lote, quantidade, lanche_nome, lanche_quantidade in alocados)
            else:
                sql = "INSERT INTO pedido_itens (pedido_id, estoque_id, nome, quantidade, unidade, preco_unitario, valor_total, lanche_nome, lanche_quantidade, validade) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                values = ((pedido_id, lote["id"], lote["nome"], quantidade, lote["unidade"],
                           item_price(lote), quantidade * item_price(lote), lanche_nome, lanche_quantidade, lote["vencimento"])
                          for lote, quantidade, lanche_nome, lanche_quantidade in alocados)
            self.db.executemany(sql, values)

        def _inserir_lanches(self, pedido_id, itens):
            values = []
            for item in itens:
                if "lanche_id" not in item:
                    continue
                lanche = self.db.query_one(
                    "SELECT nome FROM lanches WHERE id = ? AND ativo = 1",
                    (item["lanche_id"],),
                )
                if lanche:
                    values.append((pedido_id, item["lanche_id"], lanche["nome"], item["quantidade"]))
            if values:
                self.db.executemany(
                    "INSERT INTO pedido_lanches (pedido_id, lanche_id, nome, quantidade) VALUES (?, ?, ?, ?)",
                    values,
                )

        @staticmethod
        def _item_values(item):
            if isinstance(item, dict):
                nome = item.get("nome")
                quantidade = item.get("quantidade", item.get("qtd_disponivel"))
                unidade = item.get("unidade")
                lanche_nome = item.get("lanche_nome")
                lanche_quantidade = item.get("lanche_quantidade")
            else:
                nome, quantidade = item[:2]
                unidade = item[2] if len(item) > 2 else None
                lanche_nome = None
                lanche_quantidade = None
            if not nome or quantidade is None or float(quantidade) <= 0:
                raise ValueError("cada item deve ter nome e quantidade maior que zero")
            return str(nome).strip(), float(quantidade), unidade, lanche_nome, lanche_quantidade

        @staticmethod
        def _is_weight_unit(unidade):
            return str(unidade or "").strip().lower() in {
                "g", "grama", "gramas", "gram", "kg", "quilo", "quilos", "kilo", "kilos"
            }

        @classmethod
        def _to_grams(cls, quantidade, unidade):
            if str(unidade or "").strip().lower() in {"kg", "quilo", "quilos", "kilo", "kilos"}:
                return float(quantidade) * 1000
            return float(quantidade)

        @classmethod
        def _from_grams(cls, quantidade, unidade):
            if str(unidade or "").strip().lower() in {"kg", "quilo", "quilos", "kilo", "kilos"}:
                return float(quantidade) / 1000
            return float(quantidade)

        def _alocar_itens(self, itens):
            return self._alocar_itens_com_faltas(itens, permitir_faltantes=False)

        def _alocar_itens_com_faltas(self, itens, permitir_faltantes=False):
            alocados = []
            faltantes = []
            for item in itens:
                nome, quantidade, unidade, lanche_nome, lanche_quantidade = self._item_values(item)
                lotes = self.db.query_all(
                    """
                    SELECT id, nome, categoria, unidade, vencimento, qtd_disponivel, preco_venda
                    FROM estoque
                    WHERE ativo = 1 AND nome = ? AND qtd_disponivel > 0
                    ORDER BY CASE WHEN vencimento IS NULL THEN 1 ELSE 0 END, vencimento ASC, id ASC
                    """,
                    (nome,),
                )
                usa_peso = self._is_weight_unit(unidade)
                restante = self._to_grams(quantidade, unidade) if usa_peso else quantidade
                for lote in lotes:
                    disponivel = (
                        self._to_grams(lote["qtd_disponivel"], lote["unidade"])
                        if usa_peso else float(lote["qtd_disponivel"])
                    )
                    usado_base = min(restante, disponivel)
                    usado = (
                        self._from_grams(usado_base, lote["unidade"])
                        if usa_peso else usado_base
                    )
                    alocados.append((lote, usado, lanche_nome, lanche_quantidade))
                    restante -= usado_base
                    if restante <= 0:
                        break
                if restante > 0:
                    if not permitir_faltantes:
                        raise ValueError(f"estoque insuficiente para '{nome}'")
                    faltantes.append(nome)
            return alocados, faltantes

        def verificar_faltantes(self, itens):
            _, faltantes = self._alocar_itens_com_faltas(
                self._expandir_lanches(itens), permitir_faltantes=True
            )
            return list(dict.fromkeys(faltantes))

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
                    "SELECT item_nome, quantidade, unidade FROM lanche_itens WHERE lanche_id = ?",
                    (lanche["id"],),
                )
                if not componentes:
                    raise ValueError(f"o lanche '{lanche['nome']}' não possui receita")
                for componente in componentes:
                    expandidos.append({
                        "nome": componente["item_nome"],
                        "quantidade": float(componente["quantidade"]) * quantidade,
                        "unidade": componente["unidade"],
                        "lanche_nome": lanche["nome"],
                        "lanche_quantidade": quantidade,
                    })
            return expandidos

        def _valor_lanches(self, itens):
            total = 0.0
            for item in itens:
                if not isinstance(item, dict) or "lanche_id" not in item:
                    continue
                quantidade = float(item.get("quantidade", 0))
                lanche = self.db.query_one(
                    "SELECT preco FROM lanches WHERE id = ? AND ativo = 1",
                    (item["lanche_id"],),
                )
                if lanche:
                    total += float(lanche["preco"]) * quantidade
            return total

        def _valor_itens(self, itens, permitir_faltantes=False):
            itens_diretos = [item for item in itens if "lanche_id" not in item]
            alocados, _ = self._alocar_itens_com_faltas(
                itens_diretos, permitir_faltantes=permitir_faltantes
            )
            return sum(
                quantidade * (
                    0 if (lote["categoria"] or "").strip().lower() == "ingredientes"
                    else float(lote["preco_venda"] or 0)
                )
                for lote, quantidade, _lanche_nome, _lanche_quantidade in alocados
            )

        def adicionar(self, cliente, itens, observacao=None, permitir_faltantes=False):
            if not cliente or not itens:
                raise ValueError("cliente e itens são obrigatórios")
            alocados, _ = self._alocar_itens_com_faltas(
                self._expandir_lanches(itens), permitir_faltantes=permitir_faltantes
            )
            valor_total = self._valor_lanches(itens) + self._valor_itens(itens, permitir_faltantes)
            pedido_id = self._novo_pedido_id()
            now = datetime.utcnow().isoformat()
            with self.db.transaction():
                if self._pedido_tem_data_criacao:
                    self.db.execute(
                        "INSERT INTO pedidos (id, cliente, estado, data_criacao, valor_total, observacao, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (pedido_id, cliente.strip(), EstadoPedido.ABERTO.value, now, valor_total, observacao, now),
                    )
                else:
                    self.db.execute(
                        "INSERT INTO pedidos (id, cliente, estado, valor_total, observacao, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (pedido_id, cliente.strip(), EstadoPedido.ABERTO.value, valor_total, observacao, now),
                    )
                self._inserir_lanches(pedido_id, itens)
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

        def atualizar_observacao(self, pedido_id, observacao):
            self.db.execute(
                "UPDATE pedidos SET observacao = ?, updated_at = ? WHERE id = ?",
                ((observacao or "").strip() or None, datetime.utcnow().isoformat(), pedido_id),
                commit=True,
            )

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
                if novo_estado == EstadoPedido.FECHADO and not pedido["estoque_baixado"]:
                    self._baixar_estoque(pedido_id)
                    self.db.execute("UPDATE pedidos SET estoque_baixado = 1 WHERE id = ?", (pedido_id,))
                data_fechamento = datetime.utcnow().isoformat() if novo_estado == EstadoPedido.FECHADO else None
                self.db.execute(
                    """
                    UPDATE pedidos
                    SET estado = ?, updated_at = ?, data_fechamento =
                        CASE WHEN ? IS NULL THEN data_fechamento ELSE ? END
                    WHERE id = ?
                    """,
                    (novo_estado.value, datetime.utcnow().isoformat(), data_fechamento,
                     data_fechamento, pedido_id),
                )
            return True

        def adicionar_itens(self, pedido_id, itens, permitir_faltantes=False):
            pedido = self.obter(pedido_id)
            if not pedido or self._estado(pedido["estado"]) not in (EstadoPedido.ABERTO, EstadoPedido.EM_PRODUCAO, EstadoPedido.EM_CONSUMO):
                raise ValueError("só é possível editar pedidos em produção ou em consumo")
            alocados, _ = self._alocar_itens_com_faltas(
                self._expandir_lanches(itens), permitir_faltantes=permitir_faltantes
            )
            valor_adicional = self._valor_lanches(itens) + self._valor_itens(itens, permitir_faltantes)
            with self.db.transaction():
                self._inserir_lanches(pedido_id, itens)
                self._inserir_itens(pedido_id, alocados)
                self.db.execute(
                    "UPDATE pedidos SET valor_total = valor_total + ?, updated_at = ? WHERE id = ?",
                    (valor_adicional, datetime.utcnow().isoformat(), pedido_id),
                )

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
                self.db.execute("DELETE FROM pedido_lanches WHERE pedido_id = ?", (pedido_id,))
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

            def open_lanche_management():
                """Abre o cadastro de lanches mantendo a janela de gestão atual."""
                from LancheView import LancheView
                LancheView(self.db.db_path).abrir(app, login_instance, win, frame)

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
                        if pedido.get("observacao"):
                            tk.Label(card, text=f"Obs.: {pedido['observacao']}", font=("Segoe UI", 9), bg=app.COLORS["surface"], fg=app.COLORS["muted"], wraplength=220, justify=tk.LEFT).pack(anchor=tk.W, pady=(2, 0))
                        items = self.listar_itens(pedido["id"])
                        displayed_items = []
                        displayed_lanches = set()
                        saved_lanches = self.db.query_all(
                            "SELECT nome, quantidade FROM pedido_lanches WHERE pedido_id = ?",
                            (pedido["id"],),
                        )
                        displayed_lanches.update(
                            (item["nome"], float(item["quantidade"]))
                            for item in saved_lanches
                        )
                        for item in items:
                            if item.get("lanche_nome"):
                                displayed_lanches.add(
                                    (item["lanche_nome"], item.get("lanche_quantidade") or 1)
                                )
                            else:
                                displayed_items.append(
                                    f"{item['quantidade']:g} {item['unidade']} - {item['nome']}"
                                )
                        displayed_items.extend(
                            f"{quantity:g}x Lanche - {name}"
                            for name, quantity in displayed_lanches
                        )
                        tk.Label(card, text="\n".join(displayed_items), justify=tk.LEFT, anchor=tk.W, bg=app.COLORS["surface"], fg=app.COLORS["muted"]).pack(anchor=tk.W, pady=(3, 5))
                        actions = tk.Frame(card, bg=app.COLORS["surface"])
                        actions.pack(fill=tk.X, pady=(3, 0))
                        if estado not in (EstadoPedido.FECHADO, EstadoPedido.CANCELADO):
                            state_choice = ttk.Combobox(
                                actions,
                                values=[item.value for item in EstadoPedido],
                                state="readonly",
                                width=16,
                            )
                            state_choice.set(estado.value)
                            state_choice.pack(side=tk.LEFT, padx=(0, 4))

                            def change_state(_event=None, current=pedido, choice=state_choice):
                                new_state = choice.get()
                                try:
                                    self.atualizar_estado(current["id"], new_state)
                                except (TypeError, ValueError) as error:
                                    choice.set(current["estado"])
                                    messagebox.showerror("Pedidos", str(error), parent=win)
                                    return
                                refresh()

                            state_choice.bind("<<ComboboxSelected>>", change_state)
                            edit_button = tk.Button(actions, text="Atualizar", command=lambda p=pedido: open_form(p))
                            app._style_button(edit_button, "primary")
                            edit_button.configure(font=("Segoe UI", 9, "bold"), padx=6, pady=4)
                            edit_button.pack(side=tk.LEFT, expand=True, fill=tk.X)
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
                form.geometry("820x820")
                form.resizable(False, False)
                heading = tk.Label(
                    form,
                    text="Editar pedido" if pedido else "Novo pedido",
                    font=("Segoe UI", 18, "bold"),
                    bg=app.COLORS["canvas"],
                    fg=app.COLORS["ink"],
                )
                heading.pack(anchor=tk.W, padx=24, pady=(18, 8))
                body = tk.Frame(form, padx=24, pady=14, bg=app.COLORS["canvas"])
                body.pack(fill=tk.BOTH, expand=True)
                body.columnconfigure(1, weight=1)
                label_style = {"bg": app.COLORS["canvas"], "fg": app.COLORS["ink"], "font": ("Segoe UI", 11, "bold")}
                entry_style = {"bg": app.COLORS["surface"], "fg": app.COLORS["ink"], "insertbackground": app.COLORS["ink"], "relief": tk.SOLID, "borderwidth": 1, "font": ("Segoe UI", 11)}
                tk.Label(body, text="Cliente:", **label_style).grid(row=0, column=0, sticky=tk.W, pady=6)
                cliente = tk.Entry(body, width=56, **entry_style)
                cliente.grid(row=0, column=1, sticky=tk.EW, pady=4)
                if pedido:
                    cliente.insert(0, pedido["cliente"])
                tk.Label(body, text="Observação:", **label_style).grid(row=1, column=0, sticky=tk.W, pady=6)
                observacao = tk.Entry(body, width=56, **entry_style)
                observacao.grid(row=1, column=1, sticky=tk.EW, pady=4)
                if pedido and pedido.get("observacao"):
                    observacao.insert(0, pedido["observacao"])
                selected_items = {}
                selected_lanches = {}
                accepted_missing_lanches = set()
                existing_items = self.listar_itens(pedido["id"]) if pedido else []
                original_item_ids = {item["id"] for item in existing_items}
                tk.Label(body, text="Categorias:", **label_style).grid(row=2, column=0, sticky=tk.W, pady=(12, 6))
                tk.Label(body, text="Itens da categoria:", **label_style).grid(row=2, column=1, sticky=tk.W, pady=(12, 6))
                list_style = {"bg": app.COLORS["surface"], "fg": app.COLORS["ink"], "selectbackground": app.COLORS["primary"], "selectforeground": "white", "relief": tk.SOLID, "borderwidth": 1, "highlightthickness": 0, "font": ("Segoe UI", 11)}
                category_list = tk.Listbox(body, height=8, width=32, exportselection=False, **list_style)
                category_list.grid(row=3, column=0, sticky=tk.EW, padx=(0, 10), pady=4)
                item_list = tk.Listbox(body, height=8, width=44, exportselection=False, **list_style)
                item_list.grid(row=3, column=1, sticky=tk.EW, pady=4)
                quantity_frame = tk.Frame(body, bg=app.COLORS["canvas"])
                quantity_frame.grid(row=4, column=1, sticky=tk.W, pady=(10, 4))
                tk.Label(quantity_frame, text="Quantidade:", **label_style).pack(side=tk.LEFT)
                quantity_entry = ttk.Combobox(quantity_frame, values=tuple(str(value) for value in range(1, 21)), state="readonly", width=10)
                quantity_entry.pack(side=tk.LEFT, padx=6)
                quantity_entry.set("1")
                lanche_options = {}
                selected_label = "Itens a acrescentar:" if pedido else "Itens selecionados:"
                tk.Label(body, text=selected_label, **label_style).grid(row=6, column=0, sticky=tk.W, pady=(12, 6))
                selected_list = tk.Listbox(body, height=6, width=64, **list_style)
                selected_list.grid(row=6, column=1, sticky=tk.EW, pady=4)

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
                categories = [category for category in categories if category != "Ingredientes"]
                categories = list(dict.fromkeys(categories))
                for category in ("Salgados", "Doces", "Lanches"):
                    if category not in categories:
                        categories.append(category)
                category_list.insert(tk.END, *categories)
                for row in self.db.query_all(
                    "SELECT id, nome FROM lanches WHERE ativo = 1 ORDER BY nome"
                ):
                    lanche_options[row["nome"]] = row["id"]
                def load_items(_event=None):
                    selection = category_list.curselection()
                    if not selection:
                        return
                    category = category_list.get(selection[0])
                    item_list.delete(0, tk.END)
                    if category == "Lanches":
                        item_list.insert(tk.END, *lanche_options)
                        return
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
                        category_selection = category_list.curselection()
                        category = category_list.get(category_selection[0]) if category_selection else ""
                        if category == "Lanches":
                            lanche_id = lanche_options[name]
                            missing_items = self.verificar_faltantes([
                                {"lanche_id": lanche_id, "quantidade": quantity}
                            ])
                            if missing_items:
                                accepted = messagebox.askyesno(
                                    "Item faltante",
                                    f"O lanche '{name}' possui item sem estoque: {', '.join(missing_items)}.\n\nDeseja continuar?",
                                    parent=form,
                                )
                                if not accepted:
                                    return
                                accepted_missing_lanches.add(lanche_id)
                                current_note = observacao.get().strip()
                                missing_text = ", ".join(
                                    f'Sem "{item}"' for item in missing_items
                                )
                                note = f"{name} - {missing_text}"
                                observacao.delete(0, tk.END)
                                observacao.insert(0, f"{current_note}; {note}" if current_note else note)
                            current = selected_lanches.get(lanche_id, (name, 0))[1]
                            selected_lanches[lanche_id] = (name, current + quantity)
                        else:
                            selected_items[name] = selected_items.get(name, 0) + quantity
                        render_selected_items()
                        quantity_entry.delete(0, tk.END)
                        quantity_entry.set("1")
                    except (TypeError, ValueError) as error:
                        messagebox.showerror("Itens do pedido", str(error), parent=form)

                def consult_lanche_stock():
                    category_selection = category_list.curselection()
                    item_selection = item_list.curselection()
                    if not category_selection or category_list.get(category_selection[0]) != "Lanches":
                        messagebox.showwarning(
                            "Estoque do lanche",
                            "Selecione a categoria Lanches.",
                            parent=form,
                        )
                        return
                    if not item_selection:
                        messagebox.showwarning(
                            "Estoque do lanche",
                            "Selecione um lanche.",
                            parent=form,
                        )
                        return

                    lanche_name = item_list.get(item_selection[0])
                    lanche_id = lanche_options[lanche_name]
                    ingredients = self.db.query_all(
                        """
                        SELECT item_nome, quantidade, unidade
                        FROM lanche_itens
                        WHERE lanche_id = ?
                        ORDER BY id
                        """,
                        (lanche_id,),
                    )
                    popup = tk.Toplevel(form)
                    popup.title(f"Estoque: {lanche_name}")
                    popup.transient(form)
                    popup.grab_set()
                    popup.geometry("620x320")
                    popup.configure(bg=app.COLORS["canvas"])
                    tk.Label(
                        popup,
                        text=f"Ingredientes de {lanche_name}",
                        font=("Segoe UI", 14, "bold"),
                        bg=app.COLORS["canvas"],
                        fg=app.COLORS["ink"],
                    ).pack(pady=(12, 8))
                    stock_table = ttk.Treeview(
                        popup,
                        columns=("item", "receita", "disponivel", "unidade"),
                        show="headings",
                        height=8,
                    )
                    for column, heading, width in (
                        ("item", "Ingrediente", 190),
                        ("receita", "Usado por lanche", 130),
                        ("disponivel", "Disponível", 130),
                        ("unidade", "Unidade", 100),
                    ):
                        stock_table.heading(column, text=heading)
                        stock_table.column(column, width=width, anchor=tk.CENTER)
                    stock_table.pack(expand=True, fill=tk.BOTH, padx=12, pady=(0, 10))

                    for ingredient in ingredients:
                        available = self.db.query_one(
                            """
                            SELECT COALESCE(SUM(qtd_disponivel), 0) AS total
                            FROM estoque
                            WHERE nome = ? AND ativo = 1
                            """,
                            (ingredient["item_nome"],),
                        )
                        stock_table.insert(
                            "", tk.END,
                            values=(
                                ingredient["item_nome"],
                                f"{ingredient['quantidade']:g}",
                                f"{float(available['total']):g}",
                                ingredient["unidade"],
                            ),
                        )

                    close_button = tk.Button(popup, text="Fechar", command=popup.destroy)
                    app._style_button(close_button, "primary")
                    close_button.pack(pady=(0, 12))

                category_list.bind("<<ListboxSelect>>", load_items)
                add_item_button = tk.Button(quantity_frame, text="Adicionar item", command=add_selected_item)
                app._style_button(add_item_button, "primary")
                add_item_button.pack(side=tk.LEFT)
                consult_stock_button = tk.Button(
                    body,
                    text="Consultar estoque",
                    command=consult_lanche_stock,
                )
                app._style_button(consult_stock_button, "primary")
                consult_stock_button.grid(row=5, column=1, sticky=tk.W, pady=(2, 6))
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
                remove_item_button.grid(row=7, column=1, sticky=tk.W, pady=(4, 8))

                state_row = 8
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
                        missing_items = self.verificar_faltantes(values) if values else []
                        allow_missing = bool(missing_items)
                        direct_items = [item for item in values if "lanche_id" not in item]
                        direct_missing = self.verificar_faltantes(direct_items) if direct_items else []
                        unaccepted_lanches = []
                        for lanche_id, (_lanche_name, quantity) in selected_lanches.items():
                            if self.verificar_faltantes([
                                {"lanche_id": lanche_id, "quantidade": quantity}
                            ]) and lanche_id not in accepted_missing_lanches:
                                unaccepted_lanches.append(lanche_id)
                        if missing_items and (direct_missing or unaccepted_lanches):
                            missing_text = ", ".join(f"'{item}'" for item in missing_items)
                            accepted = messagebox.askyesno(
                                "Item faltante",
                                f"Os seguintes itens não estão disponíveis no estoque: {missing_text}.\n\nDeseja continuar mesmo assim?",
                                parent=form,
                            )
                            if not accepted:
                                return
                            allow_missing = True
                            note_parts = []
                            for lanche_id, (lanche_name, quantity) in selected_lanches.items():
                                lanche_missing = self.verificar_faltantes([
                                    {"lanche_id": lanche_id, "quantidade": quantity}
                                ])
                                if lanche_missing:
                                    missing_text = ", ".join(
                                        f'Sem "{item}"' for item in lanche_missing
                                    )
                                    note_parts.append(f"{lanche_name} - {missing_text}")
                            if direct_missing:
                                note_parts.extend(f'Sem "{item}"' for item in direct_missing)
                            note = "; ".join(note_parts)
                            current_note = observacao.get().strip()
                            observacao.delete(0, tk.END)
                            observacao.insert(0, f"{current_note}; {note}" if current_note else note)
                        if pedido:
                            removed_ids = original_item_ids - {item["id"] for item in existing_items}
                            self.remover_itens(pedido["id"], removed_ids)
                            self.atualizar_cliente(pedido["id"], cliente.get())
                            self.atualizar_observacao(pedido["id"], observacao.get())
                            if values:
                                self.adicionar_itens(pedido["id"], values, permitir_faltantes=allow_missing)
                            self.atualizar_estado(pedido["id"], estado.get())
                        else:
                            self.adicionar(
                                cliente.get().strip(), values, observacao.get(),
                                permitir_faltantes=allow_missing,
                            )
                    except (TypeError, ValueError) as error:
                        messagebox.showerror("Pedidos", str(error), parent=form)
                        return
                    form.destroy()
                    refresh()

                footer = tk.Frame(body, bg=app.COLORS["canvas"])
                footer.grid(row=9, column=0, columnspan=2, pady=(18, 0))
                save_button = tk.Button(footer, text="Salvar", command=save)
                app._style_button(save_button, "success")
                save_button.pack(side=tk.LEFT, padx=4)

            new_order_button = tk.Button(toolbar, text="Novo pedido", command=open_form)
            app._style_button(new_order_button, "success")
            new_order_button.pack(side=tk.LEFT)
            new_lanche_button = tk.Button(
                toolbar, text="Inserir novo lanche", command=open_lanche_management
            )
            app._style_button(new_lanche_button, "primary")
            new_lanche_button.pack(side=tk.LEFT, padx=8)
            refresh_button = tk.Button(toolbar, text="Atualizar", command=refresh)
            app._style_button(refresh_button, "primary")
            refresh_button.pack(side=tk.LEFT, padx=8)
            refresh()


Pedidos = Pedido.Pedidos
