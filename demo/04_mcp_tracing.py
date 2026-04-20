"""
Demo 4: MCP Tool Call Tracing with Context Propagation
======================================================
Demonstrates OpenTelemetry semantic conventions for Model Context Protocol.
Shows trace context propagation via params._meta.traceparent.

Run: python demo/04_mcp_tracing.py
"""
import os
import sys
import json
import time
import uuid
sys.path.insert(0, os.path.dirname(__file__))

from opentelemetry import trace, context
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace.propagation import get_current_span

os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"

resource = Resource.create({
    "service.name": "traces-to-trust-mcp",
    "service.version": "1.0.0",
})

tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)

tracer = trace.get_tracer("traces-to-trust.mcp", "1.0.0")


def format_traceparent(span) -> str:
    """Generate W3C traceparent from current span context."""
    ctx = span.get_span_context()
    return f"00-{ctx.trace_id:032x}-{ctx.span_id:016x}-01"


def simulate_mcp_client_call(method: str, tool_name: str, arguments: dict) -> dict:
    """
    Simulate an MCP client-side call with proper OTel MCP conventions.
    Shows context propagation via params._meta.traceparent.
    """
    with tracer.start_as_current_span(
        f"{method} {tool_name}",
        kind=trace.SpanKind.CLIENT,
        attributes={
            # MCP-specific attributes (per OTel MCP semconv)
            "mcp.method.name": method,
            "mcp.protocol.version": "2025-06-18",
            "mcp.session.id": "sess_demo_mcp_001",
            "network.transport": "tcp",
            "network.protocol.name": "http",
            # GenAI bridge attributes
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": tool_name,
            "gen_ai.tool.call.arguments": json.dumps(arguments),
            # Server info
            "server.address": "mcp-server.internal.corp",
            "server.port": 8443,
            # JSON-RPC
            "jsonrpc.request.id": str(uuid.uuid4())[:8],
            "jsonrpc.protocol.version": "2.0",
        },
    ) as span:
        # Build the MCP JSON-RPC request with trace context
        traceparent = format_traceparent(span)
        mcp_request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": {
                "name": tool_name,
                "arguments": arguments,
                "_meta": {
                    "traceparent": traceparent,
                },
            },
            "id": span.get_span_context().span_id,
        }

        print(f"    MCP Request (with traceparent in _meta):")
        print(f"    {json.dumps(mcp_request, indent=2)[:300]}...")

        # Simulate server-side processing
        result = simulate_mcp_server_handler(mcp_request)

        span.set_attribute("gen_ai.tool.call.result", json.dumps(result))
        return result


def simulate_mcp_server_handler(request: dict) -> dict:
    """
    Simulate MCP server receiving the request and extracting trace context.
    In production, the server would extract traceparent from params._meta
    and use it as the parent context for its spans.
    """
    with tracer.start_as_current_span(
        f"{request['method']} {request['params']['name']}",
        kind=trace.SpanKind.SERVER,
        attributes={
            "mcp.method.name": request["method"],
            "mcp.protocol.version": "2025-06-18",
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": request["params"]["name"],
        },
    ) as server_span:
        # Extract and log the propagated context
        meta = request["params"].get("_meta", {})
        traceparent = meta.get("traceparent", "none")
        server_span.add_event("mcp.context.extracted", {
            "traceparent": traceparent,
            "propagation": "W3C Trace Context via params._meta",
        })

        time.sleep(0.15)  # simulate tool execution

        tool_name = request["params"]["name"]
        args = request["params"].get("arguments", {})

        # Execute the actual tool
        from tools.weather import get_weather
        from tools.database import lookup_customer
        tool_map = {"get_weather": get_weather, "lookup_customer": lookup_customer}

        if tool_name in tool_map:
            result = tool_map[tool_name](**args)
        else:
            result = {"status": "ok", "data": "mock_result"}

        return result


def run_mcp_demo():
    """
    Demonstrates MCP tracing with:
    1. Agent deciding to call tools via MCP
    2. MCP client creating spans with mcp.* attributes
    3. Trace context propagated via params._meta.traceparent
    4. MCP server receiving and linking to parent trace
    """
    print("\n" + "=" * 70)
    print("  DEMO 4: MCP Tool Call Tracing with Context Propagation")
    print("=" * 70)
    print("\nScenario: Agent calling tools via MCP protocol")
    print("Shows: W3C traceparent propagation in params._meta\n")

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
        print("  [1/3] Agent planning (LLM decides tools)...")
        with tracer.start_as_current_span(
            "chat gpt-4o-mini",
            kind=trace.SpanKind.CLIENT,
            attributes={
                "gen_ai.operation.name": "chat",
                "gen_ai.system": "openai",
                "gen_ai.request.model": "gpt-4o-mini",
            },
        ):
            time.sleep(0.2)

        print("\n  [2/3] MCP tool call: get_weather...")
        weather = simulate_mcp_client_call(
            "tools/call", "get_weather",
            {"location": "Singapore"},
        )
        print(f"\n    Result: {weather['conditions']}, {weather['temperature']}°C")

        print("\n  [3/3] MCP tool call: lookup_customer...")
        customer = simulate_mcp_client_call(
            "tools/call", "lookup_customer",
            {"customer_id": "C-1001"},
        )
        print(f"\n    Result: {customer.get('customer', {}).get('name', 'N/A')}")

    tracer_provider.force_flush()

    print("\n" + "─" * 70)
    print("MCP TRACING CONVENTIONS DEMONSTRATED:")
    print("─" * 70)
    print("""
  Span Attributes (per OTel MCP SemConv):
    mcp.method.name          → tools/call
    mcp.protocol.version     → 2025-06-18
    mcp.session.id           → sess_demo_mcp_001
    jsonrpc.request.id       → unique per call
    gen_ai.tool.name         → get_weather, lookup_customer

  Context Propagation:
    W3C traceparent injected into params._meta:
    {
      "params": {
        "name": "get_weather",
        "_meta": {
          "traceparent": "00-<trace_id>-<span_id>-01"
        }
      }
    }

  Why This Matters:
    → Single trace ID across agent ↔ MCP server boundary
    → Parent-child relationship preserved across processes
    → Enables end-to-end latency analysis
    → Audit trail shows which agent triggered which tool
    """)
    print("─" * 70)


if __name__ == "__main__":
    run_mcp_demo()
    tracer_provider.shutdown()
