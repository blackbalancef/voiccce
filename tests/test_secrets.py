import os
import tempfile
import unittest
from pathlib import Path

from agent_voice.config import AgentVoiceConfig
from agent_voice.secrets import get_dotenv_secret, resolve_openai_api_key


class SecretTests(unittest.TestCase):
    def test_env_key_wins(self) -> None:
        env_name = "VOICCCE_TEST_OPENAI_KEY"
        os.environ[env_name] = "test-key"
        try:
            config = AgentVoiceConfig(
                voice_api_key_env=env_name,
                voice_api_key_keychain_service="voiccce-test-unused",
                voice_api_key_keychain_account="openai-test-unused",
            )

            key, status = resolve_openai_api_key(config)

            self.assertEqual(key, "test-key")
            self.assertEqual(status.source, "env")
            self.assertTrue(status.available)
        finally:
            os.environ.pop(env_name, None)

    def test_dotenv_key_is_used_after_env(self) -> None:
        env_name = "VOICCCE_TEST_OPENAI_KEY"
        os.environ.pop(env_name, None)
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.toml"
            dotenv_path = Path(tmp) / ".env"
            dotenv_path.write_text(f'{env_name}="dotenv-key"\n', encoding="utf-8")
            config = AgentVoiceConfig(
                config_path=config_path,
                voice_api_key_env=env_name,
                voice_api_key_keychain_service="voiccce-test-unused",
                voice_api_key_keychain_account="openai-test-unused",
            )

            key, status = resolve_openai_api_key(config)

            self.assertEqual(key, "dotenv-key")
            self.assertEqual(status.source, "dotenv")
            self.assertTrue(status.available)

    def test_dotenv_parser_ignores_comments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dotenv_path = Path(tmp) / ".env"
            dotenv_path.write_text("# ignored\nOPENAI_API_KEY=abc\n", encoding="utf-8")

            self.assertEqual(get_dotenv_secret(dotenv_path, "OPENAI_API_KEY"), "abc")


if __name__ == "__main__":
    unittest.main()
