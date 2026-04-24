"""Per-Digital-Human authentication + endpoint allowlist dependencies.

S1 multi-DH roadmap, Task 6.

Usage:
    @app.post("/api/agent/heartbeat")
    async def heartbeat(
        req: HeartbeatReq,
        dh_id: str = Depends(require_endpoint("heartbeat")),
    ):
        ...

Design:
- `auth_dh` resolves the calling DH from a Bearer token (NOT from request
  body — body-declared identity is spoofable)
- `require_endpoint(name)` returns a dependency that first resolves the DH
  via auth_dh, then checks the DH's endpoint_allowlist for the named endpoint
- Token minting/invalidation happens in digital_humans.py; this module only
  consumes tokens

See: docs/specs/2026-04-24-s1-observer-digital-human.md § 8
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request

from myagent.auth import verify_token
from myagent.digital_humans import validate_token

# Transitional compatibility: S1 does not update survival.py's auth path.
# Existing SurvivalEngine already exports MYAGENT_TOKEN (= server.secret, the
# master bearer token) into its cmux env. Until that migrates to a per-DH
# token (planned for T10 or a later pass), a request authenticated with the
# master token or a valid JWT is attributed to `executor` — since the only
# human/agent with those credentials today IS the executor.
#
# New Observer DH calls MUST use a per-DH token minted via
# DigitalHumanRegistry.issue_token (see digital_humans.py).
BACKCOMPAT_MASTER_AS_EXECUTOR = True


async def auth_dh(
    request: Request, authorization: str | None = Header(None)
) -> str:
    """Resolve the authenticated Digital Human id from a Bearer token.

    Token-resolution order:
    1. Token matches a DH-issued token → return that DH id
    2. [transitional] Token matches server.secret or a valid JWT → "executor"
    3. Otherwise → 401
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing_dh_token")
    token = authorization.removeprefix("Bearer ").strip()
    reg = getattr(request.app.state, "dh_registry", None)
    if reg is None:
        raise HTTPException(status_code=503, detail="dh_registry_not_initialized")
    dh_id = validate_token(reg, token)
    if dh_id:
        return dh_id

    if BACKCOMPAT_MASTER_AS_EXECUTOR:
        config = request.app.state.config
        if token == config.server.secret:
            return "executor"
        payload = verify_token(token, config.jwt.secret)
        if payload is not None:
            return "executor"

    raise HTTPException(status_code=401, detail="invalid_dh_token")


def require_endpoint(name: str):
    """Return a FastAPI dependency that enforces the DH's endpoint_allowlist.

    Rejects with 403 if the authenticated DH cannot call this endpoint.
    """

    async def _check(
        request: Request, dh_id: str = Depends(auth_dh)
    ) -> str:
        reg = request.app.state.dh_registry
        cfg = reg.get_config(dh_id)
        if cfg is None or name not in cfg.endpoint_allowlist:
            raise HTTPException(
                status_code=403,
                detail=f"role_not_permitted: {dh_id} -> {name}",
            )
        return dh_id

    return _check
