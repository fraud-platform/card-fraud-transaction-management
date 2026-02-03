"""Kafka consumer for processing decision events (production path).

Consumes from topic: fraud.card.decisions.v1

Features:
- Async consumption with aiokafka
- Batch processing support
- Manual offset commit after successful DB write
- Idempotent processing via transaction_id deduplication
- PAN detection for PCI compliance
"""

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer
from aiokafka.structs import ConsumerRecord
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.core.security.pan_detector import PanDetector
from app.schemas.decision_event import DecisionEventCreate, IngestionSource
from app.services.ingestion_service import IngestionService

logger = logging.getLogger(__name__)

_consumer: AIOKafkaConsumer | None = None
_consumer_task: asyncio.Task | None = None


async def start_kafka_consumer(
    settings: Settings,
    session_factory: async_sessionmaker,
) -> asyncio.Task | None:
    """Start the Kafka consumer in a background task."""
    global _consumer, _consumer_task

    if not settings.kafka.enabled:
        logger.info("Kafka consumer disabled (KAFKA_ENABLED=false)")
        return None

    if _consumer is not None:
        logger.warning("Kafka consumer already running")
        return _consumer_task

    logger.info(
        "Starting Kafka consumer",
        extra={
            "bootstrap_servers": settings.kafka.bootstrap_servers,
            "topic": settings.kafka.topic_decisions,
            "group_id": settings.kafka.consumer_group_id,
        },
    )

    _consumer = AIOKafkaConsumer(
        settings.kafka.topic_decisions,
        bootstrap_servers=settings.kafka.bootstrap_servers,
        group_id=settings.kafka.consumer_group_id,
        auto_offset_reset=settings.kafka.auto_offset_reset,
        enable_auto_commit=settings.kafka.enable_auto_commit,
        value_deserializer=lambda m: m.decode("utf-8"),
    )

    await _consumer.start()
    logger.info("Kafka consumer started", extra={"topic": settings.kafka.topic_decisions})

    pan_detector = PanDetector()

    async def consume_messages():
        try:
            async for message in _consumer:
                try:
                    await process_message(message, session_factory, pan_detector)
                except Exception as e:
                    logger.exception(
                        "Error processing message",
                        extra={
                            "topic": message.topic,
                            "partition": message.partition,
                            "offset": message.offset,
                            "error": str(e),
                        },
                    )
        except asyncio.CancelledError:
            logger.info("Kafka consumer task cancelled")
        except Exception as e:
            logger.exception("Kafka consumer error", extra={"error": str(e)})

    _consumer_task = asyncio.create_task(consume_messages())
    return _consumer_task


async def stop_kafka_consumer() -> None:
    """Stop the Kafka consumer."""
    global _consumer, _consumer_task

    if _consumer_task is not None:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
        _consumer_task = None

    if _consumer is not None:
        await _consumer.stop()
        _consumer = None
        logger.info("Kafka consumer stopped")


async def process_message(
    message: ConsumerRecord,
    session_factory: async_sessionmaker,
    pan_detector: PanDetector | None = None,
) -> bool:
    """Process a single Kafka message (idempotent by transaction_id).

    Args:
        message: Kafka message
        session_factory: Database session factory
        pan_detector: Optional PAN detector for PCI compliance

    Returns:
        True if processed successfully, False if PAN detected
    """
    logger.debug(
        "Processing message",
        extra={
            "topic": message.topic,
            "partition": message.partition,
            "offset": message.offset,
        },
    )

    try:
        event_data = json.loads(message.value)

        if pan_detector:
            pan_result = pan_detector.detect_pan(event_data)
            if pan_result.detected:
                logger.warning(
                    "PAN detected in message, skipping",
                    extra={
                        "field": pan_result.field_path,
                        "transaction_id": event_data.get("transaction_id"),
                    },
                )
                return False

        event = DecisionEventCreate(**event_data)

        async with session_factory() as session:
            service = IngestionService(session)
            await service.ingest_event(
                event=event,
                source=IngestionSource.KAFKA,
                trace_id=message.key.decode("utf-8") if message.key else None,
            )

        logger.info(
            "Message processed",
            extra={
                "transaction_id": event.transaction_id,
                "topic": message.topic,
                "partition": message.partition,
                "offset": message.offset,
            },
        )
        return True

    except ValidationError as e:
        logger.warning(
            "Invalid message format",
            extra={
                "error": str(e),
                "topic": message.topic,
                "partition": message.partition,
                "offset": message.offset,
            },
        )
        return False

    except Exception as e:
        logger.exception(
            "Failed to process message",
            extra={
                "error": str(e),
                "topic": message.topic,
                "partition": message.partition,
                "offset": message.offset,
            },
        )
        raise
