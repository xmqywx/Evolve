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

# Transitional compatibility flag.
#
# When True: a request with the server master token (server.secret) or a
# valid JWT is attributed to `executor`. This was needed during S1 rollout
# while the SurvivalEngine's cmux session was still using the master token.
#
# After R1 (2026-04-24 21:23), SurvivalEngine mints a per-DH executor token
# via registry.issue_token at start(), so all legitimate executor writes go
# through a proper DH token. The back-compat path is now redundant and a
# latent security hole (anyone with the master token could write as executor
# for the full allowlist of 6 endpoints). Default is now False (hardened).
#
# To re-enable for emergency rollback: set to True and restart.
BACKCOMPAT_MASTER_AS_EXECUTOR = False


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
