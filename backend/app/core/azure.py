import json
from functools import lru_cache

import httpx
from jose import jwt


@lru_cache(maxsize=1)
def _get_openid_config(tenant_id: str) -> dict:
    url = f"https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration"
    resp = httpx.get(url, timeout=5)
    resp.raise_for_status()
    return resp.json()


@lru_cache(maxsize=1)
def _get_jwks(tenant_id: str) -> dict:
    config = _get_openid_config(tenant_id)
    jwks_uri = config["jwks_uri"]
    resp = httpx.get(jwks_uri, timeout=5)
    resp.raise_for_status()
    return resp.json()


def _find_signing_key(jwks: dict, kid: str | None) -> dict | None:
    for key in jwks["keys"]:
        if key["kid"] == kid:
            return key
    return None


def verify_azure_token(token: str, tenant_id: str, client_id: str) -> dict:
    """Validate an Azure AD JWT and return the decoded claims."""
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    jwks = _get_jwks(tenant_id)
    key = _find_signing_key(jwks, kid)
    if key is None:
        # Azure may have rotated its signing keys; drop the cached JWKS
        # (and openid config) and re-fetch once before giving up.
        _get_jwks.cache_clear()
        _get_openid_config.cache_clear()
        jwks = _get_jwks(tenant_id)
        key = _find_signing_key(jwks, kid)
    if key is None:
        raise ValueError("Unable to find appropriate key")
    rsa_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
    issuer = _get_openid_config(tenant_id)["issuer"]
    return jwt.decode(
        token,
        rsa_key,
        algorithms=["RS256"],
        audience=client_id,
        issuer=issuer,
    )
