import json
import subprocess
from pathlib import Path
import pytest

from drupal_scout.module import Module, AuditStatus, ModuleDeepScan
from drupal_scout.deep_scan import audit_module_sync, resolve_module_path, perform_deep_scan, resolve_composer_patches


def test_resolve_module_path_success(make_composer_project, tmp_path):
    project_dir = make_composer_project(
        packages_map={"drupal/webform": "../../web/modules/contrib/webform"}
    )
    mod_dir = project_dir / "web" / "modules" / "contrib" / "webform"
    mod_dir.mkdir(parents=True, exist_ok=True)

    resolved_path, reason = resolve_module_path("drupal/webform", project_dir)
    assert resolved_path == mod_dir
    assert reason is None


def test_resolve_module_path_missing_installed_json(tmp_path):
    resolved_path, reason = resolve_module_path("drupal/webform", tmp_path)
    assert resolved_path is None
    assert "installed.json" in reason


def test_resolve_module_path_package_not_found(make_composer_project):
    project_dir = make_composer_project(packages_map={"drupal/token": "../../web/modules/contrib/token"})
    resolved_path, reason = resolve_module_path("drupal/webform", project_dir)
    assert resolved_path is None
    assert "Package drupal/webform not found" in reason


def test_resolve_module_path_directory_does_not_exist(make_composer_project):
    project_dir = make_composer_project(packages_map={"drupal/webform": "../../web/modules/contrib/webform"})
    resolved_path, reason = resolve_module_path("drupal/webform", project_dir)
    assert resolved_path is None
    assert "does not exist" in reason


def test_deep_scan_found_indexed_and_history(make_composer_project, make_git_repo, tmp_path):
    project_dir = make_composer_project(packages_map={"drupal/webform": "../../web/modules/contrib/webform"})
    make_git_repo(project_dir)
    mod_dir = project_dir / "web" / "modules" / "contrib" / "webform"
    mod_dir.mkdir(parents=True, exist_ok=True)
    module_file = mod_dir / "webform.module"
    module_file.write_text("<?php\n")

    subprocess.run(["git", "add", "."], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Add webform"], cwd=project_dir, check=True)

    module = Module("drupal/webform")
    audit = audit_module_sync(module, project_dir)

    assert audit.index_status == AuditStatus.FOUND
    assert audit.history_status == AuditStatus.FOUND
    assert audit.module_path == "web/modules/contrib/webform"


def test_deep_scan_indexed_clear_history(make_composer_project, make_git_repo):
    project_dir = make_composer_project(packages_map={"drupal/webform": "../../web/modules/contrib/webform"})
    make_git_repo(project_dir)
    # Initial commit so HEAD exists
    (project_dir / "README.md").write_text("Hello")
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=project_dir, check=True)

    mod_dir = project_dir / "web" / "modules" / "contrib" / "webform"
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "webform.module").write_text("<?php\n")
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True)

    module = Module("drupal/webform")
    audit = audit_module_sync(module, project_dir)

    assert audit.index_status == AuditStatus.FOUND
    assert audit.history_status == AuditStatus.CLEAR


def test_deep_scan_clear_indexed_clear_history(make_composer_project, make_git_repo):
    project_dir = make_composer_project(packages_map={"drupal/webform": "../../web/modules/contrib/webform"})
    make_git_repo(project_dir)
    (project_dir / "README.md").write_text("Hello")
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=project_dir, check=True)

    mod_dir = project_dir / "web" / "modules" / "contrib" / "webform"
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "webform.module").write_text("<?php\n")
    # Untracked file

    module = Module("drupal/webform")
    audit = audit_module_sync(module, project_dir)

    assert audit.index_status == AuditStatus.CLEAR
    assert audit.history_status == AuditStatus.CLEAR


def test_deep_scan_non_git_directory(make_composer_project):
    project_dir = make_composer_project(packages_map={"drupal/webform": "../../web/modules/contrib/webform"})
    mod_dir = project_dir / "web" / "modules" / "contrib" / "webform"
    mod_dir.mkdir(parents=True, exist_ok=True)

    module = Module("drupal/webform")
    audit = audit_module_sync(module, project_dir)

    assert audit.index_status == AuditStatus.UNAVAILABLE
    assert audit.history_status == AuditStatus.UNAVAILABLE
    assert "Not a Git repository" in audit.index_reason


def test_deep_scan_shallow_repository(make_composer_project, make_git_repo, tmp_path):
    project_dir = make_composer_project(packages_map={"drupal/webform": "../../web/modules/contrib/webform"})
    make_git_repo(project_dir)
    (project_dir / "README.md").write_text("Hello")
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=project_dir, check=True)

    mod_dir = project_dir / "web" / "modules" / "contrib" / "webform"
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "webform.module").write_text("<?php\n")
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Add webform"], cwd=project_dir, check=True)

    # Make a shallow clone of project_dir
    shallow_dir = tmp_path / "shallow_repo"
    subprocess.run(["git", "clone", "--depth", "1", f"file://{project_dir}", str(shallow_dir)], check=True)
    # Ensure installed.json is in shallow_dir
    make_composer_project(root_path=shallow_dir, packages_map={"drupal/webform": "../../web/modules/contrib/webform"})

    module = Module("drupal/webform")
    audit = audit_module_sync(module, shallow_dir)

    assert audit.index_status == AuditStatus.FOUND
    assert audit.history_status == AuditStatus.FOUND

    # Now test a module in shallow_dir that has no commit in depth=1
    shallow_mod2 = shallow_dir / "web" / "modules" / "contrib" / "token"
    shallow_mod2.mkdir(parents=True, exist_ok=True)
    make_composer_project(root_path=shallow_dir, packages_map={"drupal/token": "../../web/modules/contrib/token"})

    module2 = Module("drupal/token")
    audit2 = audit_module_sync(module2, shallow_dir)
    assert audit2.history_status == AuditStatus.INCOMPLETE
    assert "Shallow repository" in audit2.history_reason


def test_deep_scan_path_outside_repo(make_composer_project, make_git_repo, tmp_path):
    repo_dir = tmp_path / "repo"
    make_git_repo(repo_dir)

    outside_dir = tmp_path / "outside_webform"
    outside_dir.mkdir(parents=True, exist_ok=True)

    make_composer_project(root_path=repo_dir, packages_map={"drupal/webform": str(outside_dir)})

    module = Module("drupal/webform")
    audit = audit_module_sync(module, repo_dir)
    assert audit.index_status == AuditStatus.UNAVAILABLE
    assert audit.history_status == AuditStatus.UNAVAILABLE
    assert "outside" in audit.index_reason


def test_resolve_composer_patches_inline(make_composer_project):
    project_dir = make_composer_project(patches_inline={
        "drupal/webform": {"Fix webform bug": "patches/webform.patch"}
    })
    patches = resolve_composer_patches(project_dir)
    assert "drupal/webform" in patches
    assert len(patches["drupal/webform"]) == 1
    assert patches["drupal/webform"][0]["description"] == "Fix webform bug"
    assert patches["drupal/webform"][0]["source"] == "patches/webform.patch"


def test_resolve_composer_patches_external_file(make_composer_project):
    project_dir = make_composer_project(patches_file_data={
        "drupal/ctools": {"Fix ctools bug": "https://drupal.org/123.patch"}
    })
    patches = resolve_composer_patches(project_dir)
    assert "drupal/ctools" in patches
    assert len(patches["drupal/ctools"]) == 1
    assert patches["drupal/ctools"][0]["description"] == "Fix ctools bug"
    assert patches["drupal/ctools"][0]["source"] == "https://drupal.org/123.patch"


def test_deep_scan_includes_patches(make_composer_project, make_git_repo):
    project_dir = make_composer_project(
        packages_map={"drupal/webform": "../../web/modules/contrib/webform"},
        patches_inline={"drupal/webform": {"Test patch": "patches/test.patch"}}
    )
    make_git_repo(project_dir)
    mod_dir = project_dir / "web" / "modules" / "contrib" / "webform"
    mod_dir.mkdir(parents=True, exist_ok=True)

    module = Module("drupal/webform")
    audit = audit_module_sync(module, project_dir)

    assert len(audit.patches) == 1
    assert audit.patches[0]["description"] == "Test patch"


def test_resolve_composer_patches_list_formats(make_composer_project):
    project_dir = make_composer_project(patches_inline={
        "drupal/webform": [
            {"description": "Patch A", "source": "a.patch"},
            "b.patch"
        ]
    })
    patches = resolve_composer_patches(project_dir)
    assert len(patches["drupal/webform"]) == 2
    assert patches["drupal/webform"][0]["description"] == "Patch A"
    assert patches["drupal/webform"][1]["source"] == "b.patch"


def test_resolve_composer_patches_invalid_json(tmp_path):
    (tmp_path / "composer.json").write_text("{invalid json")
    (tmp_path / "composer.patches.json").write_text("{invalid json")
    patches = resolve_composer_patches(tmp_path)
    assert patches == {}


def test_resolve_module_path_invalid_installed_json(tmp_path):
    vendor_c = tmp_path / "vendor" / "composer"
    vendor_c.mkdir(parents=True, exist_ok=True)
    (vendor_c / "installed.json").write_text("{invalid json")
    path, reason = resolve_module_path("drupal/webform", tmp_path)
    assert path is None
    assert "Failed to parse" in reason


def test_resolve_module_path_non_list_packages(tmp_path):
    vendor_c = tmp_path / "vendor" / "composer"
    vendor_c.mkdir(parents=True, exist_ok=True)
    (vendor_c / "installed.json").write_text(json.dumps({"packages": "not a list"}))
    path, reason = resolve_module_path("drupal/webform", tmp_path)
    assert path is None
    assert "Invalid format" in reason


def test_perform_deep_scan_no_git_binary(make_composer_project):
    from unittest.mock import patch
    project_dir = make_composer_project(packages_map={"drupal/webform": "../../web/modules/contrib/webform"})
    with patch("shutil.which", return_value=None):
        audit = perform_deep_scan("drupal/webform", project_dir)
        assert audit.index_status == AuditStatus.UNAVAILABLE
        assert "Git executable not found" in audit.index_reason


@pytest.mark.asyncio
async def test_audit_module_async(make_composer_project, make_git_repo):
    project_dir = make_composer_project(packages_map={"drupal/webform": "../../web/modules/contrib/webform"})
    make_git_repo(project_dir)
    mod_dir = project_dir / "web" / "modules" / "contrib" / "webform"
    mod_dir.mkdir(parents=True, exist_ok=True)
    from drupal_scout.deep_scan import audit_module_async
    audit = await audit_module_async("drupal/webform", project_dir)
    assert audit.index_status == AuditStatus.CLEAR


def test_perform_deep_scan_mode_patches(make_composer_project, make_git_repo):
    from unittest.mock import patch as mock_patch
    project_dir = make_composer_project(
        packages_map={"drupal/webform": "../../web/modules/contrib/webform"},
        patches_inline={"drupal/webform": {"Patch 1": "p1.patch"}}
    )
    make_git_repo(project_dir)
    mod_dir = project_dir / "web" / "modules" / "contrib" / "webform"
    mod_dir.mkdir(parents=True, exist_ok=True)

    module = Module("drupal/webform")
    with mock_patch("drupal_scout.deep_scan.subprocess.run") as mock_sub:
        audit = audit_module_sync(module, project_dir, mode="patches")
        mock_sub.assert_not_called()

    assert audit.mode == "patches"
    assert len(audit.patches) == 1
    assert audit.patches[0]["description"] == "Patch 1"
    # Git status remains default/unavailable because git checks were skipped
    assert audit.index_status == AuditStatus.UNAVAILABLE


def test_perform_deep_scan_mode_git(make_composer_project, make_git_repo):
    project_dir = make_composer_project(
        packages_map={"drupal/webform": "../../web/modules/contrib/webform"},
        patches_inline={"drupal/webform": {"Patch 1": "p1.patch"}}
    )
    make_git_repo(project_dir)
    mod_dir = project_dir / "web" / "modules" / "contrib" / "webform"
    mod_dir.mkdir(parents=True, exist_ok=True)

    module = Module("drupal/webform")
    audit = audit_module_sync(module, project_dir, mode="git")

    assert audit.mode == "git"
    assert len(audit.patches) == 0
    assert audit.index_status == AuditStatus.CLEAR


