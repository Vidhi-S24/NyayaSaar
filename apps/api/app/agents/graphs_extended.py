"""Extended LangGraph workflows for Stage 6 modules.

Each new workflow uses a simple 3-node graph:
    START → orchestrator → analyst → finalize → END

The orchestrator checks for sufficient sources and sets up state; the analyst
makes the single LLM call (or returns a fixture); finalize persists the result.
The existing finalize node from Case Intelligence is reused for all workflows
since it only inspects state["result"] and state["status"].
"""

from __future__ import annotations

# Windows Application Control shim (identical to graph.py)
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
from app.agents.nodes.advocate_analyst import make_advocate_analyst_node
from app.agents.nodes.contradiction_analyst import make_contradiction_analyst_node
from app.agents.nodes.judge_analyst import make_judge_analyst_node
from app.agents.nodes.precedent_analyst import make_precedent_analyst_node
from app.agents.state import CaseAnalysisState


# ---------------------------------------------------------------------------
# Shared simple-workflow orchestrator & finalize
# ---------------------------------------------------------------------------


def make_simple_orchestrator(workflow_name: str):
    """Return an orchestrator node that validates sources and transitions."""

    async def orchestrator(state: CaseAnalysisState) -> dict:
        sources = state.get("sources") or []
        if not sources:
            return {
                "status": "running",
                "current_step": "finalize",
                "progress": 15,
                "outcome": "insufficient_sources",
            }
        return {
            "status": "running",
            "current_step": workflow_name,
            "progress": 15,
            "outcome": None,
        }

    return orchestrator


def make_simple_finalize():
    """Lightweight finalize node shared by all simple workflows."""

    async def finalize(state: CaseAnalysisState) -> dict:
        if state.get("status") == "failed":
            return {
                "status": "failed",
                "current_step": "failed",
                "progress": 100,
            }
        result = state.get("result")
        if result:
            return {
                "status": "completed",
                "current_step": "completed",
                "progress": 100,
                "outcome": "completed",
            }
        # Insufficient sources — build minimal result shell from state
        return {
            "status": "completed",
            "current_step": "completed",
            "progress": 100,
            "outcome": "insufficient_sources",
        }

    return finalize


def _route_after_orchestrator(state: CaseAnalysisState) -> str:
    if state.get("status") == "failed" or state.get("outcome") == "insufficient_sources":
        return "finalize"
    return "analyst"


def _route_after_analyst(state: CaseAnalysisState) -> str:
    if state.get("status") == "failed":
        return "finalize"
    return "finalize"


def _build_simple_graph(ctx: WorkflowContext, workflow_name: str, analyst_node) -> object:
    graph = StateGraph(CaseAnalysisState)
    graph.add_node("orchestrator", make_simple_orchestrator(workflow_name))
    graph.add_node("analyst", analyst_node)
    graph.add_node("finalize", make_simple_finalize())

    graph.add_edge(START, "orchestrator")
    graph.add_conditional_edges(
        "orchestrator",
        _route_after_orchestrator,
        {"analyst": "analyst", "finalize": "finalize"},
    )
    graph.add_conditional_edges(
        "analyst",
        _route_after_analyst,
        {"finalize": "finalize"},
    )
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=MemorySaver())


# ---------------------------------------------------------------------------
# Public graph runners
# ---------------------------------------------------------------------------


async def run_contradiction_graph(
    ctx: WorkflowContext,
    initial_state: CaseAnalysisState,
) -> CaseAnalysisState:
    graph = _build_simple_graph(ctx, "contradiction_analyst", make_contradiction_analyst_node(ctx))
    config = {
        "configurable": {"thread_id": initial_state.get("workflow_id", "workflow")},
        "recursion_limit": 10,
    }
    return await graph.ainvoke(initial_state, config=config)  # type: ignore[return-value]


async def run_advocate_graph(
    ctx: WorkflowContext,
    initial_state: CaseAnalysisState,
) -> CaseAnalysisState:
    graph = _build_simple_graph(ctx, "advocate_analyst", make_advocate_analyst_node(ctx))
    config = {
        "configurable": {"thread_id": initial_state.get("workflow_id", "workflow")},
        "recursion_limit": 10,
    }
    return await graph.ainvoke(initial_state, config=config)  # type: ignore[return-value]


async def run_judge_graph(
    ctx: WorkflowContext,
    initial_state: CaseAnalysisState,
) -> CaseAnalysisState:
    graph = _build_simple_graph(ctx, "judge_analyst", make_judge_analyst_node(ctx))
    config = {
        "configurable": {"thread_id": initial_state.get("workflow_id", "workflow")},
        "recursion_limit": 10,
    }
    return await graph.ainvoke(initial_state, config=config)  # type: ignore[return-value]


async def run_precedent_graph(
    ctx: WorkflowContext,
    initial_state: CaseAnalysisState,
) -> CaseAnalysisState:
    graph = _build_simple_graph(ctx, "precedent_analyst", make_precedent_analyst_node(ctx))
    config = {
        "configurable": {"thread_id": initial_state.get("workflow_id", "workflow")},
        "recursion_limit": 10,
    }
    return await graph.ainvoke(initial_state, config=config)  # type: ignore[return-value]
