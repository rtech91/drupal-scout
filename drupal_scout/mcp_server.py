"""
FastMCP server for drupal-scout.

Exposes the drupal-scout CLI capabilities as granular MCP tools,
allowing LLMs and MCP clients to invoke Drupal module compatibility
analysis programmatically.

Each tool maps directly to a CLI command/mode:
  - get_diagnostic_info        → drupal-scout info
  - perform_full_project_scan  → drupal-scout (default run)
  - scan_specific_modules      → drupal-scout --modules ... --core ...
  - generate_composer_upgrade_json → drupal-scout --format suggest
"""

import io
import json
import os
import subprocess
import sys
from argparse import Namespace
from typing import Optional

from fastmcp import FastMCP

from .application import Application
from .exceptions import (
    ComposerV1Exception,
    DirectoryNotFoundException,
    NoComposerJSONFileException,
)
from .formatters.jsonformatter import JSONFormatter
from .formatters.suggestformatter import SuggestFormatter
from .module import Module
from .workers_manager import WorkersManager

mcp = FastMCP("drupal-scout")


def _suppress_outputs():
    """Redirect stdout and stderr to StringIO to ensure output purity.

    Returns the original stdout/stderr so they can be restored later.
    """
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    return original_stdout, original_stderr


def _restore_outputs(original_stdout, original_stderr):
    """Restore the original stdout and stderr streams."""
    sys.stdout = original_stdout
    sys.stderr = original_stderr


# ---------------------------------------------------------------------------
# Tool 1: get_diagnostic_info
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_diagnostic_info(directory: str = ".") -> dict:
    """Run environment diagnostics for a Drupal project directory.

    Checks drupal-scout version, jq binary availability, presence of
    composer.json and composer.lock, Composer 2 detection, and Drupal
    core version detection.

    Equivalent to: drupal-scout info

    Args:
        directory: Path to the Drupal project directory. Defaults to
            the current working directory.

    Returns:
        A JSON object with diagnostic fields: version, jq_status,
        composer_json, composer_lock, composer2, drupal_core_version.
    """
    original_stdout, original_stderr = _suppress_outputs()
    try:
        app = Application()
        result = {}

        # Version
        result["version"] = app.get_version()

        # jq binary check
        try:
            subprocess.run(
                ["jq", "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            result["jq_status"] = "FOUND and FUNCTIONAL"
        except (subprocess.SubprocessError, FileNotFoundError):
            result["jq_status"] = "NOT FOUND OR NOT FUNCTIONAL"

        # Composer file presence
        result["composer_json"] = os.path.isfile(
            os.path.join(directory, "composer.json")
        )
        result["composer_lock"] = os.path.isfile(
            os.path.join(directory, "composer.lock")
        )

        # Composer 2 detection
        args_ns = Namespace(directory=directory)
        result["composer2"] = app.is_composer2(args_ns)

        # Drupal core version
        result["drupal_core_version"] = None
        if result["composer_json"]:
            try:
                if result["composer_lock"]:
                    detect_args = Namespace(directory=directory, no_lock=False)
                else:
                    detect_args = Namespace(directory=directory, no_lock=True)
                app.determine_drupal_core_version(detect_args)
                result["drupal_core_version"] = app.drupal_core_version
            except Exception:
                pass

        return result
    finally:
        _restore_outputs(original_stdout, original_stderr)


# ---------------------------------------------------------------------------
# Tool 2: perform_full_project_scan
# ---------------------------------------------------------------------------


@mcp.tool()
async def perform_full_project_scan(
    directory: str = ".",
    no_lock: bool = False,
    limit: int = 10,
) -> dict:
    """Analyze an entire Drupal project for module upgrade compatibility.

    Reads composer.json to discover all drupal/* modules, optionally uses
    composer.lock for installed version protection, and queries the Drupal
    packages API to find transitive-compatible versions for a core upgrade.

    Equivalent to: drupal-scout [-d DIRECTORY] [-n] [-l LIMIT]

    Args:
        directory: Path to the Drupal project directory. Defaults to ".".
        no_lock: If True, skip using composer.lock for installed version
            detection. Defaults to False.
        limit: Maximum number of concurrent API requests. Defaults to 10.

    Returns:
        A JSON object with keys:
        - modules: list of module scan results (name, version,
          suitable_entries, failed)
        - drupal_core_version: detected core version string
        - lock_file_used: whether composer.lock was used
        - error: error message if the scan could not proceed
    """
    original_stdout, original_stderr = _suppress_outputs()
    try:
        app = Application()

        # Validate directory
        if not os.path.isdir(directory):
            return {"error": f"The directory {directory} does not exist."}

        # Validate composer.json
        if not os.path.isfile(os.path.join(directory, "composer.json")):
            return {"error": "The directory does not contain a composer.json file."}

        # Check Composer 2
        args_ns = Namespace(directory=directory, no_lock=no_lock)
        if not app.is_composer2(args_ns):
            return {"error": "The Drupal project uses Composer v1. Please upgrade to Composer v2."}

        # Determine Drupal core version
        try:
            app.determine_drupal_core_version(args_ns)
        except Exception as e:
            return {"error": f"Failed to determine Drupal core version: {e}"}

        core_version = app.drupal_core_version

        # Get required modules
        app.get_required_modules(args_ns)
        modules = app.modules

        if len(modules) == 0:
            return {
                "modules": [],
                "drupal_core_version": core_version,
                "lock_file_used": False,
                "message": "No drupal/* modules were found in composer.json.",
            }

        # Determine module versions from lock file
        lock_file_used = False
        composer_lock_path = os.path.join(directory, "composer.lock")
        if not no_lock and os.path.isfile(composer_lock_path):
            app.determine_module_versions(args_ns)
            lock_file_used = True

        # Run workers
        workers_manager = WorkersManager(
            modules=list(modules.values()),
            current_core=core_version,
            use_lock_version=lock_file_used,
            concurrency_limit=limit,
        )
        await workers_manager.run()

        # Format output as JSON
        formatter = JSONFormatter()
        modules_json = json.loads(formatter.format(list(modules.values())))

        return {
            "modules": modules_json,
            "drupal_core_version": core_version,
            "lock_file_used": lock_file_used,
        }
    finally:
        _restore_outputs(original_stdout, original_stderr)


# ---------------------------------------------------------------------------
# Tool 3: scan_specific_modules
# ---------------------------------------------------------------------------


@mcp.tool()
async def scan_specific_modules(
    modules: list[str],
    core: Optional[str] = None,
    directory: str = ".",
    limit: int = 10,
) -> dict:
    """Scan specific Drupal modules for upgrade compatibility.

    Performs a targeted scan for only the provided module names, without
    requiring a full project environment. If a composer.lock file exists
    in the directory, installed-version protection is applied automatically.

    The composer.lock is auto-detected: if found, it is used for
    installed-version protection and the response includes
    ``lock_file_used: true``. If not found, the scan proceeds without it.

    Equivalent to: drupal-scout --modules ... [--core ...] [-d DIRECTORY]

    Args:
        modules: List of Drupal module names to scan
            (e.g. ["drupal/webform", "drupal/ctools"]).
        core: Drupal core version override (e.g. "10.0.0"). If omitted,
            the core version is auto-detected from composer metadata
            in the directory.
        directory: Path to the Drupal project directory for auto-detection.
            Defaults to ".".
        limit: Maximum number of concurrent API requests. Defaults to 10.

    Returns:
        A JSON object with keys:
        - modules: list of module scan results
        - drupal_core_version: resolved core version string
        - lock_file_used: whether composer.lock was used
        - error: error message if the scan could not proceed
    """
    original_stdout, original_stderr = _suppress_outputs()
    try:
        app = Application()

        # Resolve core version
        if core:
            resolved_core = core.replace("^", "").replace("~", "")
        else:
            # Auto-detect from local project files
            detected_core = _auto_detect_core(app, directory)
            if detected_core is None:
                return {
                    "error": (
                        "Unable to determine Drupal core version. "
                        "Provide the 'core' argument or ensure composer.lock/"
                        "composer.json exists in the directory."
                    )
                }
            resolved_core = detected_core

        # Build module objects
        module_objects = {}
        for name in modules:
            module_objects[name] = Module(name)

        # Auto-detect lock file
        lock_file_used = False
        composer_lock_path = os.path.join(directory, "composer.lock")
        if os.path.isfile(composer_lock_path):
            # Use Application's method to populate versions from lock
            app.modules = module_objects
            args_ns = Namespace(directory=directory, no_lock=False)
            app.determine_module_versions(args_ns)
            module_objects = app.modules
            lock_file_used = True

        # Run workers
        workers_manager = WorkersManager(
            modules=list(module_objects.values()),
            current_core=resolved_core,
            use_lock_version=lock_file_used,
            concurrency_limit=limit,
        )
        await workers_manager.run()

        # Format output
        formatter = JSONFormatter()
        modules_json = json.loads(formatter.format(list(module_objects.values())))

        return {
            "modules": modules_json,
            "drupal_core_version": resolved_core,
            "lock_file_used": lock_file_used,
        }
    finally:
        _restore_outputs(original_stdout, original_stderr)


# ---------------------------------------------------------------------------
# Tool 4: generate_composer_upgrade_json
# ---------------------------------------------------------------------------


@mcp.tool()
async def generate_composer_upgrade_json(
    directory: str = ".",
    core: Optional[str] = None,
) -> dict:
    """Generate a suggested composer.json with updated module versions.

    Performs a full project scan and then produces a modified composer.json
    structure where module version requirements are updated to their
    lowest compatible transitive versions.

    This tool does NOT write to disk — it returns the suggested
    composer.json content as JSON for the caller to review and apply.

    Equivalent to: drupal-scout --format suggest (read-only)

    Args:
        directory: Path to the Drupal project directory. Defaults to ".".
        core: Optional Drupal core version override. If omitted, auto-detected.

    Returns:
        A JSON object with keys:
        - suggested_composer_json: the full composer.json with updated versions
        - drupal_core_version: the core version used for the scan
        - error: error message if the scan could not proceed
    """
    original_stdout, original_stderr = _suppress_outputs()
    try:
        app = Application()

        # Validate directory
        if not os.path.isdir(directory):
            return {"error": f"The directory {directory} does not exist."}

        # Validate composer.json
        if not os.path.isfile(os.path.join(directory, "composer.json")):
            return {"error": "The directory does not contain a composer.json file."}

        # Check Composer 2
        args_ns = Namespace(directory=directory, no_lock=False)
        if not app.is_composer2(args_ns):
            return {"error": "The Drupal project uses Composer v1. Please upgrade to Composer v2."}

        # Determine core version
        if core:
            app.drupal_core_version = core.replace("^", "").replace("~", "")
        else:
            try:
                # Prefer lock file for core version detection
                if os.path.isfile(os.path.join(directory, "composer.lock")):
                    detect_args = Namespace(directory=directory, no_lock=False)
                else:
                    detect_args = Namespace(directory=directory, no_lock=True)
                app.determine_drupal_core_version(detect_args)
            except Exception as e:
                return {"error": f"Failed to determine Drupal core version: {e}"}

        core_version = app.drupal_core_version

        # Get required modules
        app.get_required_modules(args_ns)
        modules_dict = app.modules

        if len(modules_dict) == 0:
            return {
                "suggested_composer_json": None,
                "drupal_core_version": core_version,
                "message": "No drupal/* modules were found in composer.json.",
            }

        # Determine module versions from lock file
        lock_file_used = False
        composer_lock_path = os.path.join(directory, "composer.lock")
        if os.path.isfile(composer_lock_path):
            app.determine_module_versions(
                Namespace(directory=directory, no_lock=False)
            )
            lock_file_used = True

        # Run workers
        workers_manager = WorkersManager(
            modules=list(modules_dict.values()),
            current_core=core_version,
            use_lock_version=lock_file_used,
            concurrency_limit=10,
        )
        await workers_manager.run()

        # Use SuggestFormatter to build the suggested composer.json
        # but WITHOUT writing to disk (save_dump=False)
        suggest_args = Namespace(directory=directory, save_dump=False)
        formatter = SuggestFormatter(suggest_args)
        suggested_json_str = formatter.format(list(modules_dict.values()))
        suggested_composer = json.loads(suggested_json_str)

        return {
            "suggested_composer_json": suggested_composer,
            "drupal_core_version": core_version,
        }
    finally:
        _restore_outputs(original_stdout, original_stderr)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auto_detect_core(app: Application, directory: str) -> Optional[str]:
    """Attempt to auto-detect the Drupal core version from local project files.

    Tries composer.lock first, then falls back to composer.json.

    Returns:
        The detected core version string, or None if detection fails.
    """
    try:
        if os.path.isfile(os.path.join(directory, "composer.lock")):
            detect_args = Namespace(directory=directory, no_lock=False)
        elif os.path.isfile(os.path.join(directory, "composer.json")):
            detect_args = Namespace(directory=directory, no_lock=True)
        else:
            return None
        app.determine_drupal_core_version(detect_args)
        return app.drupal_core_version
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    """Run the drupal-scout MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
