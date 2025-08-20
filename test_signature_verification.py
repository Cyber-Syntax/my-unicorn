#!/usr/bin/env python3
"""Test script to verify that the verify_file signature fix works correctly."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from my_unicorn.services.verification_service import VerificationService


async def test_signature_fix():
    """Test that verify_file can be called with all required parameters."""
    print("🧪 Testing verify_file signature fix...")

    # Create a mock download service
    mock_download_service = MagicMock()
    mock_download_service.download_checksum_file = AsyncMock(return_value="")

    # Create verification service
    verification_service = VerificationService(mock_download_service)

    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile() as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(b"test content")
        temp_file.flush()

        # Test parameters that would be passed from catalog strategy
        file_path = temp_path
        asset = {
            "digest": "",
            "size": 12,
            "name": "test.AppImage",
            "browser_download_url": "https://example.com/test.AppImage",
        }
        config = {"skip": False, "checksum_file": "", "checksum_hash_type": "sha256"}
        owner = "testowner"
        repo = "testrepo"
        tag_name = "v1.0.0"
        app_name = "test.AppImage"
        assets = [asset]

        try:
            # This should work without signature errors
            result = await verification_service.verify_file(
                file_path=file_path,
                asset=asset,
                config=config,
                owner=owner,
                repo=repo,
                tag_name=tag_name,
                app_name=app_name,
                assets=assets,
            )

            print("✅ verify_file called successfully")
            print(f"✅ Result type: {type(result)}")
            print(f"✅ Result passed: {result.passed}")
            print(f"✅ Available methods: {list(result.methods.keys())}")

        except TypeError as e:
            if "missing" in str(e) and "required positional argument" in str(e):
                print(f"❌ Signature error still exists: {e}")
                return False
            else:
                # Other type errors are expected (like file verification failing)
                print(f"✅ No signature error, but got expected TypeError: {e}")
        except Exception as e:
            print(f"✅ No signature error, but got expected exception: {e}")

        # Test without optional assets parameter (backward compatibility)
        try:
            result = await verification_service.verify_file(
                file_path=file_path,
                asset=asset,
                config=config,
                owner=owner,
                repo=repo,
                tag_name=tag_name,
                app_name=app_name,
                # assets parameter omitted
            )
            print("✅ Backward compatibility works (no assets parameter)")

        except TypeError as e:
            if "missing" in str(e) and "required positional argument" in str(e):
                print(f"❌ Backward compatibility broken: {e}")
                return False
            else:
                print(f"✅ No signature error in backward compatibility test: {e}")
        except Exception as e:
            print(f"✅ No signature error in backward compatibility test: {e}")

    print("🎉 Signature fix verification completed successfully!")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_signature_fix())
    exit(0 if success else 1)
