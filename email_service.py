"""
Email Service for OTP Delivery
Uses Resend API for reliable email delivery on Railway
"""

import os
import resend
from dotenv import load_dotenv

load_dotenv()

# =====================================================
# RESEND CONFIGURATION
# =====================================================

resend.api_key = os.getenv('RESEND_API_KEY', 're_8FT3hMcX_AXfkM4foKyuHzKyV8weK1j6H')

FROM_EMAIL = os.getenv('FROM_EMAIL', 'shivansh@anatechconsultancy.com')
FROM_NAME  = "Anatech Consultancy"


# =====================================================
# EMAIL TEMPLATES
# =====================================================

def get_otp_template(otp_code, otp_type='signup'):
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

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 0; }}
  .container {{ max-width: 600px; margin: 40px auto; background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); overflow: hidden; }}
  .header {{ background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); color: white; padding: 30px; text-align: center; }}
  .header h1 {{ margin: 0; font-size: 24px; font-weight: 700; }}
  .content {{ padding: 40px 30px; }}
  .greeting {{ font-size: 18px; font-weight: 600; margin-bottom: 15px; color: #0f172a; }}
  .message {{ color: #475569; line-height: 1.6; margin-bottom: 30px; }}
  .otp-container {{ background: #eff6ff; border: 2px solid #2563eb; border-radius: 8px; padding: 25px; text-align: center; margin: 30px 0; }}
  .otp-label {{ font-size: 14px; color: #64748b; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .otp-code {{ font-size: 36px; font-weight: 800; color: #2563eb; letter-spacing: 8px; font-family: 'Courier New', monospace; }}
  .expiry {{ margin-top: 15px; font-size: 13px; color: #dc2626; font-weight: 600; }}
  .warning {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0; border-radius: 4px; }}
  .warning-text {{ color: #92400e; font-size: 13px; margin: 0; }}
  .footer {{ background: #f8fafc; padding: 20px 30px; text-align: center; border-top: 1px solid #e2e8f0; }}
  .footer-text {{ color: #64748b; font-size: 12px; margin: 5px 0; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header"><h1>{FROM_NAME}</h1></div>
    <div class="content">
      <div class="greeting">{heading}</div>
      <p class="message">{message}</p>
      <div class="otp-container">
        <div class="otp-label">Your OTP Code</div>
        <div class="otp-code">{otp_code}</div>
        <div class="expiry">⏰ Expires in 10 minutes</div>
      </div>
      <div class="warning">
        <p class="warning-text"><strong>Security Notice:</strong> Never share this OTP with anyone. {FROM_NAME} will never ask for your OTP via phone or email.</p>
      </div>
      <p class="message">If you didn't request this code, please ignore this email or contact support if you're concerned.</p>
    </div>
    <div class="footer">
      <p class="footer-text">© 2024 {FROM_NAME}. All rights reserved.</p>
      <p class="footer-text">Reddit Lead Discovery Platform</p>
    </div>
  </div>
</body>
</html>"""

    return subject, html


def get_welcome_email_template(user_name):
    """Welcome email after successful verification"""
    subject = "Welcome to Reddit Lead Discovery! 🎉"

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; background: #f8fafc; margin: 0; padding: 20px; }}
  .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
  .header {{ background: linear-gradient(135deg, #2563eb, #1e40af); color: white; padding: 30px; text-align: center; }}
  .header h1 {{ margin: 0; font-size: 28px; font-weight: 700; }}
  .header p {{ margin: 8px 0 0; opacity: 0.9; font-size: 15px; }}
  .content {{ padding: 40px 30px; color: #0f172a; line-height: 1.6; }}
  .content p {{ color: #475569; margin-bottom: 20px; }}
  .feature {{ background: #eff6ff; border-left: 3px solid #2563eb; padding: 14px 16px; border-radius: 6px; margin: 12px 0; }}
  .feature strong {{ color: #1e40af; display: block; margin-bottom: 4px; }}
  .feature span {{ color: #475569; font-size: 14px; }}
  .cta {{ text-align: center; margin: 32px 0; }}
  .button {{ background: #2563eb; color: white; padding: 14px 32px; border-radius: 8px; text-decoration: none; display: inline-block; font-weight: 600; font-size: 15px; }}
  .plan-badge {{ background: #f0fdf4; border: 1px solid #bbf7d0; color: #16a34a; padding: 10px 16px; border-radius: 6px; font-size: 14px; font-weight: 500; margin: 20px 0; display: inline-block; }}
  .footer {{ background: #f8fafc; padding: 20px 30px; text-align: center; border-top: 1px solid #e2e8f0; }}
  .footer-text {{ color: #64748b; font-size: 12px; margin: 4px 0; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Welcome, {user_name}! 🎉</h1>
      <p>Your account has been successfully verified</p>
    </div>
    <div class="content">
      <p>You now have full access to <strong>Reddit Lead Discovery</strong> — your AI-powered platform to find and engage with potential customers on Reddit.</p>
      <p>Here's what you can do:</p>
      <div class="feature"><strong>🔍 AI-Powered Subreddit Discovery</strong><span>Let AI find the perfect communities for your business niche</span></div>
      <div class="feature"><strong>📊 Smart Lead Scoring</strong><span>Get leads ranked by relevance and buying intent</span></div>
      <div class="feature"><strong>🤖 AI Response Generation</strong><span>Generate personalized, authentic responses instantly</span></div>
      <div class="feature"><strong>💾 Save &amp; Track Leads</strong><span>Bookmark leads and monitor your engagement pipeline</span></div>
      <div class="cta"><a href="https://reddit-lead-discovery-production.up.railway.app" class="button">Start Discovering Leads →</a></div>
      <div class="plan-badge">✅ Your Plan: Free — 100 queries per month</div>
      <p style="font-size:14px;">Need help? Reach us at <a href="mailto:support@anatechconsultancy.com" style="color:#2563eb;">support@anatechconsultancy.com</a></p>
    </div>
    <div class="footer">
      <p class="footer-text">© 2024 {FROM_NAME}. All rights reserved.</p>
      <p class="footer-text">Reddit Lead Discovery Platform</p>
    </div>
  </div>
</body>
</html>"""

    return subject, html


# =====================================================
# SEND EMAIL FUNCTION  (Resend API)
# =====================================================

def send_email(to_email, subject, html_content):
    """Send email via Resend API"""
    try:
        print(f"📧 Sending email via Resend to: {to_email}")

        params = {
            "from": f"{FROM_NAME} <{FROM_EMAIL}>",
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }

        response = resend.Emails.send(params)
        print(f"✅ Email sent. Resend ID: {response.get('id', 'N/A')}")
        return {'success': True, 'id': response.get('id')}

    except Exception as e:
        print(f"❌ Email send failure: {repr(e)}")
        return {'success': False, 'message': str(e)}


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
    print("Testing Resend email service...")
    result = send_otp_email('test@example.com', '123456', 'signup')
    print(f"OTP Email: {result}")
    result = send_welcome_email('test@example.com', 'John Doe')
    print(f"Welcome Email: {result}")
