"""Create all missing tables

Revision ID: 003_create_all
Revises: 002_add_invite
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON


# revision identifiers
revision = '003_create_all'
down_revision = '002_add_invite'
branch_labels = None
depends_on = None


def upgrade():
    # Create ENUM types first
    aiworkerstatus = sa.Enum('available', 'busy', 'offline', 'maintenance', name='aiworkerstatus', create_type=False)
    addressform = sa.Enum('u', 'jij', name='addressform', create_type=False)
    calendarprovider = sa.Enum('google', 'microsoft', 'caldav', name='calendarprovider', create_type=False)
    indexstatus = sa.Enum('pending', 'indexing', 'completed', 'failed', 'outdated', name='indexstatus', create_type=False)
    callstatus = sa.Enum('ringing', 'in_progress', 'completed', 'missed', 'voicemail', 'failed', 'abandoned', name='callstatus', create_type=False)
    calloutcome = sa.Enum('appointment_made', 'appointment_cancelled', 'appointment_rescheduled', 'info_provided', 'note_left', 'callback_requested', 'transferred', 'voicemail_left', 'no_action', name='calloutcome', create_type=False)
    appointmentstatus = sa.Enum('held', 'confirmed', 'cancelled', 'completed', 'no_show', name='appointmentstatus', create_type=False)
    notepriority = sa.Enum('low', 'normal', 'high', 'urgent', name='notepriority', create_type=False)
    
    # Create enums
    op.execute("DO $$ BEGIN CREATE TYPE aiworkerstatus AS ENUM ('available', 'busy', 'offline', 'maintenance'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE addressform AS ENUM ('u', 'jij'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE calendarprovider AS ENUM ('google', 'microsoft', 'caldav'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE indexstatus AS ENUM ('pending', 'indexing', 'completed', 'failed', 'outdated'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE callstatus AS ENUM ('ringing', 'in_progress', 'completed', 'missed', 'voicemail', 'failed', 'abandoned'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE calloutcome AS ENUM ('appointment_made', 'appointment_cancelled', 'appointment_rescheduled', 'info_provided', 'note_left', 'callback_requested', 'transferred', 'voicemail_left', 'no_action'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE appointmentstatus AS ENUM ('held', 'confirmed', 'cancelled', 'completed', 'no_show'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE notepriority AS ENUM ('low', 'normal', 'high', 'urgent'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    
    # Create ai_workers table
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_workers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID NOT NULL REFERENCES companies(id),
            name VARCHAR(100) NOT NULL,
            role_title VARCHAR(100) DEFAULT 'Klantenservice medewerker',
            avatar_url VARCHAR(500),
            voice_id VARCHAR(100),
            language VARCHAR(10) DEFAULT 'nl-NL',
            address_form addressform DEFAULT 'u',
            tone_of_voice TEXT,
            behavior_settings JSONB DEFAULT '{"apologize_on_complaints": true, "always_offer_alternatives": true, "never_guess": true, "confirm_appointments": true, "summarize_at_end": true}',
            can_make_appointments BOOLEAN DEFAULT true,
            can_cancel_appointments BOOLEAN DEFAULT false,
            can_view_prices BOOLEAN DEFAULT true,
            can_leave_notes BOOLEAN DEFAULT true,
            status aiworkerstatus DEFAULT 'available',
            current_call_id UUID,
            total_calls_handled INTEGER DEFAULT 0,
            total_appointments_made INTEGER DEFAULT 0,
            average_call_duration_seconds INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_call_at TIMESTAMP,
            is_active BOOLEAN DEFAULT true
        )
    """)
    
    # Create phone_numbers table
    op.execute("""
        CREATE TABLE IF NOT EXISTS phone_numbers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID NOT NULL REFERENCES companies(id),
            number VARCHAR(20) UNIQUE NOT NULL,
            friendly_name VARCHAR(100),
            twilio_sid VARCHAR(50),
            business_hours JSONB DEFAULT '{"monday": {"open": "09:00", "close": "17:00", "enabled": true}, "tuesday": {"open": "09:00", "close": "17:00", "enabled": true}, "wednesday": {"open": "09:00", "close": "17:00", "enabled": true}, "thursday": {"open": "09:00", "close": "17:00", "enabled": true}, "friday": {"open": "09:00", "close": "17:00", "enabled": true}, "saturday": {"open": "10:00", "close": "14:00", "enabled": false}, "sunday": {"open": "00:00", "close": "00:00", "enabled": false}}',
            queue_enabled BOOLEAN DEFAULT true,
            max_queue_size INTEGER DEFAULT 5,
            max_wait_time_seconds INTEGER DEFAULT 300,
            voicemail_enabled BOOLEAN DEFAULT true,
            voicemail_greeting VARCHAR(500),
            voicemail_email VARCHAR(255),
            after_hours_message VARCHAR(500) DEFAULT 'Wij zijn momenteel gesloten. Onze openingstijden zijn maandag tot en met vrijdag van 9:00 tot 17:00 uur.',
            after_hours_voicemail BOOLEAN DEFAULT true,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create calendar_integrations table
    op.execute("""
        CREATE TABLE IF NOT EXISTS calendar_integrations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID NOT NULL REFERENCES companies(id),
            name VARCHAR(100) NOT NULL,
            provider calendarprovider NOT NULL,
            access_token_encrypted TEXT,
            refresh_token_encrypted TEXT,
            token_expires_at TIMESTAMP,
            caldav_url VARCHAR(500),
            caldav_username VARCHAR(255),
            caldav_password_encrypted TEXT,
            external_calendar_id VARCHAR(255),
            external_calendar_name VARCHAR(255),
            availability_rules JSONB DEFAULT '{"default_appointment_duration_minutes": 30, "buffer_before_minutes": 0, "buffer_after_minutes": 15, "min_notice_hours": 1, "max_advance_days": 60}',
            appointment_types JSONB DEFAULT '[{"id": "consultation", "name": "Consult", "duration_minutes": 30}, {"id": "meeting", "name": "Afspraak", "duration_minutes": 60}]',
            last_sync_at TIMESTAMP,
            sync_error TEXT,
            is_active BOOLEAN DEFAULT true,
            is_primary BOOLEAN DEFAULT false,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create website_knowledge table
    op.execute("""
        CREATE TABLE IF NOT EXISTS website_knowledge (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID NOT NULL REFERENCES companies(id),
            base_url VARCHAR(500) NOT NULL,
            sitemap_url VARCHAR(500),
            crawl_settings JSONB DEFAULT '{"max_pages": 100, "max_depth": 3, "respect_robots_txt": true, "follow_external_links": false, "allowed_paths": [], "blocked_paths": ["/admin", "/login", "/wp-admin"], "user_agent": "klantenservice-ai-bot/1.0"}',
            status indexstatus DEFAULT 'pending',
            pages_indexed INTEGER DEFAULT 0,
            chunks_created INTEGER DEFAULT 0,
            last_error TEXT,
            failed_urls JSONB DEFAULT '[]',
            auto_update_enabled BOOLEAN DEFAULT true,
            update_frequency_hours INTEGER DEFAULT 24,
            webhook_secret VARCHAR(64),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_indexed_at TIMESTAMP,
            next_index_at TIMESTAMP,
            is_active BOOLEAN DEFAULT true
        )
    """)
    
    # Create knowledge_chunks table
    op.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id UUID NOT NULL REFERENCES website_knowledge(id),
            source_url VARCHAR(500) NOT NULL,
            page_title VARCHAR(500),
            content TEXT NOT NULL,
            content_hash VARCHAR(64) NOT NULL,
            chunk_metadata JSONB DEFAULT '{}',
            vector_id VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create training_rules table
    op.execute("""
        CREATE TABLE IF NOT EXISTS training_rules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID NOT NULL REFERENCES companies(id),
            rule_key VARCHAR(100) NOT NULL,
            rule_name VARCHAR(255) NOT NULL,
            rule_description TEXT,
            is_enabled BOOLEAN DEFAULT true,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create example_answers table
    op.execute("""
        CREATE TABLE IF NOT EXISTS example_answers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID NOT NULL REFERENCES companies(id),
            question TEXT NOT NULL,
            question_variations JSONB DEFAULT '[]',
            answer TEXT NOT NULL,
            category VARCHAR(100),
            tags JSONB DEFAULT '[]',
            source VARCHAR(50) DEFAULT 'manual',
            detected_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT true,
            is_verified BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP
        )
    """)
    
    # Create call_logs table
    op.execute("""
        CREATE TABLE IF NOT EXISTS call_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID NOT NULL REFERENCES companies(id),
            ai_worker_id UUID REFERENCES ai_workers(id),
            phone_number_id UUID REFERENCES phone_numbers(id),
            twilio_call_sid VARCHAR(50) UNIQUE,
            caller_number VARCHAR(20) NOT NULL,
            called_number VARCHAR(20) NOT NULL,
            status callstatus DEFAULT 'ringing',
            outcome calloutcome,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            answered_at TIMESTAMP,
            ended_at TIMESTAMP,
            duration_seconds INTEGER DEFAULT 0,
            queue_wait_seconds INTEGER DEFAULT 0,
            recording_url VARCHAR(500),
            recording_duration_seconds INTEGER,
            recording_consent_given BOOLEAN DEFAULT false,
            sentiment VARCHAR(20),
            topics JSONB DEFAULT '[]',
            summary TEXT,
            customer_name VARCHAR(255),
            customer_email VARCHAR(255),
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create call_transcripts table
    op.execute("""
        CREATE TABLE IF NOT EXISTS call_transcripts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            call_log_id UUID NOT NULL REFERENCES call_logs(id),
            speaker VARCHAR(20) NOT NULL,
            message TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confidence FLOAT,
            tool_calls JSONB
        )
    """)
    
    # Create appointments table
    op.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID NOT NULL REFERENCES companies(id),
            calendar_integration_id UUID REFERENCES calendar_integrations(id),
            call_log_id UUID REFERENCES call_logs(id),
            external_event_id VARCHAR(255),
            title VARCHAR(255) NOT NULL,
            description TEXT,
            appointment_type VARCHAR(100),
            starts_at TIMESTAMP NOT NULL,
            ends_at TIMESTAMP NOT NULL,
            duration_minutes INTEGER NOT NULL,
            customer_name VARCHAR(255) NOT NULL,
            customer_phone VARCHAR(20),
            customer_email VARCHAR(255),
            status appointmentstatus DEFAULT 'confirmed',
            held_until TIMESTAMP,
            reminder_sent BOOLEAN DEFAULT false,
            reminder_sent_at TIMESTAMP,
            cancelled_at TIMESTAMP,
            cancelled_by VARCHAR(50),
            cancellation_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create internal_notes table
    op.execute("""
        CREATE TABLE IF NOT EXISTS internal_notes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID NOT NULL REFERENCES companies(id),
            call_log_id UUID REFERENCES call_logs(id),
            title VARCHAR(255) NOT NULL,
            content TEXT NOT NULL,
            category VARCHAR(100),
            tags JSONB DEFAULT '[]',
            priority notepriority DEFAULT 'normal',
            customer_name VARCHAR(255),
            customer_phone VARCHAR(20),
            customer_email VARCHAR(255),
            action_required BOOLEAN DEFAULT false,
            action_description TEXT,
            action_due_at TIMESTAMP,
            is_resolved BOOLEAN DEFAULT false,
            resolved_at TIMESTAMP,
            resolved_by_user_id UUID,
            resolution_notes TEXT,
            notification_sent BOOLEAN DEFAULT false,
            notification_sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes
    op.execute("CREATE INDEX IF NOT EXISTS ix_phone_numbers_number ON phone_numbers(number)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_call_logs_twilio_call_sid ON call_logs(twilio_call_sid)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS internal_notes CASCADE")
    op.execute("DROP TABLE IF EXISTS appointments CASCADE")
    op.execute("DROP TABLE IF EXISTS call_transcripts CASCADE")
    op.execute("DROP TABLE IF EXISTS call_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS example_answers CASCADE")
    op.execute("DROP TABLE IF EXISTS training_rules CASCADE")
    op.execute("DROP TABLE IF EXISTS knowledge_chunks CASCADE")
    op.execute("DROP TABLE IF EXISTS website_knowledge CASCADE")
    op.execute("DROP TABLE IF EXISTS calendar_integrations CASCADE")
    op.execute("DROP TABLE IF EXISTS phone_numbers CASCADE")
    op.execute("DROP TABLE IF EXISTS ai_workers CASCADE")
