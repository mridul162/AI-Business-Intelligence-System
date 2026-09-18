from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


_SCHEME = "scrypt"
_SALT_BYTES = 16
_KEY_BYTES = 32
_N = 2**14
_R = 8
_P = 1


def hash_password(password: str) -> str:
	if not password:
		raise ValueError("Password must not be empty.")
	salt = secrets.token_bytes(_SALT_BYTES)
	digest = hashlib.scrypt(
		password.encode("utf-8"),
		salt=salt,
		n=_N,
		r=_R,
		p=_P,
		dklen=_KEY_BYTES,
	)
	encode = lambda value: base64.urlsafe_b64encode(value).decode("ascii")
	return f"{_SCHEME}${_N}${_R}${_P}${encode(salt)}${encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
	if not password or not password_hash:
		return False
	try:
		scheme, n, r, p, salt_text, digest_text = password_hash.split("$")
		if scheme != _SCHEME:
			return False
		salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
		expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
		actual = hashlib.scrypt(
			password.encode("utf-8"),
			salt=salt,
			n=int(n),
			r=int(r),
			p=int(p),
			dklen=len(expected),
		)
	except (ValueError, TypeError):
		return False
	return hmac.compare_digest(actual, expected)
