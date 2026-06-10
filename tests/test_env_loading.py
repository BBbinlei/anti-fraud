"""Tests for config.py 的 .env 加载机制（ENV_FILE 常量 + load_dotenv 行为）。

不调真实 LLM/网络；用临时 .env 与唯一变量名，避免污染真实环境。
"""

import os

from dotenv import dotenv_values, load_dotenv

import config

TEST_KEY = "ANTIFRAUD_TEST_ENV_VAR"


def test_env_file_constant_points_to_repo_root():
    assert config.ENV_FILE == config.BASE_DIR / ".env"
    assert config.ENV_FILE.name == ".env"


def test_dotenv_file_is_parsed(tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"{TEST_KEY}=sk-from-file\n", encoding="utf-8")

    values = dotenv_values(env)

    assert values[TEST_KEY] == "sk-from-file"


def test_load_dotenv_injects_into_environment(tmp_path, monkeypatch):
    monkeypatch.delenv(TEST_KEY, raising=False)
    env = tmp_path / ".env"
    env.write_text(f"{TEST_KEY}=sk-loaded\n", encoding="utf-8")

    load_dotenv(env)
    try:
        assert os.environ[TEST_KEY] == "sk-loaded"
    finally:
        os.environ.pop(TEST_KEY, None)


def test_shell_env_takes_precedence_over_dotenv(tmp_path, monkeypatch):
    # config 使用 override=False（默认）：真实 shell 环境变量优先于 .env 文件值。
    monkeypatch.setenv(TEST_KEY, "sk-from-shell")
    env = tmp_path / ".env"
    env.write_text(f"{TEST_KEY}=sk-from-file\n", encoding="utf-8")

    load_dotenv(env)

    assert os.environ[TEST_KEY] == "sk-from-shell"
