"""
Tests for ClientSieve field mapping and condition building.
"""

import pytest
from app.manager.mail.ClientSieve import ClientSieve


class TestFieldMapping:
    """Test _map_field_name method."""

    def setup_method(self):
        """Setup a ClientSieve instance for testing."""
        self.client = ClientSieve(
            server="localhost",
            port=4190,
            encryption="none",
            auth_mech="plain"
        )

    def test_map_standard_fields(self):
        """Test mapping of standard header fields."""
        assert self.client._map_field_name("subject") == "subject"
        assert self.client._map_field_name("from") == "from"
        assert self.client._map_field_name("to") == "to"
        assert self.client._map_field_name("cc") == "cc"

    def test_map_body_field(self):
        """Test mapping of body field."""
        assert self.client._map_field_name("body") == "body"

    def test_map_size_field(self):
        """Test mapping of size field (returns empty string)."""
        assert self.client._map_field_name("size") == ""

    def test_map_custom_header(self):
        """Test mapping of custom header field."""
        assert self.client._map_field_name("header", "X-Custom-Header") == "X-Custom-Header"
        assert self.client._map_field_name("header") == ""

    def test_map_unknown_field(self):
        """Test mapping of unknown field (returns as-is)."""
        result = self.client._map_field_name("unknown_field")
        assert result == "unknown_field"


class TestConditionBuilding:
    """Test _flatten_rules and condition building."""

    def setup_method(self):
        """Setup a ClientSieve instance for testing."""
        self.client = ClientSieve(
            server="localhost",
            port=4190,
            encryption="none",
            auth_mech="plain"
        )

    def test_simple_condition(self):
        """Test building a simple condition."""
        rule = {
            "field": "subject",
            "operator": "contains",
            "value": "test"
        }
        conditions = []
        self.client._flatten_rules(rule, conditions)
        
        assert len(conditions) == 1
        assert conditions[0] == ("subject", ":contains", "test")

    def test_cc_or_to_condition(self):
        """Test 'cc or to' field expands to anyof condition."""
        rule = {
            "field": "cc or to",
            "operator": "contains",
            "value": "test@example.com"
        }
        conditions = []
        self.client._flatten_rules(rule, conditions)
        
        # Should create an anyof with two conditions
        assert len(conditions) == 1
        assert conditions[0][0] == "anyof"
        assert len(conditions[0][1]) == 2
        assert conditions[0][1][0] == ("cc", ":contains", "test@example.com")
        assert conditions[0][1][1] == ("to", ":contains", "test@example.com")

    def test_size_condition(self):
        """Test size field condition."""
        rule = {
            "field": "size",
            "operator": "is",
            "value": "5M"
        }
        conditions = []
        self.client._flatten_rules(rule, conditions)
        
        assert len(conditions) == 1
        assert conditions[0] == ("size", ":is", "5M")

    def test_body_condition(self):
        """Test body field condition."""
        rule = {
            "field": "body",
            "operator": "contains",
            "value": "important"
        }
        conditions = []
        self.client._flatten_rules(rule, conditions)
        
        assert len(conditions) == 1
        assert conditions[0] == ("body", ":contains", "important")

    def test_nested_and_rules(self):
        """Test nested AND rules."""
        rule = {
            "op": "and",
            "rules": [
                {
                    "field": "from",
                    "operator": "contains",
                    "value": "boss@company.com"
                },
                {
                    "field": "subject",
                    "operator": "contains",
                    "value": "urgent"
                }
            ]
        }
        conditions = []
        self.client._flatten_rules(rule, conditions)
        
        assert len(conditions) == 1
        assert conditions[0][0] == "allof"
        assert len(conditions[0][1]) == 2

    def test_nested_or_rules(self):
        """Test nested OR rules."""
        rule = {
            "op": "or",
            "rules": [
                {
                    "field": "from",
                    "operator": "contains",
                    "value": "admin@company.com"
                },
                {
                    "field": "from",
                    "operator": "contains",
                    "value": "support@company.com"
                }
            ]
        }
        conditions = []
        self.client._flatten_rules(rule, conditions)
        
        assert len(conditions) == 1
        assert conditions[0][0] == "anyof"
        assert len(conditions[0][1]) == 2


class TestExtensionDetection:
    """Test detection of required Sieve extensions."""

    def setup_method(self):
        """Setup a ClientSieve instance for testing."""
        self.client = ClientSieve(
            server="localhost",
            port=4190,
            encryption="none",
            auth_mech="plain"
        )

    def test_detect_body_extension(self):
        """Test detection of body extension requirement."""
        rule = {
            "field": "body",
            "operator": "contains",
            "value": "test"
        }
        extensions = self.client._detect_required_extensions_from_rules(rule)
        
        assert "body" in extensions

    def test_detect_no_extension_for_standard_fields(self):
        """Test that standard fields don't require extensions."""
        rule = {
            "field": "from",
            "operator": "contains",
            "value": "test@example.com"
        }
        extensions = self.client._detect_required_extensions_from_rules(rule)
        
        assert len(extensions) == 0

    def test_detect_extensions_in_nested_rules(self):
        """Test extension detection in nested rules."""
        rule = {
            "op": "and",
            "rules": [
                {
                    "field": "from",
                    "operator": "contains",
                    "value": "test@example.com"
                },
                {
                    "field": "body",
                    "operator": "contains",
                    "value": "urgent"
                }
            ]
        }
        extensions = self.client._detect_required_extensions_from_rules(rule)
        
        assert "body" in extensions
        assert len(extensions) == 1

    def test_detect_no_extension_for_cc_or_to(self):
        """Test that 'cc or to' field doesn't require extensions."""
        # The anyof for cc or to is handled at flatten_rules level,
        # not at extension detection level
        rule = {
            "field": "cc or to",
            "operator": "contains",
            "value": "test@example.com"
        }
        extensions = self.client._detect_required_extensions_from_rules(rule)
        
        # cc or to shouldn't require additional extensions
        assert len(extensions) == 0


class TestComplexScenarios:
    """Test complex filtering scenarios."""

    def setup_method(self):
        """Setup a ClientSieve instance for testing."""
        self.client = ClientSieve(
            server="localhost",
            port=4190,
            encryption="none",
            auth_mech="plain"
        )

    def test_executive_emails_filter(self):
        """Test a complex executive emails filter."""
        rule = {
            "op": "and",
            "rules": [
                {
                    "field": "cc or to",
                    "operator": "contains",
                    "value": "ceo@company.com"
                },
                {
                    "field": "subject",
                    "operator": "contains",
                    "value": "Q4 Report"
                }
            ]
        }
        conditions = []
        self.client._flatten_rules(rule, conditions)
        
        # Should have allof with anyof inside it
        assert len(conditions) == 1
        assert conditions[0][0] == "allof"

    def test_multi_criteria_filter(self):
        """Test a filter with multiple different fields."""
        rule = {
            "op": "or",
            "rules": [
                {
                    "field": "body",
                    "operator": "contains",
                    "value": "invoice"
                },
                {
                    "field": "size",
                    "operator": "is",
                    "value": "10M"
                }
            ]
        }
        conditions = []
        extensions = set()
        
        self.client._flatten_rules(rule, conditions)
        extensions.update(self.client._detect_required_extensions_from_rules(rule))
        
        assert len(conditions) == 1
        assert conditions[0][0] == "anyof"
        assert "body" in extensions
