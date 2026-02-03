# Doppler Secrets Setup Guide

This guide covers setting up Doppler secrets for the card-fraud-transaction-management project.

## Overview

**Doppler** is our **primary secrets manager** for all environments:
- `local` - Local development (Docker PostgreSQL)
- `test` - CI/CD and integration testing (Neon test branch)
- `prod` - Production deployment (Neon prod branch)

**Never use `.env` files** - All secrets are managed through Doppler.

## Prerequisites

1. Install Doppler CLI:
   ```powershell
   winget install doppler.cli
   ```

2. Login to Doppler:
   ```powershell
   doppler login
   ```

3. Verify access:
   ```powershell
   doppler secrets --project=card-fraud-transaction-management --config=local
   ```

## Required Secrets

### Local Config (Docker PostgreSQL)

| Secret | Value | Purpose |
|--------|-------|---------|
| `DATABASE_URL_APP` | `postgresql://postgres:postgres@localhost:5432/fraud_gov` | App connection |
| `DATABASE_URL_ADMIN` | `postgresql://postgres:postgres@localhost:5432/fraud_gov` | Admin connection |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka connection |
| `AUTH0_DOMAIN` | `your-tenant.auth0.com` | Auth0 authentication |
| `AUTH0_AUDIENCE` | `https://api.fraud-management.com` | Auth0 audience |

### Test Config (Neon Test Branch)

| Secret | Value | Purpose |
|--------|-------|---------|
| `DATABASE_URL_APP` | `postgresql://fraud_gov_app_user:{FRAUD_GOV_APP_PASSWORD}@ep-test-xxx.us-east-1.aws.neon.tech/fraud_gov?sslmode=require` | App connection |
| `DATABASE_URL_ADMIN` | `postgresql://fraud_gov_admin:{FRAUD_GOV_ADMIN_PASSWORD}@ep-test-xxx.us-east-1.aws.neon.tech/fraud_gov?sslmode=require` | Admin connection |
| `FRAUD_GOV_APP_PASSWORD` | (generated) | App user password |
| `FRAUD_GOV_ADMIN_PASSWORD` | (generated) | Admin user password |
| `KAFKA_BOOTSTRAP_SERVERS` | `pkc-xxx.us-east-1.aws.confluent.cloud:9092` | Kafka (Confluent) |
| `AUTH0_DOMAIN` | `your-tenant.auth0.com` | Auth0 |
| `AUTH0_AUDIENCE` | `https://api.fraud-management.com` | Auth0 |

### Prod Config (Neon Main Branch)

| Secret | Value | Purpose |
|--------|-------|---------|
| `DATABASE_URL_APP` | `postgresql://fraud_gov_app_user:{FRAUD_GOV_APP_PASSWORD}@ep-prod-xxx.us-east-1.aws.neon.tech/fraud_gov?sslmode=require` | App connection |
| `DATABASE_URL_ADMIN` | `postgresql://fraud_gov_admin:{FRAUD_GOV_ADMIN_PASSWORD}@ep-prod-xxx.us-east-1.aws.neon.tech/fraud_gov?sslmode=require` | Admin connection |
| `FRAUD_GOV_APP_PASSWORD` | (generated) | App user password |
| `FRAUD_GOV_ADMIN_PASSWORD` | (generated) | Admin user password |
| `KAFKA_BOOTSTRAP_SERVERS` | `pkc-xxx.us-east-1.aws.confluent.cloud:9092` | Kafka (Confluent) |
| `AUTH0_DOMAIN` | `your-tenant.auth0.com` | Auth0 |
| `AUTH0_AUDIENCE` | `https://api.fraud-management.com` | Auth0 |

## Password Workflow

### Critical: Password Consistency

This project **shares the same database users** with `card-fraud-rule-management`. Therefore:

1. `FRAUD_GOV_APP_PASSWORD` must be **identical** in both projects' `test` config
2. `FRAUD_GOV_APP_PASSWORD` must be **identical** in both projects' `prod` config
3. `FRAUD_GOV_ADMIN_PASSWORD` must be **identical** in both projects' `test` config
4. `FRAUD_GOV_ADMIN_PASSWORD` must be **identical** in both projects' `prod` config

### Step 1: Get Passwords from card-fraud-rule-management

```powershell
# Get passwords from rule-management project
doppler secrets --project=card-fraud-rule-management --config=test get FRAUD_GOV_APP_PASSWORD
doppler secrets --project=card-fraud-rule-management --config=test get FRAUD_GOV_ADMIN_PASSWORD

doppler secrets --project=card-fraud-rule-management --config=prod get FRAUD_GOV_APP_PASSWORD
doppler secrets --project=card-fraud-rule-management --config=prod get FRAUD_GOV_ADMIN_PASSWORD
```

### Step 2: Set Passwords in This Project

```powershell
# Test config
doppler secrets set --project=card-fraud-transaction-management --config=test FRAUD_GOV_APP_PASSWORD "<value-from-step-1>"
doppler secrets set --project=card-fraud-transaction-management --config=test FRAUD_GOV_ADMIN_PASSWORD "<value-from-step-1>"

# Prod config
doppler secrets set --project=card-fraud-transaction-management --config=prod FRAUD_GOV_APP_PASSWORD "<value-from-step-1>"
doppler secrets set --project=card-fraud-transaction-management --config=prod FRAUD_GOV_ADMIN_PASSWORD "<value-from-step-1>"
```

## Quick Setup Commands

### Local Development

```powershell
# 1. Start local infrastructure
uv run infra-local-up

# 2. Initialize database (uses Doppler 'local' config)
uv run db-init --yes

# 3. Verify setup
uv run db-verify

# 4. Run tests
uv run doppler-local-test

# 5. Start dev server
uv run doppler-local
```

### Test Environment

```powershell
# 1. Sync passwords from rule-management
doppler secrets set --project=card-fraud-transaction-management --config=test FRAUD_GOV_APP_PASSWORD "<same-as-rule-management>"
doppler secrets set --project=card-fraud-transaction-management --config=test FRAUD_GOV_ADMIN_PASSWORD "<same-as-rule-management>"

# 2. Initialize database
uv run db-init-test --yes

# 3. Verify
uv run db-verify-test

# 4. Run tests
uv run doppler-test
```

### Production Environment

```powershell
# 1. Sync passwords (get from secure storage, must match rule-management)
doppler secrets set --project=card-fraud-transaction-management --config=prod FRAUD_GOV_APP_PASSWORD "<same-as-rule-management>"
doppler secrets set --project=card-fraud-transaction-management --config=prod FRAUD_GOV_ADMIN_PASSWORD "<same-as-rule-management>"

# 2. Initialize database
uv run db-init-prod --yes

# 3. Verify
uv run db-verify-prod

# 4. Run tests
uv run doppler-prod
```

## Database Users

This project shares users with `card-fraud-rule-management`:

| User | Purpose | Created By |
|------|---------|------------|
| `postgres` | Local development superuser | Docker |
| `fraud_gov_admin` | Admin operations (DDL, migrations) | card-fraud-rule-management setup |
| `fraud_gov_app_user` | Application operations (CRUD) | card-fraud-rule-management setup |

**Important:** The `fraud_gov_*` users are created by `card-fraud-rule-management`'s setup script. This project uses them.

## Verifying Doppler Configuration

### Check Local Config

```powershell
doppler secrets --project=card-fraud-transaction-management --config=local
```

Expected output:
```
DATABASE_URL_APP     = postgresql://postgres:postgres@localhost:5432/fraud_gov
DATABASE_URL_ADMIN   = postgresql://postgres:postgres@localhost:5432/fraud_gov
KAFKA_BOOTSTRAP_SERVERS = localhost:9092
AUTH0_DOMAIN         = your-tenant.auth0.com
AUTH0_AUDIENCE       = https://api.fraud-management.com
```

### Check Test Config

```powershell
doppler secrets --project=card-fraud-transaction-management --config=test
```

Expected output:
```
DATABASE_URL_APP     = postgresql://fraud_gov_app_user:***@ep-test-xxx.neon.tech/fraud_gov?sslmode=require
DATABASE_URL_ADMIN   = postgresql://fraud_gov_admin:***@ep-test-xxx.neon.tech/fraud_gov?sslmode=require
FRAUD_GOV_APP_PASSWORD = ********************
FRAUD_GOV_ADMIN_PASSWORD = ********************
KAFKA_BOOTSTRAP_SERVERS = pkc-xxx.us-east-1.aws.confluent.cloud:9092
AUTH0_DOMAIN         = your-tenant.auth0.com
AUTH0_AUDIENCE       = https://api.fraud-management.com
```

## Troubleshooting

### Issue: "DATABASE_URL_APP not set"

**Cause:** Doppler not configured or wrong config

**Fix:**
```powershell
doppler configure --project=card-fraud-transaction-management --config=local
```

### Issue: "connection refused" for PostgreSQL

**Cause:** Local PostgreSQL not running

**Fix:**
```powershell
uv run db-local-up
```

### Issue: Tests fail with authentication error

**Cause:** Password mismatch between projects

**Fix:** Verify passwords match in both projects:
```powershell
# Compare passwords
doppler secrets --project=card-fraud-rule-management --config=test get FRAUD_GOV_APP_PASSWORD
doppler secrets --project=card-fraud-transaction-management --config=test get FRAUD_GOV_APP_PASSWORD
```

### Issue: "schema 'fraud_gov' does not exist"

**Cause:** Schema not created

**Fix:**
```powershell
uv run db-init --yes
```

## Environment Variables Reference

When running commands with Doppler, these variables are injected:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL_APP` | Async connection string for SQLAlchemy |
| `DATABASE_URL_ADMIN` | Admin connection for DDL operations |
| `DOPPLER_CONFIG` | Current config name (local/test/prod) |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker addresses |
| `AUTH0_DOMAIN` | Auth0 tenant domain |
| `AUTH0_AUDIENCE` | Auth0 API identifier |

## Related Documentation

- [Database Setup](database-setup.md)
- [Kafka Setup](kafka-setup.md)
- [AGENTS.md](../../AGENTS.md) - Agent instructions
- [card-fraud-rule-management Doppler Guide](../../../card-fraud-rule-management/docs/01-setup/doppler-secrets-setup.md)
