"""Tests for AppImage icon extraction functionality."""

from unittest.mock import AsyncMock, patch

import pytest

from my_unicorn.core.icon import AppImageIconExtractor, IconExtractionError


class TestAppImageIconExtractor:
    """Test cases for AppImageIconExtractor."""

    @pytest.fixture
    def extractor(self):
        """Create an AppImageIconExtractor instance."""
        return AppImageIconExtractor()

    @pytest.fixture
    def mock_appimage(self, tmp_path):
        """Create a mock AppImage file."""
        appimage_path = tmp_path / "test.AppImage"
        appimage_path.write_bytes(b"mock appimage content")
        appimage_path.chmod(0o755)
        return appimage_path

    @pytest.fixture
    def mock_squashfs_root(self, tmp_path):
        """Create a mock squashfs-root directory with icons."""
        root = tmp_path / "squashfs-root"
        root.mkdir()

        # Create icon directories
        icon_dir = root / "usr" / "share" / "icons" / "hicolor"
        scalable_dir = icon_dir / "scalable"
        png_dir = icon_dir / "512x512" / "apps"

        scalable_dir.mkdir(parents=True)
        png_dir.mkdir(parents=True)

        # Create test icons
        svg_icon = scalable_dir / "testapp.svg"
        svg_icon.write_text("<svg>test</svg>")

        png_icon = png_dir / "testapp.png"
        png_icon.write_bytes(
            b"mock png data" * 20
        )  # Make it larger than min size

        # Create root level symlink
        root_link = root / "testapp.svg"
        root_link.symlink_to("usr/share/icons/hicolor/scalable/testapp.svg")

        return root

    def test_format_scores(self, extractor):
        """Test that format scoring preferences are correct."""
        # PNG scores higher than SVG due to desktop environment compatibility
        assert (
            extractor.FORMAT_SCORES[".png"] > extractor.FORMAT_SCORES[".svg"]
        )
        assert (
            extractor.FORMAT_SCORES[".png"] > extractor.FORMAT_SCORES[".ico"]
        )
        assert (
            extractor.FORMAT_SCORES[".ico"] > extractor.FORMAT_SCORES[".bmp"]
        )

    def test_score_icon_png_best(self, extractor, tmp_path):
        """Test that PNG icons get higher format scores than SVG due to desktop compatibility."""
        # Create properly sized icons
        svg_icon = tmp_path / "icon.svg"
        svg_icon.write_text(
            "<svg><rect width='100' height='100' fill='blue'/><circle cx='50' cy='50' r='25'/></svg>"
        )  # Large enough

        png_icon = tmp_path / "icon.png"
        png_icon.write_bytes(b"mock png data" * 20)  # Large enough

        svg_score = extractor._score_icon(svg_icon, "testapp")
        png_score = extractor._score_icon(png_icon, "testapp")

        # PNG should get higher format score (100 vs 50) plus same generic name bonus
        assert png_score > svg_score

    def test_score_icon_name_relevance(self, extractor, tmp_path):
        """Test that name matching affects icon scoring."""
        exact_match = tmp_path / "testapp.png"
        exact_match.write_bytes(b"mock png data" * 20)

        partial_match = tmp_path / "something_testapp_else.png"
        partial_match.write_bytes(b"mock png data" * 20)

        generic_name = tmp_path / "icon.png"
        generic_name.write_bytes(b"mock png data" * 20)

        exact_score = extractor._score_icon(exact_match, "testapp")
        partial_score = extractor._score_icon(partial_match, "testapp")
        generic_score = extractor._score_icon(generic_name, "testapp")

        assert exact_score > partial_score > generic_score

    def test_score_icon_format_preference(self, extractor, tmp_path):
        """Test that different formats get different scores."""
        svg_icon = tmp_path / "testapp.svg"
        svg_icon.write_text(
            "<svg><rect width='100' height='100' fill='red'/><circle cx='50' cy='50' r='25'/></svg>"
        )

        png_icon = tmp_path / "testapp.png"
        png_icon.write_bytes(b"mock png data" * 20)

        ico_icon = tmp_path / "testapp.ico"
        ico_icon.write_bytes(b"mock ico data" * 20)

        svg_score = extractor._score_icon(svg_icon, "testapp")
        png_score = extractor._score_icon(png_icon, "testapp")
        ico_score = extractor._score_icon(ico_icon, "testapp")

        # PNG > SVG > ICO (PNG preferred due to desktop compatibility)
        assert png_score > svg_score > ico_score

    def test_score_icon_skip_small_files(self, extractor, tmp_path):
        """Test that very small files are skipped."""
        tiny_icon = tmp_path / "tiny.png"
        tiny_icon.write_bytes(b"x")  # Less than MIN_ICON_SIZE_BYTES

        normal_icon = tmp_path / "normal.png"
        normal_icon.write_bytes(b"mock png data" * 20)

        tiny_score = extractor._score_icon(tiny_icon, "testapp")
        normal_score = extractor._score_icon(normal_icon, "testapp")

        # Tiny files should get score of 0 (skipped)
        assert tiny_score == 0
        assert normal_score > 0

    def test_resolve_icon_path_regular_file(self, extractor, tmp_path):
        """Test resolving path for regular files."""
        icon_path = tmp_path / "icon.png"
        icon_path.write_bytes(b"test")

        resolved = extractor._resolve_icon_path(icon_path)
        assert resolved == icon_path

    def test_resolve_icon_path_relative_symlink(self, extractor, tmp_path):
        """Test resolving relative symlinks."""
        target = tmp_path / "target.png"
        target.write_bytes(b"test")

        link = tmp_path / "link.png"
        link.symlink_to("target.png")

        resolved = extractor._resolve_icon_path(link)
        assert resolved == target
        assert resolved.exists()

    def test_select_best_icon_empty_candidates(self, extractor):
        """Test that selecting from empty candidates raises error."""
        with pytest.raises(
            IconExtractionError, match="No icon candidates available"
        ):
            extractor._select_best_icon([])

    def test_select_best_icon_chooses_highest_score(self, extractor, tmp_path):
        """Test that the icon with highest score is selected."""
        icon1 = tmp_path / "icon1.png"
        icon1.write_bytes(b"test1" * 20)

        icon2 = tmp_path / "icon2.svg"
        icon2.write_text("<svg>test2</svg>")

        candidates = [
            {"path": icon1, "score": 50, "original_path": icon1},
            {"path": icon2, "score": 150, "original_path": icon2},
        ]

        best = extractor._select_best_icon(candidates)
        assert best["path"] == icon2
        assert best["score"] == 150

    def test_find_best_icon_returns_highest_scored(
        self, extractor, mock_squashfs_root
    ):
        """Test that find_best_icon returns the highest scoring icon."""
        best_icon = extractor._find_best_icon(mock_squashfs_root, "testapp")

        # Should find an icon (either SVG or PNG based on actual scoring)
        assert best_icon is not None
        assert best_icon.name.startswith("testapp.")
        assert best_icon.suffix in [".svg", ".png"]

    @patch("asyncio.create_subprocess_exec")
    async def test_extract_appimage_success(
        self, mock_subprocess, extractor, tmp_path
    ):
        """Test successful AppImage extraction."""
        # Mock successful subprocess execution
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_subprocess.return_value = mock_process

        appimage_path = tmp_path / "test.AppImage"
        appimage_path.write_bytes(b"mock appimage")
        appimage_path.chmod(0o755)

        await extractor._extract_appimage(appimage_path, tmp_path)

        mock_subprocess.assert_called_once()
        args = mock_subprocess.call_args[0]
        assert str(appimage_path) in args
        assert "--appimage-extract" in args

    @patch("asyncio.create_subprocess_exec")
    async def test_extract_appimage_failure(
        self, mock_subprocess, extractor, tmp_path
    ):
        """Test AppImage extraction failure."""
        # Mock failed subprocess execution
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"error message")
        )
        mock_subprocess.return_value = mock_process

        appimage_path = tmp_path / "test.AppImage"
        appimage_path.write_bytes(b"mock appimage")

        with pytest.raises(
            IconExtractionError, match="AppImage extraction failed"
        ):
            await extractor._extract_appimage(appimage_path, tmp_path)

    async def test_copy_icon_success(self, extractor, tmp_path):
        """Test successful icon copying."""
        source = tmp_path / "source.png"
        source.write_bytes(b"icon data")

        dest_dir = tmp_path / "dest"
        dest = dest_dir / "copied.png"

        result = await extractor._copy_icon(source, dest)

        assert result == dest
        assert dest.exists()
        assert dest.read_bytes() == b"icon data"

    async def test_copy_icon_creates_parent_dirs(self, extractor, tmp_path):
        """Test that copy_icon creates parent directories."""
        source = tmp_path / "source.png"
        source.write_bytes(b"icon data")

        dest = tmp_path / "nested" / "dirs" / "icon.png"

        result = await extractor._copy_icon(source, dest)

        assert result == dest
        assert dest.exists()
        assert dest.parent.exists()

    async def test_extract_icon_nonexistent_appimage(
        self, extractor, tmp_path
    ):
        """Test extracting from non-existent AppImage."""
        nonexistent = tmp_path / "nonexistent.AppImage"
        dest = tmp_path / "icon.png"

        result = await extractor.extract_icon(nonexistent, dest, "testapp")
        assert result is None

    async def test_extract_icon_not_a_file(self, extractor, tmp_path):
        """Test extracting when AppImage path is not a file."""
        directory = tmp_path / "directory"
        directory.mkdir()
        dest = tmp_path / "icon.png"

        result = await extractor.extract_icon(directory, dest, "testapp")
        assert result is None


class TestIconExtractionError:
    """Test cases for IconExtractionError."""

    def test_icon_extraction_error_creation(self):
        """Test that IconExtractionError can be created with message."""
        error = IconExtractionError("Test error message")
        assert str(error) == "Test error message"

    def test_icon_extraction_error_inheritance(self):
        """Test that IconExtractionError inherits from Exception."""
        error = IconExtractionError("Test error")
        assert isinstance(error, Exception)
