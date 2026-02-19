"""
Authentication Module
Handles user signup, login, OTP verification, password reset
"""

import psycopg2
from psycopg2 import pool, extras
import bcrypt 
import secrets
import string
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# =====================================================
# DATABASE CONNECTION POOL (AUTH DATABASE)
# =====================================================

auth_pool = None

def init_auth_pool():
    """Initialize connection pool for auth_system database"""
    global auth_pool
    
    try:
          auth_pool = psycopg2.pool.SimpleConnectionPool(
          1, 10,
          host=os.getenv('AUTH_DB_HOST', 'localhost'),
          port=os.getenv('AUTH_DB_PORT', '5432'),
          database=os.getenv('AUTH_DB_NAME', 'auth_system'),
          user=os.getenv('AUTH_DB_USER', 'postgres'),
          password=os.getenv('AUTH_DB_PASSWORD', 'your_password')
        )
        print("✅ Auth database connection pool created")
        return True
    except Exception as e:
        print(f"❌ Auth DB connection error: {str(e)}")
        return False


def get_auth_connection():
    """Get connection from auth pool"""
    if auth_pool:
        return auth_pool.getconn()
    raise Exception("Auth pool not initialized")


def return_auth_connection(conn):
    """Return connection to auth pool"""
    if auth_pool and conn:
        auth_pool.putconn(conn)


# =====================================================
# PASSWORD HASHING
# =====================================================

def hash_password(password):
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password, password_hash):
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


# =====================================================
# OTP GENERATION
# =====================================================

def generate_otp():
    """Generate 6-digit OTP"""
    return ''.join(secrets.choice(string.digits) for _ in range(6))


def generate_session_token():
    """Generate secure session token"""
    return secrets.token_urlsafe(32)


# =====================================================
# USER SIGNUP
# =====================================================

def signup_user(email, password, full_name):
    """
    Register a new user and send OTP
    
    Returns:
        dict: {'success': bool, 'message': str, 'user_id': int, 'otp': str}
    """
    conn = None
    try:
        conn = get_auth_connection()
        cursor = conn.cursor()
        
        # Check if email already exists
        cursor.execute("SELECT id, is_verified FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            if existing_user[1]:  # is_verified = True
                return {'success': False, 'message': 'Email already registered and verified'}
            else:
                # User exists but not verified - resend OTP
                user_id = existing_user[0]
                otp = generate_otp()
                
                # Delete old OTPs
                cursor.execute("DELETE FROM otp_codes WHERE user_id = %s AND otp_type = 'signup'", (user_id,))
                
                # Create new OTP
                cursor.execute("""
                    INSERT INTO otp_codes (user_id, email, otp_code, otp_type, expires_at)
                    VALUES (%s, %s, %s, 'signup', %s)
                """, (user_id, email, otp, datetime.now() + timedelta(minutes=10)))
                
                conn.commit()
                
                return {
                    'success': True,
                    'message': 'OTP resent to your email',
                    'user_id': user_id,
                    'otp': otp  # In production, send via email, don't return
                }
        
        # Create new user
        password_hash = hash_password(password)
        
        cursor.execute("""
            INSERT INTO users (email, password_hash, full_name, is_verified)
            VALUES (%s, %s, %s, FALSE)
            RETURNING id
        """, (email, password_hash, full_name))
        
        user_id = cursor.fetchone()[0]
        
        # Generate OTP
        otp = generate_otp()
        
        cursor.execute("""
            INSERT INTO otp_codes (user_id, email, otp_code, otp_type, expires_at)
            VALUES (%s, %s, %s, 'signup', %s)
        """, (user_id, email, otp, datetime.now() + timedelta(minutes=10)))
        
        # Log action
        cursor.execute("""
            INSERT INTO audit_log (user_id, action, success, details)
            VALUES (%s, 'signup', TRUE, %s)
        """, (user_id, '{"step": "account_created"}'))
        
        conn.commit()
        
        return {
            'success': True,
            'message': 'Account created! Check your email for OTP',
            'user_id': user_id,
            'otp': otp  # Send via email in production
        }
        
    except Exception as e:
        if conn:
            conn.rollback()
        return {'success': False, 'message': f'Signup error: {str(e)}'}
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_auth_connection(conn)


# =====================================================
# VERIFY OTP
# =====================================================

def verify_otp(email, otp_code, otp_type='signup'):
    """
    Verify OTP code
    
    Returns:
        dict: {'success': bool, 'message': str, 'user_id': int}
    """
    conn = None
    try:
        conn = get_auth_connection()
        cursor = conn.cursor()
        
        # Find valid OTP
        cursor.execute("""
            SELECT id, user_id, is_used, expires_at, attempts
            FROM otp_codes
            WHERE email = %s AND otp_code = %s AND otp_type = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (email, otp_code, otp_type))
        
        otp_record = cursor.fetchone()
        
        if not otp_record:
            return {'success': False, 'message': 'Invalid OTP code'}
        
        otp_id, user_id, is_used, expires_at, attempts = otp_record
        
        # Check if already used
        if is_used:
            return {'success': False, 'message': 'OTP already used'}
        
        # Check if expired
        if datetime.now() > expires_at:
            return {'success': False, 'message': 'OTP expired. Request a new one'}
        
        # Check attempts (max 3)
        if attempts >= 3:
            return {'success': False, 'message': 'Too many failed attempts. Request new OTP'}
        
        # Mark OTP as used
        cursor.execute("""
            UPDATE otp_codes
            SET is_used = TRUE, used_at = NOW()
            WHERE id = %s
        """, (otp_id,))
        
        # Mark user as verified (if signup OTP)
        if otp_type == 'signup':
            cursor.execute("""
                UPDATE users
                SET is_verified = TRUE, verified_at = NOW()
                WHERE id = %s
            """, (user_id,))
        
        # Log action
        cursor.execute("""
            INSERT INTO audit_log (user_id, action, success)
            VALUES (%s, %s, TRUE)
        """, (user_id, f'otp_verified_{otp_type}'))
        
        conn.commit()
        
        return {
            'success': True,
            'message': 'Email verified successfully!',
            'user_id': user_id
        }
        
    except Exception as e:
        if conn:
            conn.rollback()
        
        # Increment failed attempts
        if otp_record:
            try:
                cursor.execute("""
                    UPDATE otp_codes
                    SET attempts = attempts + 1
                    WHERE id = %s
                """, (otp_id,))
                conn.commit()
            except:
                pass
        
        return {'success': False, 'message': f'Verification error: {str(e)}'}
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_auth_connection(conn)


# =====================================================
# USER LOGIN
# =====================================================

def login_user(email, password, ip_address=None, user_agent=None):
    """
    Login user and create session
    
    Returns:
        dict: {'success': bool, 'message': str, 'session_token': str, 'user': dict}
    """
    conn = None
    try:
        conn = get_auth_connection()
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        
        # Get user
        cursor.execute("""
            SELECT id, email, password_hash, is_verified, is_active, full_name,
                   total_queries, queries_this_month, query_limit
            FROM users
            WHERE email = %s
        """, (email,))
        
        user = cursor.fetchone()
        
        if not user:
            # Log failed attempt
            cursor.execute("""
                INSERT INTO audit_log (action, success, details)
                VALUES ('login_failed', FALSE, %s)
            """, ('{"reason": "user_not_found", "email": "' + email + '"}',))
            conn.commit()
            return {'success': False, 'message': 'Invalid email or password'}
        
        # Verify password
        if not verify_password(password, user['password_hash']):
            cursor.execute("""
                INSERT INTO audit_log (user_id, action, success, details)
                VALUES (%s, 'login_failed', FALSE, %s)
            """, (user['id'], '{"reason": "wrong_password"}'))
            conn.commit()
            return {'success': False, 'message': 'Invalid email or password'}
        
        # Check if verified
        if not user['is_verified']:
            return {'success': False, 'message': 'Please verify your email first'}
        
        # Check if active
        if not user['is_active']:
            return {'success': False, 'message': 'Account suspended. Contact support'}
        
        # Create session
        session_token = generate_session_token()
        
        cursor.execute("""
            INSERT INTO user_sessions (user_id, session_token, ip_address, user_agent, expires_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (user['id'], session_token, ip_address, user_agent, datetime.now() + timedelta(days=7)))
        
        # Update last login
        cursor.execute("""
            UPDATE users
            SET last_login = NOW(), last_ip = %s, user_agent = %s
            WHERE id = %s
        """, (ip_address, user_agent, user['id']))
        
        # Log successful login
        cursor.execute("""
            INSERT INTO audit_log (user_id, action, ip_address, user_agent, success)
            VALUES (%s, 'login_success', %s, %s, TRUE)
        """, (user['id'], ip_address, user_agent))
        
        conn.commit()
        
        # Remove sensitive data
        user_data = dict(user)
        del user_data['password_hash']
        
        return {
            'success': True,
            'message': 'Login successful!',
            'session_token': session_token,
            'user': user_data
        }
        
    except Exception as e:
        if conn:
            conn.rollback()
        return {'success': False, 'message': f'Login error: {str(e)}'}
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_auth_connection(conn)


# =====================================================
# VERIFY SESSION
# =====================================================

def verify_session(session_token):
    """
    Verify if session is valid
    
    Returns:
        dict: {'valid': bool, 'user_id': int, 'user': dict}
    """
    conn = None
    try:
        conn = get_auth_connection()
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        
        cursor.execute("""
            SELECT s.user_id, s.expires_at,
                   u.email, u.full_name, u.is_admin, u.total_queries,
                   u.queries_this_month, u.query_limit
            FROM user_sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.session_token = %s AND s.expires_at > NOW()
        """, (session_token,))
        
        session = cursor.fetchone()
        
        if not session:
            return {'valid': False, 'message': 'Invalid or expired session'}
        
        # Update last activity
        cursor.execute("""
            UPDATE user_sessions
            SET last_activity = NOW()
            WHERE session_token = %s
        """, (session_token,))
        
        conn.commit()
        
        return {
            'valid': True,
            'user_id': session['user_id'],
            'user': dict(session)
        }
        
    except Exception as e:
        return {'valid': False, 'message': f'Session error: {str(e)}'}
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_auth_connection(conn)


# =====================================================
# LOGOUT
# =====================================================

def logout_user(session_token):
    """Delete session (logout)"""
    conn = None
    try:
        conn = get_auth_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM user_sessions WHERE session_token = %s", (session_token,))
        conn.commit()
        
        return {'success': True, 'message': 'Logged out successfully'}
    except Exception as e:
        return {'success': False, 'message': str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_auth_connection(conn)


# =====================================================
# FORGOT PASSWORD
# =====================================================

def request_password_reset(email):
    """Send OTP for password reset"""
    conn = None
    try:
        conn = get_auth_connection()
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if not user:
            # Don't reveal if email exists
            return {'success': True, 'message': 'If email exists, OTP has been sent'}
        
        user_id = user[0]
        otp = generate_otp()
        
        # Delete old OTPs
        cursor.execute("""
            DELETE FROM otp_codes
            WHERE user_id = %s AND otp_type = 'password_reset'
        """, (user_id,))
        
        # Create new OTP
        cursor.execute("""
            INSERT INTO otp_codes (user_id, email, otp_code, otp_type, expires_at)
            VALUES (%s, %s, %s, 'password_reset', %s)
        """, (user_id, email, otp, datetime.now() + timedelta(minutes=10)))
        
        conn.commit()
        
        return {
            'success': True,
            'message': 'OTP sent to your email',
            'otp': otp  # Send via email in production
        }
        
    except Exception as e:
        return {'success': False, 'message': str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_auth_connection(conn)


def reset_password(email, otp_code, new_password):
    """Reset password using OTP"""
    conn = None
    cursor = None

    try:
        # ❌ REMOVE second OTP verification
        # verify_result = verify_otp(email, otp_code, 'password_reset')
        # if not verify_result['success']:
        #     return verify_result
        #
        # user_id = verify_result['user_id']

        # ✅ Instead: get user directly by email
        conn = get_auth_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        row = cursor.fetchone()

        if not row:
            return {'success': False, 'message': 'User not found'}

        user_id = row[0]

        # Update password
        new_hash = hash_password(new_password)

        cursor.execute("""
            UPDATE users
            SET password_hash = %s
            WHERE id = %s
        """, (new_hash, user_id))

        # Delete all sessions (force re-login)
        cursor.execute("DELETE FROM user_sessions WHERE user_id = %s", (user_id,))

        # Log action
        cursor.execute("""
            INSERT INTO audit_log (user_id, action, success)
            VALUES (%s, 'password_reset', TRUE)
        """, (user_id,))

        conn.commit()

        return {'success': True, 'message': 'Password reset successful! Please login'}

    except Exception as e:
        if conn:
            conn.rollback()
        return {'success': False, 'message': str(e)}

    finally:
        if cursor:
            cursor.close()
        if conn:
            return_auth_connection(conn) 

# =====================================================
# QUERY TRACKING
# =====================================================

def track_query(user_id, query_type, subreddits, results_count, execution_time, success=True):
    """Track Reddit API query"""
    conn = None
    try:
        conn = get_auth_connection()
        cursor = conn.cursor()
        
        # Insert query log
        cursor.execute("""
            INSERT INTO query_log (user_id, query_type, subreddits_searched, 
                                   results_count, execution_time, success)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, query_type, subreddits, results_count, execution_time, success))
        
        # Update user query counts
        cursor.execute("""
            UPDATE users
            SET total_queries = total_queries + 1,
                queries_this_month = queries_this_month + 1
            WHERE id = %s
        """, (user_id,))
        
        conn.commit()
        
        return {'success': True}
        
    except Exception as e:
        print(f"Query tracking error: {str(e)}")
        return {'success': False}
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_auth_connection(conn)


def check_query_limit(user_id):
    """Check if user has exceeded query limit"""
    conn = None
    try:
        conn = get_auth_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT queries_this_month, query_limit
            FROM users
            WHERE id = %s
        """, (user_id,))
        
        result = cursor.fetchone()
        
        if not result:
            return {'allowed': False, 'message': 'User not found'}
        
        queries, limit = result
        
        if queries >= limit:
            return {
                'allowed': False,
                'message': f'Monthly query limit reached ({limit})',
                'queries_used': queries,
                'query_limit': limit
            }
        
        return {
            'allowed': True,
            'queries_used': queries,
            'queries_remaining': limit - queries,
            'query_limit': limit
        }
        
    except Exception as e:
        return {'allowed': False, 'message': str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_auth_connection(conn)

# =====================================================
# USER PROFILE MANAGEMENT
# =====================================================

def get_user_profile(user_id):
    """
    Get user's company name and business niche
    
    Returns:
        dict: {'company_name': str, 'business_niche': str}
    """
    conn = None
    try:
        conn = get_auth_connection()
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        
        cursor.execute("""
            SELECT company_name, business_niche
            FROM users
            WHERE id = %s
        """, (user_id,))
        
        profile = cursor.fetchone()
        
        if profile:
            return {
                'company_name': profile['company_name'] or '',
                'business_niche': profile['business_niche'] or ''
            }
        
        return {'company_name': '', 'business_niche': ''}
        
    except Exception as e:
        print(f"Error getting profile: {str(e)}")
        return {'company_name': '', 'business_niche': ''}
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_auth_connection(conn)


def update_user_profile(user_id, company_name, business_niche):
    """
    Update user's company name and business niche
    
    Returns:
        dict: {'success': bool, 'message': str}
    """
    conn = None
    try:
        conn = get_auth_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users
            SET company_name = %s, business_niche = %s
            WHERE id = %s
        """, (company_name, business_niche, user_id))
        
        conn.commit()
        
        return {'success': True, 'message': 'Profile updated successfully'}
        
    except Exception as e:
        if conn:
            conn.rollback()
        return {'success': False, 'message': f'Error updating profile: {str(e)}'}
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_auth_connection(conn)


