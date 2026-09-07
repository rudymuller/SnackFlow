
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional

from DBProxy import DBProxy


class Estoque:
    def __init__(self, db_path: str = "data/SysDB.db"):
        self.db = DBProxy(db_path)
        self.dadosItem = {}
        self._ensure_table()

    def _ensure_table(self):
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS estoque (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                categoria TEXT,
                marca TEXT,
                fornecedor TEXT,
                vencimento DATE,
                qtd_minima REAL NOT NULL,
                unidade TEXT NOT NULL,
                qtd_disponivel REAL NOT NULL,
                data_compra DATE,
                lote TEXT,
                ativo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
            """,
            commit=True,
        )
        columns = {row["name"] for row in self.db.query_all("PRAGMA table_info(estoque)")}
        if "categoria" not in columns:
            self.db.execute("ALTER TABLE estoque ADD COLUMN categoria TEXT", commit=True)

    def adicionar(self, nome, marca, fornecedor, vencimento, qtd_minima, unidade,
                  qtd_disponivel, data_compra, lote, categoria=None) -> int:
        if not nome or not unidade:
            raise ValueError("nome e unidade são obrigatórios")
        now = datetime.utcnow().isoformat()
        cur = self.db.execute(
            """
            INSERT INTO estoque
                 (nome, categoria, marca, fornecedor, vencimento, qtd_minima, unidade,
                  qtd_disponivel, data_compra, lote, ativo, created_at)
              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
              (nome, categoria, marca, fornecedor, vencimento, qtd_minima, unidade,
             qtd_disponivel, data_compra, lote, now),
            commit=True,
        )
        self.dadosItem = self.obter(cur.lastrowid) or {}
        return cur.lastrowid

    def inserir_item(self, nome, marca, fornecedor, vencimento, qtd_minima, unidade,
                     qtd_disponivel, data_compra, lote, categoria=None):
        """Insere um item no estoque e retorna seu identificador."""
        return self.adicionar(nome, marca, fornecedor, vencimento, qtd_minima,
                              unidade, qtd_disponivel, data_compra, lote, categoria)

    def adicionar_compra(self, item_id: int, vencimento, qtd_disponivel,
                         data_compra, lote) -> int:
        """Registra uma nova compra de um item, mantendo o lançamento anterior."""
        item = self.obter(item_id)
        if not item or not item.get("ativo"):
            raise ValueError("item ativo não encontrado")
        if qtd_disponivel is None or float(qtd_disponivel) <= 0:
            raise ValueError("a quantidade da compra deve ser maior que zero")

        now = datetime.utcnow().isoformat()
        cur = self.db.execute(
            """
            INSERT INTO estoque
                (nome, categoria, marca, fornecedor, vencimento, qtd_minima, unidade,
                 qtd_disponivel, data_compra, lote, ativo, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (item["nome"], item.get("categoria"), item.get("marca"),
             item.get("fornecedor"), vencimento, item["qtd_minima"],
             item["unidade"], float(qtd_disponivel), data_compra, lote, now),
            commit=True,
        )
        self.dadosItem = self.obter(cur.lastrowid) or {}
        return cur.lastrowid

    def atualizar(self, item_id: int, **fields) -> bool:
        allowed = {"nome", "categoria", "marca", "fornecedor", "vencimento", "qtd_minima",
                   "unidade", "qtd_disponivel", "data_compra", "lote", "ativo"}
        set_parts = [f"{key} = ?" for key in fields if key in allowed]
        if not set_parts:
            return False
        params = [fields[key] for key in fields if key in allowed]
        set_parts.append("updated_at = ?")
        params.extend((datetime.utcnow().isoformat(), item_id))
        cur = self.db.execute(
            f"UPDATE estoque SET {', '.join(set_parts)} WHERE id = ?",
            params,
            commit=True,
        )
        if cur.rowcount:
            self.dadosItem = self.obter(item_id) or {}
        return cur.rowcount > 0

    def atualizar_item(self, **kwargs):
        """Atualiza o item carregado em dadosItem."""
        item_id = self.dadosItem.get("id")
        if item_id is None:
            return False
        return self.atualizar(item_id, **kwargs)

    def remover(self, item_id: int) -> bool:
        return self.atualizar(item_id, ativo=0)

    def excluir_item(self):
        """Exclusão lógica do item carregado em dadosItem."""
        item_id = self.dadosItem.get("id")
        return self.remover(item_id) if item_id is not None else False

    def obter(self, item_id: int) -> Optional[Dict[str, Any]]:
        row = self.db.query_one("SELECT * FROM estoque WHERE id = ?", (item_id,))
        return dict(row) if row else None

    def listar(self, include_inativos: bool = False) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM estoque"
        if not include_inativos:
            sql += " WHERE ativo = 1"
        rows = self.db.query_all(sql + " ORDER BY id DESC")
        return [dict(row) for row in rows]

    def agrupar_itens_semelhantes(self) -> List[Dict[str, Any]]:
        """Agrupa itens ativos e soma a quantidade disponível de cada grupo."""
        rows = self.db.query_all(
            """
            SELECT nome, categoria, marca, fornecedor, unidade,
                   SUM(qtd_disponivel) AS qtd_disponivel,
                   COUNT(*) AS quantidade_itens
            FROM estoque
            WHERE ativo = 1
            GROUP BY nome, categoria, marca, fornecedor, unidade
            ORDER BY nome, categoria, marca
            """
        )
        return [dict(row) for row in rows]

    def close(self):
        self.db.close()

    def abrir_menu(self, app, login_instance, win=None, frame=None):
        """Abre o estoque, reutilizando a janela atual quando disponível."""
        if win is None or frame is None:
            win, frame = app._new_menu_window(login_instance, "Gestão de Estoque")
        else:
            win.title("Gestão de Estoque")
        self._render_menu(app, login_instance, win, frame)

    @staticmethod
    def _voltar_menu_principal(app, login_instance, win, frame):
        app._render_main_menu_in_window(login_instance, win, frame)

    def _render_menu(self, app, login_instance, win, frame):
        for widget in frame.winfo_children():
            widget.destroy()

        title = tk.Label(frame, text="Gestão de Estoque", font=("Segoe UI", 18, "bold"))
        title.configure(bg=app.COLORS["canvas"], fg=app.COLORS["ink"])
        title.pack(pady=(4, 10))

        columns = ("id", "nome", "categoria", "marca", "fornecedor", "quantidade", "unidade", "validade")
        table = ttk.Treeview(frame, columns=columns, show="headings", height=10)
        headings = {
            "id": "ID", "nome": "Nome", "categoria": "Categoria", "marca": "Marca", "fornecedor": "Fornecedor",
            "quantidade": "Quantidade", "unidade": "Unidade", "validade": "Vencimento",
        }
        widths = {"id": 45, "nome": 130, "categoria": 100, "marca": 100, "fornecedor": 120,
                  "quantidade": 85, "unidade": 75, "validade": 100}
        for column in columns:
            table.heading(column, text=headings[column])
            table.column(column, width=widths[column], anchor=tk.CENTER)
        style = ttk.Style(frame)
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 10), background=app.COLORS["surface"],
                        fieldbackground=app.COLORS["surface"], foreground=app.COLORS["ink"])
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), background=app.COLORS["primary"],
                        foreground="white")
        style.map("Treeview", background=[("selected", app.COLORS["primary"])], foreground=[("selected", "white")])
        table.pack(expand=True, fill=tk.BOTH, pady=(0, 8))

        def refresh():
            for item in table.get_children():
                table.delete(item)
            for item in self.listar():
                table.insert("", tk.END, iid=str(item["id"]), values=(
                    item["id"], item["nome"], item["categoria"] or "", item["marca"] or "", item["fornecedor"] or "",
                    item["qtd_disponivel"], item["unidade"], item["vencimento"] or "",
                ))

        def selected_id():
            selection = table.selection()
            if not selection:
                messagebox.showwarning("Estoque", "Selecione um item.", parent=win)
                return None
            return int(selection[0])

        def open_form(item=None):
            form = tk.Toplevel(win)
            form.title("Editar item" if item else "Adicionar item")
            form.transient(win)
            form.grab_set()
            form_frame = tk.Frame(form, padx=14, pady=14)
            form_frame.pack(expand=True, fill=tk.BOTH)
            fields = [
                ("Nome", "nome"), ("Categoria", "categoria"), ("Marca", "marca"), ("Fornecedor", "fornecedor"),
                ("Vencimento", "vencimento"), ("Quantidade mínima", "qtd_minima"),
                ("Unidade", "unidade"), ("Quantidade disponível", "qtd_disponivel"),
                ("Data da compra", "data_compra"), ("Lote", "lote"),
            ]
            entries = {}
            for row, (label, key) in enumerate(fields):
                tk.Label(form_frame, text=label + ":").grid(row=row, column=0, sticky=tk.W, pady=3)
                entry = tk.Entry(form_frame, width=32)
                entry.grid(row=row, column=1, padx=(8, 0), pady=3)
                if item and item.get(key) is not None:
                    entry.insert(0, str(item[key]))
                entries[key] = entry

            def save():
                values = {key: entry.get().strip() or None for key, entry in entries.items()}
                try:
                    values["qtd_minima"] = float(values["qtd_minima"])
                    values["qtd_disponivel"] = float(values["qtd_disponivel"])
                    if item:
                        if not self.atualizar(item["id"], **values):
                            raise ValueError("item não encontrado")
                    else:
                        self.adicionar(**values)
                except (TypeError, ValueError) as error:
                    messagebox.showerror("Estoque", f"Dados inválidos: {error}", parent=form)
                    return
                form.destroy()
                refresh()

            tk.Button(form_frame, text="Salvar", command=save).grid(
                row=len(fields), column=0, columnspan=2, pady=(10, 0)
            )

        def add_item():
            open_form()

        def edit_item():
            item_id = selected_id()
            if item_id is not None:
                item = self.obter(item_id)
                if item:
                    open_form(item)

        def remove_item():
            item_id = selected_id()
            if item_id is not None and messagebox.askyesno(
                "Excluir item", "Deseja desativar o item selecionado?", parent=win
            ):
                self.remover(item_id)
                refresh()

        def add_purchase():
            item_id = selected_id()
            if item_id is not None:
                item = self.obter(item_id)
                if item:
                    self._open_purchase_form(win, item, refresh)

        actions = tk.Frame(frame)
        actions.pack(pady=(0, 8), anchor=tk.CENTER)
        buttons = [
            ("Adicionar", add_item, "success", 14),
            ("Editar", edit_item, "primary", 14),
            ("Excluir", remove_item, "danger", 14),
            ("Nova compra", add_purchase, "warning", 14),
            ("Agrupar semelhantes", lambda: self._show_grouped_items(win), "primary", 20),
        ]
        for text, command, tone, width in buttons:
            button = tk.Button(actions, text=text, width=width, command=command)
            app._style_button(button, tone)
            button.pack(side=tk.LEFT, padx=4)
        refresh()

        app._maximize_window(win)

    def _show_grouped_items(self, parent):
        window = tk.Toplevel(parent)
        window.title("Estoque agrupado")
        window.geometry("780x360")
        columns = ("nome", "categoria", "marca", "fornecedor", "unidade", "total", "itens")
        table = ttk.Treeview(window, columns=columns, show="headings")
        headings = {
            "nome": "Nome", "categoria": "Categoria", "marca": "Marca",
            "fornecedor": "Fornecedor", "unidade": "Unidade",
            "total": "Quantidade total", "itens": "Itens agrupados",
        }
        for column in columns:
            table.heading(column, text=headings[column])
            table.column(column, width=105, anchor=tk.CENTER)
        table.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        for item in self.agrupar_itens_semelhantes():
            table.insert("", tk.END, values=(
                item["nome"], item["categoria"] or "", item["marca"] or "",
                item["fornecedor"] or "", item["unidade"], item["qtd_disponivel"],
                item["quantidade_itens"],
            ))

    def _open_purchase_form(self, parent, item, on_saved):
        form = tk.Toplevel(parent)
        form.title("Registrar nova compra")
        form.transient(parent)
        form.grab_set()
        form_frame = tk.Frame(form, padx=14, pady=14)
        form_frame.pack(expand=True, fill=tk.BOTH)
        tk.Label(
            form_frame,
            text=f"Item: {item['nome']} | Categoria: {item.get('categoria') or 'Não informada'}",
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))

        fields = [
            ("Novo vencimento", "vencimento"),
            ("Quantidade comprada", "qtd_disponivel"),
            ("Data da compra", "data_compra"),
            ("Novo lote", "lote"),
        ]
        entries = {}
        for row, (label, key) in enumerate(fields, start=1):
            tk.Label(form_frame, text=label + ":").grid(row=row, column=0, sticky=tk.W, pady=3)
            entry = tk.Entry(form_frame, width=32)
            entry.grid(row=row, column=1, padx=(8, 0), pady=3)
            entries[key] = entry

        def save():
            values = {key: entry.get().strip() or None for key, entry in entries.items()}
            try:
                values["qtd_disponivel"] = float(values["qtd_disponivel"])
                self.adicionar_compra(item["id"], **values)
            except (TypeError, ValueError) as error:
                messagebox.showerror("Estoque", f"Dados inválidos: {error}", parent=form)
                return
            form.destroy()
            on_saved()

        tk.Button(form_frame, text="Registrar compra", command=save).grid(
            row=len(fields) + 1, column=0, columnspan=2, pady=(10, 0)
        )

    def __str__(self):
        if not self.dadosItem:
            return "Nenhum item cadastrado."
        status = "Ativo" if self.dadosItem["ativo"] else "Inativo"
        return (f"Item: {self.dadosItem['nome']}, Categoria: {self.dadosItem.get('categoria') or 'Não informada'}, "
            f"Marca: {self.dadosItem['marca']}, "
                f"Fornecedor: {self.dadosItem['fornecedor']}, "
                f"Qtd disponível: {self.dadosItem['qtd_disponivel']} {self.dadosItem['unidade']}, "
                f"Qtd mínima: {self.dadosItem['qtd_minima']}, "
                f"Vencimento: {self.dadosItem['vencimento']}, "
                f"Data compra: {self.dadosItem['data_compra']}, "
                f"Lote: {self.dadosItem['lote']}, Status: {status}")
