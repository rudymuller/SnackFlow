"""Authentication service: centralizes credential checks.

This module implements AuthService which checks for builtin accounts and uses
Usuario (DB-backed) lookups to validate credentials. It returns a consistent
result object that Login and other callers can use (e.g., user dict and
access-type mapping).
"""
from __future__ import annotations

from typing import Optional, Dict, Any

from Usuario import Usuario
from AuthUtils import verify_password


class AuthResult:
    """Small immutable payload returned by AuthService.authenticate()."""

    def __init__(self, ok: bool, user: Optional[Dict[str, Any]] = None, access_type: Optional[str] = None):
        self.ok = ok
        self.user = user
        # access_type: 'admin', 'atend' or None
        self.access_type = access_type

    def __repr__(self) -> str:
        return f"AuthResult(ok={self.ok}, access_type={self.access_type}, user_id={self.user and self.user.get('id')})"


class AuthService:
    """Simple authentication service.

    Behavior:
      - builtin accounts 'admin'/'admin' -> access_type 'admin'
      - builtin accounts 'atend'/'atend' -> access_type 'atend'
      - else lookup Usuario by nome_usuario and verify hashed password
    """

    def __init__(self, user_repo: Optional[Usuario] = None):
        self.user_repo = user_repo or Usuario()

    def authenticate(self, username: str, password: str) -> AuthResult:
        username = (username or '').strip()
        password = password or ''

        # quick builtin fallbacks
        if username == 'admin' and password == 'admin':
            return AuthResult(ok=True, user={'nome_usuario': 'admin', 'tipo_acesso': 'admin'}, access_type='admin')
        if username == 'atend' and password == 'atend':
            return AuthResult(ok=True, user={'nome_usuario': 'atend', 'tipo_acesso': 'atend'}, access_type='atend')

        # DB-backed user
        try:
            row = self.user_repo.obter_por_nome_usuario(username)
        except Exception:
            # If the repository raises, hide implementation details and just fail auth
            return AuthResult(ok=False)

        if not row:
            return AuthResult(ok=False)

        stored_hash = row.get('senha')
        if not stored_hash:
            return AuthResult(ok=False)

        if verify_password(password, stored_hash):
            return AuthResult(ok=True, user=row, access_type=row.get('tipo_acesso'))

        return AuthResult(ok=False)


__all__ = ['AuthService', 'AuthResult']