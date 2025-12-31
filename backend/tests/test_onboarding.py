"""Tests for onboarding normalization function."""
import pytest
from app.models import BusinessStage
from app.routers.onboarding import normalize_business_stage


def test_normalize_business_stage_uppercase_with_underscore():
    """Test normalization function with uppercase enum name like "PRE_REVENUE"."""
    result = normalize_business_stage("PRE_REVENUE")
    assert result == BusinessStage.PRE_REVENUE
    assert result.value == "pre-revenue"


def test_normalize_business_stage_lowercase_with_underscore():
    """Test normalization function with lowercase with underscore."""
    result = normalize_business_stage("pre_revenue")
    assert result == BusinessStage.PRE_REVENUE
    assert result.value == "pre-revenue"


def test_normalize_business_stage_lowercase_with_hyphen():
    """Test normalization function with lowercase with hyphen (already correct)."""
    result = normalize_business_stage("pre-revenue")
    assert result == BusinessStage.PRE_REVENUE
    assert result.value == "pre-revenue"


def test_normalize_business_stage_enum_object():
    """Test normalization function with enum object."""
    result = normalize_business_stage(BusinessStage.PRE_REVENUE)
    assert result == BusinessStage.PRE_REVENUE
    assert result.value == "pre-revenue"


def test_normalize_business_stage_early_revenue():
    """Test normalization with EARLY_REVENUE."""
    result = normalize_business_stage("EARLY_REVENUE")
    assert result == BusinessStage.EARLY_REVENUE
    assert result.value == "early-revenue"


def test_normalize_business_stage_idea():
    """Test normalization with IDEA."""
    result = normalize_business_stage("IDEA")
    assert result == BusinessStage.IDEA
    assert result.value == "idea"


def test_normalize_business_stage_scaling():
    """Test normalization with SCALING."""
    result = normalize_business_stage("SCALING")
    assert result == BusinessStage.SCALING
    assert result.value == "scaling"

