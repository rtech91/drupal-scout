# Drupal Scout

Search for Drupal module entries with transitive core version requirements to help to upgrade the Drupal Core.

## Installation

### Using uv (Recommended)

```bash
uv tool install drupal-scout
```

Or run directly without installing:

```bash
uvx drupal-scout --help
```

### Using pip

```bash
pip install drupal-scout
```

## Quick Start

Get a compatibility report for your current Drupal project:

```bash
drupal-scout
```

Scan a specific module for Drupal 11 compatibility:

```bash
drupal-scout --core 11.0.0 --modules drupal/webform
```

## Features

- **Asyncio Concurrency**: High-performance parallel module scanning using `asyncio` to speed up dependency analysis.
- **Rich TUI Integration**: Beautiful terminal output with structured tables and real-time progress bars powered by the `rich` library.
- **MCP Server Support**: Built-in [Model Context Protocol](https://modelcontextprotocol.io/) server for integration with AI IDEs (like Claude Desktop or Cursor).
- **Environment Diagnostics**: Quick self-diagnostic check of the environment and dependencies using the `info` command.
- **Multiple Output Formats**:
  - `table`: High-fidelity color-coded table for human readability.
  - `json`: Machine-readable raw data for automation scripts.
  - `suggest`: Generates a suggested `composer.json` with updated version requirements.

## Limitations

- **Python 3.11+**: The application requires Python 3.11 or higher.
- **Composer v2**: The application works with **Composer-based (Composer v2)** Drupal 8+ projects.

## Usage/Examples

```bash
drupal-scout [-h] [-v] [-d DIRECTORY] [-n] [-l LIMIT] [-f {table,json,suggest}] [-s] [-c CORE] [-m MODULES [MODULES ...]] {info} ...
```

### Arguments

- `-h, --help`: Show help message and exit.
- `-v, --version`: Show program's version number and exit.
- `-d DIRECTORY, --directory DIRECTORY`: Directory of the Drupal installation (default: `.`).
- `-n, --no-lock`: Do not use the `composer.lock` file to determine installed versions.
- `-l LIMIT, --limit LIMIT`: Concurrency limit for async requests. Default is `10`.
- `-f {table,json,suggest}, --format {table,json,suggest}`: Output format (default: `table`).
- `-s, --save-dump`: Use with `--format suggest` to save the suggested `composer.json` to disk.
- `-c CORE, --core CORE`: Optional Drupal core version override (e.g., `10.0.0`).
- `-m MODULES [MODULES ...], --modules MODULES [MODULES ...]`: Scan only specific modules, skipping full project discovery.

### Subcommands

- `info`: Show diagnostic information about the tool, `jq` availability, and the current Drupal environment.

### MCP Server Usage

To use Drupal Scout as an MCP server in your AI assistant:

```bash
drupal-scout-mcp
```

Or with `uvx`:

```bash
uvx --from drupal-scout drupal-scout-mcp
```

### Targeted Scan Examples

Scan one specific module with an explicit core version:

```bash
drupal-scout --core 10.0.0 --modules drupal/webform
```

Scan multiple modules and output JSON:

```bash
drupal-scout --core 10.0.0 --modules drupal/webform drupal/ctools --format json
```

Scan modules with auto-detected core from a local directory:

```bash
drupal-scout --directory /path/to/drupal --modules drupal/webform
```
