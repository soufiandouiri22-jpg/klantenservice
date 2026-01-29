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
            <div style="background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">Je bent uitgenodigd!</h1>
            </div>
            
            <div style="background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
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
            <div style="background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">Welkom bij klantenservice.ai!</h1>
            </div>
            
            <div style="background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
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
