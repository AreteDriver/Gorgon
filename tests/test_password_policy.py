"""Tests for password policy enforcement."""

import sys


sys.path.insert(0, "src")

from test_ai.security.password_policy import (
    PasswordPolicyConfig,
    estimate_entropy,
    validate_password,
)


class TestEstimateEntropy:
    """Tests for entropy estimation."""

    def test_empty_password(self):
        """Empty password has zero entropy."""
        assert estimate_entropy("") == 0.0

    def test_short_password(self):
        """Short passwords have low entropy."""
        entropy = estimate_entropy("abc")
        assert entropy < 20

    def test_mixed_chars_higher_entropy(self):
        """Mixed character classes increase entropy."""
        lower_only = estimate_entropy("abcdefghijkl")
        mixed = estimate_entropy("Abcdef1234!@")
        assert mixed > lower_only

    def test_longer_is_higher(self):
        """Longer passwords have higher entropy."""
        short = estimate_entropy("Abc123!")
        long = estimate_entropy("Abc123!Abc123!Abc123!")
        assert long > short


class TestPasswordPolicyConfig:
    """Tests for PasswordPolicyConfig."""

    def test_default_values(self):
        """Config has reasonable defaults."""
        config = PasswordPolicyConfig()
        assert config.min_length == 12
        assert config.max_length == 128
        assert config.require_uppercase is True
        assert config.require_lowercase is True
        assert config.require_digit is True
        assert config.min_char_classes == 3

    def test_custom_values(self):
        """Config accepts custom values."""
        config = PasswordPolicyConfig(
            min_length=8,
            require_special=True,
            min_char_classes=4,
        )
        assert config.min_length == 8
        assert config.require_special is True


class TestValidatePassword:
    """Tests for password validation."""

    def test_strong_password(self):
        """Strong password passes validation."""
        result = validate_password("MyStr0ngP@ssword2024!")
        assert result.valid is True
        assert len(result.errors) == 0
        assert result.strength_score > 0.5

    def test_too_short(self):
        """Short password fails."""
        result = validate_password("Abc1!")
        assert result.valid is False
        assert any("at least" in e for e in result.errors)

    def test_too_long(self):
        """Very long password fails."""
        result = validate_password("A1!" + "x" * 200)
        assert result.valid is False
        assert any("exceed" in e for e in result.errors)

    def test_missing_uppercase(self):
        """Missing uppercase fails."""
        result = validate_password("alllowercase123!")
        assert result.valid is False
        assert any("uppercase" in e for e in result.errors)

    def test_missing_lowercase(self):
        """Missing lowercase fails."""
        result = validate_password("ALLUPPERCASE123!")
        assert result.valid is False
        assert any("lowercase" in e for e in result.errors)

    def test_missing_digit(self):
        """Missing digit fails."""
        result = validate_password("NoDigitsHere!!")
        assert result.valid is False
        assert any("digit" in e for e in result.errors)

    def test_common_password_rejected(self):
        """Common passwords are rejected."""
        result = validate_password("password")
        assert result.valid is False
        assert any("common" in e.lower() for e in result.errors)

    def test_username_in_password(self):
        """Password containing username is rejected."""
        result = validate_password("MyAlicePassword1!", username="alice")
        assert result.valid is False
        assert any("username" in e for e in result.errors)

    def test_short_username_not_checked(self):
        """Very short usernames are not checked for containment."""
        result = validate_password("Contains_Ab_1234!", username="ab")
        # "ab" is only 2 chars, should not trigger username check
        assert not any("username" in e for e in result.errors)

    def test_entropy_too_low(self):
        """Low-entropy passwords fail."""
        config = PasswordPolicyConfig(
            min_length=3,
            require_uppercase=False,
            require_lowercase=False,
            require_digit=False,
            min_char_classes=1,
            min_entropy_bits=100,  # Very high threshold
            reject_common=False,
        )
        result = validate_password("aaa", config=config)
        assert result.valid is False
        assert any(
            "entropy" in e.lower() or "simple" in e.lower() for e in result.errors
        )

    def test_custom_reject_pattern(self):
        """Custom reject patterns work."""
        config = PasswordPolicyConfig(
            min_length=6,
            require_uppercase=False,
            require_lowercase=False,
            require_digit=False,
            min_char_classes=1,
            min_entropy_bits=10,
            reject_common=False,
            custom_reject_patterns=[r"^test"],
        )
        result = validate_password("testpassword", config=config)
        assert result.valid is False
        assert any("rejected pattern" in e for e in result.errors)

    def test_strength_score_range(self):
        """Strength score is between 0 and 1."""
        for pw in ["a", "Abc1!", "MyStr0ngP@ssword2024!", "x" * 50]:
            result = validate_password(pw)
            assert 0.0 <= result.strength_score <= 1.0

    def test_result_serialization(self):
        """Result can be serialized to dict."""
        result = validate_password("Test1234!!")
        data = result.to_dict()
        assert "valid" in data
        assert "errors" in data
        assert "strength_score" in data
        assert "entropy_bits" in data

    def test_special_char_requirement(self):
        """Special character requirement when enabled."""
        config = PasswordPolicyConfig(
            min_length=8,
            require_special=True,
            min_char_classes=4,
            min_entropy_bits=20,
        )
        result = validate_password("NoSpecial123", config=config)
        assert any("special" in e for e in result.errors)
