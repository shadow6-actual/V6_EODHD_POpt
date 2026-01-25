"""
User Agreement Tracking Module for FolioForecast

This module handles the storage and retrieval of user agreement acceptances
for Terms of Service and Investment Disclaimer documents.

Database Schema:
    user_agreements table:
        - id: Primary key
        - user_id: Foreign key to users table
        - agreement_type: 'terms' or 'disclaimer'
        - version: Document version (e.g., '1.0.0')
        - accepted_at: Timestamp of acceptance
        - ip_address: User's IP at time of acceptance
        - user_agent: Browser user agent string

Version History:
    - 1.0.0: Initial release (January 25, 2026)
"""

import os
import logging
from datetime import datetime
from functools import wraps
from flask import request, jsonify, g

# Configure logging
logger = logging.getLogger(__name__)

# Current document versions - update these when legal docs change
CURRENT_VERSIONS = {
    'terms': '1.0.0',
    'disclaimer': '1.0.0',
    'privacy': '1.0.0'
}

# Required agreements for app access
REQUIRED_AGREEMENTS = ['terms', 'disclaimer']


def get_db_connection():
    """Get database connection from Flask g or create new one."""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    if 'db' not in g:
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            # Handle Railway's postgres:// vs postgresql:// URLs
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            g.db = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        else:
            raise Exception("DATABASE_URL not configured")
    return g.db


def init_agreements_table():
    """
    Create the user_agreements table if it doesn't exist.
    Call this during app initialization.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_agreements (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                agreement_type VARCHAR(50) NOT NULL,
                version VARCHAR(20) NOT NULL,
                accepted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ip_address VARCHAR(45),
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                -- Ensure one record per user per agreement type per version
                UNIQUE(user_id, agreement_type, version)
            );
            
            -- Index for quick lookups
            CREATE INDEX IF NOT EXISTS idx_user_agreements_user_id 
                ON user_agreements(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_agreements_type_version 
                ON user_agreements(agreement_type, version);
        """)
        conn.commit()
        logger.info("user_agreements table initialized successfully")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error initializing user_agreements table: {e}")
        raise
    finally:
        cursor.close()


def get_client_ip():
    """Extract client IP address from request, handling proxies."""
    # Check for forwarded headers (behind proxy/load balancer)
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr


def record_agreement_acceptance(user_id: int, agreement_type: str) -> dict:
    """
    Record a user's acceptance of an agreement.
    
    Args:
        user_id: The user's database ID
        agreement_type: 'terms' or 'disclaimer'
        
    Returns:
        dict with success status and agreement details
    """
    if agreement_type not in CURRENT_VERSIONS:
        return {
            'success': False,
            'error': f'Invalid agreement type: {agreement_type}'
        }
    
    version = CURRENT_VERSIONS[agreement_type]
    ip_address = get_client_ip()
    user_agent = request.headers.get('User-Agent', '')[:500]  # Truncate long UAs
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Use INSERT ... ON CONFLICT to handle re-acceptance gracefully
        cursor.execute("""
            INSERT INTO user_agreements (user_id, agreement_type, version, ip_address, user_agent, accepted_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, agreement_type, version) 
            DO UPDATE SET 
                accepted_at = CURRENT_TIMESTAMP,
                ip_address = EXCLUDED.ip_address,
                user_agent = EXCLUDED.user_agent
            RETURNING id, accepted_at
        """, (user_id, agreement_type, version, ip_address, user_agent))
        
        result = cursor.fetchone()
        conn.commit()
        
        logger.info(f"User {user_id} accepted {agreement_type} v{version}")
        
        return {
            'success': True,
            'agreement_type': agreement_type,
            'version': version,
            'accepted_at': result['accepted_at'].isoformat() if result else None
        }
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error recording agreement acceptance: {e}")
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        cursor.close()


def get_user_agreements(user_id: int) -> dict:
    """
    Get all current agreement acceptances for a user.
    
    Args:
        user_id: The user's database ID
        
    Returns:
        dict mapping agreement_type to acceptance details
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT agreement_type, version, accepted_at
            FROM user_agreements
            WHERE user_id = %s
            ORDER BY accepted_at DESC
        """, (user_id,))
        
        results = cursor.fetchall()
        
        # Build dict of most recent acceptance per agreement type
        agreements = {}
        for row in results:
            atype = row['agreement_type']
            if atype not in agreements:
                agreements[atype] = {
                    'version': row['version'],
                    'accepted_at': row['accepted_at'].isoformat() if row['accepted_at'] else None,
                    'current_version': CURRENT_VERSIONS.get(atype),
                    'needs_update': row['version'] != CURRENT_VERSIONS.get(atype)
                }
        
        return agreements
        
    except Exception as e:
        logger.error(f"Error fetching user agreements: {e}")
        return {}
    finally:
        cursor.close()


def check_required_agreements(user_id: int) -> dict:
    """
    Check if user has accepted all required agreements at current versions.
    
    Args:
        user_id: The user's database ID
        
    Returns:
        dict with:
            - all_accepted: bool
            - missing: list of agreement types not yet accepted
            - outdated: list of agreements needing re-acceptance due to version change
    """
    user_agreements = get_user_agreements(user_id)
    
    missing = []
    outdated = []
    
    for agreement_type in REQUIRED_AGREEMENTS:
        if agreement_type not in user_agreements:
            missing.append(agreement_type)
        elif user_agreements[agreement_type]['needs_update']:
            outdated.append(agreement_type)
    
    all_accepted = len(missing) == 0 and len(outdated) == 0
    
    return {
        'all_accepted': all_accepted,
        'missing': missing,
        'outdated': outdated,
        'current_versions': CURRENT_VERSIONS,
        'user_agreements': user_agreements
    }


def require_agreements(f):
    """
    Decorator to require all agreements before allowing endpoint access.
    Use with @require_auth decorator - this should come after auth.
    
    Example:
        @app.route('/api/protected')
        @require_auth
        @require_agreements
        def protected_endpoint():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # g.user should be set by @require_auth decorator
        if not hasattr(g, 'user') or not g.user:
            return jsonify({'error': 'Authentication required'}), 401
        
        user_id = g.user.get('id')
        if not user_id:
            return jsonify({'error': 'User ID not found'}), 401
        
        agreement_status = check_required_agreements(user_id)
        
        if not agreement_status['all_accepted']:
            return jsonify({
                'error': 'Agreement acceptance required',
                'agreements_required': True,
                'missing': agreement_status['missing'],
                'outdated': agreement_status['outdated'],
                'current_versions': CURRENT_VERSIONS
            }), 403
        
        return f(*args, **kwargs)
    
    return decorated_function


# Flask route handlers - add these to app.py

def register_agreement_routes(app):
    """
    Register agreement-related routes with the Flask app.
    Call this during app initialization.
    
    Usage in app.py:
        from agreements import register_agreement_routes, init_agreements_table
        
        # After app creation
        register_agreement_routes(app)
        
        # During startup
        with app.app_context():
            init_agreements_table()
    """
    from auth import require_auth, optional_auth
    
    @app.route('/api/agreements/status', methods=['GET'])
    @require_auth
    def get_agreement_status():
        """Get current user's agreement status."""
        user_id = g.user.get('id')
        if not user_id:
            return jsonify({'error': 'User ID not found'}), 401
        
        status = check_required_agreements(user_id)
        return jsonify(status)
    
    @app.route('/api/agreements/accept', methods=['POST'])
    @require_auth
    def accept_agreement():
        """Accept an agreement."""
        user_id = g.user.get('id')
        if not user_id:
            return jsonify({'error': 'User ID not found'}), 401
        
        data = request.get_json()
        if not data or 'agreement_type' not in data:
            return jsonify({'error': 'agreement_type is required'}), 400
        
        agreement_type = data['agreement_type']
        
        if agreement_type not in REQUIRED_AGREEMENTS:
            return jsonify({'error': f'Invalid agreement type: {agreement_type}'}), 400
        
        result = record_agreement_acceptance(user_id, agreement_type)
        
        if result['success']:
            # Return updated status after acceptance
            status = check_required_agreements(user_id)
            return jsonify({
                'success': True,
                'accepted': result,
                'status': status
            })
        else:
            return jsonify(result), 500
    
    @app.route('/api/agreements/accept-all', methods=['POST'])
    @require_auth
    def accept_all_agreements():
        """Accept all required agreements at once."""
        user_id = g.user.get('id')
        if not user_id:
            return jsonify({'error': 'User ID not found'}), 401
        
        results = []
        for agreement_type in REQUIRED_AGREEMENTS:
            result = record_agreement_acceptance(user_id, agreement_type)
            results.append(result)
        
        all_success = all(r['success'] for r in results)
        
        if all_success:
            status = check_required_agreements(user_id)
            return jsonify({
                'success': True,
                'accepted': results,
                'status': status
            })
        else:
            return jsonify({
                'success': False,
                'results': results
            }), 500
    
    @app.route('/api/agreements/versions', methods=['GET'])
    def get_agreement_versions():
        """Get current versions of all agreements (public endpoint)."""
        return jsonify({
            'versions': CURRENT_VERSIONS,
            'required': REQUIRED_AGREEMENTS
        })
    
    logger.info("Agreement routes registered successfully")
