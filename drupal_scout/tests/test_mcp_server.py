"""
Tests for drupal_scout.mcp_server MCP tools.

Each test calls the tool function directly (they are plain async functions)
without needing a running MCP server. Uses pytest-asyncio, aioresponses,
and temporary directories following the project's existing test patterns.
"""

import json
import sys
import tempfile
from io import StringIO
from os import mkdir
from os.path import join
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from drupal_scout.mcp_server import (
    get_diagnostic_info,
    perform_full_project_scan,
    scan_specific_modules,
    generate_composer_upgrade_json,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_composer2_project(temp_dir, composer_data, lock_data=None):
    """Create a minimal Composer 2 project structure in a temp directory."""
    mkdir(join(temp_dir, "vendor"))
    mkdir(join(temp_dir, "vendor", "composer"))
    Path(join(temp_dir, "vendor", "composer", "platform_check.php")).touch()
    with open(join(temp_dir, "composer.json"), "w") as f:
        json.dump(composer_data, f)
    if lock_data is not None:
        with open(join(temp_dir, "composer.lock"), "w") as f:
            json.dump(lock_data, f)


# ---------------------------------------------------------------------------
# Tool 1: get_diagnostic_info
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_diagnostic_info_basic():
    """Verify diagnostic check returns expected JSON structure."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create composer.json
        with open(join(temp_dir, "composer.json"), "w") as f:
            json.dump({"require": {"drupal/core": "^10.0"}}, f)

        with patch("drupal_scout.mcp_server.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()  # jq found
            result = await get_diagnostic_info(directory=temp_dir)

        assert "version" in result
        assert result["jq_status"] == "FOUND and FUNCTIONAL"
        assert result["composer_json"] is True
        assert result["composer_lock"] is False
        assert result["composer2"] is False  # no vendor dir
        assert "drupal_core_version" in result


@pytest.mark.asyncio
async def test_get_diagnostic_info_jq_missing():
    """Verify diagnostic correctly reports missing jq."""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch(
            "drupal_scout.mcp_server.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            result = await get_diagnostic_info(directory=temp_dir)

        assert result["jq_status"] == "NOT FOUND OR NOT FUNCTIONAL"


@pytest.mark.asyncio
async def test_get_diagnostic_info_with_lock_and_core():
    """Verify core version detection from composer.lock."""
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(join(temp_dir, "composer.json"), "w") as f:
            json.dump({"require": {"drupal/core": "^10.0"}}, f)
        with open(join(temp_dir, "composer.lock"), "w") as f:
            json.dump(
                {"packages": [{"name": "drupal/core", "version": "10.2.0"}]}, f
            )

        with patch("drupal_scout.mcp_server.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()
            result = await get_diagnostic_info(directory=temp_dir)

        assert result["composer_lock"] is True
        assert result["drupal_core_version"] == "10.2.0"


# ---------------------------------------------------------------------------
# Tool 2: perform_full_project_scan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_perform_full_project_scan_success():
    """Full scan with mocked WorkersManager returns module data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        composer_data = {
            "require": {
                "drupal/core-recommended": "^10.0",
                "drupal/token": "^1.0",
            }
        }
        lock_data = {
            "packages": [
                {"name": "drupal/core", "version": "10.2.0"},
                {"name": "drupal/token", "version": "1.5.0"},
            ]
        }
        _make_composer2_project(temp_dir, composer_data, lock_data)

        with patch("drupal_scout.mcp_server.WorkersManager") as MockWM:
            MockWM.return_value.run = AsyncMock()
            result = await perform_full_project_scan(directory=temp_dir)

        assert "error" not in result
        assert result["drupal_core_version"] == "10.2.0"
        assert result["lock_file_used"] is True
        assert isinstance(result["modules"], list)
        assert len(result["modules"]) == 1  # only drupal/token (not core)
        assert result["modules"][0]["name"] == "drupal/token"


@pytest.mark.asyncio
async def test_perform_full_project_scan_no_lock():
    """Full scan with no_lock=True skips lock file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        composer_data = {
            "require": {
                "drupal/core": "^10.0",
                "drupal/webform": "^6.0",
            }
        }
        lock_data = {
            "packages": [
                {"name": "drupal/core", "version": "10.2.0"},
                {"name": "drupal/webform", "version": "6.1.0"},
            ]
        }
        _make_composer2_project(temp_dir, composer_data, lock_data)

        with patch("drupal_scout.mcp_server.WorkersManager") as MockWM:
            MockWM.return_value.run = AsyncMock()
            result = await perform_full_project_scan(
                directory=temp_dir, no_lock=True
            )

        assert result["lock_file_used"] is False
        assert result["drupal_core_version"] == "10.0"


@pytest.mark.asyncio
async def test_perform_full_project_scan_bad_directory():
    """Full scan returns error for non-existent directory."""
    result = await perform_full_project_scan(directory="/nonexistent/path")
    assert "error" in result
    assert "does not exist" in result["error"]


@pytest.mark.asyncio
async def test_perform_full_project_scan_no_composer_json():
    """Full scan returns error when composer.json is missing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        result = await perform_full_project_scan(directory=temp_dir)
    assert "error" in result
    assert "composer.json" in result["error"]


@pytest.mark.asyncio
async def test_perform_full_project_scan_composer_v1():
    """Full scan returns error for Composer v1 projects."""
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(join(temp_dir, "composer.json"), "w") as f:
            json.dump({"require": {"drupal/core": "^9"}}, f)
        # No vendor/composer/platform_check.php = Composer v1
        result = await perform_full_project_scan(directory=temp_dir)
    assert "error" in result
    assert "Composer v1" in result["error"]


@pytest.mark.asyncio
async def test_perform_full_project_scan_no_modules():
    """Full scan returns message when no drupal/* modules found."""
    with tempfile.TemporaryDirectory() as temp_dir:
        composer_data = {"require": {"drupal/core": "^10.0"}}
        lock_data = {
            "packages": [{"name": "drupal/core", "version": "10.0.0"}]
        }
        _make_composer2_project(temp_dir, composer_data, lock_data)

        result = await perform_full_project_scan(directory=temp_dir)

    assert result["modules"] == []
    assert "message" in result


# ---------------------------------------------------------------------------
# Tool 3: scan_specific_modules
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_specific_modules_with_core():
    """Targeted scan with explicit core version."""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch("drupal_scout.mcp_server.WorkersManager") as MockWM:
            MockWM.return_value.run = AsyncMock()
            result = await scan_specific_modules(
                modules=["drupal/webform"],
                core="10.0.0",
                directory=temp_dir,
            )

    assert "error" not in result
    assert result["drupal_core_version"] == "10.0.0"
    assert result["lock_file_used"] is False
    assert len(result["modules"]) == 1
    assert result["modules"][0]["name"] == "drupal/webform"


@pytest.mark.asyncio
async def test_scan_specific_modules_auto_detect_core():
    """Targeted scan auto-detects core version from composer.lock."""
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(join(temp_dir, "composer.lock"), "w") as f:
            json.dump(
                {
                    "packages": [
                        {"name": "drupal/core", "version": "10.1.0"},
                        {"name": "drupal/webform", "version": "6.2.0"},
                    ]
                },
                f,
            )

        with patch("drupal_scout.mcp_server.WorkersManager") as MockWM:
            MockWM.return_value.run = AsyncMock()
            result = await scan_specific_modules(
                modules=["drupal/webform"],
                directory=temp_dir,
            )

    assert result["drupal_core_version"] == "10.1.0"
    assert result["lock_file_used"] is True
    # Module should have version from lock
    assert result["modules"][0]["version"] == "6.2.0"


@pytest.mark.asyncio
async def test_scan_specific_modules_no_core_no_files():
    """Targeted scan returns error when core cannot be detected."""
    with tempfile.TemporaryDirectory() as temp_dir:
        result = await scan_specific_modules(
            modules=["drupal/webform"],
            directory=temp_dir,
        )
    assert "error" in result
    assert "Unable to determine" in result["error"]


@pytest.mark.asyncio
async def test_scan_specific_modules_multiple():
    """Targeted scan handles multiple modules."""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch("drupal_scout.mcp_server.WorkersManager") as MockWM:
            MockWM.return_value.run = AsyncMock()
            result = await scan_specific_modules(
                modules=["drupal/webform", "drupal/ctools"],
                core="10.0.0",
                directory=temp_dir,
            )

    assert len(result["modules"]) == 2
    names = {m["name"] for m in result["modules"]}
    assert names == {"drupal/webform", "drupal/ctools"}


@pytest.mark.asyncio
async def test_scan_specific_modules_lock_auto_detect():
    """Verify lock_file_used reflects actual file presence."""
    # Case 1: No lock file
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch("drupal_scout.mcp_server.WorkersManager") as MockWM:
            MockWM.return_value.run = AsyncMock()
            result = await scan_specific_modules(
                modules=["drupal/webform"],
                core="10.0.0",
                directory=temp_dir,
            )
    assert result["lock_file_used"] is False

    # Case 2: With lock file
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(join(temp_dir, "composer.lock"), "w") as f:
            json.dump(
                {
                    "packages": [
                        {"name": "drupal/core", "version": "10.0.0"},
                        {"name": "drupal/webform", "version": "6.0.0"},
                    ]
                },
                f,
            )
        with patch("drupal_scout.mcp_server.WorkersManager") as MockWM:
            MockWM.return_value.run = AsyncMock()
            result = await scan_specific_modules(
                modules=["drupal/webform"],
                core="10.0.0",
                directory=temp_dir,
            )
    assert result["lock_file_used"] is True


# ---------------------------------------------------------------------------
# Tool 4: generate_composer_upgrade_json
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_composer_upgrade_json_success():
    """Suggest formatter returns modified composer.json structure."""
    with tempfile.TemporaryDirectory() as temp_dir:
        composer_data = {
            "require": {
                "drupal/core-recommended": "^10.0",
                "drupal/token": "^1.0",
            }
        }
        lock_data = {
            "packages": [
                {"name": "drupal/core", "version": "10.2.0"},
                {"name": "drupal/token", "version": "1.5.0"},
            ]
        }
        _make_composer2_project(temp_dir, composer_data, lock_data)

        with patch("drupal_scout.mcp_server.WorkersManager") as MockWM:
            MockWM.return_value.run = AsyncMock()
            result = await generate_composer_upgrade_json(directory=temp_dir)

    assert "error" not in result
    assert "suggested_composer_json" in result
    assert result["drupal_core_version"] == "10.2.0"
    # The suggested composer.json should contain the require section
    assert "require" in result["suggested_composer_json"]


@pytest.mark.asyncio
async def test_generate_composer_upgrade_json_bad_directory():
    """Returns error for non-existent directory."""
    result = await generate_composer_upgrade_json(directory="/nonexistent")
    assert "error" in result


@pytest.mark.asyncio
async def test_generate_composer_upgrade_json_no_modules():
    """Returns message when no drupal/* modules found."""
    with tempfile.TemporaryDirectory() as temp_dir:
        composer_data = {"require": {"drupal/core": "^10.0"}}
        lock_data = {
            "packages": [{"name": "drupal/core", "version": "10.0.0"}]
        }
        _make_composer2_project(temp_dir, composer_data, lock_data)

        result = await generate_composer_upgrade_json(directory=temp_dir)

    assert result["suggested_composer_json"] is None
    assert "message" in result


@pytest.mark.asyncio
async def test_generate_composer_upgrade_json_does_not_write_to_disk():
    """Verify the tool does NOT modify the original composer.json file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        composer_data = {
            "require": {
                "drupal/core-recommended": "^10.0",
                "drupal/token": "^1.0",
            }
        }
        lock_data = {
            "packages": [
                {"name": "drupal/core", "version": "10.2.0"},
                {"name": "drupal/token", "version": "1.5.0"},
            ]
        }
        _make_composer2_project(temp_dir, composer_data, lock_data)

        # Read original content
        with open(join(temp_dir, "composer.json"), "r") as f:
            original_content = f.read()

        with patch("drupal_scout.mcp_server.WorkersManager") as MockWM:
            MockWM.return_value.run = AsyncMock()
            await generate_composer_upgrade_json(directory=temp_dir)

        # Verify file was NOT modified
        with open(join(temp_dir, "composer.json"), "r") as f:
            after_content = f.read()

        assert original_content == after_content


# ---------------------------------------------------------------------------
# Output Purity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_output_purity_no_stdout_leakage():
    """Verify that no output leaks to real sys.stdout during tool execution."""
    real_stdout = sys.stdout
    capture = StringIO()
    sys.stdout = capture

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(join(temp_dir, "composer.json"), "w") as f:
                json.dump({"require": {"drupal/core": "^10.0"}}, f)

            with patch(
                "drupal_scout.mcp_server.subprocess.run"
            ) as mock_run:
                mock_run.return_value = MagicMock()
                await get_diagnostic_info(directory=temp_dir)

        leaked_output = capture.getvalue()
    finally:
        sys.stdout = real_stdout

    assert leaked_output == "", f"Output leaked to stdout: {leaked_output!r}"


@pytest.mark.asyncio
async def test_output_purity_restored_after_error():
    """Verify stdout/stderr are restored even if tool raises an exception."""
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    # Even with an error path, outputs should be restored
    await perform_full_project_scan(directory="/nonexistent/path/for/test")

    assert sys.stdout is original_stdout
    assert sys.stderr is original_stderr
