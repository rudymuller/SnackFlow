import tkinter as tk
import tkinter.font as tkfont
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
import sys

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
except ImportError:
    Image = ImageDraw = ImageFont = ImageTk = None


class Style:
    """Centraliza a identidade visual e os estilos reutilizados pela aplicação."""

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

    def style_button(self, button, tone="primary"):
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
        colors = self.COLORS
        button.configure(
            font=("Segoe UI", 11, "bold"), bg=colors[tone] if tone in colors else colors["primary"],
            fg="white", activebackground=colors["primary_dark"], activeforeground="white",
            relief=tk.FLAT, borderwidth=0, padx=16, pady=8, cursor="hand2",
        )

    def style_heading(self, label):
        label.configure(fg=self.COLORS["ink"], bg=self.COLORS["canvas"])

    def style_subtitle(self, label):
        label.configure(fg=self.COLORS["muted"], bg=self.COLORS["canvas"])

    def add_footer(self, parent):
        """Adiciona o crédito discreto no canto inferior esquerdo."""
        footer = tk.Label(
            parent,
            text="Created by: Rudy Marques",
            font=("Segoe UI", 8),
            bg=parent.cget("bg"),
            fg=self.COLORS["muted"],
            anchor=tk.E,
        )
        footer.pack(side=tk.BOTTOM, fill=tk.X, anchor=tk.E, pady=(8, 0))
        return footer
