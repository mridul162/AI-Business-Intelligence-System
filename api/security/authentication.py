from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from .errors import AuthenticationError, TokenError
from .models import IdentityStore, Role, User
from .password import verify_password


def _encode(value: bytes) -> str:
	return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
	return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class TokenService:
	"""Minimal HS256 JWT service with strict claims for this prototype."""

	def __init__(self, secret_key: str, *, algorithm: str = "HS256") -> None:
		if algorithm != "HS256":
			raise ValueError("Only HS256 is supported by the prototype token service.")
		if len(secret_key) < 32:
			raise ValueError("JWT secret key must be at least 32 characters.")
		self.secret_key = secret_key.encode("utf-8")
		self.algorithm = algorithm

	def create_access_token(self, user: User, expires_minutes: int = 30) -> str:
		now = int(time.time())
		payload = {
			"sub": str(user.id),
			"tenant_id": str(user.tenant_id),
			"role": user.role.value,
			"iat": now,
			"exp": now + expires_minutes * 60,
		}
		header = {"alg": self.algorithm, "typ": "JWT"}
		encoded_header = _encode(json.dumps(header, separators=(",", ":")).encode())
		encoded_payload = _encode(json.dumps(payload, separators=(",", ":")).encode())
		signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
		signature = hmac.new(self.secret_key, signing_input, hashlib.sha256).digest()
		return f"{encoded_header}.{encoded_payload}.{_encode(signature)}"

	def decode_access_token(self, token: str) -> dict[str, Any]:
		try:
			encoded_header, encoded_payload, encoded_signature = token.split(".")
			header = json.loads(_decode(encoded_header))
			payload = json.loads(_decode(encoded_payload))
			if header.get("alg") != self.algorithm:
				raise TokenError("Unsupported token algorithm.")
			signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
			expected = hmac.new(
				self.secret_key, signing_input, hashlib.sha256
			).digest()
			if not hmac.compare_digest(expected, _decode(encoded_signature)):
				raise TokenError("Invalid token signature.")
			if not isinstance(payload.get("exp"), int) or payload["exp"] <= int(time.time()):
				raise TokenError("Token has expired.")
			UUID(str(payload["sub"]))
			UUID(str(payload["tenant_id"]))
			Role(str(payload["role"]))
			return payload
		except TokenError:
			raise
		except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
			raise TokenError("Malformed access token.") from exc


class AuthenticationService:
	def __init__(self, store: IdentityStore, token_service: TokenService) -> None:
		self.store = store
		self.token_service = token_service

	def authenticate(self, email: str, password: str) -> User:
		user = self.store.get_user_by_email(email)
		if user is None or not user.is_active or not verify_password(password, user.password_hash):
			raise AuthenticationError("Invalid credentials.")
		tenant = self.store.get_tenant(user.tenant_id)
		if tenant is None or not tenant.is_active:
			raise AuthenticationError("Invalid credentials.")
		return user
