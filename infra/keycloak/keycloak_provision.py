# Copyright 2026 Emin Askerov
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#!/usr/bin/env python3
"""One-shot Keycloak provisioner: creates default user and grants provisioner manage-users role.

Run once after Keycloak starts. Safe to re-run (idempotent).
"""

import os
import json
import urllib.request
import urllib.parse
import urllib.error


KC_BASE = os.environ["KC_BASE_URL"]          # e.g. http://keycloak:9090/auth
REALM = os.environ.get("KEYCLOAK_REALM", "synteles")
ADMIN_USER = os.environ["KC_ADMIN_USER"]
ADMIN_PASS = os.environ["KC_ADMIN_PASSWORD"]
DEFAULT_USER = os.environ.get("KEYCLOAK_DEFAULT_USER", "synteles")
DEFAULT_PASS = os.environ.get("KEYCLOAK_DEFAULT_PASSWORD", "synteles")
FRESH_USER = os.environ.get("KEYCLOAK_FRESH_USER", "synteles-fresh")
FRESH_PASS = os.environ.get("KEYCLOAK_FRESH_PASSWORD", "synteles-fresh")
OIDC_CLIENT_SECRET = os.environ.get("OIDC_CLIENT_SECRET", "synteles-dev-secret")
PROVISIONER_SECRET = os.environ.get("KEYCLOAK_PROVISIONER_CLIENT_SECRET", "provisioner-dev-secret")


def http(method: str, url: str, data=None, headers: dict | None = None) -> dict | None:
    body = json.dumps(data).encode() if data is not None else None
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            text = resp.read().decode()
            return json.loads(text) if text else None
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        if e.code in (409, 400) and ("already exists" in body_text or "exists" in body_text.lower()):
            return None  # idempotent — ignore conflict
        raise RuntimeError(f"HTTP {e.code} {url}: {body_text}") from e


def get_admin_token() -> str:
    data = urllib.parse.urlencode({
        "client_id": "admin-cli",
        "username": ADMIN_USER,
        "password": ADMIN_PASS,
        "grant_type": "password",
    }).encode()
    req = urllib.request.Request(
        f"{KC_BASE}/realms/master/protocol/openid-connect/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def main():
    token = get_admin_token()
    print(f"Got admin token for realm 'master'")

    # 1. Update synteles-app client secret
    # Use PUT on the full client representation — POST /client-secret generates a
    # random secret and ignores the request body (Keycloak Admin REST API behaviour).
    clients = http("GET", f"{KC_BASE}/admin/realms/{REALM}/clients?clientId=synteles-app",
                   headers=auth_headers(token))
    if not clients:
        raise RuntimeError("synteles-app client not found in realm")
    client_uuid = clients[0]["id"]
    client_rep = http("GET", f"{KC_BASE}/admin/realms/{REALM}/clients/{client_uuid}",
                      headers=auth_headers(token))
    client_rep["secret"] = OIDC_CLIENT_SECRET
    http("PUT", f"{KC_BASE}/admin/realms/{REALM}/clients/{client_uuid}",
         data=client_rep, headers=auth_headers(token))
    print(f"Updated synteles-app client secret")

    # 2. Update synteles-provisioner client secret
    prov_clients = http("GET", f"{KC_BASE}/admin/realms/{REALM}/clients?clientId=synteles-provisioner",
                        headers=auth_headers(token))
    if not prov_clients:
        raise RuntimeError("synteles-provisioner client not found in realm")
    prov_uuid = prov_clients[0]["id"]
    prov_rep = http("GET", f"{KC_BASE}/admin/realms/{REALM}/clients/{prov_uuid}",
                    headers=auth_headers(token))
    prov_rep["secret"] = PROVISIONER_SECRET
    http("PUT", f"{KC_BASE}/admin/realms/{REALM}/clients/{prov_uuid}",
         data=prov_rep, headers=auth_headers(token))
    print(f"Updated synteles-provisioner client secret")

    # 3. Grant manage-users role to provisioner service account
    sa_users = http("GET",
                    f"{KC_BASE}/admin/realms/{REALM}/clients/{prov_uuid}/service-account-user",
                    headers=auth_headers(token))
    if not sa_users:
        raise RuntimeError("synteles-provisioner service account user not found")
    sa_id = sa_users["id"]
    realm_mgmt = http("GET",
                      f"{KC_BASE}/admin/realms/{REALM}/clients?clientId=realm-management",
                      headers=auth_headers(token))
    if not realm_mgmt:
        raise RuntimeError("realm-management client not found in realm")
    rm_uuid = realm_mgmt[0]["id"]
    manage_users_role = http(
        "GET",
        f"{KC_BASE}/admin/realms/{REALM}/clients/{rm_uuid}/roles/manage-users",
        headers=auth_headers(token),
    )
    if not manage_users_role:
        raise RuntimeError("manage-users role not found in realm-management client")
    http("POST",
         f"{KC_BASE}/admin/realms/{REALM}/users/{sa_id}/role-mappings/clients/{rm_uuid}",
         data=[manage_users_role],
         headers=auth_headers(token))
    print("Granted manage-users role to synteles-provisioner service account")

    # 4. Make firstName/lastName optional in user profile (KC 26 requires them by default)
    user_profile = http("GET", f"{KC_BASE}/admin/realms/{REALM}/users/profile",
                        headers=auth_headers(token))
    if user_profile and "attributes" in user_profile:
        changed = False
        for attr in user_profile["attributes"]:
            if attr.get("name") in ("firstName", "lastName"):
                req = attr.get("required", {})
                if req.get("roles"):
                    attr["required"] = {}
                    changed = True
        if changed:
            http("PUT", f"{KC_BASE}/admin/realms/{REALM}/users/profile",
                 data=user_profile, headers=auth_headers(token))
            print("Made firstName/lastName optional in user profile")

    # 5. Create default user
    http("POST", f"{KC_BASE}/admin/realms/{REALM}/users",
         data={
             "username": DEFAULT_USER,
             "email": f"{DEFAULT_USER}@synteles.local",
             "firstName": DEFAULT_USER.capitalize(),
             "lastName": "User",
             "enabled": True,
             "emailVerified": True,
             "credentials": [{"type": "password", "value": DEFAULT_PASS, "temporary": False}],
         },
         headers=auth_headers(token))
    print(f"Created default user '{DEFAULT_USER}'")

    # 6. Create fresh test user (used by provisioning integration tests; starts with no DB record)
    http("POST", f"{KC_BASE}/admin/realms/{REALM}/users",
         data={
             "username": FRESH_USER,
             "email": f"{FRESH_USER}@synteles.local",
             "firstName": "Fresh",
             "lastName": "TestUser",
             "enabled": True,
             "emailVerified": True,
             "credentials": [{"type": "password", "value": FRESH_PASS, "temporary": False}],
         },
         headers=auth_headers(token))
    print(f"Created fresh test user '{FRESH_USER}'")

    print("Provisioning complete.")


if __name__ == "__main__":
    main()
