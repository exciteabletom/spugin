import itertools
import operator

import requests

from . import settings
from .utils import Utils


class SpigetAPI:
    headers: dict = {
        "user-agent": settings.USER_AGENT,
    }

    @staticmethod
    def build_api_url(api_request: str) -> str:
        return f"{settings.API_URL}{api_request}"

    # noinspection PyDefaultArgument
    def call_api(self, api_request: str, params: dict = {}) -> requests.Response:
        response: requests.Response = requests.get(
            self.build_api_url(api_request),
            params=params,
            headers=self.headers,
        )

        return response

    def get_plugin_by_id(self, plugin_id: int) -> dict:
        response = self.call_api(f"/resources/{plugin_id}")
        return response.json()

    def search_plugins(self, plugin_name: str) -> list:
        response_tag = self.call_api(
            f"/search/resources/{plugin_name}",
            {
                "field": "tag",
                "sort": "-downloads",
                "size": 10,
            },
        )
        response_name = self.call_api(
            f"/search/resources/{plugin_name}",
            {
                "field": "name",
                "sort": "-downloads",
                "size": 10,
            },
        )

        if response_name.status_code == 404:
            return Utils.error(f"No plugin with name {plugin_name} found.")

        # Merge tag search and title searches together
        plugin_list: list = response_tag.json() + response_name.json()

        # Sort the list by highest download, then IDs
        plugin_list.sort(key=operator.itemgetter("downloads", "id"), reverse=True)

        # remove duplicate ids from list
        plugin_list = [id_field[0] for id_field in itertools.groupby(plugin_list)]

        return plugin_list[:5]

    def download_plugin(self, plugin: dict, filename: str = "") -> dict:
        """
        Download a plugin

        :param plugin: Dict containing plugin name, tag, and ID
        :param filename: Force a specific filename for the plugin instead of automatically making one
        :return: dict as generated by Utils.status_dict
        """
        response = self.call_api(
            f"/resources/{plugin.get('id')}/download",
        )

        if not filename:
            plugin_jar_name = Utils.create_jar_name(plugin.get("name"))
        else:
            plugin_jar_name = filename

        with open(plugin_jar_name, "wb") as f:
            f.write(response.content)
            pass

        Utils.inject_metadata_file(plugin, plugin_jar_name)

        return Utils.status_dict(True)

    def download_plugin_if_update(self, filename: str) -> dict or bool:
        """

        :param filename: Filename of a plugin
        :return: dict as generated by Utils.status_dict
        """
        metadata = Utils.load_metadata_file(filename)
        if not metadata:
            return Utils.status_dict(
                False,
                f"Couldn't load metadata for {filename}. Try reinstalling with spud first",
            )

        plugin_id: int = metadata.get("plugin_id")
        plugin = self.get_plugin_by_id(plugin_id)

        local_version: int = metadata.get("plugin_version_id")
        latest_version: int = plugin.get("versions")[0].get("id")

        if local_version >= latest_version:
            return Utils.status_dict(
                True, f"You have the latest version of {plugin.get('name')}"
            )
        else:
            self.download_plugin(plugin, filename)
            return Utils.status_dict(
                True, f"Updated {plugin.get('name')} to latest version"
            )
