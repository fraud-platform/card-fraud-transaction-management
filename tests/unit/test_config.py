"""Unit tests for configuration module."""

from unittest.mock import patch

from app.core.config import (
    AppConfig,
    DatabaseConfig,
    KafkaConfig,
    Settings,
    get_settings,
)


class TestConfig:
    """Tests for configuration classes."""

    def test_app_config_defaults(self):
        """Test AppConfig has correct defaults."""
        config = AppConfig()
        assert config.name == "fraud-transaction-management"
        assert config.env.value == "local"
        assert config.version == "0.1.0"
        assert config.debug is False
        assert config.api_prefix == "/v1"

    def test_database_config_defaults(self):
        """Test DatabaseConfig has correct defaults."""
        config = DatabaseConfig()
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.name == "fraud_tm"
        assert config.user == "postgres"
        assert config.pool_size == 10
        assert config.require_ssl is True

    def test_database_url_property(self):
        """Test DatabaseConfig builds correct async URL."""
        from pydantic import SecretStr

        config = DatabaseConfig(
            url_app="",  # Override environment to test URL building
            host="localhost",
            port=5432,
            name="testdb",
            user="testuser",
            password=SecretStr("testpass"),
        )
        url = config.async_url
        assert "postgresql+asyncpg://testuser:testpass@localhost:5432/testdb" == url

    def test_kafka_config_defaults(self):
        """Test KafkaConfig has correct defaults."""
        config = KafkaConfig()
        assert config.enabled is False
        assert config.bootstrap_servers == ""
        assert config.topic_decisions == "fraud.card.decisions.v1"

    def test_kafka_config_enabled(self):
        """Test KafkaConfig when enabled."""
        config = KafkaConfig(
            enabled=True,
            bootstrap_servers="localhost:9092",
            consumer_group_id="test-group",
        )
        assert config.enabled is True
        assert config.bootstrap_servers == "localhost:9092"
        assert config.consumer_group_id == "test-group"

    def test_get_settings_cached(self):
        """Test that get_settings returns cached instance."""
        with patch.dict("os.environ", {"APP_ENV": "local"}):
            settings1 = get_settings()
            settings2 = get_settings()
            assert settings1 is settings2

    def test_settings_has_all_configs(self):
        """Test Settings has all required config objects."""
        settings = Settings()
        assert hasattr(settings, "app")
        assert hasattr(settings, "server")
        assert hasattr(settings, "database")
        assert hasattr(settings, "kafka")
        assert hasattr(settings, "s3")
        assert hasattr(settings, "auth0")
        assert hasattr(settings, "observability")
        assert hasattr(settings, "features")
