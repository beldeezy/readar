"""
Admin access control utilities.

Provides a single source of truth for admin allowlist parsing and validation.
"""

from typing import Optional


def normalize_email(email: str) -> str:
    """
    Normalize an email address for comparison.

    Args:
        email: Email address to normalize

    Returns:
        Normalized email (lowercase, trimmed whitespace)
    """
    return email.lower().strip()


def parse_admin_allowlist(raw: Optional[str]) -> set[str]:
    """
    Parse admin email allowlist from environment variable.

    Args:
        raw: Comma-separated list of admin emails (from ADMIN_EMAIL_ALLOWLIST env var)

    Returns:
        Set of normalized admin email addresses (empty entries filtered out)

    Examples:
        >>> parse_admin_allowlist("admin@example.com, USER@TEST.COM")
        {'admin@example.com', 'user@test.com'}

        >>> parse_admin_allowlist("")
        set()

        >>> parse_admin_allowlist("  admin@test.com  ,  ,  other@test.com  ")
        {'admin@test.com', 'other@test.com'}
    """
    if not raw:
        return set()

    emails = set()
    for email in raw.split(','):
        normalized = normalize_email(email)
        if normalized:  # Ignore empty entries
            emails.add(normalized)

    return emails


def is_admin_email(email: Optional[str], allowlist: set[str]) -> bool:
    """
    Check if an email is in the admin allowlist.

    Args:
        email: Email address to check (can be None)
        allowlist: Set of normalized admin emails

    Returns:
        True if email is in allowlist, False otherwise

    Examples:
        >>> allowlist = {'admin@test.com', 'user@test.com'}
        >>> is_admin_email('ADMIN@test.com', allowlist)
        True

        >>> is_admin_email('  user@TEST.com  ', allowlist)
        True

        >>> is_admin_email('other@test.com', allowlist)
        False

        >>> is_admin_email(None, allowlist)
        False
    """
    if not email:
        return False

    normalized = normalize_email(email)
    return normalized in allowlist
