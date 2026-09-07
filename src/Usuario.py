from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List

from DBProxy import DBProxy
from AuthUtils import hash_password, verify_password


@dataclass
class User:
    id: int | None = None
    nome: str | None = None
    sobrenome: str | None = None
    cpf: str | None = None
    nome_usuario: str | None = None
    senha: str | None = None
    data_admissao: str | None = None
    tipo_acesso: str | None = None
    ativo: int = 1

    @property
    def dadosUsusario(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "nome": self.nome,
            "sobrenome": self.sobrenome,
            "cpf": self.cpf,
            "nome_usuario": self.nome_usuario,
            "senha": self.senha,
            "data_admissao": self.data_admissao,
            "tipo_acesso": self.tipo_acesso,
            "ativo": self.ativo,
        }


class Usuario:
    """User manager backed by SysDB (managed via DBProxy).

    This class will create and manage a `usuarios` table inside the SysDB
    SQLite database (default file: data/SysDB.db). It exposes methods to add,
    update and logically remove users (adicionar, atualizar, remover).
    """

    def __init__(self, db_path: str = "data/SysDB.db"):
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
            ativo INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT
        )
        """
        self.db.execute(sql, commit=True)

    # Password handling is delegated to auth_utils.hash_password / verify_password

    # --- public API ---
    def adicionar(self, nome: str, sobrenome: str, cpf: str, nome_usuario: str, senha: str,
                 data_admissao: Optional[str] = None, tipo_acesso: Optional[str] = None) -> int:
        """Add a new user, return the new id. Raises sqlite3.IntegrityError on duplicates."""
        # Basic validation
        if not nome or not nome_usuario or not senha:
            raise ValueError('nome, nome_usuario and senha are required')
        hashed = hash_password(senha)
        now = datetime.utcnow().isoformat()
        cur = self.db.execute(
            """
            INSERT INTO usuarios (nome, sobrenome, cpf, nome_usuario, senha, data_admissao, tipo_acesso, ativo, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (nome, sobrenome, cpf, nome_usuario, hashed, data_admissao, tipo_acesso, now),
            commit=True,
        )
        return cur.lastrowid

    def atualizar(self, user_id: int, **fields) -> bool:
        """Update fields for user_id. Allowed: nome, sobrenome, cpf, nome_usuario, senha, data_admissao, tipo_acesso, ativo

        Returns True when a row was changed, False otherwise.
        """
        if not fields:
            return False
        allowed = {"nome", "sobrenome", "cpf", "nome_usuario", "senha", "data_admissao", "tipo_acesso", "ativo"}
        set_parts = []
        params: List[Any] = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k == 'senha':
                v = hash_password(v)
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
        """Permanently remove a user from the database.

        Returns True if a row was deleted, False if user not found.
        """
        cur = self.db.execute("DELETE FROM usuarios WHERE id = ?", (user_id,), commit=True)
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
        row = self.db.query_one("SELECT * FROM usuarios WHERE nome_usuario = ?", (nome_usuario,))
        return dict(row) if row else None

    def listar(self, include_inativos: bool = False) -> List[Dict[str, Any]]:
        if include_inativos:
            rows = self.db.query_all("SELECT * FROM usuarios ORDER BY id DESC")
        else:
            rows = self.db.query_all("SELECT * FROM usuarios WHERE ativo = 1 ORDER BY id DESC")
        return [dict(r) for r in rows]

    def close(self):
        self.db.close()


