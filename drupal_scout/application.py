import json
import os
import jq
from pprint import pprint
from argparse import ArgumentParser
from sys import exit


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

        parser = ArgumentParser()
        parser = self.get_argparser_configuration(parser)
        args = parser.parse_args()
        if args.directory is not '.':  # if the directory is not the current one
            # check if the directory exists and whether the composer.json file exists in it
            if not os.path.isdir(args.directory):
                print("The directory {} does not exist.".format(args.directory))
                exit(1)
            if not os.path.isfile(os.path.join(args.directory, "composer.json")):
                print("The directory {} does not contain a composer.json file.".format(args.directory))
                exit(1)
            modules = self.get_required_modules(args)
        else:
            # check if the composer.json file exists in the current directory
            if not os.path.isfile("composer.json"):
                print("The current directory does not contain a composer.json file.")
                exit(1)
            modules = self.get_required_modules(args)

        if len(modules) > 0 and not args.no_lock:
            versioned_modules = self.get_module_versions(modules)
            pprint(versioned_modules)
        elif len(modules) > 0 and args.no_lock:
            print("The composer.lock file was not used to determine the installed versions of the modules.")
            pprint(modules)

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
            required_modules = jq.compile(".require | keys | map(select(startswith(\"drupal/\"))) | map(select("
                                          "startswith(\"drupal/core\") | not))").input(composer_json).first()
            return required_modules

    def get_module_versions(self, modules):
        """
        Get the versions of the required modules described in the composer.lock file.
        :param modules:   the list of required modules
        :type modules:    list
        :return:          the list of required modules with their versions
        :rtype:           list
        """
        if len(modules) == 0:
            print("No modules to check.")
            exit(0)

        composer_lock = json.load(open("composer.lock", "r"))
        versioned_modules = []
        for module in modules:
            # look for the module with name in the packages array
            module_version = jq.compile(".packages | map(select(.name == \"{}\")) | .[].version".format(module)) \
                .input(composer_lock).first()
            # save the module name and version in the versioned_modules array
            versioned_modules.append({"name": module, "version": module_version})
        return versioned_modules
