"""Security API routes — 2FA, sessions, API keys, threat monitoring, and feature flags."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Header, Request

from test_ai import api_state as state
from test_ai.api_errors import bad_request, not_found, responses, unauthorized
from test_ai.api_models import (
    APIKeyCreateFullRequest,
    APIKeyCreateResponse,
    APIKeyListResponse,
    APIKeyRotateResponse,
    FeatureFlagCreateRequest,
    FeatureFlagResponse,
    LoginWithTOTPRequest,
    LoginWithTOTPResponse,
    PasswordValidateRequest,
    PasswordValidateResponse,
    PlatformInfoResponse,
    SessionListResponse,
    ThreatEventsResponse,
    ThreatStatsResponse,
    TOTPSetupResponse,
    TOTPStatusResponse,
    TOTPVerifyRequest,
)
from test_ai.api_routes.auth import verify_auth
from test_ai.config import get_settings
from test_ai.platform.device_detection import detect_platform
from test_ai.platform.feature_flags import (
    FeatureFlag,
    FlagStatus,
    get_feature_flag_manager,
)
from test_ai.security.api_key_manager import APIKeyScope, get_api_key_manager
from test_ai.security.password_policy import validate_password
from test_ai.security.session_manager import DeviceInfo, get_session_manager
from test_ai.security.threat_detection import get_threat_detector
from test_ai.security.totp import get_totp_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["security"])


# ---------------------------------------------------------------------------
# Two-Factor Authentication
# ---------------------------------------------------------------------------


@router.post(
    "/auth/2fa/setup",
    response_model=TOTPSetupResponse,
    responses=responses(401),
)
def setup_2fa(
    authorization: Optional[str] = Header(None),
) -> TOTPSetupResponse:
    """Initiate 2FA setup. Returns secret and QR provisioning URI.

    The user must confirm setup by providing a valid TOTP code via
    the ``/auth/2fa/confirm`` endpoint before 2FA is enforced.
    """
    user_id = verify_auth(authorization)
    totp = get_totp_manager()

    if totp.is_enabled(user_id):
        raise bad_request("2FA is already enabled. Disable it first to re-enroll.")

    setup = totp.setup_totp(user_id)
    return TOTPSetupResponse(
        secret=setup.secret,
        provisioning_uri=setup.provisioning_uri,
        backup_codes=setup.backup_codes,
    )


@router.post(
    "/auth/2fa/confirm",
    response_model=TOTPStatusResponse,
    responses=responses(400, 401),
)
def confirm_2fa(
    body: TOTPVerifyRequest,
    authorization: Optional[str] = Header(None),
) -> TOTPStatusResponse:
    """Confirm 2FA setup by verifying a code from the authenticator app."""
    user_id = verify_auth(authorization)
    totp = get_totp_manager()

    if not totp.confirm_setup(user_id, body.code):
        raise bad_request("Invalid TOTP code. Scan the QR code and try again.")

    return TOTPStatusResponse(
        enabled=True,
        backup_codes_remaining=totp.get_backup_code_count(user_id),
    )


@router.get(
    "/auth/2fa/status",
    response_model=TOTPStatusResponse,
    responses=responses(401),
)
def get_2fa_status(
    authorization: Optional[str] = Header(None),
) -> TOTPStatusResponse:
    """Check 2FA status for the authenticated user."""
    user_id = verify_auth(authorization)
    totp = get_totp_manager()

    return TOTPStatusResponse(
        enabled=totp.is_enabled(user_id),
        backup_codes_remaining=totp.get_backup_code_count(user_id),
    )


@router.delete(
    "/auth/2fa",
    response_model=TOTPStatusResponse,
    responses=responses(400, 401),
)
def disable_2fa(
    body: TOTPVerifyRequest,
    authorization: Optional[str] = Header(None),
) -> TOTPStatusResponse:
    """Disable 2FA. Requires a valid TOTP code for verification."""
    user_id = verify_auth(authorization)
    totp = get_totp_manager()

    if not totp.is_enabled(user_id):
        raise bad_request("2FA is not enabled.")

    # Verify current code before disabling
    if not totp.verify(user_id, body.code):
        raise bad_request("Invalid TOTP code.")

    totp.disable(user_id)
    return TOTPStatusResponse(enabled=False, backup_codes_remaining=0)


@router.post(
    "/auth/2fa/backup-codes",
    responses=responses(400, 401),
)
def regenerate_backup_codes(
    body: TOTPVerifyRequest,
    authorization: Optional[str] = Header(None),
):
    """Regenerate backup codes. Requires TOTP verification."""
    user_id = verify_auth(authorization)
    totp = get_totp_manager()

    if not totp.verify(user_id, body.code):
        raise bad_request("Invalid TOTP code.")

    codes = totp.regenerate_backup_codes(user_id)
    if codes is None:
        raise bad_request("2FA is not enabled.")

    return {"backup_codes": codes, "count": len(codes)}


@router.post(
    "/auth/login/2fa",
    response_model=LoginWithTOTPResponse,
    responses=responses(401, 429),
)
@state.limiter.limit("5/minute")
def login_with_2fa(
    request: Request,
    body: LoginWithTOTPRequest,
) -> LoginWithTOTPResponse:
    """Login with optional 2FA support.

    If the user has 2FA enabled and no ``totp_code`` is provided,
    returns ``requires_2fa: true`` without issuing a token.
    """
    from test_ai.auth import create_access_token

    settings = get_settings()

    if not settings.verify_credentials(body.user_id, body.password):
        raise unauthorized("Invalid credentials")

    totp = get_totp_manager()

    # Check if 2FA is required
    if totp.is_enabled(body.user_id):
        if not body.totp_code:
            return LoginWithTOTPResponse(requires_2fa=True)

        if not totp.verify(body.user_id, body.totp_code):
            raise unauthorized("Invalid 2FA code")

    token = create_access_token(body.user_id)

    # Create session with device info
    session_mgr = get_session_manager()
    ua = request.headers.get("user-agent", "")
    platform_info = detect_platform(ua)
    device = DeviceInfo(
        user_agent=ua,
        ip_address=request.client.host if request.client else "",
        platform=platform_info.platform.value,
        device_type=platform_info.device_type.value,
        os=platform_info.os,
        browser=platform_info.browser,
    )
    session = session_mgr.create_session(body.user_id, device)

    logger.info(
        "User '%s' logged in (2FA: %s)", body.user_id, totp.is_enabled(body.user_id)
    )
    return LoginWithTOTPResponse(
        access_token=token,
        session_id=session.session_id,
    )


# ---------------------------------------------------------------------------
# Session Management
# ---------------------------------------------------------------------------


@router.get(
    "/auth/sessions",
    response_model=SessionListResponse,
    responses=responses(401),
)
def list_sessions(
    authorization: Optional[str] = Header(None),
) -> SessionListResponse:
    """List all active sessions for the authenticated user."""
    user_id = verify_auth(authorization)
    session_mgr = get_session_manager()
    sessions = session_mgr.get_user_sessions(user_id)
    return SessionListResponse(sessions=sessions, total=len(sessions))


@router.delete(
    "/auth/sessions/{session_id}",
    responses=responses(401, 404),
)
def revoke_session(
    session_id: str,
    authorization: Optional[str] = Header(None),
):
    """Revoke a specific session."""
    verify_auth(authorization)
    session_mgr = get_session_manager()

    if not session_mgr.revoke_session(session_id):
        raise not_found("Session", session_id)

    return {"status": "revoked", "session_id": session_id}


@router.delete(
    "/auth/sessions",
    responses=responses(401),
)
def revoke_all_sessions(
    authorization: Optional[str] = Header(None),
):
    """Revoke all sessions for the authenticated user."""
    user_id = verify_auth(authorization)
    session_mgr = get_session_manager()
    count = session_mgr.revoke_all_sessions(user_id)
    return {"status": "revoked", "count": count}


# ---------------------------------------------------------------------------
# API Key Management
# ---------------------------------------------------------------------------


@router.post(
    "/auth/api-keys",
    response_model=APIKeyCreateResponse,
    responses=responses(400, 401),
)
def create_api_key(
    body: APIKeyCreateFullRequest,
    authorization: Optional[str] = Header(None),
) -> APIKeyCreateResponse:
    """Create a new API key with specified scopes.

    The raw key is returned only once in this response.
    Store it securely — it cannot be retrieved later.
    """
    user_id = verify_auth(authorization)
    manager = get_api_key_manager()

    # Parse scopes
    try:
        scopes = {APIKeyScope(s) for s in body.scopes}
    except ValueError as e:
        valid = [s.value for s in APIKeyScope]
        raise bad_request(f"Invalid scope: {e}. Valid scopes: {valid}")

    raw_key, api_key = manager.create_key(
        user_id=user_id,
        name=body.name,
        scopes=scopes,
        expires_days=body.expires_days,
        ip_whitelist=body.ip_whitelist,
        rate_limit_rpm=body.rate_limit_rpm,
    )

    return APIKeyCreateResponse(
        raw_key=raw_key,
        key_id=api_key.key_id,
        name=api_key.name,
        scopes=sorted(s.value for s in api_key.scopes),
        expires_at=api_key.to_dict().get("expires_at"),
    )


@router.get(
    "/auth/api-keys",
    response_model=APIKeyListResponse,
    responses=responses(401),
)
def list_api_keys(
    authorization: Optional[str] = Header(None),
) -> APIKeyListResponse:
    """List all API keys for the authenticated user."""
    user_id = verify_auth(authorization)
    manager = get_api_key_manager()
    return APIKeyListResponse(keys=manager.list_keys(user_id))


@router.post(
    "/auth/api-keys/{key_id}/rotate",
    response_model=APIKeyRotateResponse,
    responses=responses(401, 404),
)
def rotate_api_key(
    key_id: str,
    authorization: Optional[str] = Header(None),
) -> APIKeyRotateResponse:
    """Rotate an API key. The old key remains valid for a 24-hour grace period."""
    verify_auth(authorization)
    manager = get_api_key_manager()

    result = manager.rotate_key(key_id)
    if not result:
        raise not_found("API Key", key_id)

    new_raw, api_key = result
    return APIKeyRotateResponse(
        new_raw_key=new_raw,
        key_id=api_key.key_id,
        grace_period_seconds=86400,
    )


@router.delete(
    "/auth/api-keys/{key_id}",
    responses=responses(401, 404),
)
def revoke_api_key(
    key_id: str,
    authorization: Optional[str] = Header(None),
):
    """Revoke an API key permanently."""
    verify_auth(authorization)
    manager = get_api_key_manager()

    if not manager.revoke_key(key_id):
        raise not_found("API Key", key_id)

    return {"status": "revoked", "key_id": key_id}


# ---------------------------------------------------------------------------
# Password Policy
# ---------------------------------------------------------------------------


@router.post(
    "/auth/password/validate",
    response_model=PasswordValidateResponse,
)
def validate_password_strength(
    body: PasswordValidateRequest,
) -> PasswordValidateResponse:
    """Validate password strength against the configured policy.

    This endpoint does not require authentication — it is intended
    for password strength checking during registration flows.
    """
    result = validate_password(body.password, body.username or "")
    return PasswordValidateResponse(
        valid=result.valid,
        errors=result.errors,
        strength_score=result.strength_score,
        entropy_bits=result.entropy_bits,
    )


# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------


@router.get(
    "/features",
    response_model=FeatureFlagResponse,
    responses=responses(401),
)
def get_feature_flags(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> FeatureFlagResponse:
    """Get all feature flags evaluated for the current user and platform."""
    user_id = verify_auth(authorization)

    ua = request.headers.get("user-agent", "")
    platform_info = detect_platform(ua)

    manager = get_feature_flag_manager()
    flags = manager.get_all_flags(
        user_id=user_id,
        platform=platform_info.platform.value,
    )

    return FeatureFlagResponse(flags=flags)


@router.post(
    "/features",
    responses=responses(400, 401),
)
def create_feature_flag(
    body: FeatureFlagCreateRequest,
    authorization: Optional[str] = Header(None),
):
    """Create or update a feature flag (admin only)."""
    verify_auth(authorization)
    manager = get_feature_flag_manager()

    flag = FeatureFlag(
        name=body.name,
        description=body.description,
        status=FlagStatus(body.status),
        percentage=body.percentage,
        enabled_platforms=body.enabled_platforms,
        disabled_platforms=body.disabled_platforms,
        enabled_users=body.enabled_users,
        disabled_users=body.disabled_users,
    )
    manager.register(flag)

    return {"status": "created", "flag": flag.to_dict()}


@router.get(
    "/features/list",
    responses=responses(401),
)
def list_feature_flags(
    authorization: Optional[str] = Header(None),
):
    """List all registered feature flags."""
    verify_auth(authorization)
    manager = get_feature_flag_manager()
    return {"flags": manager.list_flags()}


@router.delete(
    "/features/{flag_name}",
    responses=responses(401, 404),
)
def delete_feature_flag(
    flag_name: str,
    authorization: Optional[str] = Header(None),
):
    """Delete a feature flag."""
    verify_auth(authorization)
    manager = get_feature_flag_manager()

    if not manager.delete(flag_name):
        raise not_found("Feature Flag", flag_name)

    return {"status": "deleted", "name": flag_name}


# ---------------------------------------------------------------------------
# Platform Detection
# ---------------------------------------------------------------------------


@router.get(
    "/platform/detect",
    response_model=PlatformInfoResponse,
)
def detect_client_platform(request: Request) -> PlatformInfoResponse:
    """Detect the client platform and device from request headers.

    Uses User-Agent and Sec-CH-UA client hints for detection.
    """
    ua = request.headers.get("user-agent", "")

    # Collect client hints if available
    client_hints = {}
    for header in (
        "sec-ch-ua",
        "sec-ch-ua-mobile",
        "sec-ch-ua-platform",
        "sec-ch-ua-platform-version",
    ):
        value = request.headers.get(header)
        if value:
            client_hints[header] = value

    info = detect_platform(ua, client_hints or None)
    return PlatformInfoResponse(**info.to_dict())


# ---------------------------------------------------------------------------
# Threat Detection
# ---------------------------------------------------------------------------


@router.get(
    "/security/threats",
    response_model=ThreatEventsResponse,
    responses=responses(401),
)
def get_threat_events(
    limit: int = 100,
    severity: Optional[str] = None,
    authorization: Optional[str] = Header(None),
) -> ThreatEventsResponse:
    """Get recent threat detection events (admin only)."""
    verify_auth(authorization)
    detector = get_threat_detector()

    from test_ai.security.threat_detection import ThreatSeverity

    sev = ThreatSeverity(severity) if severity else None
    events = detector.get_recent_events(limit=limit, severity=sev)

    return ThreatEventsResponse(events=events, total=len(events))


@router.get(
    "/security/threats/stats",
    response_model=ThreatStatsResponse,
    responses=responses(401),
)
def get_threat_stats(
    authorization: Optional[str] = Header(None),
) -> ThreatStatsResponse:
    """Get threat detection statistics (admin only)."""
    verify_auth(authorization)
    detector = get_threat_detector()
    stats = detector.get_stats()
    return ThreatStatsResponse(**stats)
