"""Regression tests for catalog verification skip format.

The catalog uses {"method": "skip"} to signal that no checksums are provided.
These tests verify that should_skip_verification correctly recognises this
format in addition to the legacy {"skip": True} format.
"""

from __future__ import annotations

from my_unicorn.core.verification.detection import should_skip_verification


class TestCatalogMethodSkipFormat:
    r"""Tests for catalog {"method": "skip"} format in should_skip_verification."""

    def test_catalog_method_skip_no_checksums(self) -> None:
        r"""Catalog {"method": "skip"} triggers skip when no checksums."""
        config = {"method": "skip"}
        should_skip, _updated_config = should_skip_verification(
            config, has_digest=False, has_checksum_files=False
        )

        assert should_skip is True

    def test_catalog_method_skip_overridden_by_digest(self) -> None:
        r"""Catalog {"method": "skip"} is overridden when digest available."""
        config = {"method": "skip"}
        should_skip, _updated_config = should_skip_verification(
            config, has_digest=True, has_checksum_files=False
        )

        assert should_skip is False

    def test_catalog_method_skip_overridden_by_checksum_files(self) -> None:
        r"""Catalog {"method": "skip"} overridden when checksum files found."""
        config = {"method": "skip"}
        should_skip, _updated_config = should_skip_verification(
            config, has_digest=False, has_checksum_files=True
        )

        assert should_skip is False

    def test_legacy_skip_true_still_works(self) -> None:
        """Legacy {"skip": True} still triggers skip when no checksums."""
        config = {"skip": True}
        should_skip, _updated_config = should_skip_verification(
            config, has_digest=False, has_checksum_files=False
        )

        assert should_skip is True
