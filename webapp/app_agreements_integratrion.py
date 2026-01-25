"""
App.py Integration Guide for Agreements Module

This file shows the code snippets to add to your existing app.py 
to integrate the agreement tracking functionality.

Add these sections to your app.py file in the appropriate places.
"""

# ============================================================
# STEP 1: Add imports at the top of app.py
# ============================================================

# Add to existing imports:
from agreements import (
    register_agreement_routes,
    init_agreements_table,
    require_agreements,
    CURRENT_VERSIONS
)


# ============================================================
# STEP 2: Register agreement routes after app creation
# ============================================================

# Add after: app = Flask(__name__)
# and after other route registrations:

register_agreement_routes(app)


# ============================================================
# STEP 3: Initialize agreements table on startup
# ============================================================

# Add to your startup/initialization code:

def init_database():
    """Initialize all database tables."""
    with app.app_context():
        # ... existing table initialization ...
        
        # Add this line:
        init_agreements_table()


# If using a startup hook:
@app.before_first_request
def startup():
    init_agreements_table()


# ============================================================
# STEP 4: Add /pricing route
# ============================================================

@app.route('/pricing')
def pricing_page():
    """Render pricing page."""
    return render_template('pricing.html')


# ============================================================
# STEP 5: (Optional) Protect sensitive endpoints with agreements
# ============================================================

# For endpoints that should require agreement acceptance,
# add the @require_agreements decorator AFTER @require_auth:

@app.route('/api/optimize', methods=['POST'])
@require_auth
@require_agreements  # Add this line
def optimize_portfolio():
    """Run portfolio optimization."""
    # ... existing code ...
    pass


# ============================================================
# STEP 6: Database Migration SQL (run manually or via migration)
# ============================================================

"""
Run this SQL in your PostgreSQL database to create the table:

CREATE TABLE IF NOT EXISTS user_agreements (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agreement_type VARCHAR(50) NOT NULL,
    version VARCHAR(20) NOT NULL,
    accepted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, agreement_type, version)
);

CREATE INDEX IF NOT EXISTS idx_user_agreements_user_id 
    ON user_agreements(user_id);
CREATE INDEX IF NOT EXISTS idx_user_agreements_type_version 
    ON user_agreements(agreement_type, version);
"""


# ============================================================
# COMPLETE EXAMPLE: Full app.py structure
# ============================================================

"""
Here's how your complete app.py should be structured:

```python
import os
from flask import Flask, render_template, jsonify, request, g

# Auth imports
from auth import require_auth, optional_auth, verify_jwt

# Agreements import
from agreements import (
    register_agreement_routes,
    init_agreements_table,
    require_agreements
)

# Subscription imports  
from subscription import (
    get_user_tier,
    check_tier_limit,
    TIER_LIMITS
)

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')

# Register agreement routes
register_agreement_routes(app)


# Database initialization
def init_db():
    with app.app_context():
        # Create users table, portfolios table, etc.
        init_agreements_table()

# Initialize on startup
init_db()


# Page routes
@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/app')
def app_page():
    return render_template('index.html')

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/disclaimer')
def disclaimer():
    return render_template('disclaimer.html')


# Protected API endpoints
@app.route('/api/optimize', methods=['POST'])
@require_auth
@require_agreements  # User must accept terms + disclaimer
def optimize():
    # ... optimization logic ...
    pass


if __name__ == '__main__':
    app.run(debug=True)
```
"""
