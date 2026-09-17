from typing import cast

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

_password_hasher = PasswordHash.recommended()


class PasswordService:
    """Service for hashing and verifying user passwords."""

    @staticmethod
    def hash(password: str) -> str:
        """
        Hash a plaintext password.

        Args:
            password: Plaintext password.

        Returns:
            Secure password hash.
        """
        if not password.strip():
            raise ValueError("Password cannot be empty.")

        return cast(str, _password_hasher.hash(password))

    @staticmethod
    def verify(
        password: str,
        password_hash: str,
    ) -> bool:
        """
        Verify a plaintext password against a stored hash.

        Returns:
            True if the password matches, otherwise False.
        """

        try:
            return cast(
                bool,
                _password_hasher.verify(
                    password,
                    password_hash,
                ),
            )
        except UnknownHashError:
            # pwdlib raises different exceptions for malformed hashes
            # depending on the configured hasher. Treat invalid hashes
            # as verification failures.
            return False
