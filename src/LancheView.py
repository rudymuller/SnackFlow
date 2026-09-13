import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from DBProxy import DBProxy
from Lanche import Lanche


class LancheView:
    """Tela Tkinter responsável pelo cadastro e edição de lanches."""

    def __init__(self, db_path):
        self.db = DBProxy(db_path)
        self.db_path = db_path

    def close(self):
        self.db.close()

    def abrir(self, app, login_instance, win=None, frame=None):
        if win is None or frame is None:
            win, frame = app._new_menu_window(login_instance, "Gestão de Lanches")
        else:
            win.title("Gestão de Lanches")

        for widget in frame.winfo_children():
            widget.destroy()

        tk.Label(
            frame, text="Gestão de Lanches", font=("Segoe UI", 18, "bold"),
            bg=app.COLORS["canvas"], fg=app.COLORS["ink"],
        ).pack(pady=(4, 10))

        actions = tk.Frame(frame, bg=app.COLORS["canvas"])
        actions.pack(fill=tk.X, pady=(0, 8))

        table = self._create_table(frame, app)
        table.pack(fill=tk.X, pady=(0, 8))

        form = tk.Frame(frame, bg=app.COLORS["canvas"])
        components = {}
        current_id = [None]
        fields = self._create_form(form, app)
        component_list = tk.Listbox(frame, height=8, width=62)

        def clear_form():
            current_id[0] = None
            fields["nome"].delete(0, tk.END)
            fields["preco"].delete(0, tk.END)
            fields["componente"].set("")
            fields["quantidade_label"].configure(text="Quantidade:")
            fields["quantidade"].delete(0, tk.END)
            components.clear()
            component_list.delete(0, tk.END)

        def show_form():
            form.pack(fill=tk.X, pady=4)
            component_list.pack(pady=10)

        def close_form():
            clear_form()
            form.pack_forget()
            component_list.pack_forget()

        def render_components():
            component_list.delete(0, tk.END)
            component_list.insert(
                tk.END,
                *(f"{name}: {value:g} {unit}" for name, (value, unit) in components.items()),
            )

        def selected_component():
            selection = component_list.curselection()
            if not selection:
                return None
            return list(components)[selection[0]]

        def open_form():
            clear_form()
            show_form()
            fields["nome"].focus_set()

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
            row = self.db.query_one(
                "SELECT nome, preco FROM lanches WHERE id = ? AND ativo = 1",
                (lanche_id,),
            )
            if not row:
                return
            clear_form()
            show_form()
            current_id[0] = lanche_id
            fields["nome"].insert(0, row["nome"])
            fields["preco"].insert(0, str(row["preco"]))
            for item in self.db.query_all(
                "SELECT item_nome, quantidade, unidade FROM lanche_itens WHERE lanche_id = ? ORDER BY id",
                (lanche_id,),
            ):
                components[item["item_nome"]] = (float(item["quantidade"]), item["unidade"])
            render_components()

        def edit_component_or_lanche():
            component_name = selected_component()
            if not component_name:
                edit_lanche()
                return
            current_quantity, unit = components[component_name]
            quantity = simpledialog.askfloat(
                "Editar ingrediente",
                f"Nova quantidade de {component_name} ({unit}):",
                initialvalue=current_quantity,
                minvalue=0.0001,
                parent=win,
            )
            if quantity is not None:
                components[component_name] = (quantity, unit)
                render_components()

        def delete_component_or_lanche():
            component_name = selected_component()
            if component_name:
                del components[component_name]
                render_components()
                return
            lanche_id = selected_id()
            if lanche_id is None or not messagebox.askyesno(
                "Excluir lanche", "Deseja desativar o lanche selecionado?", parent=win
            ):
                return
            lanche = Lanche(db_path=self.db_path)
            try:
                lanche.excluir(lanche_id)
            finally:
                lanche.close()
            clear_form()
            refresh()

        def add_component():
            try:
                item = fields["componente"].get().strip()
                quantity = float(fields["quantidade"].get().strip())
                if not item or quantity <= 0:
                    raise ValueError("selecione um item e informe uma quantidade maior que zero")
                unit = Lanche.unidade_da_receita(fields["unidades"].get(item, "unidade"))
                components[item] = (quantity, unit)
                render_components()
                fields["quantidade"].delete(0, tk.END)
            except ValueError as error:
                messagebox.showerror("Lanche", str(error), parent=win)

        def save():
            try:
                lanche = Lanche(
                    fields["nome"].get(),
                    float(fields["preco"].get() or 0),
                    self.db_path,
                )
                lanche.id = current_id[0]
                for item, (quantity, unit) in components.items():
                    lanche.incluirItem(item, quantity, unit)
                lanche.salvar()
                lanche.close()
                messagebox.showinfo("Lanche", "Lanche salvo com sucesso.", parent=win)
                close_form()
                refresh()
            except (TypeError, ValueError) as error:
                messagebox.showerror("Lanche", str(error), parent=win)

        def refresh():
            for row_id in table.get_children():
                table.delete(row_id)
            for row in self.db.query_all(
                "SELECT id, nome, preco FROM lanches WHERE ativo = 1 ORDER BY nome"
            ):
                item_rows = self.db.query_all(
                    "SELECT item_nome, quantidade, unidade FROM lanche_itens WHERE lanche_id = ? ORDER BY id",
                    (row["id"],),
                )
                composition = ", ".join(
                    f"{item['item_nome']} ({item['quantidade']:g} {item['unidade']})"
                    for item in item_rows
                )
                table.insert(
                    "", tk.END, iid=str(row["id"]),
                    values=(row["id"], row["nome"], f"R$ {row['preco']:.2f}", composition),
                )

        self._create_actions(
            actions, app, open_form, edit_component_or_lanche, delete_component_or_lanche,
        )
        self._create_form_actions(form, app, add_component, save, close_form)
        form.pack_forget()
        component_list.pack_forget()
        refresh()

    @staticmethod
    def _create_table(parent, app):
        table = ttk.Treeview(
            parent, columns=("id", "nome", "preco", "componentes"),
            show="headings", height=4, style="Lanche.Treeview",
        )
        for column, heading, width in (
            ("id", "ID", 55), ("nome", "Nome", 180),
            ("preco", "Preço", 90), ("componentes", "Composição", 320),
        ):
            table.heading(column, text=heading)
            table.column(column, width=width, anchor=tk.CENTER)
        style = ttk.Style(parent)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Lanche.Treeview", rowheight=28, font=("Segoe UI", 10),
            background=app.COLORS["surface"], fieldbackground=app.COLORS["surface"],
            foreground=app.COLORS["ink"],
        )
        style.configure(
            "Lanche.Treeview.Heading", font=("Segoe UI", 10, "bold"),
            background=app.COLORS["primary"], foreground="white",
        )
        style.map(
            "Lanche.Treeview.Heading",
            background=[("active", app.COLORS["primary_dark"]), ("pressed", app.COLORS["primary_dark"])],
            foreground=[("active", "white"), ("pressed", "white")],
        )
        style.map(
            "Lanche.Treeview",
            background=[("selected", app.COLORS["primary"])],
            foreground=[("selected", "white")],
        )
        return table

    @staticmethod
    def _create_actions(parent, app, create, edit, delete):
        buttons = (("Criar lanche", create, "primary"), ("Editar", edit, "primary"), ("Excluir", delete, "danger"))
        for text, command, tone in buttons:
            button = tk.Button(parent, text=text, command=command)
            app._style_button(button, tone)
            button.pack(side=tk.LEFT, padx=4)

    def _create_form(self, form, app):
        labels = {}
        field_font = ("Segoe UI", 11)
        label_font = ("Segoe UI", 11, "bold")
        labels["nome"] = tk.Entry(form, width=34, font=field_font)
        labels["preco"] = tk.Entry(form, width=14, font=field_font)
        stock_rows = self.db.query_all("SELECT nome, unidade FROM estoque WHERE ativo = 1 ORDER BY nome")
        labels["unidades"] = {row["nome"]: row["unidade"] for row in stock_rows}
        labels["componente"] = ttk.Combobox(form, values=tuple(labels["unidades"]), width=32, font=field_font)
        labels["quantidade_label"] = tk.Label(form, text="Quantidade:", bg=app.COLORS["canvas"], fg=app.COLORS["ink"], font=label_font)
        labels["quantidade"] = tk.Entry(form, width=14, font=field_font)
        for label, key, row, column in (
            ("Nome:", "nome", 0, 0), ("Preço:", "preco", 0, 2),
            ("Componente do estoque:", "componente", 1, 0), (None, "quantidade_label", 1, 2),
        ):
            if label:
                tk.Label(form, text=label, bg=app.COLORS["canvas"], fg=app.COLORS["ink"], font=label_font).grid(row=row, column=column, sticky=tk.W, pady=(12, 0) if row else 0)
            labels[key].grid(row=row, column=column + 1, padx=6, pady=(10, 0) if row else 0)
        labels["quantidade_label"].grid(row=1, column=2, sticky=tk.W, pady=(10, 0))
        labels["quantidade"].grid(row=1, column=3, padx=6, pady=(10, 0))

        def update_quantity_label(_event=None):
            unit = Lanche.unidade_da_receita(labels["unidades"].get(labels["componente"].get().strip(), "unidade"))
            labels["quantidade_label"].configure(text=f"Quantidade ({unit}):")

        labels["componente"].bind("<<ComboboxSelected>>", update_quantity_label)
        labels["componente"].bind("<KeyRelease>", update_quantity_label)
        return labels

    @staticmethod
    def _create_form_actions(form, app, add, save, cancel):
        actions = tk.Frame(form, bg=app.COLORS["canvas"])
        actions.grid(row=2, column=0, columnspan=4, pady=10)
        for text, command, tone in (("Incluir item", add, "primary"), ("Salvar lanche", save, "success"), ("Cancelar", cancel, "warning")):
            button = tk.Button(actions, text=text, command=command)
            app._style_button(button, tone)
            button.pack(side=tk.LEFT, padx=4)