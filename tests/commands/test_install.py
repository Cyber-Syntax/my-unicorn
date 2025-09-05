from argparse import Namespace
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.commands.install import InstallCommand, InstallHandler
from my_unicorn.models import ValidationError


@pytest.fixture
def mock_dependencies():
    """Fixture to mock dependencies for InstallCommand."""
    session = AsyncMock()
    github_client = MagicMock()
    catalog_manager = MagicMock()
    config_manager = MagicMock()
    install_dir = Path("/mock/install/dir")
    download_dir = Path("/mock/download/dir")

    return {
        "session": session,
        "github_client": github_client,
        "catalog_manager": catalog_manager,
        "config_manager": config_manager,
        "install_dir": install_dir,
        "download_dir": download_dir,
    }


@pytest.fixture
def install_command(mock_dependencies):
    """Fixture to create an InstallCommand instance with mocked dependencies."""
    deps = mock_dependencies
    return InstallCommand(
        session=deps["session"],
        github_client=deps["github_client"],
        catalog_manager=deps["catalog_manager"],
        config_manager=deps["config_manager"],
        install_dir=deps["install_dir"],
        download_dir=deps["download_dir"],
    )


@pytest.mark.skip(reason="Install command now uses template pattern, needs test rewrite")
@pytest.mark.asyncio
async def test_execute_with_valid_targets(install_command, mock_dependencies):
    """Test InstallCommand.execute with valid targets."""
    mock_dependencies["catalog_manager"].get_available_apps.return_value = {
        "app1": {},
        "app2": {},
    }
    mock_dependencies["catalog_manager"].get_app_config.return_value = {"mock": "config"}
    mock_dependencies["session"].get = AsyncMock(return_value=MagicMock(status=200))
    mock_dependencies["github_client"].get_repo = AsyncMock(return_value={"mock": "repo"})

    # Initialize services with progress
    install_command._initialize_services_with_progress(show_progress=False)

    # Mock the template method execution
    with patch.object(install_command, '_execute_catalog_install', new_callable=AsyncMock) as mock_catalog:
        with patch.object(install_command, '_execute_url_install', new_callable=AsyncMock) as mock_url:
            mock_catalog.return_value = [{"success": True}]
            mock_url.return_value = [{"success": True}]

            targets = ["app1", "https://github.com/mock/repo"]
            results = await install_command.execute(targets)

            assert len(results) == 2
            assert all(result["success"] for result in results)


@pytest.mark.asyncio
async def test_execute_with_invalid_targets(install_command, mock_dependencies):
    """Test InstallCommand.execute with invalid targets."""
    mock_dependencies["catalog_manager"].get_available_apps.return_value = {
        "app1": {},
        "app2": {},
    }

    targets = ["invalid_app"]
    with pytest.raises(ValidationError) as excinfo:
        await install_command.execute(targets)

    assert "Unknown applications or invalid URLs: invalid_app" in str(excinfo.value)


@pytest.mark.asyncio
async def test_execute_no_targets(install_command):
    """Test InstallCommand.execute with no targets."""
    with pytest.raises(ValidationError) as excinfo:
        await install_command.execute([])

    assert "No installation targets provided" in str(excinfo.value)


@pytest.mark.asyncio
async def test_install_handler_execute_with_no_targets(monkeypatch, mock_dependencies):
    """Test InstallHandler.execute with no targets."""
    handler = InstallHandler(
        config_manager=mock_dependencies["config_manager"],
        auth_manager=MagicMock(),
        update_manager=MagicMock(),
    )
    args = Namespace(targets=[])

    logger_mock = MagicMock()
    monkeypatch.setattr("my_unicorn.commands.install.logger", logger_mock)

    await handler.execute(args)

    logger_mock.error.assert_called_once_with("❌ No targets specified.")
    logger_mock.info.assert_called_once_with(
        "💡 Use 'my-unicorn list' to see available catalog apps."
    )


@pytest.mark.asyncio
async def test_install_handler_execute_with_valid_targets(monkeypatch, mock_dependencies):
    """Test InstallHandler.execute with valid targets."""
    handler = InstallHandler(
        config_manager=mock_dependencies["config_manager"],
        auth_manager=MagicMock(),
        update_manager=MagicMock(),
    )
    args = Namespace(
        targets=["app1", "https://github.com/mock/repo"], concurrency=3, no_verify=False
    )

    mock_dependencies["catalog_manager"].get_available_apps.return_value = {
        "app1": {},
        "app2": {},
    }
    mock_dependencies["catalog_manager"].get_app_config.return_value = {"mock": "config"}
    mock_dependencies["session"].get = AsyncMock(return_value=MagicMock(status=200))
    mock_dependencies["github_client"].get_repo = AsyncMock(return_value={"mock": "repo"})

    install_command_mock = MagicMock()
    install_command_mock.execute = AsyncMock(return_value=[{"success": True}])

    monkeypatch.setattr(
        "my_unicorn.commands.install.InstallCommand",
        lambda *args, **kwargs: install_command_mock,
    )

    logger_mock = MagicMock()
    monkeypatch.setattr("my_unicorn.commands.install.logger", logger_mock)

    await handler.execute(args)

    install_command_mock.execute.assert_called_once_with(
        ["app1", "https://github.com/mock/repo"],
        concurrent=3,
        show_progress=True,
        verify_downloads=True,
        force=False,
        update=False,
    )
    logger_mock.info.assert_called_with("All installations completed successfully")
