import json
import os
import jq
from pprint import pprint
from argparse import ArgumentParser
from sys import exit
from .exceptions import *


class Application:
    """
    The main application class.
    """
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

            # get the required modules from the composer.json file
            modules = self.__get_required_modules(args)

            if len(modules) > 0 and not args.no_lock and os.path.isfile(os.path.join(args.directory, "composer.lock")):
                versioned_modules = self.__get_module_versions(args, modules)
                pprint(versioned_modules)
            elif len(modules) > 0 and args.no_lock:
                print("The composer.lock file was not used to determine the installed versions of the modules.")
                pprint(modules)
        except (ComposerV1Exception, DirectoryNotFoundException, NoComposerJSONFileException, Exception) as e:
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
            default=0
        )
        return parser

    def get_drupal_core_version(self, args):
        """
        Get the version of the Drupal core.
        :param args:    the arguments passed to the application
        :type args:     argparse.Namespace
        :return:        the version of the Drupal core
        :rtype:         str
        """
        with open(os.path.join(args.directory, "composer.json"), "r") as f:
            composer_json = json.load(f)
            # Drupal core version can be represented by "drupal/core" requirement
            # or within the "drupal/core-recommended" requirement
            if "drupal/core" in composer_json["require"]:
                drupal_core_version = composer_json["require"]["drupal/core"]
            elif "drupal/core-recommended" in composer_json["require"]:
                drupal_core_version = composer_json["require"]["drupal/core-recommended"]

            return drupal_core_version

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

    def __get_required_modules(self, args):
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
            required_modules = jq.compile(".require | keys | map(select(startswith(\"drupal/\"))) | map(select("
                                          "startswith(\"drupal/core\") | not))").input(composer_json).first()
            return required_modules

    def __get_module_versions(self, args, modules):
        """
        Get the versions of the required modules described in the "composer.lock" file.
        :param args:      the arguments passed to the application
        :param modules:   the list of required modules
        :type modules:    list
        :return:          the list of required modules with their versions
        :rtype:           list
        """
        if len(modules) == 0:
            print("No modules to check.")
            exit(0)

        versioned_modules = []
        with open(os.path.join(args.directory, "composer.lock"), "r") as f:
            composer_lock = json.load(f)
            for module in modules:
                # look for the module with name in the packages array
                module_version = jq.compile(".packages | map(select(.name == \"{}\")) | .[].version".format(module)) \
                    .input(composer_lock).first()
                # save the module name and version in the versioned_modules array
                versioned_modules.append({"name": module, "version": module_version})
            return versioned_modules
