"""Plugin discovery and loading."""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Type

from .base import Plugin
from .registry import PluginRegistry, get_registry

logger = logging.getLogger(__name__)


def load_plugin_from_file(
    filepath: str | Path,
    registry: PluginRegistry | None = None,
    config: dict | None = None,
) -> Plugin | None:
    """Load a plugin from a Python file.

    The file must define a class that inherits from Plugin.

    Args:
        filepath: Path to Python file
        registry: Registry to register with (default: global)
        config: Plugin configuration

    Returns:
        Loaded Plugin instance or None on failure
    """
    filepath = Path(filepath)
    if not filepath.exists():
        logger.error(f"Plugin file not found: {filepath}")
        return None

    if not filepath.suffix == ".py":
        logger.error(f"Plugin must be a .py file: {filepath}")
        return None

    registry = registry or get_registry()
    module_name = f"gorgon_plugin_{filepath.stem}"

    try:
        # Load module from file
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if not spec or not spec.loader:
            logger.error(f"Cannot load module spec from: {filepath}")
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Find Plugin subclass
        plugin_class: Type[Plugin] | None = None
        for name in dir(module):
            obj = getattr(module, name)
            if (
                isinstance(obj, type)
                and issubclass(obj, Plugin)
                and obj is not Plugin
            ):
                plugin_class = obj
                break

        if not plugin_class:
            logger.error(f"No Plugin class found in: {filepath}")
            return None

        # Instantiate and register
        plugin = plugin_class()
        registry.register(plugin, config)

        logger.info(f"Loaded plugin from file: {filepath} -> {plugin.name}")
        return plugin

    except Exception as e:
        logger.error(f"Failed to load plugin from {filepath}: {e}")
        return None


def load_plugin_from_module(
    module_name: str,
    registry: PluginRegistry | None = None,
    config: dict | None = None,
) -> Plugin | None:
    """Load a plugin from an installed Python module.

    The module must define a class that inherits from Plugin.

    Args:
        module_name: Full module path (e.g., 'gorgon_plugins.my_plugin')
        registry: Registry to register with (default: global)
        config: Plugin configuration

    Returns:
        Loaded Plugin instance or None on failure
    """
    registry = registry or get_registry()

    try:
        module = importlib.import_module(module_name)

        # Find Plugin subclass
        plugin_class: Type[Plugin] | None = None
        for name in dir(module):
            obj = getattr(module, name)
            if (
                isinstance(obj, type)
                and issubclass(obj, Plugin)
                and obj is not Plugin
            ):
                plugin_class = obj
                break

        if not plugin_class:
            logger.error(f"No Plugin class found in module: {module_name}")
            return None

        plugin = plugin_class()
        registry.register(plugin, config)

        logger.info(f"Loaded plugin from module: {module_name} -> {plugin.name}")
        return plugin

    except ImportError as e:
        logger.error(f"Failed to import module {module_name}: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to load plugin from {module_name}: {e}")
        return None


def discover_plugins(
    directory: str | Path,
    registry: PluginRegistry | None = None,
    config: dict | None = None,
) -> list[Plugin]:
    """Discover and load plugins from a directory.

    Scans for .py files and attempts to load plugins from each.

    Args:
        directory: Directory to scan
        registry: Registry to register with (default: global)
        config: Shared plugin configuration

    Returns:
        List of successfully loaded plugins
    """
    directory = Path(directory)
    if not directory.exists():
        logger.warning(f"Plugin directory not found: {directory}")
        return []

    if not directory.is_dir():
        logger.error(f"Not a directory: {directory}")
        return []

    plugins = []
    for filepath in directory.glob("*.py"):
        # Skip private files
        if filepath.name.startswith("_"):
            continue

        plugin = load_plugin_from_file(filepath, registry, config)
        if plugin:
            plugins.append(plugin)

    logger.info(f"Discovered {len(plugins)} plugins in {directory}")
    return plugins


def load_plugins(
    sources: list[str | Path | dict],
    registry: PluginRegistry | None = None,
) -> list[Plugin]:
    """Load plugins from multiple sources.

    Args:
        sources: List of plugin sources:
            - str/Path: File path or module name
            - dict: {"path": "...", "config": {...}} or {"module": "...", "config": {...}}
        registry: Registry to register with (default: global)

    Returns:
        List of successfully loaded plugins
    """
    registry = registry or get_registry()
    plugins = []

    for source in sources:
        if isinstance(source, dict):
            config = source.get("config")
            if "path" in source:
                plugin = load_plugin_from_file(source["path"], registry, config)
            elif "module" in source:
                plugin = load_plugin_from_module(source["module"], registry, config)
            elif "directory" in source:
                plugins.extend(discover_plugins(source["directory"], registry, config))
                continue
            else:
                logger.warning(f"Invalid plugin source dict: {source}")
                continue
        elif isinstance(source, Path) or (isinstance(source, str) and "/" in source):
            path = Path(source)
            if path.is_dir():
                plugins.extend(discover_plugins(path, registry))
                continue
            else:
                plugin = load_plugin_from_file(path, registry)
        else:
            # Assume module name
            plugin = load_plugin_from_module(str(source), registry)

        if plugin:
            plugins.append(plugin)

    return plugins
