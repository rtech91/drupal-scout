import json
import multiprocessing
import os
from argparse import ArgumentParser
from sys import exit

import jq

from .exceptions import *
from .module import Module
from .workers_manager import WorkersManager


class Application:
    """
    The main application class.
    """

    __modules = {}

    def __init__(self):
        self.__drupal_core_version = "8.8"  # default and minimal supported Drupal core version for upgrade

    def run(self):
        # This is the main entry point for the application.
        # It should check the existence of the composer.json and composer.lock files,
        # parse the composer.json file to get the required modules,
        # parse the composer.lock file to get the installed versions of the modules,
        # and output the results in a human-readable format.

        try:
            parser = ArgumentParser()
            parser = self.get_argparser_configuration(parser)
            args = parser.parse_args()

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
                    print("The composer.lock file was not used to determine the installed versions of the modules.")
                    print(
                        "The only Drupal core version will be use to determine the transitive versions of the modules.")

                # create the workers manager
                workers_manager = WorkersManager(
                    modules=list(self.__modules.values()),
                    current_core=self.__drupal_core_version,
                    use_lock_version=not args.no_lock,
                    number_of_threads=args.threads
                )
                workers_manager.run()
            else:
                print("No modules were found in the composer.json file.")

        except (ComposerV1Exception, DirectoryNotFoundException, NoComposerJSONFileException) as e:
            print(e.message)
            exit(1)

    def get_argparser_configuration(self, parser) -> ArgumentParser:
        """
        Get the configuration of the ArgumentParser object.
        :param parser:  the ArgumentParser object
        :return:    the ArgumentParser object
        """
        parser.description = "Scout out for transitive versions of Drupal modules for the upgrade of the core."
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
            "-t",
            "--threads",
            help="The number of threads to use for the concurrent requests and data parsing. By default, "
                 "the application will use all available threads",
            type=int,
            # the default value is the number of CPU cores
            default=multiprocessing.cpu_count()
        )
        return parser

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
            print("No modules to check.")
            exit(0)

        with open(os.path.join(args.directory, "composer.lock"), "r") as f:
            composer_lock = json.load(f)
            for module_name in self.__modules.keys():
                module: Module = self.__modules.get(module_name)
                # look for the module with name in the packages array
                module_version = jq.compile(
                    ".packages | map(select(.name == \"{}\")) | .[].version".format(module.name)) \
                    .input(composer_lock).first()
                # save the module name and version in the versioned_modules array
                module.version = module_version
                self.__modules[module.name] = module
