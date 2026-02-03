"""Auth0 bootstrap automation (idempotent) - Transaction Management.

This script provisions Auth0 objects for the Transaction Management API:
- Resource Server (API) with txn:* permissions
- M2M Application for testing
- Client Grant with all scopes

NOTE: This script does NOT create roles. Roles are managed by
card-fraud-rule-management (the central hub). See AUTH_MODEL.md.

Required environment variables:
- AUTH0_MGMT_DOMAIN              e.g. dev-xxxx.us.auth0.com
- AUTH0_MGMT_CLIENT_ID
- AUTH0_MGMT_CLIENT_SECRET
- AUTH0_AUDIENCE                 e.g. https://fraud-transaction-management-api

Optional environment variables:
- AUTH0_API_NAME                 default: Fraud Transaction Management API
- AUTH0_M2M_APP_NAME             default: Fraud Transaction Management M2M

Usage:
  uv run auth0-bootstrap --yes --verbose

Notes:
- This script avoids printing secrets.
- It is designed to be safe to re-run (idempotent).
- Run card-fraud-rule-management bootstrap FIRST to create shared roles.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import time
from dataclasses import dataclass

import httpx

# =============================================================================
# DOPPLER SYNC
# =============================================================================


def sync_secrets_to_doppler(
    secrets_dict: dict[str, str],
    *,
    project: str = "card-fraud-transaction-management",
    config: str = "local",
    verbose: bool = False,
) -> bool:
    """Sync secrets to Doppler using CLI."""
    if not secrets_dict:
        return True

    try:
        cmd = ["doppler", "secrets", "set", "--project", project, "--config", config]
        for key, value in secrets_dict.items():
            cmd.append(f"{key}={value}")

        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", timeout=30)

        if result.returncode != 0:
            print(f"  Warning: Failed to sync to Doppler: {result.stderr}")
            return False

        if verbose:
            print(f"  Synced {len(secrets_dict)} secret(s) to Doppler ({project}/{config})")
        return True
    except subprocess.TimeoutExpired:
        print("  Warning: Doppler sync timed out")
        return False
    except FileNotFoundError:
        print("  Warning: Doppler CLI not found - skipping secret sync")
        return False
    except Exception as e:
        print(f"  Warning: Doppler sync error: {e}")
        return False


# =============================================================================
# AUTH0 CONFIGURATION
# =============================================================================


# Transaction Management API permissions (as defined in AUTH_MODEL.md)
DEFAULT_SCOPES: list[dict[str, str]] = [
    {"value": "txn:view", "description": "View transactions"},
    {"value": "txn:comment", "description": "Add analyst comments"},
    {"value": "txn:flag", "description": "Flag suspicious activity"},
    {"value": "txn:recommend", "description": "Recommend action"},
    {"value": "txn:approve", "description": "Approve transaction"},
    {"value": "txn:block", "description": "Block transaction"},
    {"value": "txn:override", "description": "Override prior decision"},
]

# NOTE: Roles are NOT created by this project.
# Roles (PLATFORM_ADMIN, FRAUD_ANALYST, FRAUD_SUPERVISOR, etc.) are
# managed by card-fraud-rule-management. See AUTH_MODEL.md.


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    mgmt_domain: str
    mgmt_client_id: str
    mgmt_client_secret: str
    audience: str

    api_name: str
    spa_name: str
    m2m_name: str

    spa_callbacks: list[str]
    spa_origins: list[str]
    spa_logout_urls: list[str]

    m2m_default_roles: list[str]


class Auth0Mgmt:
    def __init__(self, *, domain: str, token: str, timeout_s: float = 30.0, verbose: bool = False):
        self._domain = domain
        self._verbose = verbose
        self._client = httpx.Client(
            base_url=f"https://{domain}/api/v2/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout_s,
        )

    def close(self) -> None:
        self._client.close()

    def _request(
        self, method: str, path: str, *, params: dict | None = None, json: dict | list | None = None
    ):
        # Conservative retry policy: handle transient 429/5xx.
        max_attempts = 6
        base_sleep = 0.8
        last_exc: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                resp = self._client.request(method, path, params=params, json=json)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt == max_attempts:
                    raise
                time.sleep(base_sleep * attempt)
                continue

            if resp.status_code in (429, 500, 502, 503, 504):
                if attempt == max_attempts:
                    resp.raise_for_status()
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    try:
                        sleep_s = float(retry_after)
                    except ValueError:
                        sleep_s = base_sleep * attempt
                else:
                    sleep_s = base_sleep * attempt
                time.sleep(sleep_s)
                continue

            # Non-retriable
            resp.raise_for_status()
            if resp.status_code == 204:
                return None
            return resp.json()

        # Should not reach here, but keep mypy happy.
        if last_exc:
            raise last_exc
        raise RuntimeError("Unexpected request retry state")

    def find_resource_server_by_identifier(self, identifier: str) -> dict | None:
        # Auth0 supports filtering by identifier.
        results = self._request("GET", "resource-servers", params={"identifier": identifier})
        if isinstance(results, list) and results:
            for rs in results:
                if rs.get("identifier") == identifier:
                    return rs
        return None

    def create_resource_server(
        self, *, name: str, identifier: str, scopes: list[dict[str, str]]
    ) -> dict:
        return self._request(
            "POST",
            "resource-servers",
            json={
                "name": name,
                "identifier": identifier,
                "scopes": scopes,
                "signing_alg": "RS256",
                "allow_offline_access": True,
                "token_lifetime": 7200,
                "token_lifetime_for_web": 7200,
                # Enable RBAC so role assignment matters.
                "enforce_policies": True,
                "token_dialect": "access_token_authz",
            },
        )

    def update_resource_server(
        self, *, resource_server_id: str, name: str, scopes: list[dict[str, str]]
    ) -> dict:
        return self._request(
            "PATCH",
            f"resource-servers/{resource_server_id}",
            json={
                "name": name,
                "scopes": scopes,
                "allow_offline_access": True,
                "enforce_policies": True,
                "token_dialect": "access_token_authz",
            },
        )

    def list_roles(self, *, page: int = 0, per_page: int = 50) -> list[dict]:
        roles = self._request("GET", "roles", params={"page": page, "per_page": per_page})
        return roles if isinstance(roles, list) else []

    def find_role_by_name(self, name: str) -> dict | None:
        page = 0
        while True:
            roles = self.list_roles(page=page)
            if not roles:
                return None
            for role in roles:
                if role.get("name") == name:
                    return role
            if len(roles) < 50:
                return None
            page += 1

    def create_role(self, *, name: str, description: str) -> dict:
        return self._request("POST", "roles", json={"name": name, "description": description})

    def update_role(self, *, role_id: str, description: str) -> dict:
        return self._request("PATCH", f"roles/{role_id}", json={"description": description})

    def list_clients(self, *, page: int = 0, per_page: int = 50) -> list[dict]:
        clients = self._request(
            "GET",
            "clients",
            params={"page": page, "per_page": per_page, "fields": "client_id,name,app_type"},
        )
        return clients if isinstance(clients, list) else []

    def find_client_by_name(self, name: str) -> dict | None:
        page = 0
        while True:
            clients = self.list_clients(page=page)
            if not clients:
                return None
            for client in clients:
                if client.get("name") == name:
                    return client
            if len(clients) < 50:
                return None
            page += 1

    def create_client(self, *, name: str, app_type: str, payload: dict) -> dict:
        body = {"name": name, "app_type": app_type, **payload}
        return self._request("POST", "clients", json=body)

    def update_client(self, *, client_id: str, payload: dict) -> dict:
        return self._request("PATCH", f"clients/{client_id}", json=payload)

    def list_client_grants(self, *, client_id: str) -> list[dict]:
        grants = self._request("GET", "client-grants", params={"client_id": client_id})
        return grants if isinstance(grants, list) else []

    def create_client_grant(self, *, client_id: str, audience: str, scope: list[str]) -> dict:
        return self._request(
            "POST",
            "client-grants",
            json={"client_id": client_id, "audience": audience, "scope": scope},
        )

    def update_client_grant(self, *, grant_id: str, scope: list[str]) -> dict:
        return self._request("PATCH", f"client-grants/{grant_id}", json={"scope": scope})

    def list_actions(self, *, page: int = 0, per_page: int = 50) -> list[dict]:
        result = self._request(
            "GET", "actions/actions", params={"page": page, "per_page": per_page}
        )
        # Auth0 returns {"actions": [...], "total": N, "per_page": N, "page": N}
        if isinstance(result, dict) and "actions" in result:
            return result["actions"]
        return result if isinstance(result, list) else []

    def find_action_by_name(self, name: str) -> dict | None:
        page = 0
        while True:
            actions = self.list_actions(page=page)
            if not actions:
                return None
            for action in actions:
                if action.get("name") == name:
                    return action
            if len(actions) < 50:
                return None
            page += 1

    def _trigger_version(self, trigger_id: str) -> str:
        # Auth0 trigger versions vary by trigger type
        # post-login uses v3, credentials-exchange uses v2
        if trigger_id == "credentials-exchange":
            return "v2"
        return "v3"

    def create_action(
        self, *, name: str, trigger_id: str, code: str, runtime: str = "node18"
    ) -> dict:
        return self._request(
            "POST",
            "actions/actions",
            json={
                "name": name,
                "supported_triggers": [
                    {"id": trigger_id, "version": self._trigger_version(trigger_id)}
                ],
                "code": code,
                "runtime": runtime,
                "secrets": [],
            },
        )

    def update_action(
        self, *, action_id: str, code: str, trigger_id: str, runtime: str = "node18"
    ) -> dict:
        return self._request(
            "PATCH",
            f"actions/actions/{action_id}",
            json={
                "supported_triggers": [
                    {"id": trigger_id, "version": self._trigger_version(trigger_id)}
                ],
                "code": code,
                "runtime": runtime,
                "secrets": [],
            },
        )

    def deploy_action(self, *, action_id: str) -> None:
        self._request("POST", f"actions/actions/{action_id}/deploy")

    def get_trigger_bindings(self, *, trigger_id: str) -> list[dict]:
        result = self._request("GET", f"actions/triggers/{trigger_id}/bindings")
        # Auth0 returns {"bindings": [...], "total": N}
        if isinstance(result, dict) and "bindings" in result:
            return result["bindings"]
        return result if isinstance(result, list) else []

    def set_trigger_bindings(self, *, trigger_id: str, bindings: list[dict]) -> None:
        # Auth0 expects {"bindings": [...]}
        self._request(
            "PATCH", f"actions/triggers/{trigger_id}/bindings", json={"bindings": bindings}
        )


def _get_management_token(*, domain: str, client_id: str, client_secret: str) -> str:
    resp = httpx.post(
        f"https://{domain}/oauth/token",
        timeout=30.0,
        json={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "audience": f"https://{domain}/api/v2/",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise SystemExit("Auth0 token response missing access_token")
    return token


def _action_code_post_login(audience: str) -> str:
    # Keep JS minimal and deterministic.
    return (
        "exports.onExecutePostLogin = async (event, api) => {\n"
        f"  const namespace = {audience!r};\n"
        "  const roles = (event.authorization && event.authorization.roles) ? "
        "event.authorization.roles : [];\n"
        "  api.accessToken.setCustomClaim(`${namespace}/roles`, roles);\n"
        "};\n"
    )


def _action_code_credentials_exchange(audience: str, m2m_roles: list[str]) -> str:
    roles_js = str(m2m_roles)
    return (
        "exports.onExecuteCredentialsExchange = async (event, api) => {\n"
        f"  const namespace = {audience!r};\n"
        f"  api.accessToken.setCustomClaim(`${{namespace}}/roles`, {roles_js});\n"
        "};\n"
    )


def ensure_resource_server(
    mgmt: Auth0Mgmt, *, identifier: str, name: str, scopes: list[dict[str, str]], verbose: bool
) -> dict:
    existing = mgmt.find_resource_server_by_identifier(identifier)
    if not existing:
        created = mgmt.create_resource_server(name=name, identifier=identifier, scopes=scopes)
        if verbose:
            print(f"Created resource server: {created.get('id')} ({identifier})")
        return created

    updated = mgmt.update_resource_server(
        resource_server_id=existing["id"], name=name, scopes=scopes
    )
    if verbose:
        print(f"Updated resource server: {updated.get('id')} ({identifier})")
    return updated


def ensure_roles(mgmt: Auth0Mgmt, *, roles: list[tuple[str, str]], verbose: bool) -> list[dict]:
    out: list[dict] = []
    for role_name, description in roles:
        existing = mgmt.find_role_by_name(role_name)
        if not existing:
            created = mgmt.create_role(name=role_name, description=description)
            if verbose:
                print(f"Created role: {created.get('id')} ({role_name})")
            out.append(created)
            continue

        updated = mgmt.update_role(role_id=existing["id"], description=description)
        if verbose:
            print(f"Updated role: {updated.get('id')} ({role_name})")
        out.append(updated)
    return out


def ensure_spa_client(
    mgmt: Auth0Mgmt,
    *,
    name: str,
    callbacks: list[str],
    origins: list[str],
    logout_urls: list[str],
    verbose: bool,
) -> dict:
    existing = mgmt.find_client_by_name(name)

    payload = {
        "app_type": "spa",
        # SPA best-practice: no client secret.
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
        "callbacks": callbacks,
        "allowed_logout_urls": logout_urls,
        "web_origins": origins,
        "allowed_origins": origins,
        "oidc_conformant": True,
        "is_first_party": True,
    }

    if not existing:
        created = mgmt.create_client(name=name, app_type="spa", payload=payload)
        if verbose:
            print(f"Created SPA client: {created.get('client_id')} ({name})")
        return created

    updated = mgmt.update_client(client_id=existing["client_id"], payload=payload)
    if verbose:
        print(f"Updated SPA client: {existing.get('client_id')} ({name})")
    return updated


def ensure_m2m_client(mgmt: Auth0Mgmt, *, name: str, verbose: bool) -> dict:
    existing = mgmt.find_client_by_name(name)

    payload = {
        "app_type": "non_interactive",
        "grant_types": ["client_credentials"],
        "token_endpoint_auth_method": "client_secret_post",
        "oidc_conformant": True,
        "is_first_party": True,
    }

    if not existing:
        created = mgmt.create_client(name=name, app_type="non_interactive", payload=payload)
        if verbose:
            print(f"Created M2M client: {created.get('client_id')} ({name})")
        return created

    updated = mgmt.update_client(client_id=existing["client_id"], payload=payload)
    if verbose:
        print(f"Updated M2M client: {existing.get('client_id')} ({name})")
    return updated


def ensure_client_grant(
    mgmt: Auth0Mgmt, *, client_id: str, audience: str, scopes: list[str], verbose: bool
) -> dict:
    grants = mgmt.list_client_grants(client_id=client_id)
    existing = None
    for grant in grants:
        if grant.get("audience") == audience:
            existing = grant
            break

    if not existing:
        created = mgmt.create_client_grant(client_id=client_id, audience=audience, scope=scopes)
        if verbose:
            print(f"Created client grant: {created.get('id')} (client={client_id})")
        return created

    updated = mgmt.update_client_grant(grant_id=existing["id"], scope=scopes)
    if verbose:
        print(f"Updated client grant: {updated.get('id')} (client={client_id})")
    return updated


def ensure_action_and_binding(
    mgmt: Auth0Mgmt,
    *,
    action_name: str,
    trigger_id: str,
    code: str,
    verbose: bool,
) -> dict:
    existing = mgmt.find_action_by_name(action_name)
    if not existing:
        created = mgmt.create_action(name=action_name, trigger_id=trigger_id, code=code)
        mgmt.deploy_action(action_id=created["id"])
        action = created
        if verbose:
            print(f"Created+deployed action: {action.get('id')} ({action_name})")
    else:
        updated = mgmt.update_action(action_id=existing["id"], trigger_id=trigger_id, code=code)
        mgmt.deploy_action(action_id=existing["id"])
        action = updated
        if verbose:
            print(f"Updated+deployed action: {existing.get('id')} ({action_name})")

    bindings = mgmt.get_trigger_bindings(trigger_id=trigger_id)
    # Auth0 returns bindings with {"action": {"id": "...", "name": "..."}} structure
    if any(b.get("action", {}).get("id") == action["id"] for b in bindings):
        if verbose:
            print(f"Action already bound to trigger: {trigger_id}")
        return action

    # Build new binding list in the format Auth0 expects for PATCH
    # Auth0 requires ref type "action_id" (not "action")
    new_bindings = [
        {"ref": {"type": "action_id", "value": b.get("action", {}).get("id")}}
        for b in bindings
        if b.get("action", {}).get("id")
    ]
    new_bindings.append({"ref": {"type": "action_id", "value": action["id"]}})
    mgmt.set_trigger_bindings(trigger_id=trigger_id, bindings=new_bindings)
    if verbose:
        print(f"Bound action to trigger: {trigger_id}")
    return action


def load_settings() -> Settings:
    mgmt_domain = _required_env("AUTH0_MGMT_DOMAIN").strip()
    mgmt_client_id = _required_env("AUTH0_MGMT_CLIENT_ID").strip()
    mgmt_client_secret = _required_env("AUTH0_MGMT_CLIENT_SECRET").strip()
    audience = _required_env("AUTH0_AUDIENCE").strip()

    return Settings(
        mgmt_domain=mgmt_domain,
        mgmt_client_id=mgmt_client_id,
        mgmt_client_secret=mgmt_client_secret,
        audience=audience,
        api_name=os.getenv("AUTH0_API_NAME", "Fraud Transaction Management API"),
        spa_name="",  # Not used - SPA is managed by rule-management
        m2m_name=os.getenv("AUTH0_M2M_APP_NAME", "Fraud Transaction Management M2M"),
        spa_callbacks=[],
        spa_origins=[],
        spa_logout_urls=[],
        m2m_default_roles=[],  # M2M uses scopes only
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap Auth0 objects for Transaction Management (idempotent)"
    )
    parser.add_argument("--yes", "-y", action="store_true", help="Run without prompting")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print details")
    args = parser.parse_args()

    settings = load_settings()

    if not args.yes:
        print("=" * 60)
        print("AUTH0 BOOTSTRAP - Transaction Management")
        print("=" * 60)
        print(f"\nTenant: {settings.mgmt_domain}")
        print(f"Audience: {settings.audience}")
        print("\nThis will create/update:")
        print("  - API (Resource Server) with txn:* permissions")
        print("  - M2M application for testing")
        print("\nNOTE: Roles are managed by card-fraud-rule-management.")
        print("      Run that bootstrap first if roles don't exist.")
        print("\nRe-run is safe (idempotent). Continue? [y/N] ", end="")
        answer = input().strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return 1

    print("\n[1/3] Getting management token...")
    token = _get_management_token(
        domain=settings.mgmt_domain,
        client_id=settings.mgmt_client_id,
        client_secret=settings.mgmt_client_secret,
    )

    mgmt = Auth0Mgmt(domain=settings.mgmt_domain, token=token, verbose=args.verbose)
    try:
        # Step 2: Create/update API with permissions
        print("[2/3] Creating/updating API (Resource Server)...")
        ensure_resource_server(
            mgmt,
            identifier=settings.audience,
            name=settings.api_name,
            scopes=DEFAULT_SCOPES,
            verbose=args.verbose,
        )

        # NOTE: Roles are NOT created here.
        # They are managed by card-fraud-rule-management (central hub).
        # See AUTH_MODEL.md for the complete role model.
        if args.verbose:
            print("  Skipping role creation (roles managed by rule-management)")

        # Step 3: Create/update M2M client and grant
        print("[3/3] Creating/updating M2M application...")
        m2m_client = ensure_m2m_client(mgmt, name=settings.m2m_name, verbose=args.verbose)
        ensure_client_grant(
            mgmt,
            client_id=m2m_client["client_id"],
            audience=settings.audience,
            scopes=[s["value"] for s in DEFAULT_SCOPES],
            verbose=args.verbose,
        )

        # Sync M2M client credentials to Doppler
        m2m_secrets = {"AUTH0_CLIENT_ID": m2m_client["client_id"]}
        if "client_secret" in m2m_client:
            m2m_secrets["AUTH0_CLIENT_SECRET"] = m2m_client["client_secret"]
            if args.verbose:
                print("  Syncing M2M credentials to Doppler...")
            sync_secrets_to_doppler(m2m_secrets, verbose=args.verbose)
        elif args.verbose:
            print("  M2M client_secret not in response (existing client)")

        # NOTE: Actions are NOT created here.
        # They are managed by card-fraud-rule-management (central hub).
        if args.verbose:
            print("  Skipping action creation (actions managed by rule-management)")

    finally:
        mgmt.close()

    print("\n" + "=" * 60)
    print("AUTH0 BOOTSTRAP COMPLETED - Transaction Management")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Verify: uv run auth0-verify")
    print("  2. Ensure rule-management bootstrap was run for roles")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
