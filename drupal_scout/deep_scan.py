import asyncio
import json
import shutil
import subprocess
from pathlib import Path

from drupal_scout.module import Module, AuditStatus, ModuleDeepScan


def resolve_composer_patches(project_dir: str | Path) -> dict[str, list[dict[str, str]]]:
    """
    Resolve applied Composer patches from composer.json and composer.patches.json files.

    :param project_dir: Path to project root
    :return: dict mapping package name to list of patch entries ({description, source})
    """
    project_path = Path(project_dir).resolve()
    patches_by_pkg: dict[str, list[dict[str, str]]] = {}

    def _parse_patch_dict(raw_patches: dict):
        for pkg, patch_val in raw_patches.items():
            if not isinstance(pkg, str):
                continue
            pkg_list = patches_by_pkg.setdefault(pkg, [])
            if isinstance(patch_val, dict):
                for desc, src in patch_val.items():
                    pkg_list.append({"description": str(desc), "source": str(src)})
            elif isinstance(patch_val, list):
                for item in patch_val:
                    if isinstance(item, dict):
                        d = str(item.get("description", "Patch"))
                        s = str(item.get("source", item.get("url", "")))
                        pkg_list.append({"description": d, "source": s})
                    elif isinstance(item, str):
                        pkg_list.append({"description": item, "source": item})
            elif isinstance(patch_val, str):
                pkg_list.append({"description": patch_val, "source": patch_val})

    composer_json_path = project_path / "composer.json"
    patches_file_names = ["composer.patches.json"]

    if composer_json_path.exists():
        try:
            c_data = json.loads(composer_json_path.read_text(encoding="utf-8"))
            extra = c_data.get("extra", {}) if isinstance(c_data, dict) else {}
            if isinstance(extra, dict):
                inline_patches = extra.get("patches")
                if isinstance(inline_patches, dict):
                    _parse_patch_dict(inline_patches)

                custom_patches_file = extra.get("patches-file")
                if isinstance(custom_patches_file, str) and custom_patches_file not in patches_file_names:
                    patches_file_names.insert(0, custom_patches_file)
        except Exception:
            pass

    for pf_name in patches_file_names:
        p_file_path = project_path / pf_name
        if p_file_path.exists():
            try:
                p_data = json.loads(p_file_path.read_text(encoding="utf-8"))
                if isinstance(p_data, dict):
                    patches_obj = p_data.get("patches", p_data)
                    if isinstance(patches_obj, dict):
                        _parse_patch_dict(patches_obj)
            except Exception:
                pass

    return patches_by_pkg


def resolve_module_path(package_name: str, project_dir: str | Path) -> tuple[Path | None, str | None]:
    """
    Resolve the installed directory path for a Composer package.
    
    :param package_name: Composer package name (e.g. 'drupal/webform')
    :param project_dir: Path to the project root
    :return: (resolved_path, failure_reason)
    """
    project_path = Path(project_dir).resolve()
    installed_json_path = project_path / "vendor" / "composer" / "installed.json"

    if not installed_json_path.exists():
        return None, f"Composer metadata file missing: {installed_json_path}"

    try:
        data = json.loads(installed_json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"Failed to parse Composer metadata in {installed_json_path}: {exc}"

    packages = data.get("packages", data) if isinstance(data, dict) else data
    if not isinstance(packages, list):
        return None, f"Invalid format in Composer metadata {installed_json_path}"

    pkg_info = next((pkg for pkg in packages if isinstance(pkg, dict) and pkg.get("name") == package_name), None)
    if not pkg_info:
        return None, f"Package {package_name} not found in vendor/composer/installed.json"

    install_path_raw = pkg_info.get("install-path")
    if not install_path_raw:
        return None, f"Package {package_name} missing 'install-path' in Composer metadata"

    # Composer 2 install-path is relative to vendor/composer/
    vendor_composer_dir = project_path / "vendor" / "composer"
    resolved_path = (vendor_composer_dir / install_path_raw).resolve()

    if not resolved_path.exists():
        return None, f"Module installation path does not exist: {resolved_path}"

    return resolved_path, None


def perform_deep_scan(
    package_name: str,
    project_dir: str | Path,
    mode: str = "all",
    patches_map: dict | None = None
) -> ModuleDeepScan:
    """
    Perform a read-only local deep scan for a specified module.
    
    :param package_name: Composer package name
    :param project_dir: Project root directory
    :param mode: Deep scan mode ('all', 'patches', or 'git')
    :param patches_map: Optional pre-resolved patch map
    :return: ModuleDeepScan instance
    """
    mode_normalized = str(mode).lower() if mode else "all"
    if mode_normalized not in ("all", "patches", "git"):
        mode_normalized = "all"

    audit = ModuleDeepScan(mode=mode_normalized)

    if mode_normalized in ("all", "patches"):
        if patches_map is None:
            patches_map = resolve_composer_patches(project_dir)
        audit.patches = patches_map.get(package_name, [])

    if mode_normalized == "patches":
        # Skip Git repository inspection entirely
        return audit

    if not shutil.which("git"):
        audit.index_status = AuditStatus.UNAVAILABLE
        audit.history_status = AuditStatus.UNAVAILABLE
        audit.index_reason = "Git executable not found"
        audit.history_reason = "Git executable not found"
        return audit

    pkg_dir, reason = resolve_module_path(package_name, project_dir)
    if pkg_dir is None:
        audit.index_status = AuditStatus.UNAVAILABLE
        audit.history_status = AuditStatus.UNAVAILABLE
        audit.index_reason = reason
        audit.history_reason = reason
        return audit

    # Discover Git root
    try:
        git_root_proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if git_root_proc.returncode != 0 or not git_root_proc.stdout.strip():
            audit.index_status = AuditStatus.UNAVAILABLE
            audit.history_status = AuditStatus.UNAVAILABLE
            audit.index_reason = "Not a Git repository"
            audit.history_reason = "Not a Git repository"
            return audit
        git_root = Path(git_root_proc.stdout.strip()).resolve()
    except Exception as exc:
        audit.index_status = AuditStatus.UNAVAILABLE
        audit.history_status = AuditStatus.UNAVAILABLE
        audit.index_reason = f"Failed to check Git repository: {exc}"
        audit.history_reason = f"Failed to check Git repository: {exc}"
        return audit

    # Verify pkg_dir is inside git_root
    try:
        rel_module_path = pkg_dir.relative_to(git_root).as_posix()
    except ValueError:
        audit.index_status = AuditStatus.UNAVAILABLE
        audit.history_status = AuditStatus.UNAVAILABLE
        audit.index_reason = "Module path is outside the Git repository"
        audit.history_reason = "Module path is outside the Git repository"
        return audit

    audit.module_path = rel_module_path

    # 1. Git Index Check
    try:
        ls_proc = subprocess.run(
            ["git", "ls-files", "--cached", "--", rel_module_path],
            cwd=git_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if ls_proc.returncode != 0:
            audit.index_status = AuditStatus.UNAVAILABLE
            audit.index_reason = f"Git ls-files failed: {ls_proc.stderr.strip()}"
        else:
            files = [f for f in ls_proc.stdout.strip().splitlines() if f]
            audit.tracked_files_count = len(files)
            if files:
                audit.index_status = AuditStatus.FOUND
            else:
                audit.index_status = AuditStatus.CLEAR
    except Exception as exc:
        audit.index_status = AuditStatus.UNAVAILABLE
        audit.index_reason = f"Failed to check Git index: {exc}"

    # 2. Check if repository is shallow
    is_shallow = False
    try:
        shallow_proc = subprocess.run(
            ["git", "rev-parse", "--is-shallow-repository"],
            cwd=git_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if shallow_proc.returncode == 0 and shallow_proc.stdout.strip().lower() == "true":
            is_shallow = True
    except Exception:
        pass

    # 3. Git History Check
    try:
        log_proc = subprocess.run(
            ["git", "log", "-n", "5", "--format=%h%x09%s", "--", rel_module_path],
            cwd=git_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if log_proc.returncode != 0:
            audit.history_status = AuditStatus.UNAVAILABLE
            audit.history_reason = f"Git log failed: {log_proc.stderr.strip()}"
        else:
            commits = []
            for line in log_proc.stdout.strip().splitlines():
                if not line.strip():
                    continue
                parts = line.split("\t", 1)
                h = parts[0].strip()
                s = parts[1].strip() if len(parts) > 1 else ""
                commits.append({"hash": h, "subject": s})

            audit.recent_commits = commits
            if commits:
                audit.history_status = AuditStatus.FOUND
            else:
                if is_shallow:
                    audit.history_status = AuditStatus.INCOMPLETE
                    audit.history_reason = "Shallow repository clone; commit history is incomplete"
                else:
                    audit.history_status = AuditStatus.CLEAR
    except Exception as exc:
        audit.history_status = AuditStatus.UNAVAILABLE
        audit.history_reason = f"Failed to check Git history: {exc}"

    return audit


def audit_module_sync(module: Module | str, project_dir: str | Path, mode: str = "all", patches_map: dict | None = None) -> ModuleDeepScan:
    module_name = module.name if isinstance(module, Module) else module
    audit = perform_deep_scan(module_name, project_dir, mode=mode, patches_map=patches_map)
    if isinstance(module, Module):
        module.deep_scan = audit
    return audit


async def audit_module_async(module: Module | str, project_dir: str | Path, mode: str = "all", patches_map: dict | None = None) -> ModuleDeepScan:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, audit_module_sync, module, project_dir, mode, patches_map)


async def audit_modules_async(modules: list[Module], project_dir: str | Path, mode: str = "all") -> None:
    loop = asyncio.get_running_loop()
    mode_normalized = str(mode).lower() if mode else "all"
    if mode_normalized in ("all", "patches"):
        patches_map = await loop.run_in_executor(None, resolve_composer_patches, project_dir)
    else:
        patches_map = {}

    def _audit_one(mod: Module):
        audit = perform_deep_scan(mod.name, project_dir, mode=mode_normalized, patches_map=patches_map)
        mod.deep_scan = audit
        return audit

    tasks = [loop.run_in_executor(None, _audit_one, mod) for mod in modules]
    await asyncio.gather(*tasks)

