# Drupal Scout

Search for Drupal module entries with transitive core version requirements to help to upgrade the Drupal Core

## Installation

```bash
  pip install drupal-scout
```

## Features

- Use asyncio concurrency to speed up the process of searching for Drupal module entries with transitive core version requirements.
- Quick self-diagnostic check of the environment and dependencies using the `info` command.
- Choose between three output formats: table, json, and suggest.  
    - `table` format will output the data in the table format.  
    Example:
    ![Table format example](https://raw.githubusercontent.com/rtech91/drupal-scout/main/screenshots/format_table_example.png)
    - `json` format will output the raw data in the json format.  
    - `suggest` format will output the suggested composer.json file with the updated module version requirements.  
    It will also dump the suggested composer.json file to the specified path if the `--save-dump` argument is used.

## Limitations

- The application will only work with Composer-based (Composer v2) Drupal 8+ projects. 

## Usage/Examples

`drupal-scout [-h] [-v] [-d DIRECTORY] [-n] [-l LIMIT] [-f {table,json,suggest}] [-s] [-c CORE] [-m MODULES [MODULES ...]] {info} ...`

### Arguments
&dash; `-h, --help` show this help message and exit  
&ndash; `-v, --version` show program's version number and exit  
&ndash; `-d DIRECTORY, --directory DIRECTORY`  Directory of the Drupal installation  
&ndash; `-n, --no-lock` Do not use the composer.lock file to determine the installed versions of the modules  
&ndash; `-l LIMIT, --limit LIMIT` The concurrency limit for async requests and data parsing. By default, the application uses all available CPU cores.  
&ndash; `-f {table,json,suggest}, --format {table,json,suggest}` The output format. By default, the application will use the table format.  
&ndash; `-s, --save-dump` Use in pair with `--format suggest` to dump the suggested composer.json file to the specified path. 
&ndash; `-c CORE, --core CORE` Optional core version override for targeted scans. If omitted with `--modules`, core is auto-detected from composer metadata in `--directory`.  
&ndash; `-m MODULES [MODULES ...], --modules MODULES [MODULES ...]` Scan only specific modules. When used, full environment module discovery is skipped. If `composer.lock` exists and `--no-lock` is not set, installed versions are still used for downgrade protection.  

### Subcommands
&ndash; `info` - show diagnostic information about the tool and the current Drupal environment.

### Targeted Scan Examples

Scan one specific module with explicit core version:

```bash
drupal-scout --core 10.0.0 --modules drupal/webform
```

Scan multiple specific modules and output JSON:

```bash
drupal-scout --core 10.0.0 --modules drupal/webform drupal/ctools --format json
```

Scan targeted modules with auto-detected core from local `composer.lock`/`composer.json` in directory:

```bash
drupal-scout --directory /path/to/drupal --modules drupal/webform
```

If core cannot be auto-detected, provide `--core` explicitly.