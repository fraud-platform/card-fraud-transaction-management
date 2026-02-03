-- Demo seed data for card-fraud-transaction-management
-- Run after schema initialization
-- Note: IDs are hardcoded UUIDs (UUIDv7 not available in PostgreSQL)
-- In production, application generates UUIDv7
--
-- ============================================================================
-- TRANSACTIONS (5 demo records covering various scenarios)
-- ============================================================================

BEGIN;

TRUNCATE TABLE fraud_gov.case_activity_log CASCADE;
TRUNCATE TABLE fraud_gov.transaction_reviews CASCADE;
TRUNCATE TABLE fraud_gov.analyst_notes CASCADE;
TRUNCATE TABLE fraud_gov.transaction_cases CASCADE;
TRUNCATE TABLE fraud_gov.transaction_rule_matches CASCADE;
TRUNCATE TABLE fraud_gov.transactions CASCADE;

-- Transaction 1: Decline due to rule match (high value electronics)
INSERT INTO fraud_gov.transactions (
    transaction_id, card_id, card_last4, card_network,
    transaction_amount, transaction_currency, merchant_id, merchant_category_code,
    decision, decision_reason, decision_score,
    ruleset_id, ruleset_version,
    transaction_timestamp, trace_id,
    raw_payload, ingestion_source,
    kafka_topic, kafka_partition, kafka_offset, source_message_id
) VALUES (
    'a1eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    'tok_visa_42424242', '4242', 'VISA',
    299.99, 'USD', 'merch_electronics_001', '5732',
    'DECLINE', 'RULE_MATCH', 85.5,
    'b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a01', 5,
    NOW() - INTERVAL '1 hour', 'trace_001',
    '{"transaction_id": "a1eebc99-9c0b-4ef8-bb6d-6bb9bd380a11", "amount": 299.99, "merchant": "electronics"}'::jsonb,
    'HTTP',
    NULL, NULL, NULL, NULL
);

-- Transaction 2: Approved transaction (grocery, small amount)
INSERT INTO fraud_gov.transactions (
    transaction_id, card_id, card_last4, card_network,
    transaction_amount, transaction_currency, merchant_id, merchant_category_code,
    decision, decision_reason, decision_score,
    ruleset_id, ruleset_version,
    transaction_timestamp, trace_id,
    raw_payload, ingestion_source,
    kafka_topic, kafka_partition, kafka_offset, source_message_id
) VALUES (
    'a2eebc99-9c0b-4ef8-bb6d-6bb9bd380a22',
    'tok_mc_12345678', '5678', 'MASTERCARD',
    49.50, 'USD', 'merch_grocery_001', '5411',
    'APPROVE', 'DEFAULT_ALLOW', 15.0,
    'b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a01', 5,
    NOW() - INTERVAL '2 hours', 'trace_002',
    '{"transaction_id": "a2eebc99-9c0b-4ef8-bb6d-6bb9bd380a22", "amount": 49.50, "merchant": "grocery"}'::jsonb,
    'KAFKA',
    'fraud.card.decisions.v1', 0, 1001, 'msg-002-001'
);

-- Transaction 3: Decline due to velocity (multiple transactions in short time)
INSERT INTO fraud_gov.transactions (
    transaction_id, card_id, card_last4, card_network,
    transaction_amount, transaction_currency, merchant_id, merchant_category_code,
    decision, decision_reason, decision_score,
    ruleset_id, ruleset_version,
    transaction_timestamp, trace_id,
    raw_payload, ingestion_source,
    kafka_topic, kafka_partition, kafka_offset, source_message_id
) VALUES (
    'a3eebc99-9c0b-4ef8-bb6d-6bb9bd380a33',
    'tok_amex_99998888', '8888', 'AMEX',
    1500.00, 'USD', 'merch_jewelry_001', '5944',
    'DECLINE', 'VELOCITY_MATCH', 92.0,
    'b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a01', 5,
    NOW() - INTERVAL '30 minutes', 'trace_003',
    '{"transaction_id": "a3eebc99-9c0b-4ef8-bb6d-6bb9bd380a33", "amount": 1500.00, "merchant": "jewelry"}'::jsonb,
    'HTTP',
    NULL, NULL, NULL, NULL
);

-- Transaction 4: Post-auth manual review (travel, international)
INSERT INTO fraud_gov.transactions (
    transaction_id, card_id, card_last4, card_network,
    transaction_amount, transaction_currency, merchant_id, merchant_category_code,
    decision, decision_reason, decision_score,
    ruleset_id, ruleset_version,
    transaction_timestamp, trace_id,
    raw_payload, ingestion_source,
    kafka_topic, kafka_partition, kafka_offset, source_message_id
) VALUES (
    'a4eebc99-9c0b-4ef8-bb6d-6bb9bd380a44',
    'tok_visa_11112222', '2222', 'VISA',
    89.99, 'USD', 'merch_travel_001', '4511',
    'MONITORING', 'MANUAL_REVIEW', 45.0,
    'b2eebc99-9c0b-4ef8-bb6d-6bb9bd380a02', 1,
    NOW() - INTERVAL '45 minutes', 'trace_004',
    '{"transaction_id": "a4eebc99-9c0b-4ef8-bb6d-6bb9bd380a44", "amount": 89.99, "merchant": "travel"}'::jsonb,
    'KAFKA',
    'fraud.card.decisions.v1', 1, 502, 'msg-004-001'
);

-- Transaction 5: High-value decline (luxury goods)
INSERT INTO fraud_gov.transactions (
    transaction_id, card_id, card_last4, card_network,
    transaction_amount, transaction_currency, merchant_id, merchant_category_code,
    decision, decision_reason, decision_score,
    ruleset_id, ruleset_version,
    transaction_timestamp, trace_id,
    raw_payload, ingestion_source,
    kafka_topic, kafka_partition, kafka_offset, source_message_id
) VALUES (
    'a5eebc99-9c0b-4ef8-bb6d-6bb9bd380a55',
    'tok_discover_77776666', '6666', 'DISCOVER',
    5000.00, 'USD', 'merch_luxury_001', '5094',
    'DECLINE', 'RULE_MATCH', 95.0,
    'b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a01', 5,
    NOW() - INTERVAL '15 minutes', 'trace_005',
    '{"transaction_id": "a5eebc99-9c0b-4ef8-bb6d-6bb9bd380a55", "amount": 5000.00, "merchant": "luxury"}'::jsonb,
    'HTTP',
    NULL, NULL, NULL, NULL
);

COMMIT;

-- ============================================================================
-- RULE MATCHES (6 demo records)
-- ============================================================================

BEGIN;

-- Rule matches for txn_demo_001 (2 rules, one contributed)
INSERT INTO fraud_gov.transaction_rule_matches (
    transaction_id, rule_id, rule_version, rule_name,
    matched, contributing, rule_output, match_score, match_reason, evaluated_at
) VALUES
(
    'a1eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'c1eebc99-9c0b-4ef8-bb6d-6bb9bd380c01', 5,
    'High Value Transaction',
    TRUE, TRUE, '{"action": "decline"}'::jsonb, 85.5, 'Amount exceeds threshold',
    NOW() - INTERVAL '1 hour' + INTERVAL '100 milliseconds'
),
(
    'a1eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'c2eebc99-9c0b-4ef8-bb6d-6bb9bd380c02', 3,
    'Foreign Transaction',
    TRUE, FALSE, '{"action": "flag"}'::jsonb, 30.0, 'Foreign transaction detected',
    NOW() - INTERVAL '1 hour' + INTERVAL '150 milliseconds'
);

-- Rule match for txn_demo_003 (velocity check)
INSERT INTO fraud_gov.transaction_rule_matches (
    transaction_id, rule_id, rule_version, rule_name,
    matched, contributing, rule_output, match_score, match_reason, evaluated_at
) VALUES (
    'a3eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'c3eebc99-9c0b-4ef8-bb6d-6bb9bd380c03', 2,
    'Velocity Check',
    TRUE, TRUE, '{"action": "decline"}'::jsonb, 92.0, 'Too many transactions in time window',
    NOW() - INTERVAL '30 minutes' + INTERVAL '50 milliseconds'
);

-- Rule match for txn_demo_005 (luxury merchant)
INSERT INTO fraud_gov.transaction_rule_matches (
    transaction_id, rule_id, rule_version, rule_name,
    matched, contributing, rule_output, match_score, match_reason, evaluated_at
) VALUES (
    'a5eebc99-9c0b-4ef8-bb6d-6bb9bd380a55', 'c4eebc99-9c0b-4ef8-bb6d-6bb9bd380c04', 1,
    'Luxury Merchant',
    TRUE, TRUE, '{"action": "decline"}'::jsonb, 95.0, 'High-value luxury purchase',
    NOW() - INTERVAL '15 minutes' + INTERVAL '25 milliseconds'
);

COMMIT;

-- ============================================================================
-- TRANSACTION REVIEWS (demo records for workflow)
-- ============================================================================

BEGIN;

-- Create reviews for each transaction
INSERT INTO fraud_gov.transaction_reviews (
    id, transaction_id, status, priority, assigned_analyst_id,
    first_reviewed_at, last_activity_at, created_at, updated_at
) VALUES
('r1eebc99-9c0b-4ef8-bb6d-6bb9bd380a01', 'a1eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'PENDING', 2, NULL,
 NOW() - INTERVAL '30 minutes', NOW() - INTERVAL '30 minutes', NOW() - INTERVAL '1 hour', NOW()),
('r2eebc99-9c0b-4ef8-bb6d-6bb9bd380a02', 'a2eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'RESOLVED', 4, 'analyst_001',
 NOW() - INTERVAL '45 minutes', NOW() - INTERVAL '45 minutes', NOW() - INTERVAL '2 hours', NOW()),
('r3eebc99-9c0b-4ef8-bb6d-6bb9bd380a03', 'a3eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'IN_REVIEW', 1, 'analyst_001',
 NOW() - INTERVAL '10 minutes', NOW() - INTERVAL '5 minutes', NOW() - INTERVAL '30 minutes', NOW()),
('r4eebc99-9c0b-4ef8-bb6d-6bb9bd380a04', 'a4eebc99-9c0b-4ef8-bb6d-6bb9bd380a44', 'ESCALATED', 2, NULL,
 NOW() - INTERVAL '20 minutes', NOW() - INTERVAL '20 minutes', NOW() - INTERVAL '45 minutes', NOW()),
('r5eebc99-9c0b-4ef8-bb6d-6bb9bd380a05', 'a5eebc99-9c0b-4ef8-bb6d-6bb9bd380a55', 'PENDING', 1, NULL,
 NOW() - INTERVAL '5 minutes', NOW() - INTERVAL '5 minutes', NOW() - INTERVAL '15 minutes', NOW());

COMMIT;

-- ============================================================================
-- ANALYST NOTES (demo records)
-- ============================================================================

BEGIN;

INSERT INTO fraud_gov.analyst_notes (
    id, transaction_id, note_type, note_content,
    analyst_id, analyst_name, analyst_email,
    is_private, is_system_generated, created_at, updated_at
) VALUES
('n1eebc99-9c0b-4ef8-bb6d-6bb9bd380a01', 'a1eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'INITIAL_REVIEW',
 'High value electronics transaction, needs manual review.',
 'analyst_001', 'John Analyst', 'john.analyst@example.com',
 FALSE, FALSE, NOW() - INTERVAL '30 minutes', NOW()),

('n2eebc99-9c0b-4ef8-bb6d-6bb9bd380a02', 'a2eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'RESOLUTION',
 'Low risk grocery purchase, approved as legitimate.',
 'analyst_001', 'John Analyst', 'john.analyst@example.com',
 FALSE, FALSE, NOW() - INTERVAL '45 minutes', NOW()),

('n3eebc99-9c0b-4ef8-bb6d-6bb9bd380a03', 'a3eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'CUSTOMER_CONTACT',
 'Contacted customer, confirmed card not lost. Pattern suggests legitimate travel.',
 'analyst_001', 'John Analyst', 'john.analyst@example.com',
 FALSE, FALSE, NOW() - INTERVAL '10 minutes', NOW());

COMMIT;

-- ============================================================================
-- TRANSACTION CASES (demo records)
-- ============================================================================

BEGIN;

-- Create a case for the velocity transactions
INSERT INTO fraud_gov.transaction_cases (
    id, case_number, case_type, case_status, assigned_analyst_id,
    title, description, total_transaction_count, total_transaction_amount, risk_level,
    created_at, updated_at
) VALUES (
    'c1eebc99-9c0b-4ef8-bb6d-6bb9bd380c01', 'FC-20260125-001000', 'INVESTIGATION', 'IN_PROGRESS', 'analyst_001',
    'Suspicious velocity pattern - multiple high-value transactions',
    'Multiple transactions from same card in short timeframe, including luxury merchant.',
    0, 0, 'HIGH',
    NOW(), NOW()
);

-- Link transaction 3 to the case
UPDATE fraud_gov.transaction_reviews
SET case_id = 'c1eebc99-9c0b-4ef8-bb6d-6bb9bd380c01'
WHERE transaction_id = 'a3eebc99-9c0b-4ef8-bb6d-6bb9bd380a33';

COMMIT;

-- ============================================================================
-- CASE ACTIVITY LOG (demo records)
-- ============================================================================

BEGIN;

INSERT INTO fraud_gov.case_activity_log (
    case_id, activity_type, activity_description,
    analyst_id, analyst_name, created_at
) VALUES
('c1eebc99-9c0b-4ef8-bb6d-6bb9bd380c01', 'CASE_CREATED', 'Case created for velocity investigation',
 'analyst_001', 'John Analyst', NOW() - INTERVAL '25 minutes'),

('c1eebc99-9c0b-4ef8-bb6d-6bb9bd380c01', 'TRANSACTION_ADDED', 'Transaction added to case',
 'analyst_001', 'John Analyst', NOW() - INTERVAL '20 minutes');

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT 'Transactions inserted: ' || COUNT(*)::text AS status
FROM fraud_gov.transactions
WHERE transaction_id::text LIKE 'a1eebc99%';

SELECT 'Rule matches inserted: ' || COUNT(*)::text AS status
FROM fraud_gov.transaction_rule_matches;

SELECT 'Reviews inserted: ' || COUNT(*)::text AS status
FROM fraud_gov.transaction_reviews;

SELECT 'Notes inserted: ' || COUNT(*)::text AS status
FROM fraud_gov.analyst_notes;

SELECT 'Cases inserted: ' || COUNT(*)::text AS status
FROM fraud_gov.transaction_cases;

SELECT 'Activity log entries: ' || COUNT(*)::text AS status
FROM fraud_gov.case_activity_log;

SELECT transaction_id, decision, decision_reason, transaction_amount
FROM fraud_gov.transactions
ORDER BY transaction_timestamp DESC
LIMIT 5;
