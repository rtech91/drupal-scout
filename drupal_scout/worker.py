import jq
import requests
import threading
from pprint import pprint
from packaging import version
from .module import Module
from .exceptions import ModuleNotFoundException


class Worker:
    """
    The main worker class.
    """

    def __init__(self, module: Module, use_lock_version: str | bool = False, current_core: str = '8'):
        """
        Initialize the worker.
        :param module:           the module to be processed
        :param use_lock_version:  whether to use the version from the lock file
        :param current_core:
        """
        self.current_core = current_core.replace("^", "").replace("~", "")
        self.module = module
        self.use_lock_version = False
        if type(use_lock_version) is str:
            self.use_lock_version = use_lock_version.replace("^", "").replace("~", "")

    def run(self, semaphore: threading.Semaphore):
        with semaphore:
            # This is the main entry point for the worker.
            try:
                composer_url = self.prepare_composer_url(self.module.name)
                response = requests.get(composer_url)
                contents = '{}'
                if response.status_code == 200:
                    contents = response.json()
                elif response.status_code == 404:
                    raise ModuleNotFoundException(
                        "The module {} is not found Possibly it is no more supported.".format(self.module.name))
                self.module.transitive_entries = self.find_transitive_entries(contents)
                self.module.suitable_entries = self.find_suitable_entries(self.module.transitive_entries)
                print(self.module.name)
                pprint(self.module.suitable_entries)
            except ModuleNotFoundException as e:
                print(e.message)

    def prepare_composer_url(self, module_name: str) -> str:
        """
        Prepare the URL to the JSON data of the module.
        :param module_name: the name of the module
        :type module_name:  str
        :return:   the URL to the JSON data of the module
        :rtype:    str
        """
        return 'https://packages.drupal.org/files/packages/8/p2/' + module_name + '.json'

    def find_transitive_entries(self, response_contents: str) -> list:
        """
        Find the transitive entries of the module relative to the current core version.
        :param response_contents:   the contents of the response
        :type response_contents:    str
        :return:    the transitive entries of the module
        :rtype:     list
        """
        transitive_entries = []
        entries = jq.compile(
            '.packages."' + self.module.name + '" | .[] | select(.require != null) | {"version", '
                                               '"requirement":.require."drupal/core"}').input(response_contents).all()
        for entry in entries:
            if "||" in entry['requirement']:
                entry['requirement'] = entry['requirement'].replace("^", "").replace(" ", "")
                entry["requirement_parts"] = entry['requirement'].split("||")
                transitive_entries.append(entry)
        return transitive_entries

    def find_suitable_entries(self, transitive_entries: list) -> list:
        """
        Get the suitable transitive versions of the module.
        :param transitive_entries:  the transitive entries of the module
        :type transitive_entries:   list
        :return:    the suitable versions of the module
        :rtype:     list
        """
        suitable_entries = []
        current_major_version = version.parse(self.current_core).major
        for entry in transitive_entries:
            requirements_length = len(entry['requirement_parts'])
            if requirements_length == 1:
                if version.parse(entry['requirement_parts'][0]) <= version.parse(self.current_core):
                    suitable_entries.append(entry)
            elif requirements_length == 2:
                if version.parse(entry['requirement_parts'][0]) <= version.parse(self.current_core) <= version.parse(
                        entry['requirement_parts'][1]):
                    suitable_entries.append(entry)
            elif requirements_length == 3:
                index_from = 0  # the index of the first version in the requirement
                index_to = 1  # the index of the second version in the requirement
                # as for now Drupal has three major versions: 8, 9, 10
                # so we need to check if the current core version is 8 or 9
                # and then set the indexes accordingly
                if current_major_version == 9:
                    index_from = 1
                    index_to = 2
                if version.parse(entry['requirement_parts'][index_from]) >= version.parse(
                        self.current_core) <= version.parse(entry['requirement_parts'][index_to]):
                    suitable_entries.append(entry)

        # apply post-filtering if the lock version is used and the module version is specified
        if self.use_lock_version and self.module.version:
            suitable_entries = filter(
                lambda current_entry: version.parse(current_entry['version']) >= version.parse(self.module.version),
                suitable_entries
            )
        return list(suitable_entries)
