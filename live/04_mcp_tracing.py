"""
Live Demo 4: MCP Tool Call Tracing — Real LLM with Context Propagation
======================================================================
Real Azure OpenAI LLM decides which MCP tools to call.
Demonstrates W3C traceparent propagation via params._meta.

The LLM planning step is real; tools remain mock (simulating remote MCP servers).

Requires:
  AZURE_OPENAI_ENDPOINT    — e.g. https://my-resource.openai.azure.com/
  AZURE_OPENAI_DEPLOYMENT  — e.g. gpt-4o

Run: python live/04_mcp_tracing.py
"""
import os
import sys
import json
import time
import uuid
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource

os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"

resource = Resource.create({
    "service.name": "traces-to-trust-mcp-live",
    "service.version": "1.0.0",
})

tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)

tracer = trace.get_tracer("traces-to-trust.live.mcp", "1.0.0")

# ─── Tool definitions for LLM function calling ───
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name, e.g. 'Singapore'"},
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_customer",
            "description": "Look up customer information by customer ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "Customer ID, e.g. 'C-1001'"},
                },
                "required": ["customer_id"],
            },
        },
    },
]


def get_azure_client():
    """Create Azure OpenAI client with managed identity."""
    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    tenant_id = os.getenv("AZURE_TENANT_ID")
    cred_kwargs = {"tenant_id": tenant_id} if tenant_id else {}
    credential = DefaultAzureCredential(**cred_kwargs)
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version="2025-03-01-preview",
    )


def format_traceparent(span) -> str:
    """Generate W3C traceparent from current span context."""
    ctx = span.get_span_context()
    return f"00-{ctx.trace_id:032x}-{ctx.span_id:016x}-01"


def execute_mcp_tool_call(tool_name: str, arguments: dict) -> dict:
    """
    Simulate MCP client → server call with full OTel tracing.
    Client span (SpanKind.CLIENT) + Server span (SpanKind.SERVER)
    with W3C traceparent propagation via params._meta.
    """
    with tracer.start_as_current_span(
        f"tools/call {tool_name}",
        kind=trace.SpanKind.CLIENT,
        attributes={
            "mcp.method.name": "tools/call",
            "mcp.protocol.version": "2025-06-18",
            "mcp.session.id": "sess_live_mcp_001",
            "network.transport": "tcp",
            "network.protocol.name": "http",
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": tool_name,
            "gen_ai.tool.call.arguments": json.dumps(arguments),
            "server.address": "mcp-server.internal.corp",
            "server.port": 8443,
            "jsonrpc.request.id": str(uuid.uuid4())[:8],
            "jsonrpc.protocol.version": "2.0",
        },
    ) as client_span:
        traceparent = format_traceparent(client_span)

        mcp_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
                "_meta": {"traceparent": traceparent},
            },
            "id": client_span.get_span_context().span_id,
        }

        print(f"    traceparent: {traceparent}")

        # Simulate MCP server handler
        with tracer.start_as_current_span(
            f"tools/call {tool_name}",
            kind=trace.SpanKind.SERVER,
            attributes={
                "mcp.method.name": "tools/call",
                "mcp.protocol.version": "2025-06-18",
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": tool_name,
            },
        ) as server_span:
            server_span.add_event("mcp.context.extracted", {
                "traceparent": traceparent,
                "propagation": "W3C Trace Context via params._meta",
            })

            from tools.weather import get_weather
            from tools.database import lookup_customer
            tool_map = {"get_weather": get_weather, "lookup_customer": lookup_customer}

            result = tool_map[tool_name](**arguments) if tool_name in tool_map else {"status": "unknown_tool"}

        client_span.set_attribute("gen_ai.tool.call.result", json.dumps(result))
        return result


def run_mcp_demo():
    """
    Real LLM plans tool calls, executed via MCP protocol simulation.
    Shows end-to-end trace propagation across agent → MCP server boundary.
    """
    print("\n" + "=" * 70)
    print("  LIVE DEMO 4: MCP Tool Tracing — Real LLM + Context Propagation")
    print("=" * 70)
    print("\nScenario: Agent calling tools via MCP protocol")
    print("Shows: W3C traceparent propagation in params._meta\n")

    client = get_azure_client()
    model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    with tracer.start_as_current_span(
        "invoke_agent MCPEnabledAgent",
        kind=trace.SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "MCPEnabledAgent",
            "gen_ai.agent.id": "agent_mcp_001",
            "gen_ai.provider.name": "azure.ai.openai",
        },
    ) as agent_span:

        # Step 1: Real LLM planning
        print("  [Step 1] LLM planning (real call — deciding tools)...")
        messages = [
            {"role": "system", "content": (
                "You are an agent that uses MCP tools. Given a user request, "
                "decide which tools to call. Available: get_weather, lookup_customer."
            )},
            {"role": "user", "content": (
                "Look up customer C-1001 and check the weather in Singapore."
            )},
        ]

        with tracer.start_as_current_span(
            f"chat {model}",
            kind=trace.SpanKind.CLIENT,
            attributes={
                "gen_ai.operation.name": "chat",
                "gen_ai.system": "openai",
                "gen_ai.request.model": model,
                "server.address": os.environ["AZURE_OPENAI_ENDPOINT"],
            },
        ) as plan_span:
            response = client.chat.completions.create(
                model=model, messages=messages, tools=TOOLS, tool_choice="auto",
            )
            plan_span.set_attribute("gen_ai.response.model", response.model)
            plan_span.set_attribute("gen_ai.usage.input_tokens", response.usage.prompt_tokens)
            plan_span.set_attribute("gen_ai.usage.output_tokens", response.usage.completion_tokens)
            plan_span.set_attribute("gen_ai.response.finish_reasons",
                                    [response.choices[0].finish_reason])
            plan_span.add_event("llm.purpose", {"purpose": "planning: determine MCP tools to call"})

        print(f"    → {response.usage.prompt_tokens} in / {response.usage.completion_tokens} out tokens")

        tool_calls = response.choices[0].message.tool_calls or []
        print(f"    → LLM requested {len(tool_calls)} MCP tool call(s)")

        # Step 2+: Execute each tool via MCP
        for i, tc in enumerate(tool_calls, start=2):
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments)

            print(f"\n  [Step {i}] MCP tool call: {fn_name}({json.dumps(fn_args)})...")
            result = execute_mcp_tool_call(fn_name, fn_args)

            if fn_name == "get_weather":
                print(f"    → {result['conditions']}, {result['temperature']}°C")
            elif fn_name == "lookup_customer" and result.get("status") == "found":
                print(f"    → {result['customer']['name']} ({result['customer']['tier']})")

    tracer_provider.force_flush()

    print(f"\n" + "─" * 70)
    print("MCP TRACING CONVENTIONS DEMONSTRATED:")
    print("─" * 70)
    print("""
  Span Attributes (per OTel MCP SemConv):
    mcp.method.name          → tools/call
    mcp.protocol.version     → 2025-06-18
    mcp.session.id           → sess_live_mcp_001
    gen_ai.tool.name         → get_weather, lookup_customer

  Context Propagation:
    W3C traceparent injected into params._meta
    Same trace ID across agent ↔ MCP server boundary

  Span Pairs per Tool Call:
    CLIENT span (agent side) → SERVER span (MCP server side)
    Parent-child relationship preserved across processes
    """)
    print("─" * 70)


if __name__ == "__main__":
    run_mcp_demo()
    tracer_provider.shutdown()
