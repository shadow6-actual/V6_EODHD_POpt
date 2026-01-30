# webapp/stripe_integration.py
# Stripe payment integration for FolioForecast

import os
import logging
import stripe
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# Price IDs from Stripe Dashboard
PRICE_IDS = {
    'premium': os.environ.get('STRIPE_PREMIUM_PRICE_ID'),
    'pro': os.environ.get('STRIPE_PRO_PRICE_ID')
}

# Map Stripe price IDs back to tier names
PRICE_TO_TIER = {
    os.environ.get('STRIPE_PREMIUM_PRICE_ID'): 'premium',
    os.environ.get('STRIPE_PRO_PRICE_ID'): 'pro'
}


def get_stripe_publishable_key():
    """Return publishable key for frontend"""
    return os.environ.get('STRIPE_PUBLISHABLE_KEY')


def create_checkout_session(user_id, user_email, tier, success_url, cancel_url):
    """
    Create a Stripe Checkout session for subscription.
    
    Args:
        user_id: Your internal user ID (from Clerk)
        user_email: User's email for Stripe
        tier: 'premium' or 'pro'
        success_url: Where to redirect after success
        cancel_url: Where to redirect if cancelled
    
    Returns:
        Checkout session object with 'url' to redirect to
    """
    if tier not in PRICE_IDS:
        raise ValueError(f"Invalid tier: {tier}")
    
    price_id = PRICE_IDS[tier]
    if not price_id:
        raise ValueError(f"Price ID not configured for tier: {tier}")
    
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
            customer_email=user_email,
            metadata={
                'user_id': user_id,
                'tier': tier
            },
            subscription_data={
                'metadata': {
                    'user_id': user_id,
                    'tier': tier
                }
            }
        )
        logger.info(f"Created checkout session for user {user_id}, tier {tier}")
        return session
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {e}")
        raise


def create_customer_portal_session(stripe_customer_id, return_url):
    """
    Create a Stripe Customer Portal session for managing subscription.
    
    Args:
        stripe_customer_id: The Stripe customer ID
        return_url: Where to redirect after portal
    
    Returns:
        Portal session with 'url' to redirect to
    """
    try:
        session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=return_url
        )
        return session
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating portal session: {e}")
        raise


def get_subscription_from_customer(stripe_customer_id):
    """Get active subscription for a customer"""
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


def cancel_subscription(subscription_id, at_period_end=True):
    """
    Cancel a subscription.
    
    Args:
        subscription_id: Stripe subscription ID
        at_period_end: If True, cancel at end of billing period (recommended)
    """
    try:
        if at_period_end:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
        else:
            subscription = stripe.Subscription.delete(subscription_id)
        return subscription
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error cancelling subscription: {e}")
        raise


def handle_webhook_event(payload, sig_header):
    """
    Verify and parse a Stripe webhook event.
    
    Args:
        payload: Raw request body
        sig_header: Stripe-Signature header value
    
    Returns:
        Parsed event object
    """
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        return event
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {e}")
        raise
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {e}")
        raise
