import tkinter as tk
from tkinter import messagebox, ttk, font as tkfont
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
import sys
from const import WIN_WIDTH, WIN_HEIGHT

try:
	from PIL import Image, ImageDraw, ImageFont, ImageTk
except ImportError:
	Image = ImageDraw = ImageFont = ImageTk = None


class App:
	COLORS = {
		"ink": "#193B52",
		"muted": "#567286",
		"canvas": "#EEF4F7",
		"surface": "#FFFFFF",
		"line": "#D2E0E8",
		"primary": "#356B85",
		"primary_dark": "#244E66",
		"success": "#477B93",
		"warning": "#638BA0",
		"danger": "#294F65",
	}
	ICONS = {
		"Entrar": "\uf2f6", "Sair": "\uf00d", "Menu Principal": "\uf015", "Home": "\uf015",
		"Sair da conta": "\uf2f5", "Voltar": "\uf053", "Pedidos": "\uf46d",
		"Usuários": "\uf0c0", "Estoque": "\uf468", "Lanches": "\uf2e7",
		"Gastos": "\uf0d6", "Faturamento": "\uf080", "Gestão": "\uf009",
		"Adicionar": "\uf067", "Editar": "\uf044", "Excluir": "\uf1f8",
		"Nova compra": "\uf217", "Agrupar semelhantes": "\uf0c9", "Salvar": "\uf0c7",
		"Cancelar": "\uf00d", "Atualizar": "\uf021", "Remover": "\uf068",
	}
	FALLBACK_ICONS = {
		"Entrar": "➜", "Sair": "×", "Menu Principal": "⌂", "Home": "⌂",
		"Sair da conta": "⇥", "Voltar": "‹", "Pedidos": "▣",
		"Usuários": "♙", "Estoque": "▤", "Lanches": "♨", "Gastos": "¤",
		"Faturamento": "▥", "Gestão": "◆", "Adicionar": "+", "Editar": "✎",
		"Excluir": "−", "Nova compra": "＋", "Agrupar semelhantes": "≡",
		"Salvar": "✓", "Cancelar": "×", "Atualizar": "↻", "Remover": "−",
	}

	@staticmethod
	def _font_awesome_path():
		if getattr(sys, "_MEIPASS", None):
			bundled_fonts = list(Path(sys._MEIPASS).rglob("fa-solid-900.ttf"))
			if bundled_fonts:
				return bundled_fonts[0]
		try:
			package_root = Path(distribution("fontawesomefree").locate_file(""))
		except PackageNotFoundError:
			return None
		fonts = list(package_root.rglob("fa-solid-900.ttf"))
		return fonts[0] if fonts else None

	def _font_awesome_image(self, glyph, color="white", size=22):
		if not all((Image, ImageDraw, ImageFont, ImageTk)):
			return None
		font_path = self._font_awesome_path()
		if font_path is None:
			return None
		font = ImageFont.truetype(str(font_path), size)
		image = Image.new("RGBA", (size + 8, size + 8), (0, 0, 0, 0))
		draw = ImageDraw.Draw(image)
		draw.text((4, 1), glyph, font=font, fill=color, anchor="lt")
		return ImageTk.PhotoImage(image)

	def _style_button(self, button, tone="primary"):
		colors = self.COLORS
		label = button.cget("text")
		requested_width = button.cget("width")
		glyph = self.ICONS.get(label)
		if glyph:
			try:
				icon_image = self._font_awesome_image(glyph)
				if icon_image:
					button.configure(image=icon_image, compound=tk.LEFT, text=label)
					button._font_awesome_image = icon_image
					if requested_width:
						button_font = tkfont.Font(font=("Segoe UI", 11, "bold"))
						text_width = max(
							button_font.measure(label),
							button_font.measure("0") * requested_width,
						)
						button.configure(width=text_width + 22 + 32)
				else:
					button.configure(text=f"{self.FALLBACK_ICONS[label]}  {label}")
			except (OSError, RuntimeError):
				button.configure(text=f"{self.FALLBACK_ICONS[label]}  {label}")
		elif label in self.FALLBACK_ICONS:
			button.configure(text=f"{self.FALLBACK_ICONS[label]}  {label}")
		button.configure(
			font=("Segoe UI", 11, "bold"),
			bg=colors["primary"],
			fg="white",
			activebackground=colors["primary_dark"],
			activeforeground="white",
			 relief=tk.FLAT,
			borderwidth=0,
			padx=16,
			pady=8,
			cursor="hand2",
		)

	def _style_heading(self, label):
		label.configure(fg=self.COLORS["ink"], bg=self.COLORS["canvas"])

	def _style_subtitle(self, label):
		label.configure(fg=self.COLORS["muted"], bg=self.COLORS["canvas"])

	def homeScreen(self, root=None):
		"""Create a simple desktop home screen (Tkinter) with a welcome message.

		If `root` is provided, a Toplevel window will be used so this method
		can be embedded in larger apps. Otherwise a new Tk root will be created
		and mainloop will be run.
		"""
		owns_root = False
		if root is None:
			root = tk.Tk()
			owns_root = True

		# Configure window
		root.title("SnackFlow")
		width, height = WIN_WIDTH, WIN_HEIGHT
		screen_w = root.winfo_screenwidth()
		screen_h = root.winfo_screenheight()
		x = (screen_w - width) // 2
		y = (screen_h - height) // 2
		root.geometry(f"{width}x{height}+{x}+{y}")

		# Root frame
		root.configure(bg=self.COLORS["canvas"])
		frame = tk.Frame(root, padx=28, pady=28, bg=self.COLORS["canvas"])
		frame.pack(expand=True, fill=tk.BOTH)

		# Welcome message
		title = tk.Label(frame, text="SnackFlow",
						 font=("Segoe UI", 22, "bold"), wraplength=520, justify=tk.CENTER,
						 bg=self.COLORS["canvas"], fg=self.COLORS["ink"])
		title.pack(pady=(10, 18))

		subtitle = tk.Label(frame, text="Pedidos, estoque e controle em um só lugar.",
						font=("Segoe UI", 12), bg=self.COLORS["canvas"])
		self._style_subtitle(subtitle)
		subtitle.pack(pady=(0, 18))

		# Buttons
		btn_frame = tk.Frame(frame)
		btn_frame.pack(pady=10)

		def on_enter():
			# Open the Login modal and handle returned credentials
			# Provide an AuthService instance so the login dialog can authenticate
			# against the DB (falls back to built-in accounts when needed).
			from Login import Login
			from AuthService import AuthService
			authsvc = AuthService()
			login_screen = Login(parent=root, auth_handler=authsvc.authenticate)
			creds = login_screen.show()
			if creds is None:
				messagebox.showinfo("Login", "Login cancelado.")
			else:
				username, password = creds
				# If login set a userType (admin/atend), consider it a success and
				# destroy the home screen before opening the menu.
				ut = getattr(login_screen, 'userType', None)
				if ut is not None:
					if owns_root:
						root.destroy()
					else:
						root.withdraw()

					# detach the login modal from the destroyed root so the menu
					# windows will create their own root if needed
					login_screen.parent = None

					self.showMenutype(login_screen)
				else:
					# userType not set -> not a successful built-in login; inform user
					messagebox.showwarning("Login", "Credenciais não reconhecidas.\nTente novamente ou cadastre o usuário.")
			

		enter_btn = tk.Button(btn_frame, text="Entrar", width=12, command=on_enter)
		self._style_button(enter_btn, "primary")
		enter_btn.grid(row=0, column=0, padx=8)

		# Make the window non-resizable for a cleaner welcome screen
		root.resizable(False, False)

		if owns_root:
			root.mainloop()

	def showMenutype(self, login_instance):
		"""Open an admin or atendimento screen based on login_instance.userType.

		- If login_instance.userType is True -> show Administrative menu screen
		- If False -> show Atendimento menu screen
		- If None -> show a message informing that the user type was not identified
		"""
		ut = getattr(login_instance, 'userType', None)
		from MenuAdmin import MenuAdmin
		from MenuFunc import MenuFunc

		if ut is True:
			MenuAdmin(self, login_instance)
		elif ut is False:
			MenuFunc(self, login_instance)
		else:
			messagebox.showwarning("Tipo de usuário", "Tipo de usuário não identificado (userType=None).\nVerifique as credenciais ou cadastre o usuário.")

	def _render_main_menu_in_window(self, login_instance, win, frame):
		"""Renderiza o menu principal na janela atual, evitando recriá-la."""
		ut = getattr(login_instance, "userType", None)
		if ut is True:
			from MenuAdmin import MenuAdmin
			menu = MenuAdmin.__new__(MenuAdmin)
			menu.app = self
			menu.login_instance = login_instance
			menu.win = win
			menu.frame = frame
			menu.render()
		elif ut is False:
			from MenuFunc import MenuFunc
			menu = MenuFunc.__new__(MenuFunc)
			menu.app = self
			menu.login_instance = login_instance
			menu.win = win
			menu.frame = frame
			menu.render()


	def _new_menu_window(self, login_instance, title: str):
		"""Create a window with a persistent sidebar and return its content frame.

		The login_instance.parent determines whether the new window should be a
		Toplevel (attached) or a fresh Tk root.
		"""
		win = tk.Toplevel() if login_instance.parent else tk.Tk()
		win.title(title)
		win.geometry("760x560")
		win.configure(bg=self.COLORS["canvas"])
		win.protocol("WM_DELETE_WINDOW", lambda: self._confirm_exit(win))
		shell = tk.Frame(win, bg=self.COLORS["canvas"])
		shell.pack(expand=True, fill=tk.BOTH)
		sidebar = tk.Frame(shell, width=210, padx=12, pady=18, bg=self.COLORS["primary_dark"])
		sidebar.pack(side=tk.LEFT, fill=tk.Y)
		sidebar.pack_propagate(False)
		frm = tk.Frame(shell, padx=28, pady=22, bg=self.COLORS["canvas"])
		frm.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
		self._build_sidebar(sidebar, frm, win, login_instance)
		return win, frm

	def _build_sidebar(self, sidebar, content, win, login_instance):
		"""Create navigation that stays visible while content changes."""
		is_admin = getattr(login_instance, "userType", False) is True
		title = tk.Label(
			sidebar,
			text="SnackFlow",
			font=("Segoe UI", 14, "bold"),
			bg=self.COLORS["primary_dark"],
			fg="white",
			justify=tk.LEFT,
		)
		title.pack(anchor=tk.W, pady=(2, 24))

		def render_main():
			self._render_main_menu_in_window(login_instance, win, content)

		def render_users():
			self._render_user_management(content, win, render_main)

		def render_stock():
			self._open_estoque_menu(login_instance, win, content)

		def render_orders():
			from Pedidos import Pedidos
			Pedidos(is_admin=is_admin).abrir_menu(self, login_instance, win, content)

		def render_lanches():
			from Lanche import Lanche
			Lanche().abrir_menu(self, login_instance, win, content)

		items = [("Home", render_main)]
		if is_admin:
			items.extend([
				("Pedidos", render_orders),
				("Lanches", render_lanches),
				("Usuários", render_users),
				("Estoque", render_stock),
				("Gastos", lambda: self._open_placeholder("Gastos")),
				("Faturamento", lambda: self._open_placeholder("Faturamento")),
				("Gestão", lambda: self._open_placeholder("Gestão")),
			])
		else:
			items.extend([
				("Pedidos", render_orders),
				("Lanches", render_lanches),
				("Estoque", render_stock),
			])

		for label, command in items:
			button = tk.Button(sidebar, text=label, command=command, anchor=tk.W)
			self._style_button(button, "primary")
			button.configure(bg=self.COLORS["primary_dark"], activebackground=self.COLORS["primary"])
			button.pack(fill=tk.X, pady=3)

		logout = tk.Button(sidebar, text="Sair da conta", command=lambda: self._logout(win), anchor=tk.W)
		self._style_button(logout, "warning")
		logout.configure(bg=self.COLORS["primary_dark"], activebackground=self.COLORS["primary"])
		logout.pack(side=tk.BOTTOM, fill=tk.X, pady=3)

	def _render_home(self, frame, win, login_instance, access_type):
		"""Render the shared home screen with the logged-in user's summary."""
		for widget in frame.winfo_children():
			widget.destroy()

		user = getattr(login_instance, "user", None) or {}
		if isinstance(user, dict):
			first_name = user.get("nome") or ""
			last_name = user.get("sobrenome") or ""
			username = user.get("nome_usuario") or ""
			stored_access = user.get("tipo_acesso")
		else:
			first_name = getattr(user, "nome", "") or ""
			last_name = getattr(user, "sobrenome", "") or ""
			username = getattr(user, "nome_usuario", "") or ""
			stored_access = getattr(user, "tipo_acesso", None)

		full_name = " ".join(value for value in (first_name, last_name) if value).strip()
		user_display = full_name or username or "Usuário"
		access_label = "Administrador" if access_type == "admin" else "Funcionário"
		if stored_access in ("admin", "atend"):
			access_label = "Administrador" if stored_access == "admin" else "Funcionário"

		title = tk.Label(frame, text="Home", font=("Segoe UI", 22, "bold"))
		self._style_heading(title)
		title.pack(pady=(18, 8))

		subtitle = tk.Label(
			frame,
			text="Visão geral do SnackFlow",
			font=("Segoe UI", 11),
			wraplength=520,
			justify=tk.CENTER,
		)
		self._style_subtitle(subtitle)
		subtitle.pack(pady=(0, 22))

		logo = tk.Label(
			frame,
			text="SnackFlow",
			font=("Segoe UI", 20, "bold"),
			width=16,
			height=4,
			bg=self.COLORS["surface"],
			fg=self.COLORS["primary"],
			relief=tk.GROOVE,
			borderwidth=2,
		)
		logo.pack(pady=(4, 24))

		info = tk.Frame(frame, bg=self.COLORS["canvas"])
		info.pack(pady=4)
		for row, (label, value) in enumerate((("Usuário", user_display), ("Tipo de acesso", access_label))):
			label_widget = tk.Label(info, text=f"{label}:", font=("Segoe UI", 12, "bold"), anchor=tk.E,			bg=self.COLORS["canvas"], fg=self.COLORS["ink"], width=18)
			label_widget.grid(row=row, column=0, padx=(0, 10), pady=6, sticky=tk.E)
			value_widget = tk.Label(info, text=value, font=("Segoe UI", 12), anchor=tk.W,				bg=self.COLORS["canvas"], fg=self.COLORS["muted"], width=24)
			value_widget.grid(row=row, column=1, pady=6, sticky=tk.W)


	def _maximize_window(self, win):
		"""Try to maximize a window using common methods (cross-platform fallbacks)."""
		try:
			win.state('zoomed')
		except Exception:
			try:
				win.attributes('-zoomed', True)
			except Exception:
				win.attributes('-fullscreen', True)

	def _add_navigation_buttons(self, parent, win, main_callback, logout_callback=None):
		"""Add contextual main-menu and logout buttons to a screen."""
		navigation = tk.Frame(parent)
		navigation.pack(side=tk.BOTTOM, fill=tk.X, pady=(12, 0))
		main_button = tk.Button(navigation, text='Menu Principal', command=main_callback)
		self._style_button(main_button, "primary")
		main_button.pack(side=tk.LEFT, padx=6)
		if logout_callback:
			logout_button = tk.Button(navigation, text='Sair da conta', command=logout_callback)
			self._style_button(logout_button, "warning")
			logout_button.pack(side=tk.RIGHT, padx=6)

	def _logout(self, win):
		"""Close the current menu and return to the login flow."""
		win.destroy()
		self.homeScreen()

	def _confirm_exit(self, win):
		if messagebox.askyesno('Sair', 'Deseja realmente sair da aplicação?'):
			win._root().destroy()


	def _render_admin_menu(self, frm, win):
		"""Render the administrative menu inside the supplied frame."""
		label = tk.Label(frm, text="Menu Administrativo", font=("Segoe UI", 18, "bold"))
		label.pack(pady=(4, 12))
		msg = tk.Label(frm, text="Aqui você encontrará opções administrativas:", wraplength=380, justify=tk.CENTER)
		msg.pack(pady=6)

		def open_pedidos():
			try:
				from Pedidos import Pedidos
				_ = Pedidos()
				messagebox.showinfo("Pedidos", "Abrindo módulo Pedidos (placeholder)")
			except Exception:
				messagebox.showinfo("Pedidos", "Módulo Pedidos não implementado - placeholder.")

		# main admin options
		# maximize window
		self._maximize_window(win)

	def _open_placeholder(self, title: str):
		messagebox.showinfo(title, f"Abrindo {title} (placeholder)")


	def _open_estoque_menu(self, login_instance, current_win=None, current_frame=None):
		if login_instance is None:
			messagebox.showwarning("Estoque", "Não foi possível identificar o usuário logado.")
			return
		from Estoque import Estoque
		Estoque().abrir_menu(self, login_instance, current_win, current_frame)


	def _render_user_management(self, frm, win, main_callback=None):
		"""Render the user management UI inside the given frame.

		This method contains the same functionality as the previous inline
		'open_usuarios' block but separated into a single method for clarity.
		"""
		from Usuario import Usuario
		u_mgr = Usuario()

		# clear frame
		for w in list(frm.winfo_children()):
			w.destroy()

		title = tk.Label(frm, text="Gerenciamento de Usuários", font=("Segoe UI", 16, "bold"))
		self._style_heading(title)
		title.pack(pady=(4, 8))

		# top controls
		ctrl_top = tk.Frame(frm, bg=self.COLORS["canvas"])
		ctrl_top.pack(fill=tk.X, pady=(0, 8))

		def on_add():
			add_win = tk.Toplevel(win)
			add_win.title('Adicionar Usuário')
			add_win.geometry('480x360')
			add_win.configure(bg=self.COLORS["canvas"])
			frm_add = tk.Frame(add_win, padx=12, pady=12, bg=self.COLORS["canvas"])
			frm_add.pack(expand=True, fill=tk.BOTH)

			labels = ['Nome', 'Sobrenome', 'CPF', 'Nome de usuário', 'Senha', 'Data admissão', 'Tipo acesso']
			entries = {}
			for i, lbl in enumerate(labels):
				field_label = tk.Label(frm_add, text=lbl+':', bg=self.COLORS['canvas'], fg=self.COLORS['ink'])
				field_label.grid(row=i, column=0, sticky=tk.W, pady=4)
				if lbl == 'Tipo acesso':
					combo = ttk.Combobox(frm_add, values=['Administrador', 'Funcionário'], state='readonly', width=33)
					combo.grid(row=i, column=1, pady=4, padx=6)
					entries[lbl] = combo
				else:
					e = tk.Entry(frm_add, width=36, show='*' if lbl == 'Senha' else None)
					e.grid(row=i, column=1, pady=4, padx=6)
					entries[lbl] = e

			def submit_add():
				try:
					tipo_sel = entries['Tipo acesso'].get().strip()
					tipo_val = None
					if tipo_sel == 'Administrador':
						tipo_val = 'admin'
					elif tipo_sel == 'Funcionário':
						tipo_val = 'atend'

					nid = u_mgr.adicionar(
						entries['Nome'].get().strip(),
						entries['Sobrenome'].get().strip(),
						entries['CPF'].get().strip(),
						entries['Nome de usuário'].get().strip(),
						entries['Senha'].get(),
						entries['Data admissão'].get().strip() or None,
						tipo_val,
					)
					messagebox.showinfo('Usuários', f'Usuário criado (id={nid})')
					add_win.destroy()
					refresh_list()
				except Exception as ex:
					messagebox.showerror('Erro', f'Falha ao adicionar usuário: {ex}')

			btns = tk.Frame(frm_add, bg=self.COLORS["canvas"])
			btns.grid(row=len(labels), column=0, columnspan=2, pady=(12,0))
			save_button = tk.Button(btns, text='Salvar', command=submit_add)
			self._style_button(save_button)
			save_button.pack(side=tk.LEFT, padx=6)
			cancel_button = tk.Button(btns, text='Cancelar', command=add_win.destroy)
			self._style_button(cancel_button)
			cancel_button.pack(side=tk.LEFT, padx=6)
			nav_add = tk.Frame(frm_add, bg=self.COLORS["canvas"])
			nav_add.grid(row=len(labels) + 1, column=0, columnspan=2, pady=(8, 0))
			main_button = tk.Button(nav_add, text='Menu Principal', command=lambda: self._close_and_return(add_win, main_callback))
			self._style_button(main_button)
			main_button.pack(side=tk.LEFT, padx=6)

		add_btn = tk.Button(ctrl_top, text='Adicionar', width=12, command=on_add)
		self._style_button(add_btn)
		add_btn.pack(side=tk.LEFT)

		# Treeview list for users
		cols = ('id', 'nome', 'sobrenome', 'nome_usuario', 'cpf', 'tipo_acesso', 'ativo')
		tree = ttk.Treeview(frm, columns=cols, show='headings', selectmode='browse')
		tree_style = ttk.Style(frm)
		tree_style.configure('Users.Treeview', rowheight=28, font=('Segoe UI', 10),
			background=self.COLORS['surface'], fieldbackground=self.COLORS['surface'],
			foreground=self.COLORS['ink'])
		tree_style.configure('Users.Treeview.Heading', font=('Segoe UI', 10, 'bold'),
			background=self.COLORS['primary'], foreground='white')
		tree_style.map('Users.Treeview', background=[('selected', self.COLORS['primary'])], foreground=[('selected', 'white')])
		tree.configure(style='Users.Treeview')
		label_map = {
			'id': 'ID',
			'nome': 'Nome',
			'sobrenome': 'Sobrenome',
			'nome_usuario': 'Nome de Usuario',
			'cpf': 'CPF',
			'tipo_acesso': 'Tipo de acesso',
			'ativo': 'Status',
		}
		for c in cols:
			tree.heading(c, text=label_map.get(c, c), anchor=tk.CENTER)
			tree.column(c, width=120, anchor=tk.CENTER)

		# vertical scrollbar
		vsb = ttk.Scrollbar(frm, orient='vertical', command=tree.yview)
		tree.configure(yscrollcommand=vsb.set)
		tree.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
		vsb.pack(side=tk.LEFT, fill=tk.Y)

		# action area
		action_frame = tk.Frame(frm, padx=8, bg=self.COLORS['canvas'])
		action_frame.pack(side=tk.RIGHT, fill=tk.Y)

		info_label = tk.Label(action_frame, text='Selecione um usuário', wraplength=180,
			bg=self.COLORS['canvas'], fg=self.COLORS['muted'], font=('Segoe UI', 10))
		info_label.pack(pady=(4,8))

		selected_user_id = {'id': None}

		def refresh_list():
			# clear
			for r in tree.get_children():
				tree.delete(r)
			users = u_mgr.listar(include_inativos=True)
			for urec in users:
				# display human-friendly tipo_acesso label
				tipo = urec.get('tipo_acesso')
				if tipo == 'admin':
					tipo_label = 'Administrador'
				elif tipo == 'atend':
					tipo_label = 'Funcionário'
				else:
					tipo_label = tipo
				tree.insert('', tk.END, values=(urec['id'], urec['nome'], urec['sobrenome'], urec['nome_usuario'], urec['cpf'], tipo_label, 'Ativo' if urec.get('ativo',1) == 1 else 'Inativo'))

			# After populating, compute column widths based on content and header
			self._adjust_columns(tree, cols)

		def on_select(event):
			sel = tree.selection()
			if not sel:
				return
			item = tree.item(sel[0])
			uid = item['values'][0]
			selected_user_id['id'] = uid
			info_label.config(text=f"Selecionado ID {uid}\n{item['values'][1]} {item['values'][2]}")
			# show update and remove buttons
			btn_update.pack_forget()
			btn_remove.pack_forget()
			btn_update.pack(pady=6)
			btn_remove.pack(pady=6)

		tree.bind('<<TreeviewSelect>>', on_select)

		def do_remove():
			uid = selected_user_id['id']
			if uid is None:
				messagebox.showwarning('Remover', 'Nenhum usuário selecionado')
				return
			if not messagebox.askyesno('Remover', 'Confirmar remoção permanente do usuário do banco de dados?'):
				return
			ok = u_mgr.remover(uid)
			if ok:
				messagebox.showinfo('Remover', 'Usuário removido do banco de dados')
				refresh_list()
			else:
				messagebox.showwarning('Remover', 'Falha ao remover (id não encontrado)')

		def do_update():
			uid = selected_user_id['id']
			if uid is None:
				messagebox.showwarning('Atualizar', 'Nenhum usuário selecionado')
				return
			data = u_mgr.obter(uid)
			if not data:
				messagebox.showerror('Atualizar', 'Usuário não encontrado')
				return
			upd_win = tk.Toplevel(win)
			upd_win.title('Atualizar usuário')
			upd_win.geometry('480x380')
			upd_win.configure(bg=self.COLORS['canvas'])
			fup = tk.Frame(upd_win, padx=12, pady=12, bg=self.COLORS['canvas'])
			fup.pack(expand=True, fill=tk.BOTH)

			labels = [('Nome','nome'),('Sobrenome','sobrenome'),('CPF','cpf'),('Nome de usuário','nome_usuario'),('Senha (deixe em branco para não alterar)','senha'),('Data admissão','data_admissao'),('Tipo acesso','tipo_acesso')]
			entries = {}
			for i, (lbl, key) in enumerate(labels):
				field_label = tk.Label(fup, text=lbl+':', bg=self.COLORS['canvas'], fg=self.COLORS['ink'])
				field_label.grid(row=i, column=0, sticky=tk.W, pady=4)
				if key == 'tipo_acesso':
					# show combobox, map stored value ('admin'/'atend') to display
					combo = ttk.Combobox(fup, values=['Administrador', 'Funcionário'], state='readonly', width=33)
					combo.grid(row=i, column=1, pady=4, padx=6)
					current = data.get('tipo_acesso')
					if current == 'admin':
						combo.set('Administrador')
					elif current == 'atend':
						combo.set('Funcionário')
					entries[key] = combo
				else:
					e = tk.Entry(fup, width=36, show='*' if 'Senha' in lbl else None)
					e.grid(row=i, column=1, pady=4, padx=6)
					if key in data and data[key] is not None and key != 'senha':
						e.insert(0, str(data[key]))
					entries[key] = e

			# ativo checkbox (allow re-activation)
			ativo_var = tk.IntVar(value=1 if data.get('ativo', 1) == 1 else 0)
			active_label = tk.Label(fup, text='Ativo:', bg=self.COLORS['canvas'], fg=self.COLORS['ink'])
			active_label.grid(row=len(labels), column=0, sticky=tk.W, pady=4)
			ativo_chk = tk.Checkbutton(fup, variable=ativo_var, bg=self.COLORS['canvas'], activebackground=self.COLORS['canvas'])
			ativo_chk.grid(row=len(labels), column=1, sticky=tk.W, pady=4, padx=6)

			def submit_update():
				fields = {}
				for key in ['nome','sobrenome','cpf','nome_usuario','data_admissao','tipo_acesso']:
					val = entries[key].get().strip()
					if val != '':
						fields[key] = val
				passwd = entries['senha'].get()
				if passwd:
					fields['senha'] = passwd
				# map tipo_acesso display back to stored value
				ta = entries['tipo_acesso'].get().strip()
				if ta == 'Administrador':
					fields['tipo_acesso'] = 'admin'
				elif ta == 'Funcionário':
					fields['tipo_acesso'] = 'atend'
				# include ativo status (1 or 0)
				fields['ativo'] = int(ativo_var.get())
				try:
					ok = u_mgr.atualizar(uid, **fields)
					if ok:
						messagebox.showinfo('Atualizar', 'Usuário atualizado com sucesso')
						upd_win.destroy()
						refresh_list()
					else:
						messagebox.showwarning('Atualizar', 'Nenhuma alteração realizada')
				except Exception as ex:
					messagebox.showerror('Erro', f'Falha ao atualizar: {ex}')

			bfr = tk.Frame(fup, bg=self.COLORS['canvas'])
			# move buttons down one row so they don't overlap the 'Ativo' checkbox
			bfr.grid(row=len(labels) + 1, column=0, columnspan=2, pady=(12,0))
			save_update_button = tk.Button(bfr, text='Salvar', command=submit_update)
			self._style_button(save_update_button)
			save_update_button.pack(side=tk.LEFT, padx=6)
			cancel_update_button = tk.Button(bfr, text='Cancelar', command=upd_win.destroy)
			self._style_button(cancel_update_button)
			cancel_update_button.pack(side=tk.LEFT, padx=6)
			nav_update = tk.Frame(fup, bg=self.COLORS['canvas'])
			nav_update.grid(row=len(labels) + 2, column=0, columnspan=2, pady=(8, 0))
			main_update_button = tk.Button(nav_update, text='Menu Principal', command=lambda: self._close_and_return(upd_win, main_callback))
			self._style_button(main_update_button)
			main_update_button.pack(side=tk.LEFT, padx=6)

		btn_update = tk.Button(action_frame, text='Atualizar', width=16, command=do_update)
		btn_remove = tk.Button(action_frame, text='Remover', width=16, command=do_remove)
		self._style_button(btn_update)
		self._style_button(btn_remove)

		refresh_list()
		# done rendering the users screen

	def _close_and_return(self, win, callback):
		win.destroy()
		if callback:
			callback()

	def _adjust_columns(self, tree: ttk.Treeview, cols: tuple):
		"""Adjust Treeview column widths based on header and cell content."""
		try:
			f = tkfont.nametofont(tree.cget('font'))
		except Exception:
			f = tkfont.nametofont('TkDefaultFont')
		padding = 18
		for c in cols:
			header = tree.heading(c)['text']
			max_w = f.measure(str(header))
			for iid in tree.get_children():
				val = tree.set(iid, c)
				if val is None:
					val = ''
				w = f.measure(str(val))
				if w > max_w:
					max_w = w
			tree.column(c, width=max_w + padding, anchor=tk.CENTER)
    