"""
tests/test_vllm_alias.py - Pruebas unitarias para el parámetro VLLM_ALIAS en el arranque de vLLM y persistencia en .env.
"""

import os
import unittest
from unittest.mock import patch, mock_open
from app import build_vllm_cmd
from dashboard.core.env_manager import save_env_from_dict


class TestVllmAlias(unittest.TestCase):
    """Verifica la inyección del alias de API para vLLM."""

    @patch.dict(os.environ, {"VLLM_ALIAS": "", "MODEL": "google/gemma-4-E4B-it"}, clear=False)
    def test_build_vllm_cmd_without_alias(self):
        """Verifica que sin VLLM_ALIAS no se inyecte --served-model-name."""
        cmd, meta = build_vllm_cmd()
        self.assertNotIn("--served-model-name", cmd)
        self.assertEqual(meta["vllm_alias"], "")

    @patch.dict(os.environ, {"VLLM_ALIAS": "CorpAI-Gen | Legal & Compliance", "MODEL": "google/gemma-4-E4B-it"}, clear=False)
    def test_build_vllm_cmd_with_alias(self):
        """Verifica que con VLLM_ALIAS se inyecte --served-model-name y su valor correspondiente."""
        cmd, meta = build_vllm_cmd()
        self.assertIn("--served-model-name", cmd)
        idx = cmd.index("--served-model-name")
        self.assertEqual(cmd[idx + 1], "CorpAI-Gen | Legal & Compliance")
        self.assertEqual(meta["vllm_alias"], "CorpAI-Gen | Legal & Compliance")

    @patch.dict(os.environ, {"VLLM_ALIAS": '"CorpAI-Gen | Legal & Compliance"', "MODEL": "google/gemma-4-E4B-it"}, clear=False)
    def test_build_vllm_cmd_with_quoted_alias(self):
        """Verifica que comillas externas en VLLM_ALIAS se limpien adecuadamente."""
        cmd, meta = build_vllm_cmd()
        self.assertIn("--served-model-name", cmd)
        idx = cmd.index("--served-model-name")
        self.assertEqual(cmd[idx + 1], "CorpAI-Gen | Legal & Compliance")
        self.assertEqual(meta["vllm_alias"], "CorpAI-Gen | Legal & Compliance")

    @patch("builtins.open", new_callable=mock_open, read_data="MODEL=test\n")
    def test_save_env_from_dict_vllm_alias_quotes(self, mocked_file):
        """Verifica que save_env_from_dict envuelva VLLM_ALIAS en comillas dobles."""
        save_env_from_dict({"VLLM_ALIAS": "CorpAI-Gen | Legal & Compliance"})
        handle = mocked_file()
        written = "".join(call.args[0] for call in handle.write.call_args_list) if handle.write.call_args_list else ""
        if not written and handle.writelines.call_args_list:
            written = "".join(handle.writelines.call_args[0][0])
        self.assertIn('VLLM_ALIAS="CorpAI-Gen | Legal & Compliance"', written)

    @patch.dict(os.environ, {
        "VLLM_ALIAS": "CorpAI-Gen | Legal & Compliance",
        "VLLM_ATTENTION_BACKEND": "FLASHINFER",
        "MODEL": "olberdingbrands/gemma-4-12B-it-awq",
        "MAX_NUM_BATCHED_TOKENS": "1024"
    }, clear=False)
    def test_batched_tokens_auto_guard_multimodal(self):
        """Verifica que en modelos multimodales (Gemma 4), max_num_batched_tokens se eleve a 4096 si era menor."""
        cmd, meta = build_vllm_cmd()
        self.assertIn("--max-num-batched-tokens", cmd)
        idx = cmd.index("--max-num-batched-tokens")
        self.assertEqual(cmd[idx + 1], "4096")
        # Verificar saneamiento de variables no nativas en os.environ
        self.assertNotIn("VLLM_ALIAS", os.environ)
        self.assertNotIn("VLLM_ATTENTION_BACKEND", os.environ)

    @patch.dict(os.environ, {
        "MODEL": "Qwen/Qwen2.5-7B-Instruct",
        "MAX_NUM_BATCHED_TOKENS": "2048"
    }, clear=False)
    def test_batched_tokens_standard_model(self):
        """Verifica que en modelos estándar de texto se preserve el valor configurado de batched tokens."""
        cmd, meta = build_vllm_cmd()
        self.assertIn("--max-num-batched-tokens", cmd)
        idx = cmd.index("--max-num-batched-tokens")
        self.assertEqual(cmd[idx + 1], "2048")


if __name__ == "__main__":
    unittest.main()
