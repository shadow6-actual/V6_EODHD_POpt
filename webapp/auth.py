# webapp/auth.py
# PURPOSE: Clerk authentication middleware for Flask
# Verifies JWT tokens from Clerk and provides user context

import os
import logging
import requests
import jwt
from functools import wraps
from flask import request, jsonify, g
from jwt import PyJWKClient

logger = logging.getLogger("Auth")

# Clerk Configuration
CLERK_PUBLISHABLE_KEY = os.getenv('CLERK_PUBLISHABLE_KEY', '')
CLERK_FRONTEND_API = os.getenv('CLERK_FRONTEND_API', 'https://diverse-ewe-15.clerk.accounts.dev')
CLERK_SECRET_KEY = os.getenv('CLERK_SECRET_KEY', '')

# JWKS URL for verifying tokens
CLERK_JWKS_URL = f"{CLERK_FRONTEND_API}/.well-known/jwks.json"

# Cache the JWKS client
_jwks_client = None

def get_jwks_client():
    """Get or create JWKS client for token verification"""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(CLERK_JWKS_URL)
    return _jwks_client


def verify_clerk_token(token):
    """
    Verify a Clerk JWT token and return the decoded payload.
    
    Returns:
        dict: Decoded token payload with user info
        None: If verification fails
    """
    try:
        # Get the signing key from JWKS
        jwks_client = get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        # Verify and decode the token
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False}  # Clerk doesn't always set audience
        )
        
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return None


def get_user_from_clerk(user_id):
    """
    Fetch full user details from Clerk Backend API.
    
    Args:
        user_id: Clerk user ID (e.g., 'user_2abc123...')
    
    Returns:
        dict: User data including username
        None: If fetch fails
    """
    if not CLERK_SECRET_KEY:
        logger.error("CLERK_SECRET_KEY not configured")
        return None
    
    try:
        response = requests.get(
            f"https://api.clerk.com/v1/users/{user_id}",
            headers={
                "Authorization": f"Bearer {CLERK_SECRET_KEY}",
                "Content-Type": "application/json"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Failed to fetch user {user_id}: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error fetching user from Clerk: {e}")
        return None


def require_auth(f):
    """
    Decorator to require authentication for a route.
    
    Sets g.user_id and g.username if authenticated.
    Returns 401 if no valid token.
    
    Usage:
        @app.route('/api/protected')
        @require_auth
        def protected_route():
            user_id = g.user_id
            username = g.username
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid authorization header'}), 401
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        
        # Verify token
        payload = verify_clerk_token(token)
        
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        # Extract user info from token
        g.user_id = payload.get('sub')  # Clerk user ID
        g.session_id = payload.get('sid')  # Session ID
        
        # Get username from token metadata or fetch from Clerk
        # Clerk stores username in the token if configured
        g.username = payload.get('username')
        
        # If username not in token, fetch from Clerk API
        if not g.username and g.user_id:
            user_data = get_user_from_clerk(g.user_id)
            if user_data:
                g.username = user_data.get('username')
        
        return f(*args, **kwargs)
    
    return decorated_function


def optional_auth(f):
    """
    Decorator for routes that work with or without authentication.
    
    Sets g.user_id and g.username if authenticated, None otherwise.
    Never returns 401.
    
    Usage:
        @app.route('/api/public')
        @optional_auth
        def public_route():
            if g.user_id:
                # Logged in user
            else:
                # Anonymous user
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        g.user_id = None
        g.username = None
        g.session_id = None
        
        auth_header = request.headers.get('Authorization', '')
        
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            payload = verify_clerk_token(token)
            
            if payload:
                g.user_id = payload.get('sub')
                g.session_id = payload.get('sid')
                g.username = payload.get('username')
                
                if not g.username and g.user_id:
                    user_data = get_user_from_clerk(g.user_id)
                    if user_data:
                        g.username = user_data.get('username')
        
        return f(*args, **kwargs)
    
    return decorated_function


def get_clerk_config():
    """
    Return Clerk configuration for frontend.
    Safe to expose - only contains publishable key.
    """
    return {
        'publishableKey': CLERK_PUBLISHABLE_KEY,
        'frontendApi': CLERK_FRONTEND_API
    }
