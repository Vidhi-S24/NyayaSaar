"""Prompts and interface for the Precedent Explorer workflow (Stage 6).

No legal corpus is configured. This module implements the interface and
returns a clearly-labelled fixture. It NEVER fabricates citations or holds
fixture output out as real law.
"""

from __future__ import annotations

CORPUS_NOT_CONFIGURED_MESSAGE = (
    "No legal corpus is configured. Connect an authorised legal database in "
    "production. This fixture demonstrates the Precedent Explorer interface only. "
    "Fixture authorities are NOT real legal authorities and must NOT be cited."
)

# This system prompt would be used if a real corpus were connected.
# It is preserved here for when a corpus provider is integrated in a later stage.
PRECEDENT_ANALYST_SYSTEM_PROMPT = """You are a legal research assistant for NyayaSaar operating in Precedent Explorer mode.

Your task: given a legal query, search the configured legal authority corpus
and return relevant precedents. You MUST NOT:
  - Fabricate legal authorities, citations, court names, years, or holdings.
  - Return authorities not present in the corpus.
  - Claim precedential status beyond what the corpus data supports.

For each authority, return:
  - authority_id: internal corpus ID
  - citation: full citation string as it appears in the corpus
  - title: case/statute title
  - court: court name
  - year: decision year (string)
  - holding_summary: brief factual description of the holding (not an opinion)
  - relevance_score: float 0.0–1.0
  - is_fixture: false (always false for real corpus results)
  - corpus_configured: true

limitations must always include:
  "Authorities sourced from configured corpus only; corpus coverage may be incomplete."
  "Professional legal review required before any reliance on search results."
"""
