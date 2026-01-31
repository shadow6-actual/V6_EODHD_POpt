# webapp/stripe_integration.py
# PURPOSE: Stripe payment integration for FolioForecast subscriptions
# Handles checkout sessions, customer portal, webhooks, and subscription management

import os
import logging
import stripe
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
# Force redeploy - env vars updated 2026-01-31


# =============================================================================
# STRIPE INITIALIZATION
# =============================================================================

# Initialize Stripe with secret key from environment
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# Log whether Stripe is configured (without exposing the key)
if stripe.api_key:
    logger.info("Stripe API key configured")
else:
    logger.warning("STRIPE_SECRET_KEY not set - payment features will not work")

# =============================================================================
# PRICE CONFIGURATION
# =============================================================================

# Price IDs from Stripe Dashboard - these map our tier names to Stripe price IDs
# Set these in Railway environment variables after creating products in Stripe
# NOTE: We use functions to read at runtime, not import time, to handle delayed env var loading

def get_price_ids():
    """Get price IDs at runtime (not cached at import time)"""
    return {
        'premium': os.environ.get('STRIPE_PREMIUM_PRICE_ID'),
        'pro': os.environ.get('STRIPE_PRO_PRICE_ID')
    }

def get_price_to_tier_map():
    """Build reverse mapping of price IDs to tier names at runtime"""
    mapping = {}
    for tier, price_id in get_price_ids().items():
        if price_id:
            mapping[price_id] = tier
    return mapping

# Log configuration status at startup (may show as not set if env vars load later)
_startup_price_ids = get_price_ids()
for tier, price_id in _startup_price_ids.items():
    if price_id:
        logger.info(f"Stripe {tier} price ID configured: {price_id[:20]}...")
    else:
        logger.warning(f"STRIPE_{tier.upper()}_PRICE_ID not set - will check again at runtime")


# =============================================================================
# PUBLIC FUNCTIONS
# =============================================================================

def get_stripe_publishable_key():
    """
    Return the publishable key for frontend Stripe.js initialization.
    This key is safe to expose in the browser.
    
    Returns:
        str: Stripe publishable key or None if not configured
    """
    return os.environ.get('STRIPE_PUBLISHABLE_KEY')


def is_stripe_configured():
    """
    Check if Stripe is properly configured with all required keys.
    
    Returns:
        dict: Configuration status for each required setting
    """
    price_ids = get_price_ids()
    return {
        'secret_key': bool(os.environ.get('STRIPE_SECRET_KEY')),
        'publishable_key': bool(os.environ.get('STRIPE_PUBLISHABLE_KEY')),
        'webhook_secret': bool(os.environ.get('STRIPE_WEBHOOK_SECRET')),
        'premium_price_id': bool(price_ids.get('premium')),
        'pro_price_id': bool(price_ids.get('pro')),
        'fully_configured': all([
            os.environ.get('STRIPE_SECRET_KEY'),
            os.environ.get('STRIPE_PUBLISHABLE_KEY'),
            os.environ.get('STRIPE_WEBHOOK_SECRET'),
            price_ids.get('premium'),
            price_ids.get('pro')
        ])
    }


def create_checkout_session(user_id, user_email, tier, success_url, cancel_url):
    """
    Create a Stripe Checkout session for a new subscription.
    
    This redirects the user to Stripe's hosted checkout page where they
    can enter payment details securely.
    
    Args:
        user_id: Your internal user ID (will be stored in Stripe metadata)
        user_email: User's email address (pre-fills checkout form)
        tier: Subscription tier ('premium' or 'pro')
        success_url: URL to redirect to after successful payment
        cancel_url: URL to redirect to if user cancels
    
    Returns:
        stripe.checkout.Session: Session object with 'url' property for redirect
    
    Raises:
        ValueError: If tier is invalid or price ID not configured
        stripe.error.StripeError: If Stripe API call fails
    """
    
    # Validate tier and get price ID at runtime
    price_ids = get_price_ids()
    if tier not in price_ids:
        raise ValueError(f"Invalid tier: {tier}. Must be one of: {list(price_ids.keys())}")
    
    price_id = price_ids[tier]
    if not price_id:
        raise ValueError(
            f"Price ID not configured for tier: {tier}. "
            f"Set STRIPE_{tier.upper()}_PRICE_ID environment variable."
        )
    
    try:
        session = stripe.checkout.Session.create(
            mode='subscription',
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            # Pre-fill customer email
            customer_email=user_email,
            # Store our user ID in metadata for webhook processing
            metadata={
                'user_id': str(user_id),
                'tier': tier
            },
            # Also store in subscription metadata
            subscription_data={
                'metadata': {
                    'user_id': str(user_id),
                    'tier': tier
                }
            },
            # Allow promotion codes if you set them up in Stripe
            allow_promotion_codes=True,
            # Collect billing address for tax purposes
            billing_address_collection='auto',
        )
        
        logger.info(f"Created checkout session {session.id} for user {user_id}, tier {tier}")
        return session
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {e}")
        raise


def create_customer_portal_session(stripe_customer_id, return_url):
    """
    Create a Stripe Customer Portal session for subscription management.
    
    The Customer Portal allows users to:
    - Update payment method
    - View billing history
    - Cancel subscription
    - Download invoices
    
    Args:
        stripe_customer_id: The Stripe customer ID (stored in your database)
        return_url: URL to redirect to when user exits the portal
    
    Returns:
        stripe.billing_portal.Session: Session object with 'url' property
    
    Raises:
        ValueError: If customer ID is not provided
        stripe.error.StripeError: If Stripe API call fails
    """
    if not stripe_customer_id:
        raise ValueError("Stripe customer ID is required")
    
    try:
        session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=return_url
        )
        
        logger.info(f"Created portal session for customer {stripe_customer_id}")
        return session
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating portal session: {e}")
        raise


def get_customer(stripe_customer_id):
    """
    Retrieve a Stripe customer by ID.
    
    Args:
        stripe_customer_id: The Stripe customer ID
    
    Returns:
        stripe.Customer: Customer object or None if not found
    """
    if not stripe_customer_id:
        return None
    
    try:
        return stripe.Customer.retrieve(stripe_customer_id)
    except stripe.error.InvalidRequestError:
        # Customer doesn't exist
        return None
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error retrieving customer: {e}")
        return None


def get_subscription(stripe_subscription_id):
    """
    Retrieve a Stripe subscription by ID.
    
    Args:
        stripe_subscription_id: The Stripe subscription ID
    
    Returns:
        stripe.Subscription: Subscription object or None if not found
    """
    if not stripe_subscription_id:
        return None
    
    try:
        return stripe.Subscription.retrieve(stripe_subscription_id)
    except stripe.error.InvalidRequestError:
        # Subscription doesn't exist
        return None
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error retrieving subscription: {e}")
        return None


def get_active_subscription_for_customer(stripe_customer_id):
    """
    Get the active subscription for a customer (if any).
    
    Args:
        stripe_customer_id: The Stripe customer ID
    
    Returns:
        stripe.Subscription: Active subscription or None
    """
    if not stripe_customer_id:
        return None
    
    try:
        subscriptions = stripe.Subscription.list(
            customer=stripe_customer_id,
            status='active',
            limit=1
        )
        
        if subscriptions.data:
            return subscriptions.data[0]
        return None
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error getting subscription: {e}")
        return None


def cancel_subscription(stripe_subscription_id, at_period_end=True):
    """
    Cancel a subscription.
    
    Args:
        stripe_subscription_id: The Stripe subscription ID
        at_period_end: If True (recommended), cancel at end of billing period.
                       If False, cancel immediately with no refund.
    
    Returns:
        stripe.Subscription: Updated subscription object
    
    Raises:
        ValueError: If subscription ID not provided
        stripe.error.StripeError: If Stripe API call fails
    """
    if not stripe_subscription_id:
        raise ValueError("Subscription ID is required")
    
    try:
        if at_period_end:
            # Cancel at end of period - user keeps access until then
            subscription = stripe.Subscription.modify(
                stripe_subscription_id,
                cancel_at_period_end=True
            )
            logger.info(f"Subscription {stripe_subscription_id} scheduled for cancellation at period end")
        else:
            # Cancel immediately
            subscription = stripe.Subscription.delete(stripe_subscription_id)
            logger.info(f"Subscription {stripe_subscription_id} cancelled immediately")
        
        return subscription
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error cancelling subscription: {e}")
        raise


def reactivate_subscription(stripe_subscription_id):
    """
    Reactivate a subscription that was scheduled for cancellation.
    
    Args:
        stripe_subscription_id: The Stripe subscription ID
    
    Returns:
        stripe.Subscription: Updated subscription object
    """
    if not stripe_subscription_id:
        raise ValueError("Subscription ID is required")
    
    try:
        subscription = stripe.Subscription.modify(
            stripe_subscription_id,
            cancel_at_period_end=False
        )
        logger.info(f"Subscription {stripe_subscription_id} reactivated")
        return subscription
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error reactivating subscription: {e}")
        raise


# =============================================================================
# WEBHOOK HANDLING
# =============================================================================

def handle_webhook_event(payload, sig_header):
    """
    Verify and parse a Stripe webhook event.
    
    This function verifies the webhook signature to ensure the event
    actually came from Stripe and hasn't been tampered with.
    
    Args:
        payload: Raw request body (bytes)
        sig_header: Value of the 'Stripe-Signature' header
    
    Returns:
        stripe.Event: Parsed and verified event object
    
    Raises:
        ValueError: If payload is invalid
        stripe.error.SignatureVerificationError: If signature is invalid
    """
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    
    if not webhook_secret:
        logger.error("STRIPE_WEBHOOK_SECRET not configured - cannot verify webhooks")
        raise ValueError("Webhook secret not configured")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        logger.info(f"Webhook verified: {event['type']} (id: {event['id']})")
        return event
        
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {e}")
        raise
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {e}")
        raise


def get_tier_from_subscription(subscription):
    """
    Extract the tier name from a Stripe subscription object.
    
    Args:
        subscription: Stripe subscription object or dict
    
    Returns:
        str: Tier name ('premium', 'pro') or 'free' if not recognized
    """
    try:
        # Handle both Stripe objects and dicts (from webhooks)
        if hasattr(subscription, 'get'):
            items = subscription.get('items', {}).get('data', [])
        else:
            items = subscription.items.data if hasattr(subscription, 'items') else []
        
        if items:
            # Get the first item's price ID
            if hasattr(items[0], 'get'):
                price_id = items[0].get('price', {}).get('id')
            else:
                price_id = items[0].price.id if hasattr(items[0], 'price') else None
            
            price_to_tier = get_price_to_tier_map()
            if price_id and price_id in price_to_tier:
                return price_to_tier[price_id]
                        
        # Fallback: check metadata
        metadata = subscription.get('metadata', {}) if hasattr(subscription, 'get') else getattr(subscription, 'metadata', {})
        if metadata and 'tier' in metadata:
            return metadata['tier']
        
        return 'free'
        
    except Exception as e:
        logger.error(f"Error extracting tier from subscription: {e}")
        return 'free'


def get_subscription_status_details(subscription):
    """
    Get detailed status information from a subscription.
    
    Args:
        subscription: Stripe subscription object
    
    Returns:
        dict: Status details including tier, status, period dates
    """
    try:
        return {
            'tier': get_tier_from_subscription(subscription),
            'status': subscription.status,
            'cancel_at_period_end': subscription.cancel_at_period_end,
            'current_period_start': datetime.fromtimestamp(subscription.current_period_start).isoformat(),
            'current_period_end': datetime.fromtimestamp(subscription.current_period_end).isoformat(),
            'canceled_at': datetime.fromtimestamp(subscription.canceled_at).isoformat() if subscription.canceled_at else None,
        }
    except Exception as e:
        logger.error(f"Error getting subscription details: {e}")
        return None


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def format_amount_for_display(amount_cents, currency='usd'):
    """
    Format a Stripe amount (in cents) for display.
    
    Args:
        amount_cents: Amount in cents (e.g., 1400 for $14.00)
        currency: Currency code (default: 'usd')
    
    Returns:
        str: Formatted amount (e.g., '$14.00')
    """
    if currency.lower() == 'usd':
        return f"${amount_cents / 100:.2f}"
    else:
        return f"{amount_cents / 100:.2f} {currency.upper()}"


def get_price_display(tier):
    """
    Get the display price for a tier.
    
    Args:
        tier: Tier name ('premium' or 'pro')
    
    Returns:
        str: Price display string or None if tier not found
    """
    prices = {
        'premium': '$14/month',
        'pro': '$29/month'
    }
    return prices.get(tier)
