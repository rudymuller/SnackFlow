from datetime import date, datetime
import tkinter as tk
from tkinter import messagebox, ttk

from const import DB_PATH, now_iso
from DBProxy import DBProxy
from DatePicker import create_date_entry


class ContaPagarRepository:
    """Responsavel pelo armazenamento das contas a pagar."""

    def __init__(self, db: DBProxy):
        self.db = db
        self._ensure_table()

    def _ensure_table(self):
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS contas_pagar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                descricao TEXT NOT NULL,
                categoria TEXT NOT NULL,
                valor REAL NOT NULL CHECK (valor >= 0),
                vencimento DATE NOT NULL,
                status TEXT NOT NULL DEFAULT 'A vencer',
                pago_em TEXT,
                ativo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
            """,
            commit=True,
        )

    def atualizar_vencidas(self):
        self.db.execute(
            """
            UPDATE contas_pagar
            SET status = 'Vencido', updated_at = ?
            WHERE ativo = 1 AND status = 'A vencer' AND vencimento < ?
            """,
            (now_iso(), date.today().isoformat()),
            commit=True,
        )

    def listar(self):
        self.atualizar_vencidas()
        return [dict(row) for row in self.db.query_all(
            "SELECT * FROM contas_pagar WHERE ativo = 1 ORDER BY vencimento, id"
        )]

    def salvar(self, dados, conta_id=None):
        now = now_iso()
        if conta_id is None:
            cursor = self.db.execute(
                """
                INSERT INTO contas_pagar
                    (descricao, categoria, valor, vencimento, status, ativo, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (dados["descricao"], dados["categoria"], dados["valor"],
                 dados["vencimento"], dados["status"], now),
                commit=True,
            )
            return cursor.lastrowid
        self.db.execute(
            """
            UPDATE contas_pagar
            SET descricao = ?, categoria = ?, valor = ?, vencimento = ?,
                status = ?, updated_at = ?
            WHERE id = ? AND ativo = 1
            """,
            (dados["descricao"], dados["categoria"], dados["valor"],
             dados["vencimento"], dados["status"], now, conta_id),
            commit=True,
        )
        return conta_id

    def remover(self, conta_id):
        cursor = self.db.execute(
            "UPDATE contas_pagar SET ativo = 0, updated_at = ? WHERE id = ? AND ativo = 1",
            (now_iso(), conta_id),
            commit=True,
        )
        return cursor.rowcount > 0


class Gastos:
    """Modelo e servico de contas a pagar."""

    CATEGORIAS = ("Fornecedores", "Aluguel", "Servicos", "Outros")
    STATUS = ("A vencer", "Vencido", "Pago")

    def __init__(self, db_path=DB_PATH):
        self.db = DBProxy(db_path)
        self.repository = ContaPagarRepository(self.db)

    def listar(self):
        return self.repository.listar()

    def salvar(self, descricao, categoria, valor, vencimento, status="A vencer", conta_id=None):
        descricao = (descricao or "").strip()
        categoria = (categoria or "").strip()
        vencimento = (vencimento or "").strip()
        valor = float(valor)
        if not descricao or not categoria or not vencimento:
            raise ValueError("descricao, categoria e vencimento sao obrigatorios")
        if valor < 0:
            raise ValueError("o valor nao pode ser negativo")
        if status not in self.STATUS:
            raise ValueError("status de conta invalido")
        return self.repository.salvar(
            {"descricao": descricao, "categoria": categoria, "valor": valor,
             "vencimento": vencimento, "status": status}, conta_id,
        )

    def remover(self, conta_id):
        return self.repository.remover(conta_id)

    def fechar(self):
        self.db.close()


class GastosView:
    """Tela administrativa do UC09."""

    def __init__(self, db_path=DB_PATH):
        self.gastos = Gastos(db_path)

    def abrir(self, app, login_instance, win=None, frame=None):
        if win is None or frame is None:
            win, frame = app._new_menu_window(login_instance, "Contas a pagar")
        else:
            win.title("Contas a pagar")
        for widget in frame.winfo_children():
            widget.destroy()

        tk.Label(
            frame, text="Gestao de contas a pagar", font=("Segoe UI", 18, "bold"),
            bg=app.COLORS["canvas"], fg=app.COLORS["ink"],
        ).pack(pady=(4, 10))
        form = tk.Frame(frame, bg=app.COLORS["canvas"])
        form.pack(fill=tk.X, pady=(0, 10))
        descricao = tk.Entry(form, width=24)
        categoria = ttk.Combobox(form, values=Gastos.CATEGORIAS, state="readonly", width=16)
        valor = tk.Entry(form, width=12)
        vencimento = create_date_entry(form, width=12)
        status = ttk.Combobox(form, values=Gastos.STATUS, state="readonly", width=12)
        status.set("A vencer")
        entries = (("Descricao", descricao), ("Categoria", categoria), ("Valor", valor), ("Vencimento", vencimento), ("Status", status))
        for column, (label, entry) in enumerate(entries):
            tk.Label(form, text=label, bg=app.COLORS["canvas"], fg=app.COLORS["ink"]).grid(row=0, column=column, sticky=tk.W, padx=3)
            entry.grid(row=1, column=column, padx=3, pady=3)

        table = ttk.Treeview(frame, columns=("id", "descricao", "categoria", "valor", "vencimento", "status"), show="headings")
        for column, heading, width in (("id", "ID", 50), ("descricao", "Descricao", 180), ("categoria", "Categoria", 120), ("valor", "Valor", 100), ("vencimento", "Vencimento", 110), ("status", "Status", 100)):
            table.heading(column, text=heading)
            table.column(column, width=width, anchor=tk.CENTER)
        table.pack(expand=True, fill=tk.BOTH)
        selected_id = [None]

        def refresh():
            for item in table.get_children():
                table.delete(item)
            for item in self.gastos.listar():
                table.insert("", tk.END, iid=str(item["id"]), values=(
                    item["id"], item["descricao"], item["categoria"],
                    f"R$ {item['valor']:.2f}", item["vencimento"], item["status"],
                ))

        def clear():
            selected_id[0] = None
            descricao.delete(0, tk.END)
            categoria.set("")
            valor.delete(0, tk.END)
            status.set("A vencer")

        def save():
            try:
                self.gastos.salvar(descricao.get(), categoria.get(), valor.get(), vencimento.get(), status.get(), selected_id[0])
                clear()
                refresh()
            except (TypeError, ValueError) as error:
                messagebox.showerror("Contas a pagar", str(error), parent=win)

        def select(_event=None):
            selection = table.selection()
            if not selection:
                return
            selected_id[0] = int(selection[0])
            item = next(item for item in self.gastos.listar() if item["id"] == selected_id[0])
            descricao.delete(0, tk.END)
            descricao.insert(0, item["descricao"])
            categoria.set(item["categoria"])
            valor.delete(0, tk.END)
            valor.insert(0, str(item["valor"]))
            vencimento.set_date(datetime.strptime(item["vencimento"], "%Y-%m-%d").date())
            status.set(item["status"])

        def remove():
            if selected_id[0] is None:
                messagebox.showwarning("Contas a pagar", "Selecione uma conta.", parent=win)
                return
            if messagebox.askyesno("Contas a pagar", "Deseja excluir esta conta?", parent=win):
                self.gastos.remover(selected_id[0])
                clear()
                refresh()

        table.bind("<<TreeviewSelect>>", select)
        actions = tk.Frame(frame, bg=app.COLORS["canvas"])
        actions.pack(pady=8)
        for text, command, tone in (("Salvar", save, "success"), ("Novo", clear, "primary"), ("Excluir", remove, "danger")):
            button = tk.Button(actions, text=text, command=command)
            app._style_button(button, tone)
            button.pack(side=tk.LEFT, padx=4)
        refresh()