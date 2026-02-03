"""Unit tests for logging configuration."""

from unittest.mock import MagicMock


class TestLoggingSetup:
    """Test logging setup functions."""

    def test_get_logger_returns_structlog_logger(self):
        """Test get_logger returns a structured logger."""
        from app.core.logging import get_logger

        logger = get_logger("test_module")
        assert logger is not None

    def test_get_logger_with_different_names(self):
        """Test get_logger works with different module names."""
        from app.core.logging import get_logger

        logger1 = get_logger("module_a")
        logger2 = get_logger("module_b")

        assert logger1 is not None
        assert logger2 is not None
        assert logger1 != logger2

    def test_setup_logging_with_json_format(self):
        """Test setup_logging with JSON format."""
        from app.core.logging import setup_logging

        mock_settings = MagicMock()
        mock_settings.app.log_level = "INFO"
        mock_settings.observability.log_record_format = "json"

        setup_logging(mock_settings)

    def test_setup_logging_with_console_format(self):
        """Test setup_logging with console format."""
        from app.core.logging import setup_logging

        mock_settings = MagicMock()
        mock_settings.app.log_level = "DEBUG"
        mock_settings.observability.log_record_format = "console"

        setup_logging(mock_settings)

    def test_setup_logging_with_different_log_levels(self):
        """Test setup_logging with different log levels."""
        from app.core.logging import setup_logging

        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            mock_settings = MagicMock()
            mock_settings.app.log_level = level
            mock_settings.observability.log_record_format = "console"

            setup_logging(mock_settings)

    def test_logger_mixin_exists(self):
        """Test LoggerMixin class exists."""
        from app.core.logging import LoggerMixin

        assert LoggerMixin is not None

    def test_logger_mixin_provides_logger_property(self):
        """Test LoggerMixin provides logger property."""
        from app.core.logging import LoggerMixin

        class TestClass(LoggerMixin):
            pass

        obj = TestClass()
        assert obj.logger is not None

    def test_logger_mixin_returns_logger(self):
        """Test LoggerMixin.logger returns a logger."""
        from app.core.logging import LoggerMixin

        class TestClass(LoggerMixin):
            pass

        obj = TestClass()
        logger = obj.logger
        assert logger is not None

    def test_logger_setup_works(self):
        """Test logger setup works without errors."""
        from app.core.logging import get_logger, setup_logging

        mock_settings = MagicMock()
        mock_settings.app.log_level = "ERROR"
        mock_settings.observability.log_record_format = "json"

        setup_logging(mock_settings)

        logger = get_logger("test_logging")
        assert logger is not None
