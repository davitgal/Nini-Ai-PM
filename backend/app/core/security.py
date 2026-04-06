"""Webhook signature verification for ClickUp."""

import hashlib
import hmac


def verify_clickup_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify ClickUp webhook signature (HMAC-SHA256)."""
    if not secret:
        return True  # Skip verification if no secret configured
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
