"""Tests for the plugin marketplace UI."""

import pytest
from datetime import datetime

from test_ai.dashboard.plugin_marketplace import (
    CATEGORY_CONFIG,
    SAMPLE_PLUGINS,
    _init_marketplace_state,
    _get_filtered_plugins,
    _is_installed,
    _get_installed_version,
    _render_rating_stars,
)
from test_ai.plugins.models import PluginCategory


class TestCategoryConfig:
    """Test category configuration."""

    def test_all_categories_have_config(self):
        """All plugin categories should have config."""
        for category in PluginCategory:
            assert category in CATEGORY_CONFIG, f"Missing config for {category}"

    def test_config_has_required_fields(self):
        """Each config should have required fields."""
        for category, config in CATEGORY_CONFIG.items():
            assert "icon" in config, f"{category} missing icon"
            assert "color" in config, f"{category} missing color"
            assert "label" in config, f"{category} missing label"


class TestSamplePlugins:
    """Test sample plugin data."""

    def test_sample_plugins_exist(self):
        """Should have sample plugins for demonstration."""
        assert len(SAMPLE_PLUGINS) >= 5

    def test_sample_plugin_structure(self):
        """Each sample plugin should have required fields."""
        required_fields = [
            "id", "name", "display_name", "description", "author",
            "category", "tags", "downloads", "rating", "latest_version"
        ]
        for plugin in SAMPLE_PLUGINS:
            for field in required_fields:
                assert field in plugin, f"Plugin {plugin.get('name', '?')} missing {field}"

    def test_sample_plugins_have_valid_categories(self):
        """All sample plugins should have valid categories."""
        for plugin in SAMPLE_PLUGINS:
            assert isinstance(plugin["category"], PluginCategory)

    def test_sample_plugins_have_valid_ratings(self):
        """Ratings should be between 0 and 5."""
        for plugin in SAMPLE_PLUGINS:
            assert 0 <= plugin["rating"] <= 5


class TestMarketplaceState:
    """Test marketplace state management."""

    def test_init_marketplace_state(self, mock_session_state):
        """Should initialize all required state variables."""
        _init_marketplace_state()

        assert hasattr(mock_session_state, "marketplace_search")
        assert hasattr(mock_session_state, "marketplace_category")
        assert hasattr(mock_session_state, "marketplace_selected_plugin")
        assert hasattr(mock_session_state, "installed_plugins")

    def test_get_filtered_plugins_no_filter(self, mock_session_state):
        """Should return all plugins with no filter."""
        mock_session_state.marketplace_search = ""
        mock_session_state.marketplace_category = "all"

        filtered = _get_filtered_plugins()
        assert len(filtered) == len(SAMPLE_PLUGINS)

    def test_get_filtered_plugins_by_category(self, mock_session_state):
        """Should filter plugins by category."""
        mock_session_state.marketplace_search = ""
        mock_session_state.marketplace_category = "integration"

        filtered = _get_filtered_plugins()
        for plugin in filtered:
            assert plugin["category"].value == "integration"

    def test_get_filtered_plugins_by_search(self, mock_session_state):
        """Should filter plugins by search query."""
        mock_session_state.marketplace_search = "github"
        mock_session_state.marketplace_category = "all"

        filtered = _get_filtered_plugins()
        assert len(filtered) >= 1
        # At least one result should contain "github"
        assert any("github" in p["name"].lower() for p in filtered)


class TestInstallationHelpers:
    """Test installation helper functions."""

    def test_is_installed_true(self, mock_session_state):
        """Should return True for installed plugins."""
        mock_session_state.installed_plugins = {
            "test-plugin": {"version": "1.0.0"}
        }
        assert _is_installed("test-plugin") is True

    def test_is_installed_false(self, mock_session_state):
        """Should return False for non-installed plugins."""
        mock_session_state.installed_plugins = {}
        assert _is_installed("test-plugin") is False

    def test_get_installed_version(self, mock_session_state):
        """Should return installed version."""
        mock_session_state.installed_plugins = {
            "test-plugin": {"version": "2.1.0"}
        }
        assert _get_installed_version("test-plugin") == "2.1.0"

    def test_get_installed_version_not_installed(self, mock_session_state):
        """Should return None for non-installed plugins."""
        mock_session_state.installed_plugins = {}
        assert _get_installed_version("test-plugin") is None


class TestRatingStars:
    """Test rating stars rendering."""

    def test_render_rating_stars_full(self):
        """Should render full stars correctly."""
        result = _render_rating_stars(5.0)
        assert "★★★★★" in result
        assert "(5.0)" in result

    def test_render_rating_stars_partial(self):
        """Should handle partial ratings."""
        result = _render_rating_stars(4.5)
        assert "★★★★" in result
        assert "½" in result
        assert "(4.5)" in result

    def test_render_rating_stars_zero(self):
        """Should handle zero rating."""
        result = _render_rating_stars(0.0)
        assert "☆☆☆☆☆" in result
        assert "(0.0)" in result


@pytest.fixture
def mock_session_state(monkeypatch):
    """Mock Streamlit session state."""

    class MockSessionState:
        def __init__(self):
            self.marketplace_search = ""
            self.marketplace_category = "all"
            self.marketplace_selected_plugin = None
            self.installed_plugins = {}

        def __contains__(self, key):
            return hasattr(self, key)

    mock_state = MockSessionState()

    import streamlit as st
    monkeypatch.setattr(st, "session_state", mock_state)

    return mock_state
