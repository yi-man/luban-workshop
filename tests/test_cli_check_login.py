"""Tests for login session verification behavior."""

import time

from click.testing import CliRunner
import pytest

from tools.glm_coding_bot import cli as cli_module
from tools.glm_coding_bot.config import Config


class DummyStatus:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_check_login_missing_user_data_dir(tmp_path):
    runner = CliRunner()
    config = Config(user_data_dir=tmp_path / ".glm-coding-bot")

    original_get_config = cli_module.get_config
    cli_module.get_config = lambda: config
    try:
        result = runner.invoke(cli_module.cli, ["check-login"])
    finally:
        cli_module.get_config = original_get_config

    assert result.exit_code == 0
    assert "未找到登录信息" in result.output
    assert "登录状态: 无效" not in result.output


def test_check_login_invalid_session_even_with_cookie_file(tmp_path, monkeypatch):
    runner = CliRunner()
    user_data_dir = tmp_path / ".glm-coding-bot"
    cookie_file = user_data_dir / "Default" / "Cookies"
    cookie_file.parent.mkdir(parents=True)
    cookie_file.write_text("dummy")

    config = Config(user_data_dir=user_data_dir)

    async def fake_verify_session(_):
        return cli_module.SessionCheckResult.invalid("login button detected")

    monkeypatch.setattr(cli_module, "_verify_login_session", fake_verify_session, raising=False)

    original_get_config = cli_module.get_config
    cli_module.get_config = lambda: config
    try:
        result = runner.invoke(cli_module.cli, ["check-login"])
    finally:
        cli_module.get_config = original_get_config

    assert result.exit_code == 0
    assert "登录状态: 无效" in result.output


def test_check_login_verification_error_reported_separately(tmp_path, monkeypatch):
    runner = CliRunner()
    user_data_dir = tmp_path / ".glm-coding-bot"
    cookie_file = user_data_dir / "Default" / "Cookies"
    cookie_file.parent.mkdir(parents=True)
    cookie_file.write_text("dummy")

    config = Config(user_data_dir=user_data_dir)

    async def fake_verify_session(_):
        return cli_module.SessionCheckResult.error("timeout")

    monkeypatch.setattr(cli_module, "_verify_login_session", fake_verify_session, raising=False)

    original_get_config = cli_module.get_config
    cli_module.get_config = lambda: config
    try:
        result = runner.invoke(cli_module.cli, ["check-login"])
    finally:
        cli_module.get_config = original_get_config

    assert result.exit_code == 0
    assert "登录状态检查失败" in result.output
    assert "登录状态: 无效" not in result.output


def test_classify_login_session_rejects_anonymous_cookie():
    result = cli_module._classify_login_session(
        cookies=[
            {
                "name": "acw_tc",
                "domain": ".bigmodel.cn",
                "expires": time.time() + 300,
            }
        ],
        login_visible=True,
        auth_ui_visible=False,
    )

    assert result.status == "invalid"


@pytest.mark.asyncio
async def test_buy_verification_error_is_not_reported_as_logged_out(tmp_path, monkeypatch):
    user_data_dir = tmp_path / ".glm-coding-bot"
    cookie_file = user_data_dir / "Default" / "Cookies"
    cookie_file.parent.mkdir(parents=True)
    cookie_file.write_text("dummy")

    config = Config(user_data_dir=user_data_dir)
    messages: list[str] = []

    async def fake_verify_session(_):
        return cli_module.SessionCheckResult.error("profile locked")

    monkeypatch.setattr(cli_module, "_verify_login_session", fake_verify_session, raising=False)
    monkeypatch.setattr(cli_module, "get_config", lambda: config)
    monkeypatch.setattr(cli_module, "Status", DummyStatus)
    monkeypatch.setattr(
        cli_module.console,
        "print",
        lambda *args, **kwargs: messages.append(" ".join(str(arg) for arg in args)),
    )

    await cli_module._buy("Max", "quarterly", "10:00:00", headless=True, now=True)

    output = "\n".join(messages)
    assert "登录状态校验失败" in output
    assert "登录状态无效，请先运行" not in output
