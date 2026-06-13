# api/user_overrides.py
# Per-user classification overrides stored in Supabase.
#
# Resolution order during classification:
#   1. User Override  (this module)
#   2. Bluebeam Mapping Spreadsheet  (mapping_loader — future integration)
#   3. Normal Classification Rules  (classification.py)
#
# Overrides are keyed on lower-cased normalised_description so slight
# variations in raw input that normalise to the same term share one entry.

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_TABLE = "classification_overrides"


def load_overrides(db, user_id: str) -> dict:
    """Return all overrides for user_id as {lower_source_term: {nrm2_section, rate_key}}.

    Returns {} when the user has no overrides or the database is unavailable
    (fail-open: classification continues without stored preferences).
    """
    if not db or not user_id:
        return {}
    try:
        res = (
            db.table(_TABLE)
            .select("source_term, nrm2_section, rate_key")
            .eq("user_id", user_id)
            .execute()
        )
        rows = res.data or []
        return {
            r["source_term"].lower(): {
                "nrm2_section": r.get("nrm2_section"),
                "rate_key":     r.get("rate_key"),
            }
            for r in rows
            if r.get("source_term")
        }
    except Exception as exc:
        logger.warning("load_overrides failed for user %s: %s", user_id, exc)
        return {}


def save_override(db, user_id: str, source_term: str,
                  nrm2_section, rate_key) -> None:
    """Upsert one override. Raises on DB error so the caller can return 500."""
    if not db or not user_id:
        raise RuntimeError("Database client or user_id missing.")
    key = (source_term or "").lower().strip()
    if not key:
        raise ValueError("source_term must not be empty.")
    now = datetime.now(timezone.utc).isoformat()
    (
        db.table(_TABLE)
        .upsert(
            {
                "user_id":      user_id,
                "source_term":  key,
                "nrm2_section": nrm2_section or None,
                "rate_key":     rate_key or None,
                "updated_at":   now,
            },
            on_conflict="user_id,source_term",
        )
        .execute()
    )
    logger.info(
        "Override saved: user=%s term=%r nrm2=%s rate=%s",
        user_id, key, nrm2_section, rate_key,
    )


def delete_override(db, user_id: str, source_term: str) -> None:
    """Delete one override. No-op if it does not exist. Raises on DB error."""
    if not db or not user_id:
        raise RuntimeError("Database client or user_id missing.")
    key = (source_term or "").lower().strip()
    if not key:
        raise ValueError("source_term must not be empty.")
    (
        db.table(_TABLE)
        .delete()
        .eq("user_id", user_id)
        .eq("source_term", key)
        .execute()
    )
    logger.info("Override deleted: user=%s term=%r", user_id, key)
