"""Tests for the Cloud Sandbox interface."""

from pathlib import Path

import pytest

from codepilot.config import Config
from codepilot.sandbox.cloud_sandbox import (
    CloudSandbox,
    LocalSandbox,
    SandboxConfig,
    SandboxInterface,
    create_sandbox,
)


@pytest.fixture
def config():
    return Config(
        _env_file=None,
        sandbox_base_dir="~/.codepilot/sandboxes/",
        sandbox_provider="local",
    )


class TestSandboxInterface:
    """Test the sandbox ABC."""

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            SandboxInterface()  # type: ignore[abstract]

    def test_local_is_instance(self, config):
        sb = LocalSandbox(config)
        assert isinstance(sb, SandboxInterface)

    def test_cloud_is_instance(self, config):
        sb = CloudSandbox(config)
        assert isinstance(sb, SandboxInterface)


class TestLocalSandbox:
    """Test local sandbox via the interface."""

    @pytest.mark.asyncio
    async def test_create_and_cleanup(self, config, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("def hello(): pass\n")

        sc = SandboxConfig(
            base_dir=str(tmp_path / "sandboxes"),
            issue_id=1,
            relevant_files=["src/main.py"],
        )
        sb = LocalSandbox(config)
        path = await sb.create(sc, str(tmp_path))
        assert Path(path).exists()
        assert (Path(path) / "src" / "main.py").exists()
        await sb.cleanup(path)
        assert not Path(path).exists()

    @pytest.mark.asyncio
    async def test_execute(self, config, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("pass\n")

        sc = SandboxConfig(
            base_dir=str(tmp_path / "sandboxes"),
            issue_id=2,
            relevant_files=["src/main.py"],
        )
        sb = LocalSandbox(config)
        path = await sb.create(sc, str(tmp_path))
        output, code = await sb.execute(path, "echo hello")
        assert code == 0
        assert "hello" in output
        await sb.cleanup(path)

    @pytest.mark.asyncio
    async def test_diff(self, config, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("original\n")

        sc = SandboxConfig(
            base_dir=str(tmp_path / "sandboxes"),
            issue_id=3,
            relevant_files=["src/main.py"],
        )
        sb = LocalSandbox(config)
        path = await sb.create(sc, str(tmp_path))
        (Path(path) / "src" / "main.py").write_text("modified\n")
        diff = await sb.get_diff(path, str(tmp_path))
        assert len(diff) > 0
        await sb.cleanup(path)


class TestCloudSandbox:
    """Test cloud sandbox falls back to local."""

    @pytest.mark.asyncio
    async def test_falls_back_to_local(self, config, tmp_path):
        config.sandbox_provider = "daytona"
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("pass\n")

        sc = SandboxConfig(
            base_dir=str(tmp_path / "sandboxes"),
            issue_id=4,
            relevant_files=["src/main.py"],
        )
        sb = CloudSandbox(config)
        path = await sb.create(sc, str(tmp_path))
        assert Path(path).exists()
        await sb.cleanup(path)


class TestCreateSandbox:
    """Test the factory function."""

    def test_local_provider(self, config):
        sb = create_sandbox(config)
        assert isinstance(sb, LocalSandbox)

    def test_unknown_provider_falls_back(self, config):
        config.sandbox_provider = "nonexistent"
        sb = create_sandbox(config)
        assert isinstance(sb, LocalSandbox)
