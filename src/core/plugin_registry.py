"""
Plugin Registry for Dynamic Discovery and Execution of Accounting Plugins.
"""

from typing import Dict, List, Optional, Type
from src.core.plugin_base import BaseAccountingPlugin


class PluginRegistry:
    def __init__(self):
        self._plugins: Dict[str, BaseAccountingPlugin] = {}

    def register(self, plugin: BaseAccountingPlugin):
        """Register a plugin instance."""
        self._plugins[plugin.plugin_id] = plugin

    def get(self, plugin_id: str) -> Optional[BaseAccountingPlugin]:
        """Get plugin by ID."""
        return self._plugins.get(plugin_id)

    def list_plugins(self) -> List[Dict[str, str]]:
        """List all available plugins metadata."""
        return [
            {
                "id": p.plugin_id,
                "name": p.plugin_name,
                "category": p.category,
                "description": p.description
            }
            for p in self._plugins.values()
        ]

    def get_all(self) -> Dict[str, BaseAccountingPlugin]:
        return self._plugins


# Global singleton registry
registry = PluginRegistry()
