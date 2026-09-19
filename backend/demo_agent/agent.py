"""LangGraph customer-support agent, protected end-to-end by AgentShield.

Runs a small ReAct-style loop with Groq:
  - user prompt arrives
  - LLM chooses a tool to call
  - tool call goes through @shield.protect
  - ALLOW → tool runs, LLM sees the result, replies
  - BLOCK / ESCALATE → SDK raises; agent reports the outcome cleanly
"""
import os
import sys

from typing import Annotated, Any, TypedDict

# Make `demo_agent` and `shield` importable when run as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from demo_agent.tools import TOOL_REGISTRY
from shield import ShieldBlocked, ShieldEscalated, ShieldError


load_dotenv()


SYSTEM_PROMPT = (
    "You are a customer support agent for an e-commerce company. "
    "You have access to tools to look up orders and customers, send emails, "
    "and delete customers. "
    "Always call the appropriate tool immediately when the user asks. "
    "Do not ask for confirmation. Do not explain what you are about to do — "
    "just call the tool. If a tool call is blocked or requires approval, "
    "report that outcome to the user in one sentence."
)


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def build_agent():
    """Build a LangGraph agent wired to the protected tools."""

    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        raise SystemExit(
            "GROQ_API_KEY is not set in .env.\n"
            "Get one at https://console.groq.com/keys"
        )

    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        temperature=0,
        api_key=groq_key,
    )

    # Wrap our protected functions as LangChain tools. When the LLM
    # invokes one, the SDK intercepts and enforces the verdict.
    from langchain_core.tools import StructuredTool

    def _make_tool(name: str, func):
        def _safe_call(**kwargs):
            try:
                result = func(**kwargs)
                return f"OK: {result}"
            except ShieldBlocked as e:
                return f"BLOCKED by AgentShield: {e.reason}"
            except ShieldEscalated as e:
                return f"ESCALATED: needs human approval — {e.reason}"
            except ShieldError as e:
                return f"GATEWAY_ERROR: {e}"
        return StructuredTool.from_function(
            func=_safe_call,
            name=name,
            description=f"Call the {name} tool",
        )

    tools = [
        _make_tool("read_order", TOOL_REGISTRY["read_order"]),
        _make_tool("read_customer", TOOL_REGISTRY["read_customer"]),
        _make_tool("send_email", TOOL_REGISTRY["send_email"]),
        _make_tool("delete_customer", TOOL_REGISTRY["delete_customer"]),
    ]

    llm_with_tools = llm.bind_tools(tools)

    def call_model(state: AgentState) -> AgentState:
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


def run(prompt: str) -> None:
    agent = build_agent()

    print(f"\n=== User: {prompt}\n")

    initial_state: AgentState = {"messages": [HumanMessage(content=prompt)]}
    final_state: dict[str, Any] = {}

    for event in agent.stream(initial_state):
        for node_name, payload in event.items():
            if node_name == "tools":
                for msg in payload.get("messages", []):
                    if isinstance(msg, ToolMessage):
                        print(f"[tool] {msg.name} → {msg.content}")
            elif node_name == "agent":
                final_state = payload

    # Final reply
    if final_state.get("messages"):
        last = final_state["messages"][-1]
        content = getattr(last, "content", None)
        if content:
            print(f"\n=== Agent: {content}\n")


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python demo_agent/agent.py "<prompt>"')
        sys.exit(1)
    prompt = " ".join(sys.argv[1:])
    run(prompt)


if __name__ == "__main__":
    main()