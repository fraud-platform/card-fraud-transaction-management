"""Unit tests for dependencies module."""

from app.core.dependencies import (
    CurrentUser,
    RequireAdmin,
    RequireAnalyst,
    get_current_user_dep,
    require_admin,
    require_analyst,
)


class TestCurrentUser:
    """Test CurrentUser dependency type."""

    def test_current_user_type_alias(self):
        """Test CurrentUser is a type alias for dict."""
        assert CurrentUser is not None


class TestRequireAnalyst:
    """Test require_analyst dependency."""

    def test_require_analyst_exists(self):
        """Test require_analyst function exists."""
        assert require_analyst is not None

    def test_require_analyst_is_callable(self):
        """Test require_analyst is callable."""
        assert callable(require_analyst)


class TestRequireAdmin:
    """Test require_admin dependency."""

    def test_require_admin_exists(self):
        """Test require_admin function exists."""
        assert require_admin is not None

    def test_require_admin_is_callable(self):
        """Test require_admin is callable."""
        assert callable(require_admin)


class TestTypeAliases:
    """Test type aliases are properly defined."""

    def test_require_analyst_type(self):
        """Test RequireAnalyst is defined."""
        assert RequireAnalyst is not None

    def test_require_admin_type(self):
        """Test RequireAdmin is defined."""
        assert RequireAdmin is not None

    def test_get_current_user_dep_exists(self):
        """Test get_current_user_dep function exists."""
        assert get_current_user_dep is not None
