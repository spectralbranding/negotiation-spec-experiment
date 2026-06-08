"""Publish the frozen pre-run preregistration + design to OSF.

Creates (or reuses) a PUBLIC OSF project node for the negotiation spec-vs-style
experiment and uploads the pre-run scientific artifacts. Reads OSF_ACCESS_TOKEN
from the environment (via BWS); never prints the token.

Run:
    bws run -- uv run python research/negotiation_spec_experiment/code/osf_publish.py

Idempotent: reuses an existing node with the same title and overwrites files of
the same name (so re-running updates the uploads rather than duplicating).

NOTE on registration: this script creates a PUBLIC PROJECT + file uploads (each
upload is OSF-timestamped) — this is reversible (the node can be deleted). It does
NOT create an immutable OSF Registration (that action is permanent); the canonical
pre-run freeze remains git commit 2ed95ffd. Finalizing an immutable Registration is
a separate, deliberate step.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.osf.io/v2"
TITLE = "Spec-Agent vs Styled-Agent in AI-AI Negotiation (preregistration + design)"
DESCRIPTION = (
    "Preregistration and design for an experiment testing whether a "
    "specification-first negotiation agent (explicit objective, reservation value, "
    "ranked issue weights, concession + stop rules) outperforms style-based agents "
    "(warmth / dominance), isolating structured specification from chain-of-thought "
    "via a 2x2 factorial. Extension of Vaccaro, Caoson, Ju, Aral & Curhan (2026), "
    "'Advancing AI negotiations' (arXiv:2503.06416). Canonical pre-run freeze = git "
    "commit 2ed95ffd. Full code/data will be mirrored on GitHub + Zenodo + HuggingFace."
)
ROOT = Path(__file__).resolve().parent.parent
UPLOADS = [
    ROOT / "PREREGISTRATION.md",
    ROOT / "PREREGISTRATION_STUDY2.md",
    ROOT / "EXPERIMENT_DESIGN.md",
    ROOT / "EXTENSION_DESIGN.md",
    ROOT / "PILOT_GATE_AUDIT.md",
    ROOT / "LOGGING_AND_PROVENANCE_STANDARD.md",
    ROOT / "paper.md",
    ROOT / "DATA_AVAILABILITY.md",
    ROOT / "prompts" / "PROMPT_HASHES.txt",
    ROOT / "prompts" / "SCORING_WARMTH_DOMINANCE.txt",
    ROOT / "prompts" / "SCORING_SVI.txt",
]


def _token() -> str:
    tok = os.environ.get("OSF_ACCESS_TOKEN", "").strip()
    if not tok:
        sys.exit("OSF_ACCESS_TOKEN not in environment (run via: bws run -- ...)")
    return tok


def _req(method, url, token, data=None, ctype="application/vnd.api+json", raw=False):
    headers = {"Authorization": f"Bearer {token}"}
    body = None
    if data is not None:
        body = data if raw else json.dumps(data).encode()
        headers["Content-Type"] = ctype
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            payload = r.read()
            return r.status, (json.loads(payload) if payload and not raw else payload)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def find_or_create_node(token) -> str:
    status, body = _req(
        "GET", f"{API}/users/me/nodes/?filter[title]={urllib.parse.quote(TITLE)}", token
    )
    if status == 200 and isinstance(body, dict):
        for n in body.get("data", []):
            if n.get("attributes", {}).get("title") == TITLE:
                print(f"[osf] reusing existing node {n['id']}")
                return n["id"]
    payload = {
        "data": {
            "type": "nodes",
            "attributes": {
                "title": TITLE,
                "category": "project",
                "description": DESCRIPTION,
                "public": True,
            },
        }
    }
    status, body = _req("POST", f"{API}/nodes/", token, payload)
    if status not in (201, 200):
        sys.exit(f"[osf] node create failed: {status} {body}")
    node_id = body["data"]["id"]
    print(f"[osf] created node {node_id}")
    # ensure public
    _req(
        "PATCH",
        f"{API}/nodes/{node_id}/",
        token,
        {"data": {"type": "nodes", "id": node_id, "attributes": {"public": True}}},
    )
    return node_id


def existing_files(node_id, token) -> dict:
    out = {}
    url = f"{API}/nodes/{node_id}/files/osfstorage/"
    while url:
        status, body = _req("GET", url, token)
        if status != 200 or not isinstance(body, dict):
            break
        for f in body.get("data", []):
            a = f.get("attributes", {})
            out[a.get("name")] = f.get("links", {}).get("upload")
        url = body.get("links", {}).get("next")
    return out


def upload(node_id, token, path: Path, existing: dict):
    name = path.name
    content = path.read_bytes()
    if name in existing and existing[name]:
        url = existing[name] + "?kind=file"
    else:
        url = f"https://files.osf.io/v1/resources/{node_id}/providers/osfstorage/?kind=file&name={urllib.parse.quote(name)}"
    status, body = _req(
        "PUT", url, token, data=content, ctype="application/octet-stream", raw=True
    )
    ok = status in (200, 201)
    print(f"[osf] {'OK ' if ok else 'FAIL'} {name} ({status})")
    return ok


def main():
    token = _token()
    status, me = _req("GET", f"{API}/users/me/", token)
    if status != 200:
        sys.exit(f"[osf] token check failed: {status} {me}")
    print(
        f"[osf] authenticated as: {me['data']['attributes'].get('full_name')} (id {me['data']['id']})"
    )
    node_id = find_or_create_node(token)
    existing = existing_files(node_id, token)
    n_ok = sum(upload(node_id, token, p, existing) for p in UPLOADS if p.exists())
    url = f"https://osf.io/{node_id}/"
    print("\n[osf] DONE")
    print(f"[osf] node URL: {url}")
    print(f"[osf] files uploaded OK: {n_ok}/{len([p for p in UPLOADS if p.exists()])}")
    print(
        "[osf] (public project; immutable Registration is a separate deliberate step)"
    )


if __name__ == "__main__":
    main()
