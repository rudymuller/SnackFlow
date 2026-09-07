from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, List, Optional

from DBProxy import DBProxy


class Lanche:
    """Cadastro de um lanche e dos itens do estoque que formam sua receita."""

    def __init__(self, nome: Optional[str] = None, preco: float = 0,
                 db_path: str = "data/SysDB.db"):
        self.db = DBProxy(db_path)
        self.id = None
        self.nome = nome
        self.preco = float(preco)
        self.dadosLanche: Dict[str, float] = {}
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS lanches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                preco REAL NOT NULL DEFAULT 0,
                ativo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
            """,
            commit=True,
        )
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS lanche_itens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lanche_id INTEGER NOT NULL,
                item_nome TEXT NOT NULL,
                quantidade REAL NOT NULL CHECK (quantidade > 0),
                UNIQUE (lanche_id, item_nome),
                FOREIGN KEY (lanche_id) REFERENCES lanches(id) ON DELETE CASCADE
            )
            """,
            commit=True,
        )

    def incluirItem(self, nome: str, quantidade: float = 1) -> None:
        nome = (nome or "").strip()
        quantidade = float(quantidade)
        if not nome or quantidade <= 0:
            raise ValueError("o item e sua quantidade devem ser válidos")
        if nome in self.dadosLanche:
            raise ValueError(f"o item '{nome}' já existe na receita")
        self.dadosLanche[nome] = quantidade

    def atualizarItem(self, nome: str, nova_quantidade: float) -> None:
        nome = (nome or "").strip()
        nova_quantidade = float(nova_quantidade)
        if nome not in self.dadosLanche:
            raise ValueError(f"o item '{nome}' não existe na receita")
        if nova_quantidade <= 0:
            raise ValueError("a quantidade deve ser maior que zero")
        self.dadosLanche[nome] = nova_quantidade

    def excluirItem(self, nome: str) -> None:
        if nome not in self.dadosLanche:
            raise ValueError(f"o item '{nome}' não existe na receita")
        del self.dadosLanche[nome]

    def salvar(self) -> int:
        nome = (self.nome or "").strip()
        if not nome:
            raise ValueError("o nome do lanche é obrigatório")
        if self.preco < 0:
            raise ValueError("o preço não pode ser negativo")
        if not self.dadosLanche:
            raise ValueError("o lanche deve ter pelo menos um item")
        now = datetime.utcnow().isoformat()
        with self.db.transaction():
            if self.id is None:
                cursor = self.db.execute(
                    "INSERT INTO lanches (nome, preco, created_at) VALUES (?, ?, ?)",
                    (nome, self.preco, now),
                )
                self.id = cursor.lastrowid
            else:
                self.db.execute(
                    "UPDATE lanches SET nome = ?, preco = ?, updated_at = ? WHERE id = ?",
                    (nome, self.preco, now, self.id),
                )
                self.db.execute("DELETE FROM lanche_itens WHERE lanche_id = ?", (self.id,))
            self.db.executemany(
                "INSERT INTO lanche_itens (lanche_id, item_nome, quantidade) VALUES (?, ?, ?)",
                ((self.id, item_nome, quantidade) for item_nome, quantidade in self.dadosLanche.items()),
            )
        return self.id

    @classmethod
    def obter(cls, lanche_id: int, db_path: str = "data/SysDB.db"):
        lanche = cls(db_path=db_path)
        row = lanche.db.query_one(
            "SELECT id, nome, preco FROM lanches WHERE id = ? AND ativo = 1", (lanche_id,)
        )
        if not row:
            lanche.close()
            return None
        lanche.id, lanche.nome, lanche.preco = row["id"], row["nome"], row["preco"]
        lanche.dadosLanche = lanche._listar_componentes()
        return lanche

    @classmethod
    def listar(cls, db_path: str = "data/SysDB.db") -> List[dict]:
        db = DBProxy(db_path)
        try:
            return [dict(row) for row in db.query_all(
                "SELECT id, nome, preco FROM lanches WHERE ativo = 1 ORDER BY nome"
            )]
        finally:
            db.close()

    def _listar_componentes(self) -> Dict[str, float]:
        rows = self.db.query_all(
            "SELECT item_nome, quantidade FROM lanche_itens WHERE lanche_id = ? ORDER BY id",
            (self.id,),
        )
        return {row["item_nome"]: float(row["quantidade"]) for row in rows}

    def componentes(self) -> List[dict]:
        return [
            {"nome": nome, "quantidade": quantidade}
            for nome, quantidade in self.dadosLanche.items()
        ]

    def close(self) -> None:
        self.db.close()

    def excluir(self, lanche_id: int) -> bool:
        cursor = self.db.execute(
            "UPDATE lanches SET ativo = 0, updated_at = ? WHERE id = ? AND ativo = 1",
            (datetime.utcnow().isoformat(), lanche_id),
            commit=True,
        )
        return cursor.rowcount > 0

    def abrir_menu(self, app, login_instance, win=None, frame=None) -> None:
        if win is None or frame is None:
            win, frame = app._new_menu_window(login_instance, "Gestão de Lanches")
        else:
            win.title("Gestão de Lanches")
        for widget in frame.winfo_children():
            widget.destroy()
        tk.Label(frame, text="Gestão de Lanches", font=("Segoe UI", 18, "bold"),
                 bg=app.COLORS["canvas"], fg=app.COLORS["ink"]).pack(pady=(4, 10))
        actions = tk.Frame(frame, bg=app.COLORS["canvas"])
        actions.pack(fill=tk.X, pady=(0, 8))
        save_button = tk.Button(actions, text="Salvar", command=lambda: save())
        app._style_button(save_button, "success")
        save_button.pack(side=tk.LEFT, padx=4)
        new_button = tk.Button(actions, text="Adicionar", command=lambda: clear_form())
        app._style_button(new_button, "primary")
        new_button.pack(side=tk.LEFT, padx=4)
        edit_button = tk.Button(actions, text="Editar", command=lambda: edit_lanche())
        app._style_button(edit_button, "primary")
        edit_button.pack(side=tk.LEFT, padx=4)
        delete_button = tk.Button(actions, text="Excluir", command=lambda: delete_lanche())
        app._style_button(delete_button, "danger")
        delete_button.pack(side=tk.LEFT, padx=4)
        table = ttk.Treeview(frame, columns=("id", "nome", "preco", "componentes"), show="headings", height=4)
        for column, heading, width in (
            ("id", "ID", 55), ("nome", "Nome", 180), ("preco", "Preço", 90),
            ("componentes", "Composição", 320),
        ):
            table.heading(column, text=heading)
            table.column(column, width=width, anchor=tk.CENTER)
        table.pack(fill=tk.X, pady=(0, 8))
        form = tk.Frame(frame, bg=app.COLORS["canvas"])
        form.pack(fill=tk.X, pady=4)
        tk.Label(form, text="Nome:", bg=app.COLORS["canvas"], fg=app.COLORS["ink"]).grid(row=0, column=0, sticky=tk.W)
        name_entry = tk.Entry(form, width=30)
        name_entry.grid(row=0, column=1, padx=6)
        tk.Label(form, text="Preço:", bg=app.COLORS["canvas"], fg=app.COLORS["ink"]).grid(row=0, column=2, sticky=tk.W)
        price_entry = tk.Entry(form, width=12)
        price_entry.grid(row=0, column=3, padx=6)
        tk.Label(form, text="Componente do estoque:", bg=app.COLORS["canvas"], fg=app.COLORS["ink"]).grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        stock_options = {row["nome"]: row["nome"] for row in self.db.query_all(
            "SELECT DISTINCT nome FROM estoque WHERE ativo = 1 ORDER BY nome"
        )}
        stock_choice = tk.StringVar()
        stock_menu = tk.OptionMenu(form, stock_choice, *stock_options)
        stock_menu.grid(row=1, column=1, sticky=tk.W, padx=6, pady=(10, 0))
        tk.Label(form, text="Quantidade:", bg=app.COLORS["canvas"], fg=app.COLORS["ink"]).grid(row=1, column=2, sticky=tk.W, pady=(10, 0))
        component_quantity = tk.Entry(form, width=12)
        component_quantity.grid(row=1, column=3, padx=6, pady=(10, 0))
        components = {}
        component_list = tk.Listbox(frame, height=8, width=62)
        component_list.pack(pady=10)
        current_id = [None]

        def refresh():
            for row_id in table.get_children():
                table.delete(row_id)
            for row in self.db.query_all(
                "SELECT id, nome, preco FROM lanches WHERE ativo = 1 ORDER BY nome"
            ):
                item_rows = self.db.query_all(
                    "SELECT item_nome, quantidade FROM lanche_itens WHERE lanche_id = ? ORDER BY id",
                    (row["id"],),
                )
                composition = ", ".join(
                    f"{item['item_nome']} ({item['quantidade']:g})" for item in item_rows
                )
                table.insert("", tk.END, iid=str(row["id"]), values=(
                    row["id"], row["nome"], f"R$ {row['preco']:.2f}", composition,
                ))

        def clear_form():
            current_id[0] = None
            name_entry.delete(0, tk.END)
            price_entry.delete(0, tk.END)
            components.clear()
            component_list.delete(0, tk.END)

        def selected_id():
            selection = table.selection()
            if not selection:
                messagebox.showwarning("Lanche", "Selecione um lanche.", parent=win)
                return None
            return int(selection[0])

        def edit_lanche():
            lanche_id = selected_id()
            if lanche_id is None:
                return
            row = self.db.query_one("SELECT nome, preco FROM lanches WHERE id = ? AND ativo = 1", (lanche_id,))
            if not row:
                return
            clear_form()
            current_id[0] = lanche_id
            name_entry.insert(0, row["nome"])
            price_entry.insert(0, str(row["preco"]))
            for item in self.db.query_all(
                "SELECT item_nome, quantidade FROM lanche_itens WHERE lanche_id = ? ORDER BY id",
                (lanche_id,),
            ):
                components[item["item_nome"]] = float(item["quantidade"])
            component_list.insert(tk.END, *(f"{name}: {value:g}" for name, value in components.items()))

        def delete_lanche():
            lanche_id = selected_id()
            if lanche_id is None or not messagebox.askyesno(
                "Excluir lanche", "Deseja desativar o lanche selecionado?", parent=win
            ):
                return
            self.excluir(lanche_id)
            clear_form()
            refresh()

        def add_component():
            try:
                item = stock_choice.get().strip()
                quantity = float(component_quantity.get().strip())
                if not item or quantity <= 0:
                    raise ValueError("selecione um item e informe uma quantidade maior que zero")
                components[item] = quantity
                component_list.delete(0, tk.END)
                component_list.insert(tk.END, *(f"{name}: {value:g}" for name, value in components.items()))
                component_quantity.delete(0, tk.END)
            except ValueError as error:
                messagebox.showerror("Lanche", str(error), parent=win)

        def save():
            try:
                lanche = Lanche(name_entry.get(), float(price_entry.get() or 0), self.db.db_path)
                lanche.id = current_id[0]
                for item, quantity in components.items():
                    lanche.incluirItem(item, quantity)
                lanche.salvar()
                lanche.close()
                messagebox.showinfo("Lanche", "Lanche salvo com sucesso.", parent=win)
                clear_form()
                refresh()
            except (TypeError, ValueError) as error:
                messagebox.showerror("Lanche", str(error), parent=win)

        add_button = tk.Button(form, text="Adicionar", command=add_component)
        app._style_button(add_button, "primary")
        add_button.grid(row=2, column=0, columnspan=2, pady=10)
        refresh()
