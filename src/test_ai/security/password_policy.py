"""Password policy enforcement.

Validates passwords against configurable strength requirements:
- Minimum length
- Character class diversity (upper, lower, digits, special)
- Common password rejection
- Entropy estimation
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field


# Common passwords to reject (subset; in production, use a larger wordlist)
_COMMON_PASSWORDS = frozenset(
    {
        "password",
        "123456",
        "12345678",
        "qwerty",
        "abc123",
        "letmein",
        "admin",
        "welcome",
        "monkey",
        "master",
        "dragon",
        "login",
        "princess",
        "football",
        "shadow",
        "sunshine",
        "trustno1",
        "iloveyou",
        "batman",
        "password1",
        "password123",
        "changeme",
        "gorgon",
        "test",
        "demo",
    }
)


@dataclass
class PasswordPolicyConfig:
    """Configuration for password validation.

    Args:
        min_length: Minimum password length.
        max_length: Maximum password length (prevents DoS via bcrypt).
        require_uppercase: Require at least one uppercase letter.
        require_lowercase: Require at least one lowercase letter.
        require_digit: Require at least one digit.
        require_special: Require at least one special character.
        min_char_classes: Minimum number of character classes required.
        min_entropy_bits: Minimum estimated entropy in bits.
        reject_common: Reject passwords from the common password list.
        reject_username_in_password: Reject passwords containing the username.
        custom_reject_patterns: Additional regex patterns to reject.
    """

    min_length: int = 12
    max_length: int = 128
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digit: bool = True
    require_special: bool = False
    min_char_classes: int = 3
    min_entropy_bits: float = 40.0
    reject_common: bool = True
    reject_username_in_password: bool = True
    custom_reject_patterns: list[str] = field(default_factory=list)


@dataclass
class PasswordValidationResult:
    """Result of password validation."""

    valid: bool
    errors: list[str]
    strength_score: float  # 0.0 to 1.0
    entropy_bits: float

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "valid": self.valid,
            "errors": self.errors,
            "strength_score": round(self.strength_score, 2),
            "entropy_bits": round(self.entropy_bits, 1),
        }


def estimate_entropy(password: str) -> float:
    """Estimate the entropy of a password in bits.

    Uses character class pool size and length to estimate entropy.
    This is a simplified estimate — not a full zxcvbn-style analysis.

    Args:
        password: The password to analyze.

    Returns:
        Estimated entropy in bits.
    """
    pool_size = 0

    if re.search(r"[a-z]", password):
        pool_size += 26
    if re.search(r"[A-Z]", password):
        pool_size += 26
    if re.search(r"\d", password):
        pool_size += 10
    if re.search(r"[^a-zA-Z0-9]", password):
        pool_size += 32  # Approximate special char set

    if pool_size == 0:
        return 0.0

    return len(password) * math.log2(pool_size)


def _count_char_classes(password: str) -> int:
    """Count distinct character classes in password."""
    classes = 0
    if re.search(r"[a-z]", password):
        classes += 1
    if re.search(r"[A-Z]", password):
        classes += 1
    if re.search(r"\d", password):
        classes += 1
    if re.search(r"[^a-zA-Z0-9]", password):
        classes += 1
    return classes


def _compute_strength_score(
    password: str,
    entropy: float,
    config: PasswordPolicyConfig,
) -> float:
    """Compute a 0.0-1.0 strength score.

    Args:
        password: The password.
        entropy: Estimated entropy in bits.
        config: Policy configuration.

    Returns:
        Strength score from 0.0 (weak) to 1.0 (strong).
    """
    score = 0.0

    # Length contribution (up to 0.3)
    length_ratio = min(len(password) / 20, 1.0)
    score += length_ratio * 0.3

    # Entropy contribution (up to 0.4)
    entropy_ratio = min(entropy / 80.0, 1.0)
    score += entropy_ratio * 0.4

    # Character class diversity (up to 0.2)
    classes = _count_char_classes(password)
    score += (classes / 4) * 0.2

    # Uniqueness bonus (up to 0.1)
    unique_ratio = len(set(password)) / max(len(password), 1)
    score += unique_ratio * 0.1

    return min(score, 1.0)


def validate_password(
    password: str,
    username: str = "",
    config: PasswordPolicyConfig | None = None,
) -> PasswordValidationResult:
    """Validate a password against the policy.

    Args:
        password: The password to validate.
        username: Optional username (for containment check).
        config: Policy configuration (uses defaults if not provided).

    Returns:
        Validation result with errors and strength score.
    """
    config = config or PasswordPolicyConfig()
    errors: list[str] = []

    # Length checks
    if len(password) < config.min_length:
        errors.append(f"Password must be at least {config.min_length} characters long")
    if len(password) > config.max_length:
        errors.append(f"Password must not exceed {config.max_length} characters")

    # Character class checks
    char_classes = _count_char_classes(password)

    if config.require_uppercase and not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")

    if config.require_lowercase and not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")

    if config.require_digit and not re.search(r"\d", password):
        errors.append("Password must contain at least one digit")

    if config.require_special and not re.search(r"[^a-zA-Z0-9]", password):
        errors.append("Password must contain at least one special character")

    if char_classes < config.min_char_classes:
        errors.append(
            f"Password must use at least {config.min_char_classes} character types "
            f"(uppercase, lowercase, digits, special)"
        )

    # Entropy check
    entropy = estimate_entropy(password)
    if entropy < config.min_entropy_bits:
        errors.append(
            f"Password is too simple (estimated entropy: {entropy:.0f} bits, "
            f"minimum: {config.min_entropy_bits:.0f} bits)"
        )

    # Common password check
    if config.reject_common and password.lower() in _COMMON_PASSWORDS:
        errors.append("Password is too common — choose a more unique password")

    # Username containment check
    if (
        config.reject_username_in_password
        and username
        and len(username) >= 3
        and username.lower() in password.lower()
    ):
        errors.append("Password must not contain your username")

    # Custom patterns
    for pattern_str in config.custom_reject_patterns:
        pattern = re.compile(pattern_str, re.IGNORECASE)
        if pattern.search(password):
            errors.append("Password matches a rejected pattern")
            break

    # Compute strength score
    strength = _compute_strength_score(password, entropy, config)

    return PasswordValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        strength_score=strength,
        entropy_bits=entropy,
    )
