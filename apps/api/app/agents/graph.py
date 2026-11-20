"""Case Intelligence LangGraph.

    START → orchestrator ──(no sources)──────────────→ finalize → END
                 │
                 └──→ case_analyst ──(provider error)──→ finalize → END
                            │
                            └──→ verifier ──(unsupported, budget left)──→ case_analyst
                                       │
                                       └──(verified / retry exhausted)──→ finalize → END

The graph is compiled per run with an in-process ``MemorySaver`` checkpoint
store. Durable workflow status/results are persisted by the service layer; the
in-process checkpoints support inspection and bounded resumability within a
process. True cross-restart resume is a later-stage concern (see D-0xx).
"""

from __future__ import annotations

# Windows Application Control / environment compatibility shim.
# On Windows, WDAC blocks unsigned DLLs such as ormsgpack.
try:
    import ormsgpack  # noqa: F401
except ImportError:
    import json
    import sys
    import types

    class _DummyMsgpack(types.ModuleType):
        MsgpackEncodeError = ValueError
        OPT_NON_STR_KEYS = 1
        OPT_PASSTHROUGH_DATACLASS = 2
        OPT_PASSTHROUGH_DATETIME = 4
        OPT_PASSTHROUGH_ENUM = 8
        OPT_PASSTHROUGH_UUID = 16
        OPT_REPLACE_SURROGATES = 32

        @staticmethod
        def packb(data, default=None, option=0):
            return json.dumps(data, default=str).encode("utf-8")

        @staticmethod
        def unpackb(data, ext_hook=None, option=0):
            return json.loads(data.decode("utf-8"))

        class Ext:
            def __init__(self, tag, data):
                self.tag = tag
                self.data = data

    sys.modules["ormsgpack"] = _DummyMsgpack("ormsgpack")

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.context import WorkflowContext
from app.agents.nodes.case_analyst import make_case_analyst_node
from app.agents.nodes.finalize import make_finalize_node
from app.agents.nodes.orchestrator import make_orchestrator_node
from app.agents.nodes.verifier import make_verifier_node
from app.agents.state import CaseAnalysisState


def route_after_orchestrator(state: CaseAnalysisState) -> str:
    if state.get("status") == "failed":
        return "finalize"
    if state.get("outcome") == "insufficient_sources":
        return "finalize"
    return "case_analyst"


def route_after_case_analyst(state: CaseAnalysisState) -> str:
    if state.get("status") == "failed":
        return "finalize"
    return "verifier"


def route_after_verifier(state: CaseAnalysisState) -> str:
    if state.get("status") == "failed":
        return "finalize"
    if state.get("needs_revision"):
        return "case_analyst"
    return "finalize"


def build_case_analysis_graph(ctx: WorkflowContext):
    graph = StateGraph(CaseAnalysisState)

    graph.add_node("orchestrator", make_orchestrator_node(ctx))
    graph.add_node("case_analyst", make_case_analyst_node(ctx))
    graph.add_node("verifier", make_verifier_node(ctx))
    graph.add_node("finalize", make_finalize_node(ctx))

    graph.add_edge(START, "orchestrator")
    graph.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {"case_analyst": "case_analyst", "finalize": "finalize"},
    )
    graph.add_conditional_edges(
        "case_analyst",
        route_after_case_analyst,
        {"verifier": "verifier", "finalize": "finalize"},
    )
    graph.add_conditional_edges(
        "verifier",
        route_after_verifier,
        {"case_analyst": "case_analyst", "finalize": "finalize"},
    )
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=MemorySaver())


async def run_case_analysis_graph(
    ctx: WorkflowContext,
    initial_state: CaseAnalysisState,
) -> CaseAnalysisState:
    graph = build_case_analysis_graph(ctx)
    config = {
        "configurable": {"thread_id": initial_state.get("workflow_id", "workflow")},
        "recursion_limit": 20,
    }
    return await graph.ainvoke(initial_state, config=config)  # type: ignore[return-value]
