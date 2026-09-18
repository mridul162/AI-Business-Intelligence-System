class AuthenticationError(Exception):
	"""Credentials or access token are invalid."""


class AuthorizationError(Exception):
	"""An authenticated principal lacks the required permission."""


class TokenError(AuthenticationError):
	"""A token is malformed, expired, or has an invalid signature."""
