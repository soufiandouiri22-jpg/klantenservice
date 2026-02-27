"""
klantenservice.ai - Email Service using Resend
"""
import resend
from typing import Optional

from app.core.config import settings


def init_resend():
    """Initialize Resend with API key."""
    if settings.RESEND_API_KEY:
        resend.api_key = settings.RESEND_API_KEY


def send_verification_code_email(
    to_email: str,
    first_name: str,
    code: str
) -> bool:
    """
    Send a 6-digit verification code to verify email address.
    
    Returns True if successful, False otherwise.
    """
    if not settings.RESEND_API_KEY:
        print(f"[DEV] Would send verification code to {to_email}")
        print(f"[DEV] Code: {code}")
        return True
    
    try:
        init_resend()
        
        # Format code with spaces for readability: "123 456"
        formatted_code = f"{code[:3]} {code[3:]}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Verifieer uw e-mailadres</title>
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #2563eb; padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">Verifieer uw e-mail</h1>
            </div>
            
            <div style="background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p style="font-size: 16px; margin-bottom: 20px;">
                    Hoi {first_name},
                </p>
                
                <p style="font-size: 16px; margin-bottom: 20px;">
                    Gebruik de onderstaande code om uw e-mailadres te verifiëren:
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <div style="background: #ffffff; border: 2px solid #2563eb; border-radius: 12px; padding: 20px 40px; display: inline-block;">
                        <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #2563eb; font-family: monospace;">
                            {formatted_code}
                        </span>
                    </div>
                </div>
                
                <p style="font-size: 14px; color: #6b7280; text-align: center;">
                    Deze code is <strong>10 minuten</strong> geldig.
                </p>
                
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                
                <p style="font-size: 12px; color: #9ca3af; text-align: center;">
                    Als u geen account heeft aangemaakt bij klantenservice.ai, kunt u deze email negeren.
                </p>
            </div>
        </body>
        </html>
        """
        
        params = {
            "from": f"klantenservice.ai <{settings.RESEND_FROM_EMAIL}>",
            "to": [to_email],
            "subject": f"Uw verificatiecode: {formatted_code}",
            "html": html_content,
        }
        
        resend.Emails.send(params)
        return True
        
    except Exception as e:
        print(f"Error sending verification code email: {e}")
        return False


def send_invite_email(
    to_email: str,
    first_name: str,
    company_name: str,
    inviter_name: str,
    invite_link: str,
    role: str
) -> bool:
    """
    Send an invitation email to a new user.
    
    Returns True if successful, False otherwise.
    """
    if not settings.RESEND_API_KEY:
        print(f"[DEV] Would send invite email to {to_email}")
        print(f"[DEV] Invite link: {invite_link}")
        return True
    
    try:
        init_resend()
        
        role_dutch = {
            "owner": "Eigenaar",
            "admin": "Admin",
            "manager": "Manager",
            "user": "Gebruiker",
            "viewer": "Kijker"
        }.get(role, role)
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Uitnodiging voor {company_name}</title>
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #2563eb; padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">Je bent uitgenodigd!</h1>
            </div>
            
            <div style="background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p style="font-size: 16px; margin-bottom: 20px;">
                    Hoi {first_name},
                </p>
                
                <p style="font-size: 16px; margin-bottom: 20px;">
                    <strong>{inviter_name}</strong> heeft je uitgenodigd om deel te nemen aan <strong>{company_name}</strong> op klantenservice.ai als <strong>{role_dutch}</strong>.
                </p>
                
                <p style="font-size: 16px; margin-bottom: 30px;">
                    Klik op de onderstaande knop om je account te activeren en een wachtwoord in te stellen:
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{invite_link}" style="background: #2563eb; color: white; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block;">
                        Account activeren
                    </a>
                </div>
                
                <p style="font-size: 14px; color: #6b7280; margin-top: 30px;">
                    Deze uitnodiging is 7 dagen geldig. Als de knop niet werkt, kopieer en plak deze link in je browser:
                </p>
                <p style="font-size: 12px; color: #9ca3af; word-break: break-all;">
                    {invite_link}
                </p>
                
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                
                <p style="font-size: 12px; color: #9ca3af; text-align: center;">
                    Dit is een automatische email van klantenservice.ai.<br>
                    Heb je deze uitnodiging niet verwacht? Je kunt deze email negeren.
                </p>
            </div>
        </body>
        </html>
        """
        
        params = {
            "from": f"klantenservice.ai <{settings.RESEND_FROM_EMAIL}>",
            "to": [to_email],
            "subject": f"Uitnodiging voor {company_name} - klantenservice.ai",
            "html": html_content,
        }
        
        resend.Emails.send(params)
        return True
        
    except Exception as e:
        print(f"Error sending invite email: {e}")
        return False


def send_password_reset_email(
    to_email: str,
    first_name: str,
    reset_link: str,
) -> bool:
    """
    Send a password reset email with a link to reset the password.

    Returns True if successful, False otherwise.
    """
    if not settings.RESEND_API_KEY:
        print(f"[DEV] Would send password reset to {to_email}")
        print(f"[DEV] Reset link: {reset_link}")
        return True

    try:
        init_resend()

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Wachtwoord herstellen</title>
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #2563eb; padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">Wachtwoord herstellen</h1>
            </div>

            <div style="background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p style="font-size: 16px; margin-bottom: 20px;">
                    Hoi {first_name},
                </p>

                <p style="font-size: 16px; margin-bottom: 20px;">
                    We hebben een verzoek ontvangen om uw wachtwoord te herstellen. Klik op de onderstaande knop om een nieuw wachtwoord in te stellen:
                </p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}" style="background: #2563eb; color: white; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block;">
                        Wachtwoord herstellen
                    </a>
                </div>

                <p style="font-size: 14px; color: #6b7280; text-align: center;">
                    Deze link is <strong>1 uur</strong> geldig.
                </p>

                <p style="font-size: 14px; color: #6b7280; margin-top: 20px;">
                    Als de knop niet werkt, kopieer en plak deze link in je browser:
                </p>
                <p style="font-size: 12px; color: #9ca3af; word-break: break-all;">
                    {reset_link}
                </p>

                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">

                <p style="font-size: 12px; color: #9ca3af; text-align: center;">
                    Als u dit verzoek niet heeft gedaan, kunt u deze email negeren. Uw wachtwoord wordt niet gewijzigd.
                </p>
            </div>
        </body>
        </html>
        """

        params = {
            "from": f"klantenservice.ai <{settings.RESEND_FROM_EMAIL}>",
            "to": [to_email],
            "subject": "Wachtwoord herstellen - klantenservice.ai",
            "html": html_content,
        }

        resend.Emails.send(params)
        return True

    except Exception as e:
        print(f"Error sending password reset email: {e}")
        return False


def send_welcome_email(
    to_email: str,
    first_name: str,
    company_name: str
) -> bool:
    """
    Send a welcome email after user accepts invite.
    """
    if not settings.RESEND_API_KEY:
        print(f"[DEV] Would send welcome email to {to_email}")
        return True
    
    try:
        init_resend()
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #2563eb; padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">Welkom bij klantenservice.ai!</h1>
            </div>
            
            <div style="background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p style="font-size: 16px; margin-bottom: 20px;">
                    Hoi {first_name},
                </p>
                
                <p style="font-size: 16px; margin-bottom: 20px;">
                    Je account voor <strong>{company_name}</strong> is succesvol geactiveerd. Je kunt nu inloggen op het dashboard.
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{settings.FRONTEND_URL}/login" style="background: #2563eb; color: white; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block;">
                        Ga naar het dashboard
                    </a>
                </div>
                
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                
                <p style="font-size: 12px; color: #9ca3af; text-align: center;">
                    Dit is een automatische email van klantenservice.ai.
                </p>
            </div>
        </body>
        </html>
        """
        
        params = {
            "from": f"klantenservice.ai <{settings.RESEND_FROM_EMAIL}>",
            "to": [to_email],
            "subject": f"Welkom bij {company_name} - klantenservice.ai",
            "html": html_content,
        }
        
        resend.Emails.send(params)
        return True
        
    except Exception as e:
        print(f"Error sending welcome email: {e}")
        return False


def send_contact_form_email(
    sender_name: str,
    sender_email: str,
    company: str = "",
    phone: str = "",
    subject: str = "Algemene vraag",
    message: str = "",
) -> bool:
    """
    Send a contact form submission to the team inbox.

    Returns True if successful, False otherwise.
    """
    if not settings.RESEND_API_KEY:
        print(f"[DEV] Contact form from {sender_name} <{sender_email}>")
        print(f"[DEV] Subject: {subject}")
        print(f"[DEV] Message: {message}")
        return True

    try:
        init_resend()

        details = []
        if company:
            details.append(f"<strong>Bedrijf:</strong> {company}")
        if phone:
            details.append(f"<strong>Telefoon:</strong> {phone}")
        details_html = "<br>".join(details)
        if details_html:
            details_html = f"<p style='color:#6b7280;font-size:14px;'>{details_html}</p>"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"></head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #2563eb; padding: 24px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 20px;">Nieuw contactformulier bericht</h1>
            </div>
            <div style="background-color: #f9fafb; padding: 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p style="font-size: 14px; color: #6b7280; margin-bottom: 4px;">Onderwerp</p>
                <p style="font-size: 18px; font-weight: 600; margin-top: 0;">{subject}</p>

                <p style="font-size: 14px; color: #6b7280; margin-bottom: 4px;">Van</p>
                <p style="font-size: 16px; margin-top: 0;">{sender_name} &lt;{sender_email}&gt;</p>

                {details_html}

                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">

                <p style="font-size: 14px; color: #6b7280; margin-bottom: 4px;">Bericht</p>
                <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; white-space: pre-wrap; font-size: 15px;">
{message}
                </div>

                <p style="font-size: 12px; color: #9ca3af; text-align: center; margin-top: 24px;">
                    Beantwoord dit bericht door te reageren naar {sender_email}
                </p>
            </div>
        </body>
        </html>
        """

        params = {
            "from": f"klantenservice.ai <{settings.RESEND_FROM_EMAIL}>",
            "to": ["info@klantenservice.ai"],
            "reply_to": sender_email,
            "subject": f"[Contact] {subject} - {sender_name}",
            "html": html_content,
        }

        resend.Emails.send(params)
        return True

    except Exception as e:
        print(f"Error sending contact form email: {e}")
        return False
