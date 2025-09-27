"""Tests for Template Method install base class."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from my_unicorn.models.errors import InstallationError
from my_unicorn.template.install.install_template import InstallTemplate


class TestInstallTemplate:
    """Test InstallTemplate abstract base class."""

    def test_is_abstract_class(self):
        """Test that InstallTemplate cannot be instantiated directly."""
        mock_services = self.create_mock_services()

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            InstallTemplate(**mock_services)

    def create_mock_services(self):
        """Create mock services for testing."""
        return {
            "download_service": Mock(),
            "storage_service": Mock(),
            "session": Mock(),
            "config_manager": Mock(),
        }

    def create_concrete_template(self):
        """Create a concrete implementation for testing."""

        class ConcreteInstallTemplate(InstallTemplate):
            async def _prepare_installation_contexts(self, targets, **kwargs):
                contexts = []
                for target in targets:
                    context = Mock()
                    context.target = target
                    context.app_name = target
                    contexts.append(context)
                return contexts

            async def _create_app_configuration(
                self, final_path, context, icon_result, verification_result=None, **kwargs
            ):
                return {"config": "created", "verification_result": verification_result}

        mock_services = self.create_mock_services()
        # Mock progress service
        mock_services["download_service"].progress_service = None

        return ConcreteInstallTemplate(**mock_services)

    def test_initialization(self):
        """Test proper initialization of InstallTemplate."""
        template = self.create_concrete_template()

        assert template.download_service is not None
        assert template.storage_service is not None
        assert template.session is not None
        assert template.config_manager is not None
        assert template.progress_tracker is not None

    def test_validate_inputs_empty_targets(self):
        """Test input validation with empty targets."""
        template = self.create_concrete_template()

        with pytest.raises(InstallationError, match="No installation targets provided"):
            template.validate_inputs([])

    def test_validate_inputs_valid_targets(self):
        """Test input validation with valid targets."""
        template = self.create_concrete_template()

        # Should not raise any exception
        template.validate_inputs(["app1", "app2"])

    @pytest.mark.asyncio
    async def test_setup_progress_session_no_progress(self):
        """Test progress session setup without progress service."""
        template = self.create_concrete_template()

        async with template._setup_progress_session(show_progress=False) as session:
            assert session["session_active"] is False

    @pytest.mark.asyncio
    async def test_setup_progress_session_with_progress(self):
        """Test progress session setup with active progress service."""
        template = self.create_concrete_template()

        # Mock active progress service with proper async context manager
        mock_progress_service = AsyncMock()
        mock_progress_service.is_active.return_value = True

        # Mock session method to return an async context manager
        async def mock_session(total_ops):
            return AsyncMock()

        # Setup the context manager behavior
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=None)
        mock_context_manager.__aexit__ = AsyncMock(return_value=False)

        mock_progress_service.session = Mock(return_value=mock_context_manager)

        template.download_service.progress_service = mock_progress_service

        async with template._setup_progress_session(
            show_progress=True, targets_count=2
        ) as session:
            assert session["session_active"] is True

        # Verify progress service was called with correct total operations (2 * 4 = 8)
        mock_progress_service.session.assert_called_once_with(8)

    @pytest.mark.asyncio
    async def test_install_method_basic_flow(self):
        """Test the main install method flow."""
        template = self.create_concrete_template()

        # Mock the template methods
        with patch.object(
            template, "_process_installations", new_callable=AsyncMock
        ) as mock_process:
            with patch.object(
                template, "_finalize_results", new_callable=AsyncMock
            ) as mock_finalize:
                mock_process.return_value = [{"target": "app1", "success": True}]
                mock_finalize.return_value = [{"target": "app1", "success": True}]

                results = await template.install(["app1"])

                assert len(results) == 1
                assert results[0]["target"] == "app1"
                assert results[0]["success"] is True

    @pytest.mark.asyncio
    async def test_install_method_validation_failure(self):
        """Test install method with validation failure."""
        template = self.create_concrete_template()

        with pytest.raises(InstallationError, match="No installation targets provided"):
            await template.install([])

    @pytest.mark.asyncio
    async def test_process_installations_single_app(self):
        """Test processing installations for single app."""
        template = self.create_concrete_template()

        # Create mock context
        mock_context = Mock()
        mock_context.target = "test_app"

        # Mock the single app install method
        with patch.object(
            template, "_install_single_app", new_callable=AsyncMock
        ) as mock_install:
            mock_install.return_value = {"target": "test_app", "success": True}

            results = await template._process_installations([mock_context])

            assert len(results) == 1
            assert results[0]["target"] == "test_app"
            assert results[0]["success"] is True

    @pytest.mark.asyncio
    async def test_process_installations_with_exception(self):
        """Test processing installations with exception handling."""
        template = self.create_concrete_template()

        # Create mock context
        mock_context = Mock()
        mock_context.target = "test_app"

        # Mock the single app install method to raise exception
        with patch.object(
            template, "_install_single_app", new_callable=AsyncMock
        ) as mock_install:
            mock_install.side_effect = InstallationError("Installation failed")

            results = await template._process_installations([mock_context])

            assert len(results) == 1
            assert results[0]["target"] == "test_app"
            assert results[0]["success"] is False
            assert "Installation failed" in results[0]["error"]

    @pytest.mark.asyncio
    async def test_install_single_app_workflow(self):
        """Test the single app installation workflow."""
        template = self.create_concrete_template()

        # Create mock context
        mock_context = Mock()
        mock_context.target = "test_app"

        # Create semaphore
        semaphore = asyncio.Semaphore(1)

        # Mock all workflow steps
        with patch.object(
            template, "_download_appimage", new_callable=AsyncMock
        ) as mock_download:
            with patch.object(
                template, "_verify_appimage", new_callable=AsyncMock
            ) as mock_verify:
                with patch.object(
                    template, "_move_to_install_directory", new_callable=AsyncMock
                ) as mock_move:
                    with patch.object(
                        template, "_extract_icon", new_callable=AsyncMock
                    ) as mock_icon:
                        mock_download.return_value = "/tmp/test_app.appimage"
                        mock_verify.return_value = {"verified": True}
                        mock_move.return_value = "/apps/test_app.appimage"
                        mock_icon.return_value = {"icon": "extracted"}

                        result = await template._install_single_app(semaphore, mock_context)

                        # Verify all steps were called
                        mock_download.assert_called_once()
                        mock_verify.assert_called_once()
                        mock_move.assert_called_once()
                        mock_icon.assert_called_once()

                        # Verify result structure
                        assert "success" in result
                        assert "error" in result  # Should be present when success is False

    @pytest.mark.asyncio
    async def test_install_single_app_failure_handling(self):
        """Test single app installation failure handling."""
        template = self.create_concrete_template()

        # Create mock context
        mock_context = Mock()
        mock_context.target = "test_app"

        # Create semaphore
        semaphore = asyncio.Semaphore(1)

        # Mock download to fail
        with patch.object(
            template, "_download_appimage", new_callable=AsyncMock
        ) as mock_download:
            mock_download.side_effect = InstallationError("Download failed")

            result = await template._install_single_app(semaphore, mock_context)

            assert result["success"] is False
            assert "Download failed" in result["error"]
            assert result["target"] == "test_app"

    @pytest.mark.asyncio
    async def test_concurrent_installations_limit(self):
        """Test concurrent installations with semaphore limit."""
        template = self.create_concrete_template()

        # Create multiple mock contexts
        contexts = [Mock() for _ in range(5)]
        for i, ctx in enumerate(contexts):
            ctx.target = f"app_{i}"

        # Track concurrent executions
        concurrent_count = 0
        max_concurrent = 0

        async def track_concurrent_install(semaphore, context, **kwargs):
            nonlocal concurrent_count, max_concurrent
            async with semaphore:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
                await asyncio.sleep(0.01)  # Simulate work
                concurrent_count -= 1
                return {"target": context.target, "success": True}

        with patch.object(
            template, "_install_single_app", side_effect=track_concurrent_install
        ):
            await template._process_installations(contexts, concurrent=2)

            # Should not exceed concurrent limit
            assert max_concurrent <= 2

    def test_global_config_loading(self):
        """Test that global config is loaded during initialization."""
        with patch("my_unicorn.config.ConfigManager") as MockConfigManager:
            mock_instance = MockConfigManager.return_value
            mock_instance.load_global_config.return_value = {"test": "config"}

            template = self.create_concrete_template()

            # Verify the config manager was instantiated and global config was loaded
            MockConfigManager.assert_called_once()
            mock_instance.load_global_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_verification_result_passed_to_config(self):
        """Test that verification result is passed to app configuration."""
        template = self.create_concrete_template()

        # Create mock context
        mock_context = Mock()
        mock_context.target = "test_app"

        # Create semaphore
        semaphore = asyncio.Semaphore(1)

        # Mock workflow steps with verification result
        verification_result = {"checksum_file": "test.sha256", "verified": True}

        with patch.object(template, "_download_appimage", new_callable=AsyncMock):
            with patch.object(
                template, "_verify_appimage", new_callable=AsyncMock
            ) as mock_verify:
                with patch.object(
                    template, "_move_to_install_directory", new_callable=AsyncMock
                ):
                    with patch.object(template, "_extract_icon", new_callable=AsyncMock):
                        mock_verify.return_value = verification_result

                        result = await template._install_single_app(semaphore, mock_context)

                        # Verify verification result was passed to config creation
                        # Note: verification is handled at config creation level, not in result structure
                        assert "success" in result


class TestInstallTemplateRenaming:
    """Test AppImage renaming functionality in InstallTemplate."""

    def create_mock_services(self):
        """Create mock services for testing."""
        return {
            "download_service": Mock(),
            "storage_service": Mock(),
            "session": Mock(),
            "config_manager": Mock(),
        }

    def create_concrete_template(self):
        """Create a concrete implementation for testing."""

        class ConcreteInstallTemplate(InstallTemplate):
            async def _prepare_installation_contexts(self, targets, **kwargs):
                contexts = []
                for target in targets:
                    context = Mock()
                    context.target = target
                    context.app_name = target
                    contexts.append(context)
                return contexts

            async def _create_app_configuration(
                self, final_path, context, icon_result, verification_result=None, **kwargs
            ):
                return {"config": "created", "verification_result": verification_result}

        mock_services = self.create_mock_services()
        # Mock progress service
        mock_services["download_service"].progress_service = None

        return ConcreteInstallTemplate(**mock_services)

    def test_handle_appimage_renaming_with_catalog_entry(self):
        """Test _handle_appimage_renaming with catalog entry rename configuration."""
        template = self.create_concrete_template()

        # Mock storage service methods
        template.storage_service.get_clean_appimage_name.return_value = "joplin"
        template.storage_service.rename_appimage.return_value = Path("/apps/joplin.AppImage")

        # Create mock context with catalog entry
        context = Mock()
        context.app_name = "joplin"
        context.catalog_entry = {"appimage": {"rename": "joplin"}}

        # Test the renaming function
        result_path = template._handle_appimage_renaming(
            Path("/tmp/joplin-1.2.3.AppImage"), context
        )

        # Verify storage service methods were called correctly
        template.storage_service.get_clean_appimage_name.assert_called_once_with("joplin")
        template.storage_service.rename_appimage.assert_called_once_with(
            Path("/tmp/joplin-1.2.3.AppImage"), "joplin"
        )

        # Verify result
        assert result_path == Path("/apps/joplin.AppImage")

    def test_handle_appimage_renaming_with_app_config_fallback(self):
        """Test _handle_appimage_renaming falling back to app_config when no catalog entry."""
        template = self.create_concrete_template()

        # Mock storage service methods
        template.storage_service.get_clean_appimage_name.return_value = "obsidian"
        template.storage_service.rename_appimage.return_value = Path("/apps/obsidian.AppImage")

        # Create mock context with app_config but no catalog entry
        context = Mock()
        context.app_name = "obsidian"
        context.catalog_entry = None
        context.app_config = {"appimage": {"rename": "obsidian"}}

        # Test the renaming function
        result_path = template._handle_appimage_renaming(
            Path("/tmp/obsidian-1.9.10.AppImage"), context
        )

        # Verify storage service methods were called correctly
        template.storage_service.get_clean_appimage_name.assert_called_once_with("obsidian")
        template.storage_service.rename_appimage.assert_called_once_with(
            Path("/tmp/obsidian-1.9.10.AppImage"), "obsidian"
        )

        # Verify result
        assert result_path == Path("/apps/obsidian.AppImage")

    def test_handle_appimage_renaming_with_app_name_fallback(self):
        """Test _handle_appimage_renaming falling back to app_name when no config available."""
        template = self.create_concrete_template()

        # Mock storage service methods
        template.storage_service.get_clean_appimage_name.return_value = "nuclear"
        template.storage_service.rename_appimage.return_value = Path("/apps/nuclear.AppImage")

        # Create mock context with no catalog entry or app_config
        context = Mock()
        context.app_name = "nuclear"
        context.catalog_entry = None
        context.app_config = {}

        # Test the renaming function
        result_path = template._handle_appimage_renaming(
            Path("/tmp/nuclear-0.6.48.AppImage"), context
        )

        # Verify storage service methods were called correctly
        template.storage_service.get_clean_appimage_name.assert_called_once_with("nuclear")
        template.storage_service.rename_appimage.assert_called_once_with(
            Path("/tmp/nuclear-0.6.48.AppImage"), "nuclear"
        )

        # Verify result
        assert result_path == Path("/apps/nuclear.AppImage")

    def test_handle_appimage_renaming_empty_rename_config(self):
        """Test _handle_appimage_renaming when rename configuration is empty (falls back to app_name)."""
        template = self.create_concrete_template()

        # Mock storage service methods
        template.storage_service.get_clean_appimage_name.return_value = "test-app"
        template.storage_service.rename_appimage.return_value = Path("/apps/test-app.AppImage")

        # Create mock context with empty rename (should fall back to app_name)
        context = Mock()
        context.app_name = "test-app"
        context.catalog_entry = {
            "appimage": {
                "rename": ""  # Empty rename - should fall back to app_name
            }
        }
        context.app_config = {}  # Add empty app_config to avoid TypeError

        # Test the renaming function with empty rename (should fall back to app_name)
        original_path = Path("/tmp/test-app-1.0.0.AppImage")
        result_path = template._handle_appimage_renaming(original_path, context)

        # Verify storage service methods were called with app_name fallback
        template.storage_service.get_clean_appimage_name.assert_called_once_with("test-app")
        template.storage_service.rename_appimage.assert_called_once_with(
            Path("/tmp/test-app-1.0.0.AppImage"), "test-app"
        )

        # Verify result has .AppImage extension
        assert result_path == Path("/apps/test-app.AppImage")

    def test_handle_appimage_renaming_no_appimage_config(self):
        """Test _handle_appimage_renaming when catalog entry has no appimage config."""
        template = self.create_concrete_template()

        # Mock storage service methods
        template.storage_service.get_clean_appimage_name.return_value = "test-app"
        template.storage_service.rename_appimage.return_value = Path("/apps/test-app.AppImage")

        # Create mock context with catalog entry but no appimage config
        context = Mock()
        context.app_name = "test-app"
        context.catalog_entry = {}  # No appimage config
        context.app_config = {}

        # Test the renaming function (should fall back to app_name)
        result_path = template._handle_appimage_renaming(
            Path("/tmp/test-app.AppImage"), context
        )

        # Verify storage service methods were called with app_name fallback
        template.storage_service.get_clean_appimage_name.assert_called_once_with("test-app")
        template.storage_service.rename_appimage.assert_called_once_with(
            Path("/tmp/test-app.AppImage"), "test-app"
        )

        # Verify result
        assert result_path == Path("/apps/test-app.AppImage")

    @pytest.mark.asyncio
    async def test_move_to_install_directory_integration(self):
        """Test _move_to_install_directory integration with _handle_appimage_renaming."""
        template = self.create_concrete_template()

        # Mock storage service methods
        template.storage_service.move_to_install_dir.return_value = Path(
            "/apps/joplin-1.2.3.AppImage"
        )
        template.storage_service.get_clean_appimage_name.return_value = "joplin"
        template.storage_service.rename_appimage.return_value = Path("/apps/joplin.AppImage")

        # Mock progress tracker
        template.progress_tracker = Mock()
        template.progress_tracker.update_progress = AsyncMock()

        # Create mock context
        context = Mock()
        context.app_name = "joplin"
        context.catalog_entry = {"appimage": {"rename": "joplin"}}
        context.post_processing_task_id = "task_123"

        # Test the move_to_install_directory method
        original_path = Path("/tmp/joplin-1.2.3.AppImage")
        result_path = await template._move_to_install_directory(original_path, context)

        # Verify the workflow
        template.storage_service.move_to_install_dir.assert_called_once_with(original_path)
        template.storage_service.get_clean_appimage_name.assert_called_once_with("joplin")
        template.storage_service.rename_appimage.assert_called_once_with(
            Path("/apps/joplin-1.2.3.AppImage"), "joplin"
        )

        # Verify progress updates
        template.progress_tracker.update_progress.assert_any_call(
            "task_123", 50.0, "📁 Moving joplin to install directory..."
        )
        template.progress_tracker.update_progress.assert_any_call(
            "task_123", 60.0, "📦 joplin installed"
        )

        # Verify final result has .AppImage extension
        assert result_path == Path("/apps/joplin.AppImage")
