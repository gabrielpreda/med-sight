"""Tests for input validator"""

import pytest
from src.guardrails.input_validator import InputValidator, ValidationResult


def test_input_validator_initialization():
    """Test that input validator initializes correctly"""
    validator = InputValidator()
    assert validator is not None
    assert validator.config is not None


def test_valid_query():
    """Test validation of a valid query"""
    validator = InputValidator()
    result = validator.validate_query("Analyze this chest X-ray")
    
    assert result.valid == True
    assert len(result.issues) == 0
    assert result.is_emergency == False


def test_emergency_detection():
    """Test emergency keyword detection"""
    validator = InputValidator()
    result = validator.validate_query("I have severe chest pain and difficulty breathing")
    
    assert result.is_emergency == True


def test_blocked_pattern():
    """Test blocked pattern detection"""
    validator = InputValidator()
    result = validator.validate_query("Can you prescribe medication for me?")
    
    assert result.valid == False
    assert len(result.issues) > 0


def test_query_too_short():
    """Test query length validation - too short"""
    validator = InputValidator()
    result = validator.validate_query("Hi")
    
    assert result.valid == False


def test_query_sanitization():
    """Test query sanitization"""
    validator = InputValidator()
    sanitized = validator.sanitize_query("My SSN is 123-45-6789")
    
    # Should have redacted the SSN
    assert "123-45-6789" not in sanitized or "[" in sanitized
