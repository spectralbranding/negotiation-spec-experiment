"""hash_prompts.py — compute and record sha256 hashes of all prompt files.

Run before OSF registration to freeze the exact prompt texts.
Writes prompts/PROMPT_HASHES.txt.

Usage:
    uv run python research/negotiation_spec_experiment/prompts/hash_prompts.py
"""

import hashlib
import sys
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent
HASH_FILE = PROMPTS_DIR / "PROMPT_HASHES.txt"

PROMPT_FILES = [
    # Experimental treatment prompts (condition bodies + harness)
    "harness_preface.txt",
    "NEUTRAL.txt",
    "WARMTH.txt",
    "DOMINANCE.txt",
    "COT_ONLY.txt",
    "SPEC_NOCOT.txt",
    "SPEC_COT.txt",
    # Extension Component 1: logrolling ablation
    "SPEC_NOLOGROLL.txt",
    # Extension Component 2: paraphrase robustness envelope
    # SPEC_NOCOT paraphrases (keep spec structure, no warmth/rapport/dominance)
    "SPEC_NOCOT_p1.txt",
    "SPEC_NOCOT_p2.txt",
    "SPEC_NOCOT_p3.txt",
    "SPEC_NOCOT_p4.txt",
    # COT_ONLY paraphrases (keep reasoning-in-think-tags, no spec structure)
    "COT_ONLY_p1.txt",
    "COT_ONLY_p2.txt",
    "COT_ONLY_p3.txt",
    "COT_ONLY_p4.txt",
    # WARMTH paraphrases (keep friendliness/rapport, no spec structure)
    "WARMTH_p1.txt",
    "WARMTH_p2.txt",
    "WARMTH_p3.txt",
    "WARMTH_p4.txt",
    # NEUTRAL paraphrases (keep minimal plain instruction)
    "NEUTRAL_p1.txt",
    "NEUTRAL_p2.txt",
    "NEUTRAL_p3.txt",
    "NEUTRAL_p4.txt",
    # Scoring rubric prompts (experimental measurement instrument)
    # Published as standalone files per PROMPT_PURITY_PROTOCOL HARD RULE.
    # Source code references: code/scoring_llm.py::WARMTH_DOMINANCE_SYSTEM
    # and code/scoring_llm.py::SVI_SYSTEM. The YAML front-matter in these
    # files is part of the published record; the system prompt begins after
    # the closing "---" line.
    "SCORING_WARMTH_DOMINANCE.txt",
    "SCORING_SVI.txt",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    lines = []
    print("Prompt file SHA-256 hashes (for OSF registration freeze record):")
    print("-" * 72)
    all_ok = True
    for fname in PROMPT_FILES:
        fpath = PROMPTS_DIR / fname
        if not fpath.exists():
            print(f"  MISSING: {fname}")
            all_ok = False
            continue
        h = sha256_file(fpath)
        size = fpath.stat().st_size
        line = f"{h}  {fname}  ({size} bytes)"
        print(f"  {line}")
        lines.append(line)

    if not all_ok:
        print("\nERROR: one or more prompt files missing.", file=sys.stderr)
        sys.exit(1)

    # Compute a combined hash (hash of all file hashes concatenated)
    combined = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    combined_line = f"\nCOMBINED (hash of all hashes): {combined}"
    print(combined_line)
    lines.append(combined_line)

    HASH_FILE.write_text("\n".join(lines) + "\n")
    print(f"\nWrote: {HASH_FILE}")


if __name__ == "__main__":
    main()
