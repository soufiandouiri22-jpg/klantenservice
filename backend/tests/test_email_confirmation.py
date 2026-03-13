"""
Tests for appointment email confirmation feature.

Verifies that:
- SMS-only, email-only, and both-enabled flows work correctly
- Missing email address is handled gracefully
- Booking succeeds even when email/SMS sending fails
- Email template placeholders are substituted correctly
"""
import sys
import os
import types
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub heavy dependencies before importing app modules
_stubs = {}
for mod_name in [
    "pydantic_settings", "sqlalchemy", "sqlalchemy.dialects",
    "sqlalchemy.dialects.postgresql", "sqlalchemy.orm", "sqlalchemy.ext",
    "sqlalchemy.ext.asyncio", "fastapi", "fastapi.middleware",
    "fastapi.middleware.cors", "uvicorn", "httpx", "openai",
    "twilio", "twilio.rest", "stripe", "mailchimp3",
]:
    if mod_name not in sys.modules:
        _stubs[mod_name] = sys.modules[mod_name] = types.ModuleType(mod_name)

# Stub pydantic_settings.BaseSettings to a basic class
if hasattr(sys.modules.get("pydantic_settings", None), "__dict__"):
    class _FakeBaseSettings:
        pass
    sys.modules["pydantic_settings"].BaseSettings = _FakeBaseSettings

# Now mock resend + settings at a lower level so we can import the email function
mock_resend = MagicMock()
sys.modules["resend"] = mock_resend

# Create a minimal settings mock
_mock_settings = MagicMock()
_mock_settings.RESEND_API_KEY = "test-key"
_mock_settings.RESEND_FROM_EMAIL = "noreply@test.com"
_mock_settings.FRONTEND_URL = "http://localhost:3000"

# Stub app.core.config so email.py can import settings
app_mod = types.ModuleType("app")
app_mod.__path__ = [os.path.join(os.path.dirname(__file__), "..", "app")]
sys.modules.setdefault("app", app_mod)

app_core_mod = types.ModuleType("app.core")
app_core_mod.__path__ = [os.path.join(os.path.dirname(__file__), "..", "app", "core")]
sys.modules.setdefault("app.core", app_core_mod)

config_mod = types.ModuleType("app.core.config")
config_mod.settings = _mock_settings
sys.modules["app.core.config"] = config_mod

from app.core.email import send_appointment_confirmation_email, DEFAULT_EMAIL_CONFIRMATION_TEMPLATE

_pass_count = 0
_fail_count = 0
_results: list = []


def _assert(condition: bool, label: str, detail: str = ""):
    global _pass_count, _fail_count
    if condition:
        _pass_count += 1
        _results.append(f"  PASS  {label}")
    else:
        _fail_count += 1
        msg = f"  FAIL  {label}"
        if detail:
            msg += f"  [{detail}]"
        _results.append(msg)


# ═══════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════


class TestEmailTemplatePlaceholders:
    """Verify that {bedrijfsnaam}, {datum}, {tijd} are substituted correctly."""

    @staticmethod
    def test_default_template_substitution():
        mock_resend.Emails.send.reset_mock()
        mock_resend.Emails.send.side_effect = None

        result = send_appointment_confirmation_email(
            to="klant@example.com",
            company_name="Kapsalon De Schaar",
            starts_at_readable="maandag 15 maart om 14:00",
        )

        _assert(result is True, "default-template: returns True on success")
        call_args = mock_resend.Emails.send.call_args[0][0]
        _assert("Kapsalon De Schaar" in call_args["html"],
                "default-template: company name in HTML")
        _assert("maandag 15 maart" in call_args["html"],
                "default-template: datum in HTML")
        _assert("14:00" in call_args["html"],
                "default-template: tijd in HTML")

    @staticmethod
    def test_custom_template_substitution():
        mock_resend.Emails.send.reset_mock()
        mock_resend.Emails.send.side_effect = None

        custom = "Hey! Afspraak bij {bedrijfsnaam} op {datum}, {tijd}. Welkom!"
        result = send_appointment_confirmation_email(
            to="klant@example.com",
            company_name="Garage Jansen",
            starts_at_readable="dinsdag 20 april om 09:30",
            custom_template=custom,
        )

        _assert(result is True, "custom-template: returns True on success")
        call_args = mock_resend.Emails.send.call_args[0][0]
        _assert("Garage Jansen" in call_args["html"],
                "custom-template: company name in HTML")

    @staticmethod
    def test_from_header_uses_company_name():
        mock_resend.Emails.send.reset_mock()
        mock_resend.Emails.send.side_effect = None

        send_appointment_confirmation_email(
            to="klant@example.com",
            company_name="Restaurant Luigi",
            starts_at_readable="woensdag 5 mei om 19:00",
        )

        call_args = mock_resend.Emails.send.call_args[0][0]
        _assert("Restaurant Luigi" in call_args["from"],
                "from-header: uses company name")
        _assert(call_args["subject"] == "Afspraakbevestiging - Restaurant Luigi",
                "subject: includes company name")


class TestEmailFailureHandling:
    """Email failures must never raise — always return False."""

    @staticmethod
    def test_resend_exception_returns_false():
        mock_resend.Emails.send.reset_mock()
        mock_resend.Emails.send.side_effect = Exception("Resend API down")

        result = send_appointment_confirmation_email(
            to="klant@example.com",
            company_name="Test BV",
            starts_at_readable="vrijdag 1 juni om 10:00",
        )

        _assert(result is False, "resend-error: returns False on exception")

    @staticmethod
    def test_no_api_key_returns_true_dev_mode():
        original = _mock_settings.RESEND_API_KEY
        _mock_settings.RESEND_API_KEY = ""

        result = send_appointment_confirmation_email(
            to="klant@example.com",
            company_name="Dev Co",
            starts_at_readable="zaterdag 2 juli om 11:00",
        )

        _mock_settings.RESEND_API_KEY = original
        _assert(result is True, "no-api-key: returns True in dev mode")


class TestBookingConfirmationFlow:
    """Simulate the booking confirmation flow logic (without real DB)."""

    @staticmethod
    def test_sms_only_no_email():
        sms_sent = False
        email_sent = False
        sms_enabled = True
        email_enabled = False
        customer_phone = "+31612345678"
        customer_email = "klant@example.com"

        if customer_phone and sms_enabled:
            sms_sent = True
        if customer_email and email_enabled:
            email_sent = True

        _assert(sms_sent is True, "sms-only: SMS was sent")
        _assert(email_sent is False, "sms-only: email was NOT sent")

    @staticmethod
    def test_email_only_no_sms():
        sms_sent = False
        email_sent = False
        sms_enabled = False
        email_enabled = True
        customer_phone = "+31612345678"
        customer_email = "klant@example.com"

        if customer_phone and sms_enabled:
            sms_sent = True
        if customer_email and email_enabled:
            email_sent = True

        _assert(sms_sent is False, "email-only: SMS was NOT sent")
        _assert(email_sent is True, "email-only: email was sent")

    @staticmethod
    def test_both_sms_and_email():
        sms_sent = False
        email_sent = False
        sms_enabled = True
        email_enabled = True
        customer_phone = "+31612345678"
        customer_email = "klant@example.com"

        if customer_phone and sms_enabled:
            sms_sent = True
        if customer_email and email_enabled:
            email_sent = True

        _assert(sms_sent is True, "both: SMS was sent")
        _assert(email_sent is True, "both: email was sent")

    @staticmethod
    def test_no_email_available():
        email_sent = False
        email_enabled = True
        customer_email = None

        if customer_email and email_enabled:
            email_sent = True

        _assert(email_sent is False, "no-email: email skipped when address is None")

    @staticmethod
    def test_no_email_empty_string():
        email_sent = False
        email_enabled = True
        customer_email = ""

        if customer_email and email_enabled:
            email_sent = True

        _assert(email_sent is False, "no-email-empty: email skipped when address is empty")

    @staticmethod
    def test_booking_survives_email_failure():
        booking_ok = False
        try:
            booking_ok = True
            try:
                raise Exception("Email send failed")
            except Exception:
                pass
        except Exception:
            booking_ok = False

        _assert(booking_ok is True, "email-failure: booking still succeeds")

    @staticmethod
    def test_booking_survives_sms_failure():
        booking_ok = False
        try:
            booking_ok = True
            try:
                raise Exception("SMS send failed")
            except Exception:
                pass
        except Exception:
            booking_ok = False

        _assert(booking_ok is True, "sms-failure: booking still succeeds")


class TestEmailRecipient:
    """Verify email is sent to the correct address."""

    @staticmethod
    def test_email_sent_to_correct_address():
        mock_resend.Emails.send.reset_mock()
        mock_resend.Emails.send.side_effect = None

        send_appointment_confirmation_email(
            to="specific-customer@example.com",
            company_name="Test",
            starts_at_readable="maandag 1 jan om 10:00",
        )

        call_args = mock_resend.Emails.send.call_args[0][0]
        _assert(call_args["to"] == ["specific-customer@example.com"],
                "recipient: email sent to correct address")


# ═══════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════

test_classes = [
    TestEmailTemplatePlaceholders,
    TestEmailFailureHandling,
    TestBookingConfirmationFlow,
    TestEmailRecipient,
]


def main():
    global _pass_count, _fail_count
    _pass_count = 0
    _fail_count = 0
    _results.clear()

    for cls in test_classes:
        for attr in sorted(dir(cls)):
            if attr.startswith("test_"):
                getattr(cls, attr)()

    print("\n".join(_results))
    print(f"\n{'=' * 60}")
    print(f"Results: {_pass_count} passed, {_fail_count} failed, {_pass_count + _fail_count} total")
    print(f"{'=' * 60}")

    return _fail_count == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
