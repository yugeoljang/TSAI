from __future__ import annotations

import unittest

from app.config import Settings
from app.security import decrypt_api_key, encrypt_api_key
import app.security as security


class SecurityTests(unittest.TestCase):
    def test_ephemeral_key_is_stable_for_process_lifetime(self) -> None:
        instance = Settings()
        instance.master_key_hex = ""
        first = instance.master_key_bytes
        second = instance.master_key_bytes
        self.assertEqual(first, second)
        self.assertEqual(len(first), 32)

    def test_encrypt_then_decrypt_with_missing_env_key(self) -> None:
        original = security.settings
        instance = Settings()
        instance.master_key_hex = ""
        security.settings = instance
        try:
            encrypted = encrypt_api_key("sk-test-secret")
            self.assertNotIn("sk-test-secret", encrypted)
            self.assertEqual(decrypt_api_key(encrypted), "sk-test-secret")
        finally:
            security.settings = original


if __name__ == "__main__":
    unittest.main()
