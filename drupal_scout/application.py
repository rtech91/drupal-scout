from sys import exit, stderr
import asyncio
import json
import os
from argparse import ArgumentParser
import jq
from .formatters.formatterfactory import FormatterFactory
from .exceptions import *
from .module import Module
from .workers_manager import WorkersManager


class Application:
    """
    The main application class.
    """

    def __init__(self):
        self.__modules = {}
        self.__drupal_core_version = "8.8"  # default and minimal supported Drupal core version for upgrade

    @property
    def modules(self) -> dict:
        return self.__modules

    @modules.setter
    def modules(self, value: dict) -> None:
        self.__modules = value

    @property
    def drupal_core_version(self) -> str:
        return self.__drupal_core_version

    @drupal_core_version.setter
    def drupal_core_version(self, value: str) -> None:
        self.__drupal_core_version = value

    async def run(self):
        # This is the main entry point for the application.
        # It should check the existence of the composer.json and composer.lock files,
        # parse the composer.json file to get the required modules,
        # parse the composer.lock file to get the installed versions of the modules,
        # and output the results in a human-readable format.

        try:
            parser = ArgumentParser()
            parser = self.get_argparser_configuration(parser)
            args = parser.parse_args()

            if hasattr(args, "command") and args.command == "info":
                self.handle_info(args)
                return

            # Targeted scan: specific modules provided via CLI
            if args.modules:
                await self._run_targeted_scan(args)
                return

            # Full environment scan
            await self._run_environment_scan(args)

        except (ComposerV1Exception, DirectoryNotFoundException, NoComposerJSONFileException) as e:
            print(e.message)
            exit(1)

    async def _run_targeted_scan(self, args) -> None:
        """Scan one or more specific modules and optionally use local lock metadata."""
        self.__drupal_core_version = self._resolve_targeted_core_version(args)
        for name in args.modules:
            self.__modules[name] = Module(name)

        use_lock_version = False
        composer_lock_path = os.path.join(args.directory, "composer.lock")
        if not args.no_lock and os.path.isfile(composer_lock_path):
            self.determine_module_versions(args)
            use_lock_version = True
        elif not args.no_lock:
            print(
                "composer.lock was not found; running targeted scan without installed-version protection.",
                file=stderr
            )
        else:
            print(
                "The composer.lock file was not used to determine installed versions of targeted modules.",
                file=stderr
            )

        workers_manager = WorkersManager(
            modules=list(self.__modules.values()),
            current_core=self.__drupal_core_version,
            use_lock_version=use_lock_version,
            concurrency_limit=args.limit
        )
        await workers_manager.run()

        formatter = FormatterFactory.get_formatter(args)
        if formatter:
            print(formatter.format(list(self.__modules.values())))

    def _resolve_targeted_core_version(self, args) -> str:
        """Resolve Drupal core version for targeted scans with CLI override + environment fallback."""
        if args.core:
            resolved_core = args.core.replace("^", "").replace("~", "")
            print(f"Using Drupal core version from --core: {resolved_core}", file=stderr)
            return resolved_core

        try:
            self.determine_drupal_core_version(args)
            if self.__drupal_core_version:
                return self.__drupal_core_version
        except FileNotFoundError:
            pass
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass

        print(
            "Unable to determine Drupal core version. Provide --core or run inside a project directory with "
            "composer.lock/composer.json.",
            file=stderr,
        )
        exit(1)

    async def _run_environment_scan(self, args) -> None:
        """Scan all modules discovered from the Drupal project's composer files."""
        # check if the directory exists and whether the composer.json file exists in it
        if not os.path.isdir(args.directory):
            raise DirectoryNotFoundException("The directory {} does not exist.".format(args.directory))

        # check if the directory contains the composer.json file
        if not os.path.isfile(os.path.join(args.directory, "composer.json")):
            raise NoComposerJSONFileException()

        # check if the Drupal project uses Composer 2
        if not self.is_composer2(args):
            raise ComposerV1Exception()

        # determine the Drupal core version
        self.determine_drupal_core_version(args)

        # get the required modules from the composer.json file
        self.get_required_modules(args)

        if len(self.__modules) > 0:
            if not args.no_lock and os.path.isfile(os.path.join(args.directory, "composer.lock")):
                self.determine_module_versions(args)
            elif args.no_lock:
                print("The composer.lock file was not used to determine the installed versions of the modules.",
                      file=stderr)
                print(
                    "The only Drupal core version will be use to determine the transitive versions of the modules.",
                    file=stderr)

            # create the workers manager
            workers_manager = WorkersManager(
                modules=list(self.__modules.values()),
                current_core=self.__drupal_core_version,
                use_lock_version=not args.no_lock,
                concurrency_limit=args.limit
            )
            await workers_manager.run()

            # output the results
            formatter = FormatterFactory.get_formatter(args)
            if formatter:
                print(formatter.format(list(self.__modules.values())))
        else:
            print("No modules were found in the composer.json file.", file=stderr)

    def get_argparser_configuration(self, parser) -> ArgumentParser:
        """
        Get the configuration of the ArgumentParser object.
        :param parser:  the ArgumentParser object
        :type  parser:  ArgumentParser
        :return:    the ArgumentParser object
        """
        parser.description = "Scout out for transitive versions of Drupal modules for the upgrade of the core."
        parser.add_argument(
            "-v",
            "--version",
            action="version",
            version="drupal-scout {}".format(self.get_version())
        )
        parser.add_argument(
            "-d",
            "--directory",
            help="The directory of the Drupal installation.",
            type=str,
            default="."
        )
        # special argument to support the composer.lock file
        parser.add_argument(
            "-n",
            "--no-lock",
            help="Do not use the composer.lock file to determine the installed versions of the modules.",
            action="store_true",
            default=False
        )
        parser.add_argument(
            "-l",
            "--limit",
            help="Maximum number of concurrent network requests. This prevents overwhelming the upstream API "
                "and hitting rate limits. Default: 10.",
            type=int,
            default=10
        )

        # "table" format is for human-readable output in the console
        # "json" format is for machine-readable output
        # "suggest" format is for the suggestion of the transitive versions of the modules
        # in the separate composer.json file
        parser.add_argument(
            "-f",
            "--format",
            help="The output format. By default, the application will use the table format.",
            choices=["table", "json", "suggest"],
            default="table"
        )

        # the following argument is only available for the "suggest" format
        parser.add_argument(
            '-s',
            '--save-dump',
            help='Use in pair with --format suggest to dump the suggested composer.json file to the specified path.',
            default=False,
            action='store_true'
        )

        parser.add_argument(
            '-c',
            '--core',
            help='Optional Drupal core version override for targeted module scans (e.g. 10.0.0). '
                  'If omitted, the core version is auto-detected from composer.lock/composer.json in --directory.',
            type=str,
            default=None
        )

        parser.add_argument(
            '-m',
            '--modules',
            nargs='+',
            help='One or more specific Drupal module names to scan (e.g. drupal/webform drupal/ctools). '
                 'When provided, the full environment scan is skipped. The tool still uses composer.lock from '
                 '--directory for installed-version protection when available.',
            default=[]
        )

        subparsers = parser.add_subparsers(dest="command")
        info_parser = subparsers.add_parser('info', help='Diagnostic information about the tool and environment')

        return parser

    def get_version(self):
        """
        Identify the current version of the application dynamically.
        :return: String representation of the version
        """
        import importlib.metadata
        import re
        
        try:
            return importlib.metadata.version('drupal-scout')
        except importlib.metadata.PackageNotFoundError:
            try:
                # relative path to find pyproject.toml in the source tree
                current_dir = os.path.dirname(os.path.abspath(__file__))
                pyproject_path = os.path.join(os.path.dirname(current_dir), "pyproject.toml")
                with open(pyproject_path, "r") as f:
                    content = f.read()
                    match = re.search(r'version\s*=\s*"([^"]+)"', content)
                    if match:
                        return match.group(1)
            except Exception:
                pass
        return "Unknown"

    def handle_info(self, args):
        """
        Handle the 'info' subcommand to provide diagnostic information about the tool and environment.
        """
        import subprocess

        version = self.get_version()


        jq_status = "NOT FOUND OR NOT FUNCTIONAL"
        try:
            subprocess.run(["jq", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            jq_status = "FOUND and FUNCTIONAL"
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        print(f"Drupal Scout v{version}")
        print("-" * 19)
        print("Status:")
        print(f"  - Version: {version} (verified from metadata)")
        print(f"  - Dependencies: jq binary is {jq_status}")
        print("  - Environment: ")
        
        composer_json = "DETECTED" if os.path.isfile(os.path.join(args.directory, "composer.json")) else "NOT DETECTED"
        composer_lock = "DETECTED" if os.path.isfile(os.path.join(args.directory, "composer.lock")) else "NOT DETECTED"
        
        print(f"      * composer.json: {composer_json}")
        print(f"      * composer.lock: {composer_lock}")
        
        composer2_status = "DETECTED" if self.is_composer2(args) else "NOT DETECTED"
        print(f"      * Composer 2: {composer2_status}")
        
        core_version = "[Unknown]"
        if composer_json == "DETECTED":
            try:
                if composer_lock == "DETECTED":
                    args_mock = type('Args', (object,), {"no_lock": False, "directory": args.directory})()
                else:
                    args_mock = type('Args', (object,), {"no_lock": True, "directory": args.directory})()
                
                import sys, io
                original_stdout = sys.stdout
                sys.stdout = io.StringIO()
                try:
                    self.determine_drupal_core_version(args_mock)
                    core_version = self.__drupal_core_version
                finally:
                    sys.stdout = original_stdout
            except Exception:
                pass
                
        print(f"      * Drupal Core Version: {core_version}")

    def is_composer2(self, args):
        """
        Check if the Drupal project uses Composer 2.
        :param args:    the arguments passed to the application
        :type args:     argparse.Namespace
        :return:        True if the Drupal project uses Composer 2, False otherwise
        :rtype:         bool
        """
        # check whether the vendor directory exists and has a composer/platform_check.php file
        # because this clue is only available in Composer 2
        if os.path.isdir(os.path.join(args.directory, "vendor")):
            if os.path.isfile(os.path.join(args.directory, "vendor", "composer", "platform_check.php")):
                return True
        return False

    def determine_drupal_core_version(self, args):
        """
        Get the version of the Drupal core or use the default version.
        :param args:    the arguments passed to the application
        :type args:     argparse.Namespace
        """
        # default Drupal core version
        if not args.no_lock:
            with open(os.path.join(args.directory, "composer.lock"), "r") as f:
                composer_lock = json.load(f)
                self.__drupal_core_version = jq.compile(".packages[] | select(.name == \"drupal/core\") | .version") \
                    .input(composer_lock).first()
        else:
            with open(os.path.join(args.directory, "composer.json"), "r") as f:
                composer_json = json.load(f)
                # Drupal core version can be represented by "drupal/core" requirement
                # or within the "drupal/core-recommended" requirement
                if "drupal/core" in composer_json["require"]:
                    # clear special characters from the version
                    self.__drupal_core_version = composer_json["require"]["drupal/core"] \
                        .replace("^", "").replace("~", "")
                elif "drupal/core-recommended" in composer_json["require"]:
                    # clear special characters from the version
                    self.__drupal_core_version = composer_json["require"]["drupal/core-recommended"] \
                        .replace("^", "").replace("~", "")
        print("The Drupal core version is: " + self.__drupal_core_version, file=stderr)

    def get_required_modules(self, args):
        """
        Get the list of required modules from the composer.json file.
        :param args:    the arguments passed to the application
        :type args:     argparse.Namespace
        :return:        the list of required modules
        :rtype:         list
        """
        with open(os.path.join(args.directory, "composer.json"), "r") as f:
            composer_json = json.load(f)
            # load required modules, but only with drupal/* prefix and exclude modules with drupal/core prefix
            found_modules = jq.compile(".require | keys | map(select(startswith(\"drupal/\"))) | map(select("
                                       "startswith(\"drupal/core\") | not))").input(composer_json).first()
            for module in found_modules:
                self.__modules[module] = Module(module)

    def determine_module_versions(self, args):
        """
        Get the versions of the required modules described in the "composer.lock" file.
        :param args:      the arguments passed to the application
        :return:          the list of required modules with their versions
        :rtype:           list
        """
        if len(self.__modules) == 0:
            print("No modules to check.", file=stderr)
            exit(0)

        with open(os.path.join(args.directory, "composer.lock"), "r") as f:
            composer_lock = json.load(f)
            for module_name in self.__modules.keys():
                module = self.__modules.get(module_name)
                if module is None:
                    continue
                # look for the module with name in the packages array
                module_version = None
                try:
                    module_version = jq.compile(
                        ".packages | map(select(.name == \"{}\")) | .[].version".format(module.name)) \
                        .input(composer_lock).first()
                except StopIteration:
                    module_version = None
                # save the module name and version in the versioned_modules array
                module.version = module_version
                self.__modules[module.name] = module
