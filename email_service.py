"""
Email Service for OTP Delivery
Uses Gmail SMTP (Free) - You can also use SendGrid, Mailgun, etc.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

# =====================================================
# EMAIL CONFIGURATION
# =====================================================

# Gmail SMTP (Free option)
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER', 'your-email@gmail.com')  # Your Gmail
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', 'your-app-password')  # Gmail App Password

FROM_EMAIL = os.getenv('FROM_EMAIL', SMTP_USER)
FROM_NAME = "Anatech Consultancy"

# =====================================================
# HOW TO GET GMAIL APP PASSWORD
# =====================================================
"""
1. Go to Google Account Settings
2. Security → 2-Step Verification (turn ON if not already)
3. Search for "App Passwords"
4. Select app: Mail
5. Select device: Other (Custom name)
6. Name it: "Reddit Lead Discovery"
7. Copy the 16-character password
8. Put it in .env as SMTP_PASSWORD
"""

# =====================================================
# EMAIL TEMPLATES
# =====================================================

def get_otp_template(otp_code, otp_type='signup'):
    """HTML template for OTP emails"""
    
    if otp_type == 'signup':
        subject = "Verify Your Email - Reddit Lead Discovery"
        heading = "Welcome to Reddit Lead Discovery!"
        message = "Thank you for signing up. Please verify your email address using the OTP below:"
    elif otp_type == 'password_reset':
        subject = "Password Reset - Reddit Lead Discovery"
        heading = "Reset Your Password"
        message = "You requested to reset your password. Use the OTP below to proceed:"
    elif otp_type == 'login':
        subject = "Login OTP - Reddit Lead Discovery"
        heading = "Login Verification"
        message = "Use this OTP to complete your login:"
    else:
        subject = "Verification Code"
        heading = "Your Verification Code"
        message = "Use this OTP to verify your action:"
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            background-color: #f8fafc;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 40px auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 700;
        }}
        .content {{
            padding: 40px 30px;
        }}
        .greeting {{
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 15px;
            color: #0f172a;
        }}
        .message {{
            color: #475569;
            line-height: 1.6;
            margin-bottom: 30px;
        }}
        .otp-container {{
            background: #eff6ff;
            border: 2px solid #2563eb;
            border-radius: 8px;
            padding: 25px;
            text-align: center;
            margin: 30px 0;
        }}
        .otp-label {{
            font-size: 14px;
            color: #64748b;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .otp-code {{
            font-size: 36px;
            font-weight: 800;
            color: #2563eb;
            letter-spacing: 8px;
            font-family: 'Courier New', monospace;
        }}
        .expiry {{
            margin-top: 15px;
            font-size: 13px;
            color: #dc2626;
            font-weight: 600;
        }}
        .warning {{
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .warning-text {{
            color: #92400e;
            font-size: 13px;
            margin: 0;
        }}
        .footer {{
            background: #f8fafc;
            padding: 20px 30px;
            text-align: center;
            border-top: 1px solid #e2e8f0;
        }}
        .footer-text {{
            color: #64748b;
            font-size: 12px;
            margin: 5px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{FROM_NAME}</h1>
        </div>
        
        <div class="content">
            <div class="greeting">{heading}</div>
            
            <p class="message">{message}</p>
            
            <div class="otp-container">
                <div class="otp-label">Your OTP Code</div>
                <div class="otp-code">{otp_code}</div>
                <div class="expiry">⏰ Expires in 10 minutes</div>
            </div>
            
            <div class="warning">
                <p class="warning-text">
                    <strong>Security Notice:</strong> Never share this OTP with anyone. 
                    {FROM_NAME} will never ask for your OTP via phone or email.
                </p>
            </div>
            
            <p class="message">
                If you didn't request this code, please ignore this email or contact support if you're concerned.
            </p>
        </div>
        
        <div class="footer">
            <p class="footer-text">© 2024 {FROM_NAME}. All rights reserved.</p>
            <p class="footer-text">Reddit Lead Discovery Platform</p>
        </div>
    </div>
</body>
</html>
    """
    
    return subject, html


def get_welcome_email_template(user_name):
    """Welcome email after successful verification"""
    subject = "Welcome to Reddit Lead Discovery! 🎉"
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; background: #f8fafc; margin: 0; padding: 20px; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; padding: 40px; }}
        .header {{ background: linear-gradient(135deg, #2563eb, #1e40af); color: white; padding: 30px; text-align: center; border-radius: 8px; margin-bottom: 30px; }}
        h1 {{ margin: 0; font-size: 28px; }}
        .content {{ color: #0f172a; line-height: 1.6; }}
        .feature {{ background: #eff6ff; padding: 15px; border-radius: 6px; margin: 15px 0; }}
        .cta {{ text-align: center; margin: 30px 0; }}
        .button {{ background: #2563eb; color: white; padding: 14px 30px; border-radius: 6px; text-decoration: none; display: inline-block; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Welcome, {user_name}! 🎉</h1>
        </div>
        
        <div class="content">
            <p>Your account has been successfully verified!</p>
            
            <p>You now have full access to Reddit Lead Discovery, where you can:</p>
            
            <div class="feature">
                <strong>🔍 AI-Powered Subreddit Discovery</strong><br>
                Let AI find the perfect communities for your business
            </div>
            
            <div class="feature">
                <strong>📊 Smart Lead Scoring</strong><br>
                Get leads ranked by relevance and buying intent
            </div>
            
            <div class="feature">
                <strong>🤖 AI Response Generation</strong><br>
                Generate personalized, authentic responses instantly
            </div>
            
            <div class="feature">
                <strong>💾 Save & Track Leads</strong><br>
                Bookmark leads and track your engagement
            </div>
            
            <div class="cta">
                <a href="reddit-lead-discovery-production.up.railway.app" class="button">Start Discovering Leads</a>
            </div>
            
            <p><strong>Your Plan:</strong> Free (100 queries per month)</p>
            
            <p>Need help? Contact us at support@anatech.com</p>
        </div>
    </div>
</body>
</html>
    """
    
    return subject, html


# =====================================================
# SEND EMAIL FUNCTION
# =====================================================

def send_email(to_email, subject, html_content):
    """
    Send email using SMTP
    
    Returns:
        dict: {'success': bool, 'message': str}
    """
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg['To'] = to_email
        
        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Connect to SMTP server
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Secure connection
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        
        print(f"✅ Email sent to {to_email}")
        return {'success': True, 'message': 'Email sent successfully'}
        
    except Exception as e:
        print(f"❌ Email error: {str(e)}")
        return {'success': False, 'message': f'Failed to send email: {str(e)}'}


# =====================================================
# CONVENIENCE FUNCTIONS
# =====================================================

def send_otp_email(to_email, otp_code, otp_type='signup'):
    """Send OTP email"""
    subject, html = get_otp_template(otp_code, otp_type)
    return send_email(to_email, subject, html)


def send_welcome_email(to_email, user_name):
    """Send welcome email after verification"""
    subject, html = get_welcome_email_template(user_name)
    return send_email(to_email, subject, html)


# =====================================================
# TESTING
# =====================================================

if __name__ == '__main__':
    # Test email sending
    print("Testing email service...")
    
    # Test OTP email
    result = send_otp_email('test@example.com', '123456', 'signup')
    print(f"OTP Email: {result}")
    
    # Test welcome email
    result = send_welcome_email('test@example.com', 'John Doe')

    print(f"Welcome Email: {result}")
