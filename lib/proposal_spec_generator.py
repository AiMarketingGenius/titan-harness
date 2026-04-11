"""
titan-harness/lib/proposal_spec_generator.py

Thread 2 of the Autopilot Suite — Proposal Spec Generator (call-notes → spec.yaml).
See plans/PLAN_2026-04-11_proposal-from-call-notes.md for the full DR.

This is the SMALL gap — build_proposal.py (608 lines, Gates 1+2+3) is
already shipped at commit f1ab8b0. This module adds the missing front
door: take call notes + prospect metadata and emit a valid spec.yaml
that build_proposal.py consumes via the --spec flag.

Status: STUB module — public API shipped, implementation TODO.

Phase wiring (from the DR):
  Phase 1 spec-schema-audit-and-typing  → ProposalSpec + validators (TODO)
  Phase 2 extraction-prompt-chain       → extract_spec_from_notes() (TODO)
  Phase 3 cli-integration                → build_proposal.py --from-call-notes (TODO)
  Phase 4 war-room-integration           → war-room grade on generated spec (TODO)
  Phase 5 fireflies-integration          → resolve_fireflies_id() (TODO)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass
class ProspectMetadata:
    """Input: prospect info Solon provides (or Titan extracts from the call)."""
    business_name: str
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class ExtractionResult:
    """Output of extract_spec_from_notes()."""
    spec_yaml: Optional[str]                           # The generated spec.yaml or None if incomplete
    generated_from: str                                # 'call_notes' | 'fireflies' | 'manual'
    source_ref: Optional[str]                          # file path or fireflies id
    confidence: str                                    # 'high' | 'medium' | 'low'
    missing_fields: list[str] = field(default_factory=list)
    rationale: str = ""                                # Titan's reasoning for plan selection
    candidate_plans: list[dict] = field(default_factory=list)
    war_room_grade: Optional[str] = None
    war_room_exchange_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Phase 2: extractor (TODO implementation)
# ---------------------------------------------------------------------------

def extract_spec_from_notes(call_notes: str,
                            prospect: ProspectMetadata,
                            catalog_path: str = "/home/titan/amg/payment_links_paypal.json",
                            project_id: str = "EOM") -> ExtractionResult:
    """Run the 3-step prompt chain and emit a ProposalSpec.

    Chain:
      1. Entity extraction (Haiku) — pull contact, business, industry,
         website, timeline, budget, pain points, goals from notes
      2. Plan matching (Sonnet) — propose 1-3 candidate plans from
         catalog with reasoning
      3. Spec composition (Sonnet) — assemble full ProposalSpec, run
         validators inline, return missing_fields list

    TODO: wire via lib/prompt_pipeline.run_pipeline(). Currently stubbed.
    """
    raise NotImplementedError(
        "extract_spec_from_notes: Phase 2 extraction-prompt-chain not yet "
        "implemented. See plans/PLAN_2026-04-11_proposal-from-call-notes.md "
        "Phase 2 spec."
    )


def resolve_fireflies_id(transcript_id: str,
                         corpus_path: str = "/opt/amg-titan/solon-corpus/fireflies/transcripts") -> tuple[str, ProspectMetadata]:
    """Given a Fireflies transcript id, return (call_notes_text, prospect_metadata).

    Looks up the transcript JSON file, extracts the flat content_text,
    infers prospect metadata from attendee emails + title.

    TODO: Phase 5 fireflies-integration. Currently stubbed.
    """
    raise NotImplementedError(
        "resolve_fireflies_id: Phase 5 fireflies-integration not yet "
        "implemented."
    )


def war_room_grade_spec(extraction: ExtractionResult,
                        prospect: ProspectMetadata) -> ExtractionResult:
    """Grade the extracted spec via WarRoom using a custom phase name
    'proposal_spec_generation'. Iterates up to 2 rounds if below A.

    TODO: Phase 4 war-room-integration. Currently stubbed.
    """
    raise NotImplementedError(
        "war_room_grade_spec: Phase 4 war-room-integration not yet "
        "implemented."
    )


def is_enabled() -> bool:
    """True iff policy.yaml autopilot.proposal_from_notes_enabled is true."""
    import os
    return os.environ.get("POLICY_AUTOPILOT_PROPOSAL_FROM_NOTES_ENABLED", "0") == "1"
