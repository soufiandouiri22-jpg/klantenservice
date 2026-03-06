-- Downgrade database to pre-Telnyx schema (035_sms_confirmation)
-- Run this in Supabase SQL Editor (production database)
-- 
-- This removes Telnyx-related tables and columns added in migrations 036-041.
-- After running, also update alembic_version: UPDATE alembic_version SET version_num = '035_sms_confirmation';

-- 1. Drop orphaned_phone_numbers table (041)
DROP TABLE IF EXISTS orphaned_phone_numbers CASCADE;

-- 2. Remove ai_worker_id from crm_integrations (039)
ALTER TABLE crm_integrations DROP CONSTRAINT IF EXISTS fk_crm_integrations_ai_worker_id;
DROP INDEX IF EXISTS ix_crm_integrations_ai_worker_id;
ALTER TABLE crm_integrations DROP COLUMN IF EXISTS ai_worker_id;

-- 3. Reset call_recording_enabled default (038)
ALTER TABLE companies ALTER COLUMN call_recording_enabled SET DEFAULT false;

-- 4. Update alembic version
UPDATE alembic_version SET version_num = '035_sms_confirmation';

-- 5. Fix stuck workers (Erik)
UPDATE ai_workers SET status = 'available', current_call_id = NULL WHERE status = 'busy' OR current_call_id IS NOT NULL;
