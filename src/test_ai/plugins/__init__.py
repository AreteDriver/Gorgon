"""Plugin System.

Provides extensibility for custom step handlers, hooks, and integrations.
"""

from .base import (
    Plugin,
    PluginContext,
    PluginHook,
    StepHandler,
)
from .registry import (
    PluginRegistry,
    get_registry,
    register_plugin,
    register_handler,
)
from .loader import (
    load_plugins,
    load_plugin_from_file,
    discover_plugins,
)

__all__ = [
    "Plugin",
    "PluginContext",
    "PluginHook",
    "StepHandler",
    "PluginRegistry",
    "get_registry",
    "register_plugin",
    "register_handler",
    "load_plugins",
    "load_plugin_from_file",
    "discover_plugins",
]
