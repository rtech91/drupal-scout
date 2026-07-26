# Model Context Protocol (MCP) Connection Guide

This guide provides comprehensive instructions for connecting and configuring the **`drupal-scout`** MCP server across various AI coding assistants and environments, including **Claude Desktop**, **Claude Code CLI**, **GitHub Copilot**, **Google Antigravity**, and **OpenAI Codex**.

---

## Table of Contents

1. [Overview & Server Architecture](#1-overview--server-architecture)
2. [Common Launch Syntax & Environment Standards](#2-common-launch-syntax--environment-standards)
3. [Claude Desktop & Claude Code Configuration](#3-claude-desktop--claude-code-configuration)
   - [Claude Desktop (`claude_desktop_config.json`)](#claude-desktop-claude_desktop_configjson)
   - [Claude Code CLI (`claude mcp add`)](#claude-code-cli-claude-mcp-add)
4. [GitHub Copilot & VS Code Configuration](#4-github-copilot--vs-code-configuration)
5. [Google Antigravity (AGY CLI / IDE) Configuration](#5-google-antigravity-agy-cli--ide-configuration)
6. [OpenAI Codex & Generic MCP Client Configuration](#6-openai-codex--generic-mcp-client-configuration)
7. [MCP Tool Reference Catalog](#7-mcp-tool-reference-catalog)
   - [`get_diagnostic_info`](#1-get_diagnostic_info)
   - [`perform_full_project_scan`](#2-perform_full_project_scan)
   - [`scan_specific_modules`](#3-scan_specific_modules)
   - [`generate_composer_upgrade_json`](#4-generate_composer_upgrade_json)
8. [Connection Troubleshooting & Diagnostics](#8-connection-troubleshooting--diagnostics)

---

## 1. Overview & Server Architecture

`drupal-scout` includes a built-in FastMCP server (`drupal_scout.mcp_server`) that exposes Drupal module upgrade compatibility tools directly to LLMs.

- **Protocol**: Model Context Protocol (MCP) JSON-RPC 2.0
- **Transport**: Standard Input/Output (`stdio`)
- **Server Name**: `drupal-scout`
- **Output Purity**: Uses `SilentOutputHandler` to route all diagnostic and log output to `stderr`, leaving `stdout` clean for JSON-RPC message framing.

---

## 2. Common Launch Syntax & Environment Standards

Depending on your Python package manager and environment setup, you can launch `drupal-scout` using one of three standard methods:

### Method A: `uv run` — local checkout (Recommended for development)
Runs the server using the project's own virtual environment without requiring manual activation. Use this when working with a local checkout of the repository:
```bash
uv run --directory /path/to/drupal-scout drupal-scout-mcp
```

### Method B: `uvx --from` — installed package from PyPI
Installs `drupal-scout` into an isolated ephemeral environment and runs the entry point. Use this for a globally-available, install-free invocation:
```bash
uvx --from drupal-scout drupal-scout-mcp
```

### Method C: Virtual Environment Interpreter
Points directly to the Python interpreter in the local `.venv`:
```bash
/path/to/drupal-scout/.venv/bin/python -m drupal_scout.mcp_server
```

### Method D: Conda Environment Run
Executes within a designated Conda environment. Use `--no-capture-output` to prevent Conda from buffering `stdout`, which would corrupt the MCP stdio stream:
```bash
conda run --no-capture-output -n drupal-scout python -m drupal_scout.mcp_server
```

### Environment Variables
- `PYTHONUNBUFFERED=1`: Ensures unbuffered standard I/O streams.
- `PYTHONPATH=/path/to/drupal-scout`: Ensures `drupal_scout` module imports resolve properly if running outside an installed environment.

---

## 3. Claude Desktop & Claude Code Configuration

### Claude Desktop (`claude_desktop_config.json`)

**Config Location**:
- **Linux**: `~/.config/Claude/claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

#### Option 1: Using `uv run` (Recommended)
```json
{
  "mcpServers": {
    "drupal-scout": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/drupal-scout",
        "drupal-scout-mcp"
      ]
    }
  }
}
```

#### Option 2: Using Virtual Environment Python
```json
{
  "mcpServers": {
    "drupal-scout": {
      "command": "/path/to/drupal-scout/.venv/bin/python",
      "args": [
        "-m",
        "drupal_scout.mcp_server"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": "/path/to/drupal-scout"
      }
    }
  }
}
```

---

### Claude Code CLI (`claude mcp add`)

Register `drupal-scout` directly via the Claude Code command line interface. The `--` separator is required to separate `claude mcp add` flags from the server command:

```bash
# Using uv run (local checkout)
claude mcp add drupal-scout -- uv run --directory /path/to/drupal-scout drupal-scout-mcp

# Using uvx (from PyPI, no local checkout needed)
claude mcp add drupal-scout -- uvx --from drupal-scout drupal-scout-mcp

# Using virtualenv python directly
claude mcp add drupal-scout -- /path/to/drupal-scout/.venv/bin/python -m drupal_scout.mcp_server
```

To pass environment variables at registration time, use the `-e` flag **before** the `--` separator:
```bash
claude mcp add drupal-scout -e PYTHONPATH=/path/to/drupal-scout -- /path/to/.venv/bin/python -m drupal_scout.mcp_server
```

To list registered MCP servers in Claude Code:
```bash
claude mcp list
```

---

## 4. GitHub Copilot & VS Code Configuration

**Config Location**: Workspace `.vscode/mcp.json` (recommended, add to source control) or via the Command Palette → **MCP: Open User Configuration** for global settings.

> **⚠️ Note**: VS Code's `${workspaceFolder}` variable is **not** expanded in `mcp.json`. Always use an absolute path in `command` and `args`.

Add the server definition to `.vscode/mcp.json`:

#### Option 1: Using `uvx` (from PyPI — no local checkout needed)
```json
{
  "mcpServers": {
    "drupal-scout": {
      "command": "uvx",
      "args": [
        "--from",
        "drupal-scout",
        "drupal-scout-mcp"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

#### Option 2: Using `uv run` (local checkout)
```json
{
  "mcpServers": {
    "drupal-scout": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/drupal-scout",
        "drupal-scout-mcp"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

#### Option 3: Using Virtual Environment Python
```json
{
  "mcpServers": {
    "drupal-scout": {
      "command": "/absolute/path/to/drupal-scout/.venv/bin/python",
      "args": [
        "-m",
        "drupal_scout.mcp_server"
      ],
      "cwd": "/absolute/path/to/drupal-scout"
    }
  }
}
```

---

## 5. Google Antigravity (AGY CLI / IDE) Configuration

**Config File Locations**:
- **Global**: `~/.gemini/antigravity-cli/mcp_config.json`
- **Workspace**: `<project-root>/.agents/mcp_config.json`

All MCP servers are defined in a single `mcp_config.json` file under the `mcpServers` key. You can also use the interactive `/mcp` manager inside the AGY CLI to add and inspect servers without editing JSON manually.

### Server Definition

```json
{
  "mcpServers": {
    "drupal-scout": {
      "command": "/path/to/drupal-scout/.venv/bin/python",
      "args": [
        "-m",
        "drupal_scout.mcp_server"
      ],
      "cwd": "/path/to/drupal-scout",
      "env": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": "/path/to/drupal-scout"
      }
    }
  }
}
```

Alternatively, using `uvx` (no local checkout required):

```json
{
  "mcpServers": {
    "drupal-scout": {
      "command": "uvx",
      "args": [
        "--from",
        "drupal-scout",
        "drupal-scout-mcp"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

---

## 6. OpenAI Codex Configuration

The OpenAI Codex CLI (2025+) uses a **TOML** configuration file at `~/.codex/config.toml`. MCP servers are defined under `[mcp_servers.<name>]` sections.

### `~/.codex/config.toml`

#### Using `uvx` (from PyPI — no local checkout needed)
```toml
[mcp_servers.drupal-scout]
command = "uvx"
args = ["--from", "drupal-scout", "drupal-scout-mcp"]

[mcp_servers.drupal-scout.env]
PYTHONUNBUFFERED = "1"
```

#### Using a local virtual environment interpreter
```toml
[mcp_servers.drupal-scout]
command = "/path/to/drupal-scout/.venv/bin/python"
args = ["-m", "drupal_scout.mcp_server"]

[mcp_servers.drupal-scout.env]
PYTHONUNBUFFERED = "1"
PYTHONPATH = "/path/to/drupal-scout"
```

After saving, restart the Codex session — tools are discovered automatically.

> **Note**: TOML is strict about syntax. A formatting error in `config.toml` disables MCP integration for all servers. Validate with `toml-cli` or a TOML linter if tools fail to appear.

---

## 7. MCP Tool Reference Catalog

### 1. `get_diagnostic_info`
Runs environment pre-flight diagnostics for a target Drupal project directory.

- **Equivalent CLI Command**: `drupal-scout info`
- **Arguments**:
  - `directory` (*string*, optional, default: `"."`): Path to the Drupal project root.
- **Return Format**:
  ```json
  {
    "version": "3.1.0",
    "jq_status": "FOUND and FUNCTIONAL",
    "composer_json": true,
    "composer_lock": true,
    "composer2": true,
    "drupal_core_version": "10.2.0"
  }
  ```

---

### 2. `perform_full_project_scan`
Scans `composer.json` in the target project to evaluate all `drupal/*` dependencies for core upgrade compatibility.

- **Equivalent CLI Command**: `drupal-scout [-d DIRECTORY] [-n] [-l LIMIT] [--deep-scan]`
- **Arguments**:
  - `directory` (*string*, optional, default: `"."`): Drupal project directory path.
  - `no_lock` (*boolean*, optional, default: `false`): If true, skips reading installed versions from `composer.lock`.
  - `limit` (*integer*, optional, default: `10`): Max concurrent API HTTP requests.
  - `deep_scan` (*boolean|string*, optional, default: `false`): Perform local deep audit (`"all"`, `"patches"`, `"git"`).
- **Return Format**:
  ```json
  {
    "modules": [
      {
        "name": "drupal/webform",
        "version": "6.2.0",
        "suitable_entries": ["6.2.2"],
        "failed": false
      }
    ],
    "drupal_core_version": "10.2.0",
    "lock_file_used": true
  }
  ```

---

### 3. `scan_specific_modules`
Targeted scan for specific Drupal modules without requiring full project environment setup.

- **Equivalent CLI Command**: `drupal-scout --modules ... [--core ...] [-d DIRECTORY] [--deep-scan]`
- **Arguments**:
  - `modules` (*list[string]*, required): Module names (e.g. `["drupal/webform", "drupal/ctools"]`).
  - `core` (*string*, optional): Target Drupal core version override (e.g. `"10.0.0"`).
  - `directory` (*string*, optional, default: `"."`): Directory path for auto-detecting core/lock settings.
  - `limit` (*integer*, optional, default: `10`): Concurrency limit.
  - `deep_scan` (*boolean|string*, optional, default: `false`): Deep audit mode.
- **Return Format**:
  ```json
  {
    "modules": [...],
    "drupal_core_version": "10.0.0",
    "lock_file_used": true
  }
  ```

---

### 4. `generate_composer_upgrade_json`
Generates a modified `composer.json` payload with compatible transitive module version constraints.

- **Equivalent CLI Command**: `drupal-scout --format suggest` (read-only)
- **Arguments**:
  - `directory` (*string*, optional, default: `"."`): Target project path.
  - `core` (*string*, optional): Core version override.
- **Return Format**:
  ```json
  {
    "suggested_composer_json": {
      "require": {
        "drupal/webform": "^6.2.2"
      }
    },
    "drupal_core_version": "10.2.0"
  }
  ```

---

## 8. Connection Troubleshooting & Diagnostics

### Issue 1: `JSON-RPC framing error` / `Unexpected token in JSON`
- **Cause**: Diagnostic messages, ANSI colors, or `print()` calls leaking into standard output (`stdout`), corrupting the MCP JSON-RPC protocol stream.
- **Resolution**: `drupal-scout` uses `SilentOutputHandler` in `mcp_server.py`. Ensure you run via `drupal-scout-mcp` or `python -m drupal_scout.mcp_server` rather than running the standard interactive CLI command line wrapper. All logs are routed strictly to `stderr`.

### Issue 2: `ModuleNotFoundError: No module named 'drupal_scout'`
- **Cause**: The Python interpreter launched by the MCP client cannot locate the `drupal_scout` package.
- **Resolution**: Pass `PYTHONPATH` in the server `env` configuration pointing to the project directory, or use `uv run --directory /path/to/drupal-scout`.

### Issue 3: `jq binary NOT FOUND OR NOT FUNCTIONAL`
- **Cause**: `jq` system utility is missing from system `PATH`.
- **Resolution**: Install `jq` via system package manager (`sudo apt install jq` or `brew install jq`), or add `PATH` to the server `env` section in your MCP client configuration.
