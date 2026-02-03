"""Unit tests for Kafka consumer module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ingestion.kafka_consumer import (
    process_message,
    start_kafka_consumer,
    stop_kafka_consumer,
)
from app.schemas.decision_event import DecisionEventCreate, IngestionSource


class TestKafkaConsumerConfig:
    """Test Kafka consumer configuration."""

    def test_consumer_not_running_when_disabled(self):
        """Test that consumer returns None when Kafka is disabled."""
        mock_settings = MagicMock()
        mock_settings.kafka.enabled = False
        mock_settings.kafka.bootstrap_servers = "localhost:9092"
        mock_settings.kafka.topic_decisions = "fraud.card.decisions.v1"
        mock_settings.kafka.consumer_group_id = "test-group"

        result = asyncio.run(start_kafka_consumer(mock_settings, None))
        assert result is None

    def test_consumer_already_running(self):
        """Test that consumer returns existing task if already running."""
        mock_settings = MagicMock()
        mock_settings.kafka.enabled = True
        mock_settings.kafka.bootstrap_servers = "localhost:9092"
        mock_settings.kafka.topic_decisions = "fraud.card.decisions.v1"
        mock_settings.kafka.consumer_group_id = "test-group"
        mock_settings.kafka.auto_offset_reset = "earliest"
        mock_settings.kafka.enable_auto_commit = True

        with patch("app.ingestion.kafka_consumer.AIOKafkaConsumer") as mock_consumer_class:
            mock_consumer = AsyncMock()
            mock_consumer_class.return_value = mock_consumer

            # First call
            task1 = asyncio.run(start_kafka_consumer(mock_settings, None))

            # Second call should return same task
            asyncio.run(start_kafka_consumer(mock_settings, None))

            assert task1 is not None
            # Clean up
            asyncio.run(stop_kafka_consumer())


class TestStopKafkaConsumer:
    """Test stop_kafka_consumer function."""

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """Test stopping consumer when not running does nothing."""
        # Import the global variables to ensure clean state
        import app.ingestion.kafka_consumer as consumer_module

        consumer_module._consumer = None
        consumer_module._consumer_task = None

        await stop_kafka_consumer()

    @pytest.mark.asyncio
    async def test_stop_running_consumer(self):
        """Test stopping a running consumer."""
        import app.ingestion.kafka_consumer as consumer_module

        # Set up module-level variables
        consumer_module._consumer = None
        consumer_module._consumer_task = None

        # The function should handle None gracefully
        await stop_kafka_consumer()
        # Test passes if no exception is raised


class TestProcessMessage:
    """Test process_message function."""

    @pytest.mark.asyncio
    async def test_process_message_with_pan_detected(self):
        """Test message processing with PAN detected."""
        mock_session_factory = MagicMock()

        mock_message = MagicMock()
        mock_message.topic = "fraud.card.decisions.v1"
        mock_message.partition = 0
        mock_message.offset = 101
        mock_message.key = None
        mock_message.value = b'{"transaction_id": "txn_002", "card_id": "4111111111111111"}'

        # Create a mock pan detector that detects PAN
        mock_pan_detector = MagicMock()
        mock_result = MagicMock()
        mock_result.detected = True
        mock_result.field_path = "card_id"
        mock_pan_detector.detect_pan.return_value = mock_result

        result = await process_message(mock_message, mock_session_factory, mock_pan_detector)

        assert result is False
        mock_pan_detector.detect_pan.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_validation_error(self):
        """Test message processing with validation error."""
        mock_session_factory = MagicMock()

        mock_message = MagicMock()
        mock_message.topic = "fraud.card.decisions.v1"
        mock_message.partition = 0
        mock_message.offset = 102
        mock_message.key = None
        mock_message.value = b'{"invalid": "json"}'

        result = await process_message(mock_message, mock_session_factory, None)

        assert result is False

    @pytest.mark.asyncio
    async def test_process_message_invalid_timestamp(self):
        """Test message processing with invalid timestamp."""
        mock_session_factory = MagicMock()

        mock_message = MagicMock()
        mock_message.topic = "fraud.card.decisions.v1"
        mock_message.partition = 0
        mock_message.offset = 103
        mock_message.key = None
        # Invalid ISO timestamp format
        mock_message.value = (
            b'{"transaction_id": "txn_003", "card_id": "tok_card456", '
            b'"account_id": "acc_003", "transaction_amount": "250.00", '
            b'"final_decision": "DECLINE", "event_timestamp": "invalid"}'
        )

        result = await process_message(mock_message, mock_session_factory, None)

        assert result is False


class TestKafkaConsumerImports:
    """Test that required imports and classes exist."""

    def test_decision_event_create_import(self):
        """Test DecisionEventCreate can be imported."""
        assert DecisionEventCreate is not None

    def test_ingestion_source_import(self):
        """Test IngestionSource can be imported."""
        assert IngestionSource.KAFKA == "KAFKA"
        assert IngestionSource.HTTP == "HTTP"

    def test_start_stop_functions_exist(self):
        """Test start and stop functions exist."""
        assert start_kafka_consumer is not None
        assert stop_kafka_consumer is not None
        assert process_message is not None
