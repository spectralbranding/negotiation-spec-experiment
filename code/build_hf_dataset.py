#!/usr/bin/env python3
"""Package the negotiation-spec transcripts + outcomes into a HuggingFace dataset and upload.

One-time data-of-record builder: consolidates each arm's per-dyad transcript JSONs into a
single JSONL, copies the per-arm outcomes.csv, writes a dataset card, and uploads to the
spectralbranding HF org. Token from HUGGINGFACE_API_KEY (inject via `bws run --`).

    bws run -- uv run --with huggingface_hub python code/build_hf_dataset.py [--no-upload]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent  # [internal path removed]
STAGE = Path("[internal path removed]")
REPO_ID = "spectralbranding/negotiation-spec-experiment"
CONCEPT_DOI = "10.5281/zenodo.20595996"
GITHUB = "https://github.com/spectralbranding/negotiation-spec-experiment"

ARMS = {
    "study1": "data",
    "study2": "data_study2",
    "haiku": "data_haiku",
    "ablation": "data_ablation_full",
    "frontier": "data_frontier",
    "paraphrase": "data_paraphrase",
    "headroom": "data_headroom",
}

CARD = f"""---
license: cc-by-4.0
language:
  - en
tags:
  - llm
  - negotiation
  - agents
  - integrative-bargaining
pretty_name: "Negotiation Spec Experiment — Transcripts & Outcomes"
size_categories:
  - 1K<n<10K
---

# Negotiation Spec Experiment — Transcripts & Outcomes

Full dyad-level negotiation transcripts and computed outcomes for the empirical note
*Value Headroom Moderates Whether Specification Beats Style in LLM Negotiation*.

- **Paper + code:** {GITHUB}
- **Archival DOI (concept):** [`{CONCEPT_DOI}`](https://doi.org/{CONCEPT_DOI})
- **License:** CC BY 4.0 (data). Code lives in the GitHub repository under MIT.

## Contents

`transcripts/<arm>.jsonl` — one JSON object per dyad (the full turn-by-turn dialogue, the
agreed terms, deal flag). `outcomes/<arm>.csv` — the computed per-dyad outcomes (deal,
value created, value claimed, split, style scores where scored).

Arms: `study1` (near-ceiling scenarios), `study2` (high-headroom scenarios), `haiku`
(cross-family), `ablation` (logrolling-sentence ablation), `frontier` (capability scaling),
`paraphrase` (wording robustness), `headroom` (graded dose-response).

Each transcript JSON includes: `dyad_id`, `scenario_id`, `role_a`/`role_b`,
`agent_a_condition`/`agent_b_condition`, `model_a`/`model_b`, `turns`, `deal`, `deal_terms`.

## Reconstruction disclosure

The scenarios and harness were authored independently, informed by public materials. This is
not a one-to-one reproduction of any base study (base study public ref arXiv:2503.06416).
"""


def build() -> int:
    (STAGE / "transcripts").mkdir(parents=True, exist_ok=True)
    (STAGE / "outcomes").mkdir(parents=True, exist_ok=True)
    total = 0
    for arm, d in ARMS.items():
        tdir = SRC / d / "transcripts"
        if not tdir.exists():
            print(f"  [skip] {arm}: {tdir} missing")
            continue
        files = sorted(tdir.glob("*.json"))
        out = STAGE / "transcripts" / f"{arm}.jsonl"
        with out.open("w") as fh:
            for f in files:
                try:
                    obj = json.loads(f.read_text())
                except Exception as e:  # pragma: no cover
                    print(f"  [warn] {arm}/{f.name}: {e}")
                    continue
                obj["_arm"] = arm
                obj["_transcript_id"] = f.stem
                fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
        oc = SRC / d / "outcomes.csv"
        if oc.exists():
            (STAGE / "outcomes" / f"{arm}.csv").write_text(oc.read_text())
        print(
            f"  {arm}: {len(files)} transcripts -> {out.name}; outcomes {'ok' if oc.exists() else 'MISSING'}"
        )
        total += len(files)
    (STAGE / "README.md").write_text(CARD)
    print(f"Staged {total} transcripts across {len(ARMS)} arms at {STAGE}")
    return total


def upload() -> None:
    from huggingface_hub import HfApi

    token = os.environ.get("HUGGINGFACE_API_KEY")
    if not token:
        print("ERROR: HUGGINGFACE_API_KEY not set (run under `bws run --`).")
        sys.exit(2)
    api = HfApi(token=token)
    api.create_repo(REPO_ID, repo_type="dataset", exist_ok=True, private=False)
    api.upload_folder(
        folder_path=str(STAGE),
        repo_id=REPO_ID,
        repo_type="dataset",
        commit_message="Initial dataset of record: negotiation spec experiment transcripts + outcomes",
    )
    print(f"Uploaded to https://huggingface.co/datasets/{REPO_ID}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-upload", action="store_true")
    args = ap.parse_args()
    n = build()
    if n == 0:
        print("Nothing staged; aborting upload.")
        return 1
    if not args.no_upload:
        upload()
    return 0


if __name__ == "__main__":
    sys.exit(main())
