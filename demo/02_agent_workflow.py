"""
Demo 2: Multi-Step Agent Workflow with OTel GenAI Semantic Conventions
=====================================================================
Shows the full agent span hierarchy:
  invoke_agent → chat (planning) → execute_tool → chat (synthesis)

This demonstrates the OTel GenAI Agent Spans spec with proper parent-child relationships.

Run: python demo/02_agent_workflow.py
"""
import os
import sys
import json
import time
sys.path.insert(0, os.path.dirname(__file__))

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource

os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"

resource = Resource.create({
    "service.name": "traces-to-trust-agent",
    "service.version": "1.0.0",
    "deployment.environment": "demo",
})

tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)

tracer = trace.get_tracer("traces-to-trust.agent", "1.0.0")

# ─── Import mock tools ───
from tools.weather import get_weather
from tools.database import lookup_customer, get_purchase_history
from tools.email_tool import send_email

# ─── Tool registry ───
TOOL_REGISTRY = {
    "get_weather": get_weather,
    "lookup_customer": lookup_customer,
    "get_purchase_history": get_purchase_history,
    "send_email": send_email,
}


def execute_tool_with_tracing(tool_name: str, arguments: dict) -> dict:
    """Execute a tool call with proper OTel GenAI execute_tool span."""
    with tracer.start_as_current_span(
        f"execute_tool {tool_name}",
        kind=trace.SpanKind.INTERNAL,
        attributes={
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": tool_name,
            "gen_ai.tool.call.id": f"call_{tool_name}_{int(time.time())}",
        },
    ) as span:
        # Record arguments (opt-in per OTel spec)
        span.set_attribute("gen_ai.tool.call.arguments", json.dumps(arguments))

        try:
            tool_fn = TOOL_REGISTRY.get(tool_name)
            if not tool_fn:
                raise ValueError(f"Unknown tool: {tool_name}")

            result = tool_fn(**arguments)
            span.set_attribute("gen_ai.tool.call.result", json.dumps(result))
            return result

        except Exception as e:
            span.set_attribute("error.type", type(e).__name__)
            span.set_status(trace.StatusCode.ERROR, str(e))
            raise


def simulate_llm_call(purpose: str, model: str = "gpt-4o-mini",
                       input_tokens: int = 0, output_tokens: int = 0) -> None:
    """Simulate an LLM inference call with proper chat span."""
    with tracer.start_as_current_span(
        f"chat {model}",
        kind=trace.SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "chat",
            "gen_ai.system": "openai",
            "gen_ai.request.model": model,
            "server.address": "api.openai.com",
        },
    ) as span:
        time.sleep(0.3)  # simulate LLM latency
        span.set_attribute("gen_ai.response.model", model)
        span.set_attribute("gen_ai.response.finish_reasons", ["stop"])
        span.set_attribute("gen_ai.usage.input_tokens", input_tokens or 85)
        span.set_attribute("gen_ai.usage.output_tokens", output_tokens or 42)
        span.add_event("llm.purpose", {"purpose": purpose})


def run_agent_workflow():
    """
    Simulates a Customer Success Agent that:
    1. Receives a user query
    2. Plans which tools to call (LLM)
    3. Executes tools (weather + customer lookup)
    4. Synthesizes a response (LLM)

    Span hierarchy:
    └── invoke_agent CustomerSuccessAgent
        ├── chat gpt-4o-mini          (planning)
        ├── execute_tool lookup_customer
        ├── execute_tool get_purchase_history
        ├── execute_tool get_weather
        ├── chat gpt-4o-mini          (synthesis)
        └── execute_tool send_email
    """
    print("\n" + "=" * 70)
    print("  DEMO 2: Multi-Step Agent — OTel GenAI Semantic Conventions")
    print("=" * 70)
    print("\nScenario: Customer Success Agent preparing an account briefing")
    print("Query: 'Prepare a briefing for Acme Corp including weather at HQ'\n")

    # Top-level agent invocation span
    with tracer.start_as_current_span(
        "invoke_agent CustomerSuccessAgent",
        kind=trace.SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "CustomerSuccessAgent",
            "gen_ai.agent.id": "agent_cs_001",
            "gen_ai.agent.description": "Prepares customer briefings with account data and context",
            "gen_ai.agent.version": "2.1.0",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.provider.name": "azure.ai.openai",
            "server.address": "my-foundry.openai.azure.com",
        },
    ) as agent_span:
        user_query = "Prepare a briefing for Acme Corp (C-1001) including weather at their HQ in Singapore"
        agent_span.add_event("gen_ai.user.message", {"content": user_query})

        # Step 1: Planning — LLM decides which tools to call
        print("  [1/5] Planning — LLM deciding tool calls...")
        simulate_llm_call("planning: determine required tools", input_tokens=120, output_tokens=85)

        # Step 2: Execute tool — Customer lookup
        print("  [2/5] Executing tool: lookup_customer...")
        customer = execute_tool_with_tracing("lookup_customer", {"customer_id": "C-1001"})
        print(f"        → Found: {customer['customer']['name']} ({customer['customer']['tier']})")

        # Step 3: Execute tool — Purchase history
        print("  [3/5] Executing tool: get_purchase_history...")
        history = execute_tool_with_tracing("get_purchase_history", {"customer_id": "C-1001", "limit": 3})
        print(f"        → {len(history['purchases'])} recent purchases")

        # Step 4: Execute tool — Weather at HQ
        print("  [4/5] Executing tool: get_weather...")
        weather = execute_tool_with_tracing("get_weather", {"location": "Singapore"})
        print(f"        → {weather['conditions']}, {weather['temperature']}°C")

        # Step 5: Synthesis — LLM generates final response
        print("  [5/5] Synthesizing response...")
        simulate_llm_call("synthesis: compose briefing from tool results", input_tokens=350, output_tokens=280)

        # Record total token usage on agent span
        agent_span.set_attribute("gen_ai.usage.input_tokens", 470)
        agent_span.set_attribute("gen_ai.usage.output_tokens", 365)

        print(f"\n  Agent completed successfully!")

    tracer_provider.force_flush()

    print("\n" + "─" * 70)
    print("SPAN HIERARCHY GENERATED:")
    print("─" * 70)
    print("""
  └── invoke_agent CustomerSuccessAgent    [gen_ai.agent.name, gen_ai.agent.id]
      ├── chat gpt-4o-mini                 [planning — 120 in / 85 out tokens]
      ├── execute_tool lookup_customer     [tool args + result captured]
      ├── execute_tool get_purchase_history [tool args + result captured]
      ├── execute_tool get_weather          [tool args + result captured]
      └── chat gpt-4o-mini                 [synthesis — 350 in / 280 out tokens]
    """)
    print("KEY ATTRIBUTES ON AGENT SPAN:")
    print("  • gen_ai.operation.name: invoke_agent")
    print("  • gen_ai.agent.name: CustomerSuccessAgent")
    print("  • gen_ai.agent.id: agent_cs_001")
    print("  • gen_ai.provider.name: azure.ai.openai")
    print("  • gen_ai.usage.input_tokens: 470 (total)")
    print("─" * 70)


if __name__ == "__main__":
    run_agent_workflow()
    tracer_provider.shutdown()
