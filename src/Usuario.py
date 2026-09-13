from dataclasses import dataclass
from datetime import datetime
import re
from typing import Optional, Dict, Any, List

from const import DB_PATH
from DBProxy import DBProxy
from AuthUtils import hash_password, verify_password


@dataclass
class User:
    id: int | None = None
    nome: str | None = None
    sobrenome: str | None = None
    cpf: str | None = None
    data_nascimento: str | None = None
    email: str | None = None
    celular: str | None = None
    nome_usuario: str | None = None
    senha: str | None = None
    data_admissao: str | None = None
    tipo_acesso: str | None = None
    ativo: int = 1

    @property
    def dados_usuario(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "nome": self.nome,
            "sobrenome": self.sobrenome,
            "cpf": self.cpf,
            "data_nascimento": self.data_nascimento,
            "email": self.email,
            "celular": self.celular,
            "nome_usuario": self.nome_usuario,
            "senha": self.senha,
            "data_admissao": self.data_admissao,
            "tipo_acesso": self.tipo_acesso,
            "ativo": self.ativo,
        }

    @property
    def dadosUsusario(self) -> Dict[str, Any]:
        """Compatibilidade com o nome legado da propriedade."""
        return self.dados_usuario


class Usuario:
    """User manager backed by SysDB (managed via DBProxy).

    This class will create and manage a `usuarios` table inside the SysDB
    SQLite database (default file: data/SysDB.db). It exposes methods to add,
    update and logically remove users (adicionar, atualizar, remover).
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db = DBProxy(db_path)
        self._ensure_table()

    def _ensure_table(self):
        sql = """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            sobrenome TEXT NOT NULL,
            cpf INTEGER UNIQUE NOT NULL,
            nome_usuario TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            data_admissao DATE,
            tipo_acesso TEXT,
            data_nascimento DATE,
            email TEXT,
            celular TEXT,
            ativo INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT
        )
        """
        self.db.execute(sql, commit=True)
        columns = {row["name"] for row in self.db.query_all("PRAGMA table_info(usuarios)")}
        migrations = {
            "data_nascimento": "ALTER TABLE usuarios ADD COLUMN data_nascimento DATE",
            "email": "ALTER TABLE usuarios ADD COLUMN email TEXT",
            "celular": "ALTER TABLE usuarios ADD COLUMN celular TEXT",
        }
        for column, migration in migrations.items():
            if column not in columns:
                self.db.execute(migration, commit=True)

    @staticmethod
    def _validar_dados(nome, sobrenome, senha, email, celular):
        nome_completo = f"{nome} {sobrenome}".strip()
        letras = re.sub(r"[^A-Za-zÀ-ÿ]", "", nome_completo)
        if len(letras) < 6:
            raise ValueError("o nome do usuário deve conter pelo menos 6 letras")
        if not re.fullmatch(r"(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}", senha):
            raise ValueError("a senha deve ter 8 caracteres, uma maiúscula, um número e um caractere especial")
        if email and "@" not in email:
            raise ValueError("e-mail inválido")
        if celular:
            digits = re.sub(r"\D", "", celular)
            if len(digits) not in {8, 10, 11}:
                raise ValueError("celular inválido")

    # Password handling is delegated to auth_utils.hash_password / verify_password

    # --- public API ---
    def adicionar(self, nome: str, sobrenome: str, cpf: str, nome_usuario: str, senha: str,
                 data_admissao: Optional[str] = None, tipo_acesso: Optional[str] = None,
                 data_nascimento: Optional[str] = None, email: Optional[str] = None,
                 celular: Optional[str] = None) -> int:
        """Add a new user, return the new id. Raises sqlite3.IntegrityError on duplicates."""
        # Basic validation
        if not nome or not nome_usuario or not senha:
            raise ValueError('nome, nome_usuario and senha are required')
        self._validar_dados(nome, sobrenome, senha, email, celular)
        hashed = hash_password(senha)
        now = datetime.utcnow().isoformat()
        cur = self.db.execute(
            """
            INSERT INTO usuarios (nome, sobrenome, cpf, nome_usuario, senha, data_admissao, tipo_acesso,
                                  data_nascimento, email, celular, ativo, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (nome, sobrenome, cpf, nome_usuario, hashed, data_admissao, tipo_acesso,
             data_nascimento, email, celular, now),
            commit=True,
        )
        return cur.lastrowid

    def atualizar(self, user_id: int, **fields) -> bool:
        """Update fields for user_id. Allowed: nome, sobrenome, cpf, nome_usuario, senha, data_admissao, tipo_acesso, ativo

        Returns True when a row was changed, False otherwise.
        """
        if not fields:
            return False
        allowed = {"nome", "sobrenome", "cpf", "nome_usuario", "senha", "data_admissao",
               "tipo_acesso", "data_nascimento", "email", "celular", "ativo"}
        current = self.obter(user_id) or {}
        merged = {**current, **fields}
        nome_completo = f"{merged.get('nome', '')} {merged.get('sobrenome', '')}".strip()
        letras = re.sub(r"[^A-Za-zÀ-ÿ]", "", nome_completo)
        if len(letras) < 6:
            raise ValueError("o nome do usuário deve conter pelo menos 6 letras")
        if merged.get("email") and "@" not in merged["email"]:
            raise ValueError("e-mail inválido")
        if merged.get("celular") and len(re.sub(r"\D", "", merged["celular"])) not in {8, 10, 11}:
            raise ValueError("celular inválido")
        if fields.get("senha"):
            self._validar_dados(
                merged.get("nome", ""), merged.get("sobrenome", ""), fields["senha"],
                merged.get("email"), merged.get("celular"),
            )
        set_parts = []
        params: List[Any] = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k == 'senha':
                v = hash_password(v)
            if k == "email" and v and "@" not in v:
                raise ValueError("e-mail inválido")
            if k == "celular" and v and len(re.sub(r"\D", "", v)) not in {8, 10, 11}:
                raise ValueError("celular inválido")
            set_parts.append(f"{k} = ?")
            params.append(v)

        if not set_parts:
            return False

        # always set updated_at
        set_parts.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        params.append(user_id)

        sql = f"UPDATE usuarios SET {', '.join(set_parts)} WHERE id = ?"
        cur = self.db.execute(sql, params, commit=True)
        return cur.rowcount > 0

    def remover(self, user_id: int) -> bool:
        """Desativa logicamente um usuário, preservando seu histórico."""
        cur = self.db.execute(
            "UPDATE usuarios SET ativo = 0, updated_at = ? WHERE id = ? AND ativo = 1",
            (datetime.utcnow().isoformat(), user_id),
            commit=True,
        )
        return cur.rowcount > 0

    # helpers
    def obter(self, user_id: int) -> Optional[Dict[str, Any]]:
        row = self.db.query_one("SELECT * FROM usuarios WHERE id = ?", (user_id,))
        return dict(row) if row else None

    def obter_por_nome_usuario(self, nome_usuario: str) -> Optional[Dict[str, Any]]:
        """Lookup a user row by the `nome_usuario` string.

        Returns a dict or None when not found.
        """
        if not nome_usuario:
            return None
        row = self.db.query_one(
            "SELECT * FROM usuarios WHERE nome_usuario = ? AND ativo = 1",
            (nome_usuario,),
        )
        return dict(row) if row else None

    def listar(self, include_inativos: bool = False) -> List[Dict[str, Any]]:
        if include_inativos:
            rows = self.db.query_all("SELECT * FROM usuarios ORDER BY id DESC")
        else:
            rows = self.db.query_all("SELECT * FROM usuarios WHERE ativo = 1 ORDER BY id DESC")
        return [dict(r) for r in rows]

    def close(self):
        self.db.close()


