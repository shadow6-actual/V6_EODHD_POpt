"""
User Agreements Module
Handles storage and retrieval of user agreement records (Terms, Disclaimer)
"""

from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def init_agreements_table(conn):
    """
    Create the user_agreements table if it doesn't exist.
    This should be called during app initialization.
    """
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_agreements (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            agreement_type VARCHAR(50) NOT NULL,
            version VARCHAR(20) NOT NULL,
            agreed_at TIMESTAMP NOT NULL,
            ip_address VARCHAR(45),
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, agreement_type, version)
        )
    ''')
    
    # Create index for faster lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_user_agreements_user_id 
        ON user_agreements(user_id)
    ''')
    
    conn.commit()
    logger.info("User agreements table initialized")


def record_agreement(conn, user_id, agreement_type, version, ip_address=None, user_agent=None):
    """
    Record a user's agreement to Terms or Disclaimer.
    
    Args:
        conn: Database connection
        user_id: Clerk user ID
        agreement_type: 'terms' or 'disclaimer'
        version: Version string (e.g., '1.0.0')
        ip_address: Optional IP address for audit purposes
        user_agent: Optional user agent for audit purposes
    
    Returns:
        dict with agreement details
    """
    cursor = conn.cursor()
    agreed_at = datetime.utcnow()
    
    try:
        cursor.execute('''
            INSERT INTO user_agreements (user_id, agreement_type, version, agreed_at, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, agreement_type, version) 
            DO UPDATE SET 
                agreed_at = EXCLUDED.agreed_at,
                ip_address = EXCLUDED.ip_address,
                user_agent = EXCLUDED.user_agent
            RETURNING id, agreed_at
        ''', (user_id, agreement_type, version, agreed_at, ip_address, user_agent))
        
        result = cursor.fetchone()
        conn.commit()
        
        logger.info(f"Recorded {agreement_type} agreement v{version} for user {user_id}")
        
        return {
            'id': result[0],
            'user_id': user_id,
            'agreement_type': agreement_type,
            'version': version,
            'agreed_at': result[1].isoformat()
        }
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error recording agreement: {e}")
        raise


def get_user_agreements(conn, user_id):
    """
    Get all agreements for a user.
    
    Args:
        conn: Database connection
        user_id: Clerk user ID
    
    Returns:
        dict with agreement status
    """
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT agreement_type, version, agreed_at
        FROM user_agreements
        WHERE user_id = %s
        ORDER BY agreed_at DESC
    ''', (user_id,))
    
    rows = cursor.fetchall()
    
    result = {
        'user_id': user_id,
        'terms_agreed_at': None,
        'terms_version': None,
        'disclaimer_agreed_at': None,
        'disclaimer_version': None
    }
    
    for row in rows:
        agreement_type, version, agreed_at = row
        if agreement_type == 'terms' and result['terms_agreed_at'] is None:
            result['terms_agreed_at'] = agreed_at.isoformat()
            result['terms_version'] = version
        elif agreement_type == 'disclaimer' and result['disclaimer_agreed_at'] is None:
            result['disclaimer_agreed_at'] = agreed_at.isoformat()
            result['disclaimer_version'] = version
    
    return result


def has_agreed_to_latest(conn, user_id, agreement_type, required_version):
    """
    Check if user has agreed to the latest version of an agreement.
    
    Args:
        conn: Database connection
        user_id: Clerk user ID
        agreement_type: 'terms' or 'disclaimer'
        required_version: The version that must be agreed to
    
    Returns:
        bool
    """
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT COUNT(*) FROM user_agreements
        WHERE user_id = %s 
        AND agreement_type = %s 
        AND version = %s
    ''', (user_id, agreement_type, required_version))
    
    count = cursor.fetchone()[0]
    return count > 0


def get_agreement_history(conn, user_id):
    """
    Get full agreement history for a user (for audit purposes).
    
    Args:
        conn: Database connection
        user_id: Clerk user ID
    
    Returns:
        list of agreement records
    """
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, agreement_type, version, agreed_at, ip_address, created_at
        FROM user_agreements
        WHERE user_id = %s
        ORDER BY agreed_at DESC
    ''', (user_id,))
    
    rows = cursor.fetchall()
    
    return [{
        'id': row[0],
        'agreement_type': row[1],
        'version': row[2],
        'agreed_at': row[3].isoformat(),
        'ip_address': row[4],
        'created_at': row[5].isoformat()
    } for row in rows]
