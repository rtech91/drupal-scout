from unittest.mock import Mock

import pytest
from aiohttp.client_reqrep import ClientResponse


@pytest.fixture(autouse=True, scope="session")
def _patch_aiohttp_clientresponse_init_stream_writer():
    """Ensure tests remain compatible with aiohttp >= 3.14 when stream_writer is required."""

    original_init = ClientResponse.__init__

    def patched_init(self, *args, **kwargs):
        kwargs.setdefault("stream_writer", Mock())
        return original_init(self, *args, **kwargs)

    ClientResponse.__init__ = patched_init  # type: ignore[method-assign]
    try:
        yield
    finally:
        ClientResponse.__init__ = original_init  # type: ignore[method-assign]


import json
import subprocess
from pathlib import Path


@pytest.fixture
def make_composer_project(tmp_path):
    """Factory fixture to create a mock Composer project with installed.json and optional patches."""

    def _create(
        root_path=None,
        packages_map=None,
        patches_inline=None,
        patches_file_data=None,
        patches_file_name="composer.patches.json",
    ):
        project_root = Path(root_path) if root_path else tmp_path
        vendor_composer = project_root / "vendor" / "composer"
        vendor_composer.mkdir(parents=True, exist_ok=True)
        (vendor_composer / "platform_check.php").touch()

        packages_list = []
        if packages_map:
            for pkg_name, info in packages_map.items():
                if isinstance(info, str):
                    install_path = info
                    version = "1.0.0"
                elif isinstance(info, dict):
                    install_path = info.get(
                        "install_path",
                        f"../../web/modules/contrib/{pkg_name.split('/')[-1]}",
                    )
                    version = info.get("version", "1.0.0")
                else:
                    install_path = (
                        f"../../web/modules/contrib/{pkg_name.split('/')[-1]}"
                    )
                    version = "1.0.0"

                packages_list.append(
                    {
                        "name": pkg_name,
                        "version": version,
                        "install-path": install_path,
                    }
                )

        installed_json = vendor_composer / "installed.json"
        installed_json.write_text(json.dumps({"packages": packages_list}))

        composer_json_data = {"require": {}}
        extra_data = {}
        if patches_inline:
            extra_data["patches"] = patches_inline
        if patches_file_data is not None:
            extra_data["patches-file"] = patches_file_name
            content = (
                {"patches": patches_file_data}
                if isinstance(patches_file_data, dict)
                and "patches" not in patches_file_data
                else patches_file_data
            )
            p_file = project_root / patches_file_name
            p_file.write_text(json.dumps(content))
        if extra_data:
            composer_json_data["extra"] = extra_data

        composer_json = project_root / "composer.json"
        composer_json.write_text(json.dumps(composer_json_data))

        return project_root

    return _create


@pytest.fixture
def make_git_repo():
    """Factory fixture to create and initialize a temporary Git repository."""

    def _create(repo_dir):
        repo_dir = Path(repo_dir)
        repo_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )
        return repo_dir

    return _create
