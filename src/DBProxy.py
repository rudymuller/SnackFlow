
import sqlite3
from typing import Optional, Any, Iterable, Tuple
from contextlib import contextmanager


class DBProxy:
    """Simple SQLite database proxy for SysDB.

    Usage:
        db = DBProxy()  # uses data/SysDB.db in the repo by default
        db.execute("CREATE TABLE IF NOT EXISTS ...")

    The class provides helpers to run queries and a context-manager interface.
    """

    def __init__(self, db_path: str = "data/SysDB.db", *, enable_foreign_keys: bool = True):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.enable_foreign_keys = enable_foreign_keys
        self.connect()

    def connect(self) -> None:
        """Open a connection to the SQLite database (if not already opened)."""
        if self.conn:
            return
        # ensure parent directory exists and move old root DB if needed
        import os, shutil
        parent = os.path.dirname(self.db_path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)

        # if an old SysDB.db is at repo root, move it into data/
        try:
            root_db = os.path.join(os.getcwd(), 'SysDB.db')
            if os.path.exists(root_db) and os.path.abspath(root_db) != os.path.abspath(self.db_path):
                shutil.move(root_db, self.db_path)
        except Exception:
            pass

        # allow multi-threaded usage if required; keep default check_same_thread=True
        self.conn = sqlite3.connect(self.db_path)
        # return rows as sqlite3.Row for convenience
        self.conn.row_factory = sqlite3.Row
        if self.enable_foreign_keys:
            try:
                self.conn.execute("PRAGMA foreign_keys = ON;")
            except Exception:
                # pragma may not be supported in some sqlite builds; ignore failures
                pass

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            try:
                self.conn.close()
            finally:
                self.conn = None

    def execute(self, sql: str, params: Optional[Iterable[Any]] = None, commit: bool = False) -> sqlite3.Cursor:
        """Execute a SQL statement and return the cursor.

        Params accepts any iterable (tuple/list) that maps to SQL parameters.
        If commit=True the transaction is committed after execution.
        """
        if self.conn is None:
            self.connect()
        cur = self.conn.cursor()
        if params:
            cur.execute(sql, tuple(params))
        else:
            cur.execute(sql)
        if commit:
            self.conn.commit()
        return cur

    def executemany(self, sql: str, seq_of_params: Iterable[Tuple]) -> sqlite3.Cursor:
        if self.conn is None:
            self.connect()
        cur = self.conn.cursor()
        cur.executemany(sql, seq_of_params)
        self.conn.commit()
        return cur

    def query_all(self, sql: str, params: Optional[Iterable[Any]] = None):
        cur = self.execute(sql, params)
        return cur.fetchall()

    def query_one(self, sql: str, params: Optional[Iterable[Any]] = None):
        cur = self.execute(sql, params)
        return cur.fetchone()

    @contextmanager
    def transaction(self):
        """Context manager for small transactions.

        Usage:
            with db.transaction():
                db.execute(...)
                db.execute(...)
        """
        if self.conn is None:
            self.connect()
        try:
            yield self
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # allow use with `with DBProxy(...) as db:`
    def __enter__(self):
        if self.conn is None:
            self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            try:
                if self.conn:
                    self.conn.commit()
            finally:
                self.close()
        else:
            # on exception: close the connection and re-raise
            self.close()
            return False


"""if __name__ == '__main__':
    # quick demo: create a tiny config table and insert a row (in data/ by default)
    db = DBProxy('data/SysDB_demo.db')
    db.execute('CREATE TABLE IF NOT EXISTS demo (id INTEGER PRIMARY KEY, name TEXT)', commit=True)
    db.execute('INSERT INTO demo (name) VALUES (?)', ('example',), commit=True)
    rows = db.query_all('SELECT * FROM demo')
    print('Rows in demo:', [dict(r) for r in rows])
    db.close()"""

    
