"""Generate a flat ``POSTMAN_CURLS.md`` of copy-paste curls from the
generated Postman collection.

Reads ``PMIS_API_Collection.postman_collection.json`` (sibling of
this repo root), walks the folder/item tree, emits one curl per
request into a markdown file grouped by folder. Variables
``{{baseUrl}}``, ``{{accessToken}}``, and path placeholders
(``:project_uuid`` etc.) are left as-is so they're trivial to
find-replace.

Run after ``scripts/generate_postman_collection.py`` so the curls
match the live OpenAPI surface. The two outputs sit side-by-side
at the repo root.

Usage:
    python scripts/generate_curls.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
COLLECTION = REPO_ROOT / "PMIS_API_Collection.postman_collection.json"
OUTPUT = REPO_ROOT / "POSTMAN_CURLS.md"

URL_VAR_DEFAULTS = {
    "{{baseUrl}}": "http://10.1.131.199:8000",
    "{{accessToken}}": "<ACCESS_TOKEN>",
}

PATH_VAR_DEFAULTS = {
    "user_id": "94eeede1-c925-44ad-8de6-416dc87b5999",
    "target_id": "94eeede1-c925-44ad-8de6-416dc87b5999",
    "role_id": "12",
    "role_name": "admin",
    "vendor_id": "7f9ec285-5a94-4d2f-9d2c-a248d302b1c5",
    "project_uuid": "a278f77b-a2ef-4797-b4fa-ac3fe82e7037",
    "project_id": "a278f77b-a2ef-4797-b4fa-ac3fe82e7037",
    "code": "users:read",
    "permission_code": "users:read",
    "assignment_id": "<ASSIGNMENT_ID>",
    "milestone_id": "<MILESTONE_ID>",
    "activity_id": "<ACTIVITY_ID>",
    "task_id": "<TASK_ID>",
    "subtask_id": "<SUBTASK_ID>",
    "parent_subtask_id": "<PARENT_SUBTASK_ID>",
    "comment_id": "<COMMENT_ID>",
    "attachment_id": "<ATTACHMENT_ID>",
    "membership_id": "<MEMBERSHIP_ID>",
    "transition_id": "<TRANSITION_ID>",
    "division_id": "<DIVISION_ID>",
    "resource_type_id": "<RESOURCE_TYPE_ID>",
    "id": "<ID>",
    "target_kind": "task",
    "target_uuid": "<TARGET_UUID>",
    "target_type": "tasks",
}

BODY_FIELD_DEFAULTS = {
    "login": "your_login",
    "login_or_email": "your_login",
    "password": "Pmis@1234",
    "new_password": "Pmis@1234",
    "ephemeral_token": "<EPHEMERAL_TOKEN>",
    "code": "000000",
    "channel": "email",
    "token_or_code": "<TOKEN_OR_CODE>",
    "access_token": "<ACCESS_TOKEN>",
    "refresh_token": "<REFRESH_TOKEN>",
    "email": "user@example.com",
    "firstName": "John",
    "lastName": "Doe",
    "phoneNumber": "+919999999999",
    "phone_number": "+919999999999",
    "admin": False,
    "status": "published",
    "vendorId": "7f9ec285-5a94-4d2f-9d2c-a248d302b1c5",
    "vendor_id": "7f9ec285-5a94-4d2f-9d2c-a248d302b1c5",
    "division": "tmd1",
    "divisionOther": None,
    "division_other": None,
    "orgRole": "project_member",
    "name": "Sample Name",
    "description": "Sample description",
    "active": True,
    "contactPerson": "Jane Doe",
    "contact_person": "Jane Doe",
    "userId": "94eeede1-c925-44ad-8de6-416dc87b5999",
    "user_id": "94eeede1-c925-44ad-8de6-416dc87b5999",
    "roleId": 12,
    "role_id": 12,
    "projectId": "a278f77b-a2ef-4797-b4fa-ac3fe82e7037",
    "project_id": "a278f77b-a2ef-4797-b4fa-ac3fe82e7037",
    "organizationId": "7f9ec285-5a94-4d2f-9d2c-a248d302b1c5",
    "organization_id": "7f9ec285-5a94-4d2f-9d2c-a248d302b1c5",
    "role": "project_member",
    "label": "Sample Label",
    "requiresOther": False,
    "requires_other": False,
    "owner": "tmd1",
    "ownerOther": None,
    "owner_other": None,
    "priority": "p2",
    "startDate": "2026-05-15T00:00:00+05:30",
    "endDate": "2026-06-15T00:00:00+05:30",
    "actualStartDate": None,
    "actualEndDate": None,
    "start_date": "2026-05-15T00:00:00+05:30",
    "end_date": "2026-06-15T00:00:00+05:30",
    "actual_start_date": None,
    "actual_end_date": None,
    "position": 1,
    "statusExplanation": "Sample status note",
    "parentId": None,
    "parent_id": None,
    "isPublic": False,
    "is_public": False,
    "public": False,
    "concernedDivision": ["tmd1"],
    "concerned_division": ["tmd1"],
    "ownerDivision": "tmd1",
    "owner_division": "tmd1",
    "body": "Sample comment text.",
    "content": "Sample comment text.",
    "filename": "sample.pdf",
    "contentType": "application/pdf",
    "content_type": "application/pdf",
    "size": 1024,
}

LIST_FIELD_DEFAULTS = {
    "project_ids": ["a278f77b-a2ef-4797-b4fa-ac3fe82e7037"],
    "projectIds": ["a278f77b-a2ef-4797-b4fa-ac3fe82e7037"],
    "vendor_ids": ["7f9ec285-5a94-4d2f-9d2c-a248d302b1c5"],
    "vendorIds": ["7f9ec285-5a94-4d2f-9d2c-a248d302b1c5"],
    "user_ids": ["94eeede1-c925-44ad-8de6-416dc87b5999"],
    "userIds": ["94eeede1-c925-44ad-8de6-416dc87b5999"],
    "permissions": ["users:read"],
    "dependsOn": [],
    "depends_on": [],
}


def _fill_body(value: Any, key_hint: str | None = None) -> Any:
    if isinstance(value, dict):
        return {k: _fill_body(v, key_hint=k) for k, v in value.items()}
    if isinstance(value, list):
        if key_hint in LIST_FIELD_DEFAULTS:
            return list(LIST_FIELD_DEFAULTS[key_hint])
        return [_fill_body(v) for v in value]
    if key_hint in BODY_FIELD_DEFAULTS:
        is_empty_string = isinstance(value, str) and value == ""
        is_zero = value == 0 or value is False
        is_none = value is None
        if is_empty_string or is_none or is_zero or value == "user@example.com":
            return BODY_FIELD_DEFAULTS[key_hint]
    return value


def _substitute_url(url_raw: str) -> str:
    out = url_raw
    for var, val in URL_VAR_DEFAULTS.items():
        out = out.replace(var, val)
    for var, val in PATH_VAR_DEFAULTS.items():
        out = out.replace("{" + var + "}", val)
    return out


def _substitute_header(value: str) -> str:
    out = value
    for var, val in URL_VAR_DEFAULTS.items():
        out = out.replace(var, val)
    return out


def _substitute_body(raw: str) -> str:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw
    filled = _fill_body(parsed)
    return json.dumps(filled, indent=2)


def _flatten_items(items: List[dict], parent_path: Tuple[str, ...] = ()) -> Iterable[Tuple[Tuple[str, ...], dict]]:
    for it in items:
        if "item" in it:
            yield from _flatten_items(it["item"], parent_path + (it["name"],))
        elif "request" in it:
            yield parent_path, it


def _curl_for(item: dict) -> str:
    """Build a multi-line curl with sample values from the substitution
    maps. Postman ``{{baseUrl}}`` / ``{path_var}`` are replaced with
    real seeded IDs from the dev server; body fields are filled from
    BODY_FIELD_DEFAULTS / LIST_FIELD_DEFAULTS. Auth header keeps
    ``<ACCESS_TOKEN>`` for the user to paste a fresh JWT."""
    req = item["request"]
    method = req.get("method", "GET").upper()
    url_raw = _substitute_url(req.get("url", {}).get("raw", ""))

    parts: List[str] = [f"curl -X {method} '{url_raw}'"]
    for h in req.get("header", []) or []:
        if h.get("disabled"):
            continue
        key = h.get("key", "")
        val = _substitute_header(h.get("value", ""))
        val_safe = val.replace("'", "'\\''")
        parts.append(f"  -H '{key}: {val_safe}'")

    body = req.get("body") or {}
    if body.get("mode") == "raw":
        raw = body.get("raw", "")
        if raw:
            filled = _substitute_body(raw)
            body_safe = filled.replace("'", "'\\''")
            parts.append(f"  -d '{body_safe}'")

    return " \\\n".join(parts)


def main() -> None:
    if not COLLECTION.exists():
        raise SystemExit(
            f"{COLLECTION.name} not found in {REPO_ROOT}. "
            "Run scripts/generate_postman_collection.py first."
        )

    data = json.loads(COLLECTION.read_text(encoding="utf-8"))
    name = data.get("info", {}).get("name", "API")
    desc = data.get("info", {}).get("description", "")

    out: List[str] = []
    out.append(f"# {name} — direct curls\n")
    out.append(
        "> Auto-generated by `scripts/generate_curls.py` from "
        f"`{COLLECTION.name}`. Re-run after the Postman collection is "
        "regenerated so this file stays in sync.\n"
    )
    if desc:
        out.append(f"\n{desc}\n")
    out.append(
        "\n## How to use\n\n"
        "Sample values are pre-filled — most curls run as-is once you "
        "paste a fresh `<ACCESS_TOKEN>`. Keep the placeholders below "
        "in mind:\n\n"
        "- **`<ACCESS_TOKEN>`** — bearer JWT. Get one from the "
        "user-mgmt login flow (`POST :8001/api/v3/users/login` → "
        "`/login/send-otp` → `/login/verify-otp`). On the dev server "
        "the universal OTP is `000000`. Tokens last ~15 min.\n"
        "- **`<MILESTONE_ID>`** / **`<ACTIVITY_ID>`** / **`<TASK_ID>`** "
        "/ **`<SUBTASK_ID>`** etc. — IDs the curl can't know up-front. "
        "Hit the relevant `GET .../tree` or list endpoint first and "
        "paste an ID from the response.\n"
        "- **`<COMMENT_ID>`**, **`<ATTACHMENT_ID>`**, etc. — same.\n\n"
        "Pre-filled sample IDs use real seeded data on the dev server "
        "(`http://10.1.131.199`):\n"
        "- bootstrap admin user `94eeede1-c925-44ad-8de6-416dc87b5999`,\n"
        "- vendor `7f9ec285-5a94-4d2f-9d2c-a248d302b1c5` (\"role org\"),\n"
        "- published project `a278f77b-a2ef-4797-b4fa-ac3fe82e7037` (\"ey app\"),\n"
        "- `admin` role id `12`.\n\n"
        "**Windows PowerShell**: swap single-quoted bodies for double-"
        "quoted with escaped inner quotes, or run the curls from Git "
        "Bash / WSL where the quoting works verbatim.\n\n"
        "---\n"
    )

    by_folder: dict[str, List[dict]] = {}
    for parent, item in _flatten_items(data.get("item", [])):
        folder = " / ".join(parent) if parent else "(top-level)"
        by_folder.setdefault(folder, []).append(item)

    for folder in sorted(by_folder.keys()):
        out.append(f"\n## {folder}\n")
        for item in sorted(by_folder[folder], key=lambda it: it["name"]):
            req_name = item["name"]
            method = item["request"].get("method", "GET").upper()
            url_raw = item["request"].get("url", {}).get("raw", "")
            req_desc = item["request"].get("description", "").strip()

            out.append(f"\n### {method} — {req_name}\n")
            out.append(f"`{method} {url_raw}`\n")
            if req_desc:
                first_para = req_desc.split("\n\n", 1)[0]
                out.append(f"\n{first_para}\n")
            out.append("\n```bash\n")
            out.append(_curl_for(item))
            out.append("\n```\n")

    OUTPUT.write_text("".join(out), encoding="utf-8")
    n_requests = sum(len(v) for v in by_folder.values())
    print(f"Wrote {OUTPUT}")
    print(f"  {len(by_folder)} folders, {n_requests} requests")


if __name__ == "__main__":
    main()
