from datetime import datetime
from typing import Dict, List, Optional

from const import DB_PATH
from DBProxy import DBProxy


class LancheRepository:
    """Responsavel pelas consultas e alteracoes das tabelas de lanches."""

    def __init__(self, db: DBProxy):
        self.db = db
        self._ensure_tables()

    def _ensure_tables(self):
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
                unidade TEXT NOT NULL DEFAULT 'unidade',
                UNIQUE (lanche_id, item_nome),
                FOREIGN KEY (lanche_id) REFERENCES lanches(id) ON DELETE CASCADE
            )
            """,
            commit=True,
        )
        columns = {row["name"] for row in self.db.query_all("PRAGMA table_info(lanche_itens)")}
        if "unidade" not in columns:
            self.db.execute(
                "ALTER TABLE lanche_itens ADD COLUMN unidade TEXT NOT NULL DEFAULT 'unidade'",
                commit=True,
            )

    def salvar(self, lanche) -> int:
        now = datetime.utcnow().isoformat()
        with self.db.transaction():
            if lanche.id is None:
                cursor = self.db.execute(
                    "INSERT INTO lanches (nome, preco, created_at) VALUES (?, ?, ?)",
                    (lanche.nome, lanche.preco, now),
                )
                lanche.id = cursor.lastrowid
            else:
                self.db.execute(
                    "UPDATE lanches SET nome = ?, preco = ?, updated_at = ? WHERE id = ?",
                    (lanche.nome, lanche.preco, now, lanche.id),
                )
                self.db.execute("DELETE FROM lanche_itens WHERE lanche_id = ?", (lanche.id,))
            self.db.executemany(
                "INSERT INTO lanche_itens (lanche_id, item_nome, quantidade, unidade) VALUES (?, ?, ?, ?)",
                (
                    (lanche.id, nome, quantidade, lanche.unidadesLanche.get(nome, "unidade"))
                    for nome, quantidade in lanche.dadosLanche.items()
                ),
            )
        return lanche.id

    def obter_dados(self, lanche_id: int):
        lanche = self.db.query_one(
            "SELECT id, nome, preco FROM lanches WHERE id = ? AND ativo = 1",
            (lanche_id,),
        )
        if not lanche:
            return None
        componentes = self.db.query_all(
            "SELECT item_nome, quantidade, unidade FROM lanche_itens WHERE lanche_id = ? ORDER BY id",
            (lanche_id,),
        )
        return lanche, componentes

    def listar(self) -> List[dict]:
        return [dict(row) for row in self.db.query_all(
            "SELECT id, nome, preco FROM lanches WHERE ativo = 1 ORDER BY nome"
        )]

    def excluir(self, lanche_id: int) -> bool:
        cursor = self.db.execute(
            "UPDATE lanches SET ativo = 0, updated_at = ? WHERE id = ? AND ativo = 1",
            (datetime.utcnow().isoformat(), lanche_id),
            commit=True,
        )
        return cursor.rowcount > 0


class Lanche:
    """Representa um lanche e sua receita, sem depender da interface grafica."""

    def __init__(self, nome: Optional[str] = None, preco: float = 0, db_path: str = DB_PATH):
        self.db = DBProxy(db_path)
        self.repository = LancheRepository(self.db)
        self.id = None
        self.nome = nome
        self.preco = float(preco)
        self.dadosLanche: Dict[str, float] = {}
        self.unidadesLanche: Dict[str, str] = {}

    @staticmethod
    def unidade_da_receita(unidade: str) -> str:
        unidade_normalizada = (unidade or "").strip().lower()
        if unidade_normalizada in {"g", "grama", "gramas", "gram", "kg", "quilo", "quilos", "kilo", "kilos"}:
            return "g"
        return unidade.strip() or "unidade"

    @classmethod
    def quantidade_da_receita(cls, quantidade: float, unidade: str) -> float:
        quantidade = float(quantidade)
        if unidade.strip().lower() in {"kg", "quilo", "quilos", "kilo", "kilos"}:
            return quantidade * 1000
        return quantidade

    def incluirItem(self, nome: str, quantidade: float = 1, unidade: str = "unidade") -> None:
        nome = (nome or "").strip()
        quantidade = float(quantidade)
        if not nome or quantidade <= 0:
            raise ValueError("o item e sua quantidade devem ser validos")
        if nome in self.dadosLanche:
            raise ValueError(f"o item '{nome}' ja existe na receita")
        self.dadosLanche[nome] = self.quantidade_da_receita(quantidade, unidade)
        self.unidadesLanche[nome] = self.unidade_da_receita(unidade)

    def atualizarItem(self, nome: str, nova_quantidade: float) -> None:
        nome = (nome or "").strip()
        nova_quantidade = float(nova_quantidade)
        if nome not in self.dadosLanche:
            raise ValueError(f"o item '{nome}' nao existe na receita")
        if nova_quantidade <= 0:
            raise ValueError("a quantidade deve ser maior que zero")
        self.dadosLanche[nome] = nova_quantidade

    def excluirItem(self, nome: str) -> None:
        if nome not in self.dadosLanche:
            raise ValueError(f"o item '{nome}' nao existe na receita")
        del self.dadosLanche[nome]
        self.unidadesLanche.pop(nome, None)

    def garantir_item_no_estoque(self, nome: str) -> None:
        item = self.db.query_one(
            "SELECT id FROM estoque WHERE nome = ? AND ativo = 1 LIMIT 1", (nome,)
        )
        if item:
            return
        self.db.execute(
            """
            INSERT INTO estoque
                (nome, categoria, marca, fornecedor, vencimento, unidade,
                 qtd_disponivel, data_compra, lote, ativo, created_at)
            VALUES (?, ?, NULL, NULL, NULL, ?, 0, NULL, NULL, 1, ?)
            """,
            (nome, "Ingredientes", "unidade", datetime.utcnow().isoformat()),
        )

    def salvar(self) -> int:
        self._validar()
        with self.db.transaction():
            for item_nome in self.dadosLanche:
                self.garantir_item_no_estoque(item_nome)
            return self.repository.salvar(self)

    def _validar(self):
        self.nome = (self.nome or "").strip()
        if not self.nome:
            raise ValueError("o nome do lanche e obrigatorio")
        if self.preco < 0:
            raise ValueError("o preco nao pode ser negativo")
        if not self.dadosLanche:
            raise ValueError("o lanche deve ter pelo menos um item")

    @classmethod
    def obter(cls, lanche_id: int, db_path: str = DB_PATH):
        lanche = cls(db_path=db_path)
        dados = lanche.repository.obter_dados(lanche_id)
        if not dados:
            lanche.close()
            return None
        row, componentes = dados
        lanche.id, lanche.nome, lanche.preco = row["id"], row["nome"], row["preco"]
        lanche.dadosLanche = {item["item_nome"]: float(item["quantidade"]) for item in componentes}
        lanche.unidadesLanche = {item["item_nome"]: item["unidade"] for item in componentes}
        return lanche

    @classmethod
    def listar(cls, db_path: str = DB_PATH) -> List[dict]:
        db = DBProxy(db_path)
        try:
            return LancheRepository(db).listar()
        finally:
            db.close()

    def componentes(self) -> List[dict]:
        return [
            {"nome": nome, "quantidade": quantidade,
             "unidade": self.unidadesLanche.get(nome, "unidade")}
            for nome, quantidade in self.dadosLanche.items()
        ]

    def close(self):
        self.db.close()

    def excluir(self, lanche_id: int) -> bool:
        return self.repository.excluir(lanche_id)
