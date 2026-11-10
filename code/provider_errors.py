"""provider_errors.py — LLM provider error classification, retry, and human-alert.

Classifies exceptions from OpenAI and Anthropic SDKs into four kinds:
    needs_deposit  — BALANCE/CREDIT exhaustion (non-transient, requires deposit)
    auth           — 401/403 / invalid key (non-transient, requires key fix)
    transient      — 429 rate-limit (not quota), 5xx, timeout, connection error
    unknown        — anything else (treated as non-transient, fail-safe)

Retry policy:
    Only "transient" errors are retried (exponential backoff: 2 / 8 / 20 s).
    All other kinds trip immediately without retry.

Human-alert:
    write_run_status()   — writes data/RUN_STATUS.md with ACTION REQUIRED block
    append_blocker_log() — appends a row to data/run_blockers.jsonl
    notify_ntfy()        — best-effort POST to local ntfy (never raises)
    print_stderr_banner() — boxed ASCII banner on stderr

Usage:
    from provider_errors import classify_provider_error, call_with_retry

    info = classify_provider_error(exc)
    # info = {"kind": "needs_deposit", "provider": "openai", "transient": False}
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# ntfy constants (fleet-standard; POST to localhost; never raises on failure)
# ---------------------------------------------------------------------------
NTFY_TOPIC = "spectral-runs"
NTFY_URL = f"http://localhost:8090/{NTFY_TOPIC}"

# ---------------------------------------------------------------------------
# Retry timing (seconds)
# ---------------------------------------------------------------------------
RETRY_DELAYS = [2, 8, 20]  # 3 attempts total


# ---------------------------------------------------------------------------
# Core classifier
# ---------------------------------------------------------------------------


def classify_provider_error(exc: BaseException) -> dict[str, Any]:
    """Classify a provider API exception.

    Returns a dict with:
        kind:      "needs_deposit" | "auth" | "transient" | "unknown"
        provider:  "openai" | "anthropic" | "unknown"
        transient: bool
        summary:   short human-readable description
    """
    try:
        return _classify(exc)
    except Exception:
        # The classifier must never itself throw.
        return {
            "kind": "unknown",
            "provider": "unknown",
            "transient": False,
            "summary": f"classifier internal error for exc type={type(exc).__name__}",
        }


def _classify(exc: BaseException) -> dict[str, Any]:
    exc_type = type(exc).__name__
    exc_module = type(exc).__module__ or ""
    msg = str(exc).lower()

    # ---- provider detection -----------------------------------------------
    provider = "unknown"
    if "openai" in exc_module:
        provider = "openai"
    elif "anthropic" in exc_module:
        provider = "anthropic"
    elif "openai" in msg or "openai" in exc_type.lower():
        provider = "openai"
    elif "anthropic" in msg or "anthropic" in exc_type.lower():
        provider = "anthropic"

    # ---- status code extraction (defensive) -------------------------------
    status_code: int | None = None
    try:
        status_code = int(getattr(exc, "status_code", None) or 0) or None
    except (TypeError, ValueError):
        status_code = None
    if status_code is None:
        try:
            # Anthropic wraps it in response.status_code
            status_code = int(exc.response.status_code)  # type: ignore[attr-defined]
        except Exception:
            pass

    # ---- error code extraction (OpenAI-style) ------------------------------
    error_code: str = ""
    try:
        # openai.BadRequestError / RateLimitError have .code
        error_code = str(getattr(exc, "code", "") or "").lower()
    except Exception:
        pass
    if not error_code:
        try:
            # OpenAI error body: exc.error.code
            error_code = str(exc.error.code or "").lower()  # type: ignore[attr-defined]
        except Exception:
            pass

    # ---- body / message text for substring matching -----------------------
    body_text = msg
    try:
        body_text += " " + str(getattr(exc, "body", "") or "")
    except Exception:
        pass
    try:
        body_text += " " + str(getattr(exc, "message", "") or "")
    except Exception:
        pass
    body_text = body_text.lower()

    # -----------------------------------------------------------------------
    # NEEDS_DEPOSIT — OpenAI insufficient_quota
    # -----------------------------------------------------------------------
    if error_code == "insufficient_quota":
        return {
            "kind": "needs_deposit",
            "provider": "openai" if provider == "unknown" else provider,
            "transient": False,
            "summary": "OpenAI: insufficient_quota (account out of credits)",
        }

    # NEEDS_DEPOSIT — HTTP 402 from either provider
    if status_code == 402:
        return {
            "kind": "needs_deposit",
            "provider": provider,
            "transient": False,
            "summary": f"{provider}: HTTP 402 Payment Required",
        }

    # NEEDS_DEPOSIT — Anthropic billing/credit messages
    anthropic_credit_phrases = [
        "credit balance is too low",
        "billing",
        "insufficient credits",
        "credit limit",
        "out of credits",
        "insufficient funds",
    ]
    if provider in ("anthropic", "unknown") and any(
        p in body_text for p in anthropic_credit_phrases
    ):
        return {
            "kind": "needs_deposit",
            "provider": "anthropic" if provider == "unknown" else provider,
            "transient": False,
            "summary": "Anthropic: credit/billing issue",
        }

    # -----------------------------------------------------------------------
    # AUTH / PERMISSION
    # -----------------------------------------------------------------------
    if status_code in (401, 403):
        return {
            "kind": "auth",
            "provider": provider,
            "transient": False,
            "summary": f"{provider}: HTTP {status_code} (auth / permission error)",
        }

    auth_phrases = [
        "invalid api key",
        "authentication",
        "unauthorized",
        "permission denied",
        "invalid_api_key",
        "api key",
    ]
    # Check for auth_phrases but exclude billing-adjacent ones we already handled
    if any(p in body_text for p in auth_phrases) and not any(
        p in body_text for p in anthropic_credit_phrases
    ):
        return {
            "kind": "auth",
            "provider": provider,
            "transient": False,
            "summary": f"{provider}: authentication / API key error",
        }

    # -----------------------------------------------------------------------
    # TRANSIENT — rate limit (not quota exhaustion), 5xx, network
    # -----------------------------------------------------------------------
    # Generic 429 that is NOT insufficient_quota
    if status_code == 429 and error_code != "insufficient_quota":
        return {
            "kind": "transient",
            "provider": provider,
            "transient": True,
            "summary": f"{provider}: HTTP 429 rate-limit (retryable)",
        }

    if status_code in (500, 502, 503, 504):
        return {
            "kind": "transient",
            "provider": provider,
            "transient": True,
            "summary": f"{provider}: HTTP {status_code} server error (retryable)",
        }

    # Connection / timeout errors (no status code)
    if status_code is None:
        transient_exc_names = {
            "ConnectionError",
            "ConnectError",
            "Timeout",
            "TimeoutError",
            "ReadTimeout",
            "ConnectTimeout",
            "RemoteDisconnected",
        }
        if exc_type in transient_exc_names:
            return {
                "kind": "transient",
                "provider": provider,
                "transient": True,
                "summary": f"network/timeout error: {exc_type}",
            }
        transient_msg_phrases = [
            "connection",
            "timeout",
            "network",
            "socket",
            "read error",
        ]
        if any(p in body_text for p in transient_msg_phrases):
            return {
                "kind": "transient",
                "provider": provider,
                "transient": True,
                "summary": f"network/connection error: {exc_type}",
            }

    # -----------------------------------------------------------------------
    # UNKNOWN — fail safe (non-transient)
    # -----------------------------------------------------------------------
    return {
        "kind": "unknown",
        "provider": provider,
        "transient": False,
        "summary": f"unclassified: {exc_type}: {str(exc)[:120]}",
    }


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------


def call_with_retry(fn, *args, **kwargs):
    """Call fn(*args, **kwargs) with retry for transient errors only.

    Retries up to len(RETRY_DELAYS) times for transient errors.
    Non-transient errors are re-raised immediately.

    Returns:
        The return value of fn on success.

    Raises:
        The last exception if all retries exhausted, or the first non-transient
        exception.
    """
    last_exc: BaseException | None = None
    for attempt, delay in enumerate([0] + RETRY_DELAYS):
        if attempt > 0:
            time.sleep(delay)
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            info = classify_provider_error(exc)
            if not info["transient"]:
                raise  # non-transient: bubble up immediately
            last_exc = exc
            print(
                f"  [retry] transient error (attempt {attempt + 1}/"
                f"{len(RETRY_DELAYS) + 1}): {info['summary']}",
                file=__import__("sys").stderr,
            )
    # All retries exhausted
    assert last_exc is not None
    raise last_exc


# ---------------------------------------------------------------------------
# Human-alert helpers
# ---------------------------------------------------------------------------


def write_run_status(
    data_dir: Path,
    provider: str,
    kind: str,
    dyads_done: int,
    dyads_remaining: int,
    cost_so_far: float,
    resume_cmd: str,
    extra_hint: str = "",
) -> Path:
    """Overwrite data/RUN_STATUS.md with an ACTION REQUIRED block."""
    data_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    status_path = data_dir / "RUN_STATUS.md"

    action_verb = (
        "Add a deposit" if kind == "needs_deposit" else "Fix the API key / permissions"
    )
    provider_name = provider.upper()

    lines = [
        "# RUN STATUS — ACTION REQUIRED",
        "",
        "```",
        f"Timestamp (UTC) : {ts}",
        f"Provider blocked : {provider_name}",
        f"Error kind       : {kind}",
        f"Dyads completed  : {dyads_done}",
        f"Dyads remaining  : {dyads_remaining}",
        f"Cost so far      : ${cost_so_far:.4f} USD",
        "```",
        "",
        "## What happened",
        "",
    ]

    if kind == "needs_deposit":
        lines += [
            f"The run was stopped because {provider_name} reported that the account "
            f"has insufficient credits / balance. No data was lost.",
            "",
        ]
    elif kind == "auth":
        lines += [
            f"The run was stopped because {provider_name} rejected the API key "
            f"(authentication / permission error). No data was lost.",
            "",
        ]
    else:
        lines += [
            f"The run was stopped due to a non-transient {provider_name} error "
            f"(kind={kind}). No data was lost.",
            "",
        ]

    if extra_hint:
        lines += [f"Hint: {extra_hint}", ""]

    lines += [
        "## How to resume",
        "",
        f"1. {action_verb} to your {provider_name} account.",
        "2. Run the exact command below:",
        "",
        "```bash",
        resume_cmd,
        "```",
        "",
        "_The --resume flag skips already-completed dyads (idempotent). "
        "No work will be duplicated._",
    ]

    status_path.write_text("\n".join(lines) + "\n")
    return status_path


def append_blocker_log(
    data_dir: Path,
    provider: str,
    kind: str,
    error_summary: str,
    dyads_done: int,
    cost_so_far: float,
) -> None:
    """Append one structured row to data/run_blockers.jsonl."""
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "run_blockers.jsonl"
    row = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "kind": kind,
        "error_summary": error_summary,
        "dyads_done": dyads_done,
        "cost_so_far_usd": round(cost_so_far, 6),
    }
    with log_path.open("a") as f:
        f.write(json.dumps(row) + "\n")


def notify_ntfy(message: str) -> None:
    """POST a short message to the fleet ntfy server.

    Uses only stdlib urllib. ANY failure (no server, offline, timeout) is
    swallowed and logged to stderr at debug level — never affects the run.
    """
    try:
        import urllib.request

        data = message.encode("utf-8")
        req = urllib.request.Request(
            NTFY_URL,
            data=data,
            headers={"Content-Type": "text/plain; charset=utf-8"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass  # intentionally swallow all errors


def print_stderr_banner(
    provider: str,
    kind: str,
    dyads_done: int,
    dyads_remaining: int,
    cost_so_far: float,
    resume_cmd: str,
) -> None:
    """Print a boxed ASCII banner to stderr."""
    import sys

    width = 70
    border = "+" + "-" * (width - 2) + "+"

    def row(text: str) -> str:
        return f"| {text:<{width - 4}} |"

    lines = [
        border,
        row("  ACTION REQUIRED — PROVIDER BLOCKED"),
        border,
        row(f"  Provider : {provider.upper()}"),
        row(f"  Kind     : {kind}"),
        row(f"  Dyads done / remaining : {dyads_done} / {dyads_remaining}"),
        row(f"  Cost so far : ${cost_so_far:.4f} USD"),
        border,
    ]

    if kind == "needs_deposit":
        lines.append(row("  Add a deposit, then run the resume command below."))
    elif kind == "auth":
        lines.append(row("  Fix the API key / permissions, then resume."))

    lines += [
        border,
        row("  Resume command:"),
        row(f"  {resume_cmd[:width - 6]}"),
    ]
    if len(resume_cmd) > width - 6:
        # Wrap long commands
        remainder = resume_cmd[width - 6 :]
        lines.append(row(f"    {remainder[:width - 6]}"))

    lines += [border]

    print("\n".join(lines), file=sys.stderr)


def handle_provider_block(
    info: dict[str, Any],
    data_dir: Path,
    dyads_done: int,
    dyads_remaining: int,
    cost_so_far: float,
    resume_cmd: str,
) -> None:
    """All four alert actions in one call: RUN_STATUS.md, jsonl, ntfy, stderr."""
    provider = info.get("provider", "unknown")
    kind = info.get("kind", "unknown")
    error_summary = info.get("summary", "")

    hint = ""
    if kind == "needs_deposit":
        hint = f"Add a deposit to {provider.upper()} billing, then run the resume command above."

    write_run_status(
        data_dir=data_dir,
        provider=provider,
        kind=kind,
        dyads_done=dyads_done,
        dyads_remaining=dyads_remaining,
        cost_so_far=cost_so_far,
        resume_cmd=resume_cmd,
        extra_hint=hint,
    )

    append_blocker_log(
        data_dir=data_dir,
        provider=provider,
        kind=kind,
        error_summary=error_summary,
        dyads_done=dyads_done,
        cost_so_far=cost_so_far,
    )

    print_stderr_banner(
        provider=provider,
        kind=kind,
        dyads_done=dyads_done,
        dyads_remaining=dyads_remaining,
        cost_so_far=cost_so_far,
        resume_cmd=resume_cmd,
    )

    ntfy_msg = (
        f"[spectral-runs] PROVIDER BLOCKED: {provider.upper()} ({kind}). "
        f"Dyads done: {dyads_done}. Cost: ${cost_so_far:.4f}. Resume: {resume_cmd}"
    )
    notify_ntfy(ntfy_msg)
