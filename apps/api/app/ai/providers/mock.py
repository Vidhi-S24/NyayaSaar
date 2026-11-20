"""Development fixture provider.

This adapter never calls a network service. It returns the ``mock_fixture``
that an agent node supplies, so the graph can exercise real source IDs and
page references without credentials. Every result is flagged ``is_mock=True``
and the UI labels it as a development fixture.
"""

from __future__ import annotations

import json

from app.ai.base import (
    LLMProvider,
    ProviderResponseError,
    RawCompletion,
    StructuredRequest,
)


class MockProvider(LLMProvider):
    name = "mock"
    is_mock = True

    def __init__(self, *, model: str = "fixture") -> None:
        super().__init__(model=model, max_retries=0, structured_retries=0)

    async def _generate_text(self, request: StructuredRequest) -> RawCompletion:
        if request.mock_fixture is None:
            raise ProviderResponseError(
                "No development fixture was supplied for this workflow step.",
                code="mock_fixture_missing",
            )
        return RawCompletion(
            text=json.dumps(request.mock_fixture, ensure_ascii=False),
            input_tokens=0,
            output_tokens=0,
        )
