"""Shared dependencies for API route handlers."""

from services.fund_engine import fund_engine
from services.risk_classifier import risk_classifier
from db.repository import repo


def get_fund_engine():
    """Dependency: returns the fund engine singleton."""
    return fund_engine


def get_risk_classifier():
    """Dependency: returns the risk classifier singleton."""
    return risk_classifier


def get_repository():
    """Dependency: returns the repository singleton."""
    return repo
