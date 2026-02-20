"""
Database Configuration Module
Handles PostgreSQL connection and operations
"""

import psycopg2
from psycopg2 import pool, extras
import json
import os
from datetime import datetime
from dotenv import load_dotenv 

load_dotenv()

# =====================================================
# DATABASE CONNECTION POOL
# =====================================================
# Connection pool manages multiple database connections efficiently

connection_pool = None

def init_db_pool():
    """
    Initialize PostgreSQL connection pool
    Call this when your Flask app starts
    """
    global connection_pool
    
    try:
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            1,  # Minimum number of connections
            10, # Maximum number of connections
            host=os.getenv('DB_HOST', 'caboose.proxy.rlwy.net'),
            port=os.getenv('DB_PORT', '46006'),
            database=os.getenv('DB_NAME', 'railway'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'SFInAexrrqTRMcZelVliSsmPtYAsqoYo')
        )
        print("✅ PostgreSQL connection pool created successfully")
        return True
    except Exception as e:
        print(f"❌ Error creating connection pool: {str(e)}")
        return False


def get_db_connection():
    """
    Get a connection from the pool
    Always use with 'with' statement to ensure it's returned to pool
    """
    if connection_pool:
        return connection_pool.getconn()
    else:
        raise Exception("Connection pool not initialized. Call init_db_pool() first.")


def return_db_connection(conn):
    """
    Return a connection back to the pool
    """
    if connection_pool and conn:
        connection_pool.putconn(conn)


def close_db_pool():
    """
    Close all connections in the pool
    Call this when your Flask app shuts down
    """
    global connection_pool
    if connection_pool:
        connection_pool.closeall()
        print("🔒 PostgreSQL connection pool closed")


# =====================================================
# SAVED LEADS OPERATIONS
# =====================================================

def save_lead_to_db(lead_data, user_id=None):
    """
    Save a Reddit lead to the database
    
    Args:
        lead_data (dict): Lead information from Reddit + AI analysis
        user_id (int): ID of the user saving this lead
        
    Returns:
        dict: {'success': bool, 'message': str, 'lead_id': int}
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Prepare data
        insert_query = """
            INSERT INTO saved_leads (
                reddit_post_id, title, subreddit, author, url, content,
                score, num_comments, relevancy_score, reasoning,
                intent_strength, potential_value, key_pain_points,
                help_seeking_signals, ai_response, ai_response_generated,
                post_timestamp, user_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (reddit_post_id, user_id) DO NOTHING
            RETURNING id;
        """
        
        # Convert arrays to JSON
        key_pain_points_json = json.dumps(lead_data.get('key_pain_points', []))
        help_seeking_signals_json = json.dumps(lead_data.get('help_seeking_signals', []))
        
        # Parse timestamp
        post_timestamp = datetime.fromisoformat(lead_data.get('timestamp', datetime.now().isoformat()))
        
        values = (
            lead_data.get('id'),                    # reddit_post_id
            lead_data.get('title', ''),
            lead_data.get('subreddit', ''),
            lead_data.get('author', '[deleted]'),
            lead_data.get('url', ''),
            lead_data.get('content', ''),
            lead_data.get('score', 0),
            lead_data.get('num_comments', 0),
            lead_data.get('relevancy_score', 0),
            lead_data.get('reasoning', ''),
            lead_data.get('intent_strength', 'low'),
            lead_data.get('potential_value', 'low'),
            key_pain_points_json,
            help_seeking_signals_json,
            lead_data.get('ai_response'),
            lead_data.get('ai_response_generated', False),
            post_timestamp,
            user_id
        )
        
        cursor.execute(insert_query, values)
        result = cursor.fetchone()
        
        conn.commit()
        
        if result:
            return {
                'success': True,
                'message': 'Lead saved successfully',
                'lead_id': result[0]
            }
        else:
            return {
                'success': False,
                'message': 'Lead already exists in database',
                'lead_id': None
            }
        
    except Exception as e:
        if conn:
            conn.rollback()
        return {
            'success': False,
            'message': f'Error saving lead: {str(e)}',
            'lead_id': None
        }
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


def get_all_saved_leads(limit=100, offset=0, min_score=0, user_id=None):
    """
    Retrieve saved leads from database, filtered by user
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        
        query = """
            SELECT 
                id, reddit_post_id, title, subreddit, author, url, content,
                score, num_comments, relevancy_score, reasoning,
                intent_strength, potential_value, key_pain_points,
                help_seeking_signals, ai_response, ai_response_generated,
                post_timestamp, saved_at, user_notes, is_contacted, contacted_at
            FROM saved_leads
            WHERE relevancy_score >= %s AND user_id = %s
            ORDER BY saved_at DESC
            LIMIT %s OFFSET %s;
        """
        
        cursor.execute(query, (min_score, user_id, limit, offset))
        leads = cursor.fetchall()
        
        # Convert to list of dicts and parse JSON fields
        result = []
        for lead in leads:
            lead_dict = dict(lead)
            # Parse JSON fields back to arrays
            lead_dict['key_pain_points'] = lead_dict.get('key_pain_points', [])
            lead_dict['help_seeking_signals'] = lead_dict.get('help_seeking_signals', [])
            # Convert timestamps to ISO format
            if lead_dict.get('post_timestamp'):
                lead_dict['post_timestamp'] = lead_dict['post_timestamp'].isoformat()
            if lead_dict.get('saved_at'):
                lead_dict['saved_at'] = lead_dict['saved_at'].isoformat()
            if lead_dict.get('contacted_at'):
                lead_dict['contacted_at'] = lead_dict['contacted_at'].isoformat()
            result.append(lead_dict)
        
        return result
        
    except Exception as e:
        print(f"Error retrieving leads: {str(e)}")
        return []
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


def check_if_lead_saved(reddit_post_id):
    """
    Check if a lead is already saved in database
    
    Args:
        reddit_post_id (str): Reddit's unique post ID
        
    Returns:
        bool: True if saved, False if not
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "SELECT COUNT(*) FROM saved_leads WHERE reddit_post_id = %s;"
        cursor.execute(query, (reddit_post_id,))
        
        count = cursor.fetchone()[0]
        return count > 0
        
    except Exception as e:
        print(f"Error checking lead: {str(e)}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


def delete_saved_lead(reddit_post_id):
    """
    Delete a saved lead from database
    
    Args:
        reddit_post_id (str): Reddit's unique post ID
        
    Returns:
        dict: {'success': bool, 'message': str}
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "DELETE FROM saved_leads WHERE reddit_post_id = %s RETURNING id;"
        cursor.execute(query, (reddit_post_id,))
        
        result = cursor.fetchone()
        conn.commit()
        
        if result:
            return {'success': True, 'message': 'Lead deleted successfully'}
        else:
            return {'success': False, 'message': 'Lead not found'}
        
    except Exception as e:
        if conn:
            conn.rollback()
        return {'success': False, 'message': f'Error deleting lead: {str(e)}'}
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


def update_lead_notes(reddit_post_id, notes):
    """
    Update user notes for a saved lead
    
    Args:
        reddit_post_id (str): Reddit's unique post ID
        notes (str): User's notes
        
    Returns:
        dict: {'success': bool, 'message': str}
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            UPDATE saved_leads 
            SET user_notes = %s 
            WHERE reddit_post_id = %s 
            RETURNING id;
        """
        cursor.execute(query, (notes, reddit_post_id))
        
        result = cursor.fetchone()
        conn.commit()
        
        if result:
            return {'success': True, 'message': 'Notes updated successfully'}
        else:
            return {'success': False, 'message': 'Lead not found'}
        
    except Exception as e:
        if conn:
            conn.rollback()
        return {'success': False, 'message': f'Error updating notes: {str(e)}'}
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


def mark_lead_contacted(reddit_post_id, contacted=True):
    """
    Mark a lead as contacted or not contacted
    
    Args:
        reddit_post_id (str): Reddit's unique post ID
        contacted (bool): Whether lead was contacted
        
    Returns:
        dict: {'success': bool, 'message': str}
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if contacted:
            query = """
                UPDATE saved_leads 
                SET is_contacted = TRUE, contacted_at = CURRENT_TIMESTAMP 
                WHERE reddit_post_id = %s 
                RETURNING id;
            """
        else:
            query = """
                UPDATE saved_leads 
                SET is_contacted = FALSE, contacted_at = NULL 
                WHERE reddit_post_id = %s 
                RETURNING id;
            """
        
        cursor.execute(query, (reddit_post_id,))
        result = cursor.fetchone()
        conn.commit()
        
        if result:
            return {'success': True, 'message': 'Lead status updated'}
        else:
            return {'success': False, 'message': 'Lead not found'}
        
    except Exception as e:
        if conn:
            conn.rollback()
        return {'success': False, 'message': f'Error updating status: {str(e)}'}
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


def get_saved_leads_stats(user_id=None):
    """
    Get statistics about saved leads for a specific user
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Total saved leads
        cursor.execute("SELECT COUNT(*) FROM saved_leads WHERE user_id = %s;", (user_id,))
        stats['total_saved'] = cursor.fetchone()[0]
        
        # High quality leads (70+)
        cursor.execute("SELECT COUNT(*) FROM saved_leads WHERE relevancy_score >= 70 AND user_id = %s;", (user_id,))
        stats['high_quality'] = cursor.fetchone()[0]
        
        # Contacted leads
        cursor.execute("SELECT COUNT(*) FROM saved_leads WHERE is_contacted = TRUE AND user_id = %s;", (user_id,))
        stats['contacted'] = cursor.fetchone()[0]
        
        # Average score
        cursor.execute("SELECT AVG(relevancy_score) FROM saved_leads WHERE user_id = %s;", (user_id,))
        avg = cursor.fetchone()[0]
        stats['average_score'] = round(float(avg), 1) if avg else 0
        
        # Top 5 subreddits
        cursor.execute("""
            SELECT subreddit, COUNT(*) as count 
            FROM saved_leads 
            WHERE user_id = %s
            GROUP BY subreddit 
            ORDER BY count DESC 
            LIMIT 5;
        """, (user_id,))
        stats['top_subreddits'] = [{'name': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        return stats
        
    except Exception as e:
        print(f"Error getting stats: {str(e)}")
        return {}
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


# =====================================================
# DISMISSED POSTS OPERATIONS
# =====================================================

def dismiss_post(user_id, post_id):
    """
    Dismiss a post for 30 days (user won't see it again)
    
    Args:
        user_id (int): User ID
        post_id (str): Reddit post ID
        
    Returns:
        dict: {'success': bool, 'message': str}
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            INSERT INTO dismissed_posts (user_id, post_id)
            VALUES (%s, %s)
            ON CONFLICT (user_id, post_id) DO NOTHING
            RETURNING id;
        """
        
        cursor.execute(query, (user_id, post_id))
        result = cursor.fetchone()
        conn.commit()
        
        if result:
            return {'success': True, 'message': 'Post dismissed for 30 days'}
        else:
            return {'success': True, 'message': 'Post already dismissed'}
        
    except Exception as e:
        if conn:
            conn.rollback()
        return {'success': False, 'message': f'Error dismissing post: {str(e)}'}
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


def get_dismissed_post_ids(user_id):
    """
    Get all active dismissed post IDs for a user (not expired)
    
    Args:
        user_id (int): User ID
        
    Returns:
        set: Set of dismissed post IDs
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT post_id 
            FROM dismissed_posts
            WHERE user_id = %s AND expires_at > NOW();
        """
        
        cursor.execute(query, (user_id,))
        post_ids = {row[0] for row in cursor.fetchall()}
        
        return post_ids
        
    except Exception as e:
        print(f"Error getting dismissed posts: {str(e)}")
        return set()
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


def cleanup_expired_dismissed_posts():
    """
    Delete dismissed posts older than 30 days
    Should be run daily via cron or scheduler
    
    Returns:
        int: Number of rows deleted
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "DELETE FROM dismissed_posts WHERE expires_at < NOW();"
        cursor.execute(query)
        
        deleted_count = cursor.rowcount
        conn.commit()
        
        print(f"✅ Cleaned up {deleted_count} expired dismissed posts")
        return deleted_count
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Error cleaning dismissed posts: {str(e)}")
        return 0
    finally:
        if cursor:
            cursor.close()
        if conn: 

            return_db_connection(conn)
