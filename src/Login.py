import tkinter as tk
from tkinter import ttk


from typing import Optional, Callable


class Login:
   """Small modal login dialog.

   Usage:
      login = Login(parent)
      creds = login.show()  # returns (username, password) or None if cancelled
   """

   def __init__(self, parent=None, auth_handler: Optional[Callable[[str, str], object]] = None):
      self.parent = parent
      self.username = None
      self.password = None
      self.user = None
      # userType: True for admin, False for atend, None for not-set/other users
      self.userType = None
      # auth_handler: callable(username, password) -> AuthResult-like object
      # If not provided, Login will only use its minimal builtin checks
      self.auth_handler = auth_handler

   def _center(self, win, w=380, h=200):
      win.update_idletasks()
      sw = win.winfo_screenwidth()
      sh = win.winfo_screenheight()
      x = (sw - w) // 2
      y = (sh - h) // 2
      win.geometry(f"{w}x{h}+{x}+{y}")

   def show(self):
      # Create the window
      owns_root = False
      if self.parent is None:
         root = tk.Tk()
         owns_root = True
      else:
         root = tk.Toplevel(self.parent)
         root.transient(self.parent)

      root.title("Login")
      self._center(root, 420, 190)

      # Make it modal
      if self.parent is not None:
         root.grab_set()

      frm = ttk.Frame(root, padding=16)
      frm.pack(expand=True, fill=tk.BOTH)

      ttk.Label(frm, text="Usuário:").grid(row=0, column=0, sticky=tk.W)
      user_entry = ttk.Entry(frm, width=36)
      user_entry.grid(row=0, column=1, pady=6, padx=6)

      ttk.Label(frm, text="Senha:").grid(row=1, column=0, sticky=tk.W)
      pass_entry = ttk.Entry(frm, width=36, show="*")
      pass_entry.grid(row=1, column=1, pady=6, padx=6)

      result = {'value': None}

      def submit(event=None):
         # event is optional so this can be called from the Enter key binding
         u = user_entry.get().strip()
         p = pass_entry.get()
         # Attempt to authenticate using provided handler (AuthService) if available
         if self.auth_handler is not None:
            try:
               res = self.auth_handler(u, p)
               # Res may be an AuthResult-like object with access_type attribute
               if getattr(res, 'ok', False):
                  self.user = getattr(res, 'user', None)
                  at = getattr(res, 'access_type', None)
                  if at == 'admin':
                     self.userType = True
                  elif at == 'atend':
                     self.userType = False
                  else:
                     self.userType = None
               else:
                  # if handler failed to authenticate, fallback to builtin check
                  self.userCheck(u, p)
            except Exception:
               # any errors from handler should not break UI - fallback to builtin
               self.userCheck(u, p)
         else:
            # No handler provided -> use builtin check only
            self.userCheck(u, p)
         # Accept values and return them
         self.username = u
         self.password = p
         result['value'] = (u, p)
         root.destroy()

      def cancel():
         result['value'] = None
         root.destroy()

      btn_frame = ttk.Frame(frm)
      btn_frame.grid(row=2, column=0, columnspan=2, pady=(12, 0))

      from App import App
      app_style = App()

      enter_btn = tk.Button(btn_frame, text="Entrar", command=submit)
      app_style._style_button(enter_btn)
      enter_btn.pack(side=tk.LEFT, padx=6)

      cancel_btn = tk.Button(btn_frame, text="Cancelar", command=cancel)
      app_style._style_button(cancel_btn)
      cancel_btn.pack(side=tk.LEFT, padx=6)

      # Focus
      user_entry.focus_set()

      # allow pressing Enter (Return / keypad Enter) to submit the dialog
      root.bind('<Return>', submit)
      root.bind('<KP_Enter>', submit)

      if owns_root:
         root.mainloop()
      else:
         # Wait for the window to be closed when used as a modal
         root.wait_window()

      return result['value']

   def userCheck(self, nome_usuario: str, senha: str) -> bool:
      """Check for the two built-in credentials and set `self.userType`.

      - admin/admin -> set self.userType = True and return True
      - atend/atend -> set self.userType = False and return True
      - otherwise -> return False (self.userType is left as None)
      """
      if nome_usuario == 'admin' and senha == 'admin':
         self.userType = True
         return True
      if nome_usuario == 'atend' and senha == 'atend':
         self.userType = False
         return True
      # leave userType unchanged for other credentials
      return False