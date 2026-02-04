# ADR-001: Use Async SQLAlchemy

**Status:** Accepted

**Date:** 2026-01-27

**Context:**

The Card Fraud Transaction Management service needs to handle high-volume ingestion of fraud decision events (potentially thousands per second) while maintaining responsiveness for API queries. The related card-fraud-rule-management service uses synchronous SQLAlchemy.

**Key Requirements:**
- High throughput ingestion via Kafka consumer
- Concurrent API request handling
- Non-blocking I/O for database operations
- Shared schema with card-fraud-rule-management (which uses sync SQLAlchemy)

**Decision:**

Use async SQLAlchemy with `asyncpg` driver for this project, while card-fraud-rule-management continues to use sync SQLAlchemy with `psycopg`.

Both projects share:
- Same `fraud_gov` schema in PostgreSQL
- Same `DATABASE_URL_APP` environment variable
- Same config pattern with automatic URL driver conversion

**Technical Implementation:**
```python
# This project (async)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text

engine = create_async_engine(settings.database.async_url)
async with AsyncSession(engine) as session:
    result = await session.execute(select(Transaction))

# Connection string format
postgresql+asyncpg://user:pass@host:5432/database
```

**Consequences:**

**Positive:**
- Higher throughput for concurrent operations (Kafka consumer + API)
- Non-blocking database calls allow efficient resource utilization
- Better suited for I/O-bound workloads (database queries)
- Scales better under high load

**Negative:**
- Different from card-fraud-rule-management (inconsistency in code patterns)
- Slightly more complex code (async/await required)
- All database operations must be async functions
- Test fixtures must use `async def` and `await`

**Trade-offs:**
- More verbose error handling (try/except with async context managers)
- Debugging can be more complex with async call stacks
- Some third-party libraries may not support async

**Alternatives Considered:**

1. **Sync SQLAlchemy (like rule-management)**
   - Rejected: Would block event loop during ingestion, limiting throughput

2. **NoSQL database (MongoDB, Cassandra)**
   - Rejected: PCI compliance requirements favor relational databases
   - Need for ACID transactions and complex joins

3. **Separate read/write databases**
   - Rejected: Added complexity without clear benefit at current scale

**Migration Path:**

If sync becomes preferred in future:
- Replace `create_async_engine()` with `create_engine()`
- Change `AsyncSession` to `Session`
- Remove `await` keywords from database calls
- Update test fixtures

**Related:**
- [AGENTS.md](../../AGENTS.md) - Async vs Sync section
- [docs/01-architecture.md](../02-development/architecture.md)
