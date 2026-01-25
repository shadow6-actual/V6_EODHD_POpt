"""
Agreement API Routes
Add these routes to your app.py file

Usage:
    from agreement_routes import register_agreement_routes
    register_agreement_routes(app, get_db_connection, verify_clerk_token)
"""

from flask import request, jsonify
from functools import wraps
import logging

logger = logging.getLogger(__name__)

def register_agreement_routes(app, get_db_connection, verify_clerk_token):
    """
    Register agreement-related API routes.
    
    Args:
        app: Flask application
        get_db_connection: Function that returns a database connection
        verify_clerk_token: Function that verifies Clerk JWT and returns user_id
    """
    
    # Import the agreements module
    from agreements import (
        init_agreements_table, 
        record_agreement, 
        get_user_agreements,
        has_agreed_to_latest
    )
    
    # Current versions - update these when you change the agreements
    CURRENT_VERSIONS = {
        'terms': '1.0.0',
        'disclaimer': '1.0.0'
    }
    
    @app.route('/api/agreement-status', methods=['GET'])
    def api_agreement_status():
        """Get user's agreement status"""
        try:
            # Get auth token
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'error': 'No authorization token'}), 401
            
            token = auth_header.split(' ')[1]
            user_id = verify_clerk_token(token)
            
            if not user_id:
                return jsonify({'error': 'Invalid token'}), 401
            
            # Get agreements from database
            conn = get_db_connection()
            try:
                agreements = get_user_agreements(conn, user_id)
                
                # Add info about whether they have latest versions
                agreements['has_latest_terms'] = has_agreed_to_latest(
                    conn, user_id, 'terms', CURRENT_VERSIONS['terms']
                )
                agreements['has_latest_disclaimer'] = has_agreed_to_latest(
                    conn, user_id, 'disclaimer', CURRENT_VERSIONS['disclaimer']
                )
                agreements['current_terms_version'] = CURRENT_VERSIONS['terms']
                agreements['current_disclaimer_version'] = CURRENT_VERSIONS['disclaimer']
                
                return jsonify(agreements)
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error getting agreement status: {e}")
            return jsonify({'error': str(e)}), 500
    
    
    @app.route('/api/record-agreement', methods=['POST'])
    def api_record_agreement():
        """Record a user's agreement acceptance"""
        try:
            # Get auth token
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'error': 'No authorization token'}), 401
            
            token = auth_header.split(' ')[1]
            user_id = verify_clerk_token(token)
            
            if not user_id:
                return jsonify({'error': 'Invalid token'}), 401
            
            # Get request data
            data = request.get_json()
            agreement_type = data.get('agreement_type')
            version = data.get('version')
            
            if agreement_type not in ['terms', 'disclaimer']:
                return jsonify({'error': 'Invalid agreement type'}), 400
            
            if not version:
                # Use current version if not specified
                version = CURRENT_VERSIONS.get(agreement_type)
            
            # Get client info for audit
            ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
            user_agent = request.headers.get('User-Agent', '')[:500]  # Truncate if too long
            
            # Record the agreement
            conn = get_db_connection()
            try:
                result = record_agreement(
                    conn, 
                    user_id, 
                    agreement_type, 
                    version,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                return jsonify(result)
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error recording agreement: {e}")
            return jsonify({'error': str(e)}), 500


# SQL to add to your database initialization
INIT_SQL = """
-- Run this SQL to create the user_agreements table

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
);

CREATE INDEX IF NOT EXISTS idx_user_agreements_user_id ON user_agreements(user_id);

-- Example query to see all user agreements:
-- SELECT * FROM user_agreements ORDER BY agreed_at DESC;
"""
