"""
Live Demo 2: Multi-Step Agent Workflow — Real LLM with Tool Calling
===================================================================
Real Azure OpenAI agent that:
  1. Receives a user query
  2. LLM plans which tools to call (function calling)
  3. Executes tools (weather + customer lookup)
  4. LLM synthesizes a final response

Full OTel GenAI agent span hierarchy with live token counts.

Requires:
  AZURE_OPENAI_ENDPOINT    — e.g. https://my-resource.openai.azure.com/
  AZURE_OPENAI_DEPLOYMENT  — e.g. gpt-4o

Run: python live/02_agent_workflow.py
"""
import os
import sys
import json
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
    "service.name": "traces-to-trust-agent-live",
    "service.version": "1.0.0",
    "deployment.environment": "live",
})

tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)

tracer = trace.get_tracer("traces-to-trust.live.agent", "1.0.0")

# ─── Import mock tools ───
from tools.weather import get_weather
from tools.database import lookup_customer, get_purchase_history

# ─── Tool registry ───
TOOL_REGISTRY = {
    "get_weather": get_weather,
    "lookup_customer": lookup_customer,
    "get_purchase_history": get_purchase_history,
}

# ─── Tool definitions for OpenAI function calling ───
TOOLS = [
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
    {
        "type": "function",
        "function": {
            "name": "get_purchase_history",
            "description": "Get recent purchase history for a customer",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "Customer ID"},
                    "limit": {"type": "integer", "description": "Max number of purchases to return", "default": 3},
                },
                "required": ["customer_id"],
            },
        },
    },
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


def execute_tool_with_tracing(tool_name: str, arguments: dict) -> dict:
    """Execute a tool call with proper OTel GenAI execute_tool span."""
    with tracer.start_as_current_span(
        f"execute_tool {tool_name}",
        kind=trace.SpanKind.INTERNAL,
        attributes={
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": tool_name,
            "gen_ai.tool.call.id": f"call_{tool_name}",
        },
    ) as span:
        span.set_attribute("gen_ai.tool.call.arguments", json.dumps(arguments))

        tool_fn = TOOL_REGISTRY.get(tool_name)
        if not tool_fn:
            span.set_status(trace.StatusCode.ERROR, f"Unknown tool: {tool_name}")
            raise ValueError(f"Unknown tool: {tool_name}")

        result = tool_fn(**arguments)
        span.set_attribute("gen_ai.tool.call.result", json.dumps(result))
        return result


def traced_chat(client, model, messages, tools=None, step_label=""):
    """Make a traced LLM call and return the response."""
    with tracer.start_as_current_span(
        f"chat {model}",
        kind=trace.SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "chat",
            "gen_ai.system": "openai",
            "gen_ai.request.model": model,
            "server.address": os.environ["AZURE_OPENAI_ENDPOINT"],
        },
    ) as span:
        kwargs = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = client.chat.completions.create(**kwargs)

        span.set_attribute("gen_ai.response.model", response.model)
        span.set_attribute("gen_ai.response.id", response.id)
        span.set_attribute("gen_ai.response.finish_reasons",
                           [c.finish_reason for c in response.choices])
        span.set_attribute("gen_ai.usage.input_tokens", response.usage.prompt_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", response.usage.completion_tokens)
        if step_label:
            span.add_event("llm.purpose", {"purpose": step_label})

        return response


def run_agent_workflow():
    """
    Real agent loop:
    1. Send user query + tools to LLM
    2. LLM returns tool_calls
    3. Execute each tool, collect results
    4. Send tool results back to LLM for synthesis
    """
    print("\n" + "=" * 70)
    print("  LIVE DEMO 2: Multi-Step Agent — Real LLM with Tool Calling")
    print("=" * 70)

    client = get_azure_client()
    model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    user_query = "Prepare a briefing for Acme Corp (customer ID C-1001) including weather at their HQ in Singapore"
    print(f"\n  Scenario: Customer Success Agent preparing an account briefing")
    print(f"  Query: '{user_query}'\n")

    total_input_tokens = 0
    total_output_tokens = 0

    with tracer.start_as_current_span(
        "invoke_agent CustomerSuccessAgent",
        kind=trace.SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "CustomerSuccessAgent",
            "gen_ai.agent.id": "agent_cs_001",
            "gen_ai.agent.description": "Prepares customer briefings with account data and context",
            "gen_ai.request.model": model,
            "gen_ai.provider.name": "azure.ai.openai",
            "server.address": os.environ["AZURE_OPENAI_ENDPOINT"],
        },
    ) as agent_span:
        agent_span.add_event("gen_ai.user.message", {"content": user_query})

        messages = [
            {"role": "system", "content": (
                "You are a Customer Success Agent. Use the available tools to gather "
                "customer data and weather information, then write a concise briefing. "
                "Always call lookup_customer and get_purchase_history for the customer, "
                "and get_weather for their HQ location."
            )},
            {"role": "user", "content": user_query},
        ]

        # Step 1: Planning — LLM decides which tools to call
        print("  [Step 1] Planning — LLM deciding tool calls...")
        response = traced_chat(client, model, messages, tools=TOOLS,
                               step_label="planning: determine required tools")
        total_input_tokens += response.usage.prompt_tokens
        total_output_tokens += response.usage.completion_tokens

        choice = response.choices[0]
        tool_calls = choice.message.tool_calls

        if not tool_calls:
            print("  LLM did not request any tools — printing direct response.")
            print(f"  {choice.message.content}")
        else:
            print(f"  LLM requested {len(tool_calls)} tool call(s):")
            for tc in tool_calls:
                print(f"    → {tc.function.name}({tc.function.arguments})")

            # Step 2: Execute each tool call
            messages.append(choice.message)

            for i, tc in enumerate(tool_calls, start=2):
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments)

                print(f"\n  [Step {i}] Executing tool: {fn_name}...")
                result = execute_tool_with_tracing(fn_name, fn_args)

                # Summarize result
                if fn_name == "lookup_customer" and result.get("status") == "found":
                    c = result["customer"]
                    print(f"    → Found: {c['name']} ({c['tier']}, {c['region']})")
                elif fn_name == "get_purchase_history":
                    print(f"    → {len(result.get('purchases', []))} recent purchases")
                elif fn_name == "get_weather":
                    print(f"    → {result['conditions']}, {result['temperature']}°C")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })

            # Step 3: Synthesis — LLM generates final response
            step_num = len(tool_calls) + 2
            print(f"\n  [Step {step_num}] Synthesizing briefing from tool results...")
            response = traced_chat(client, model, messages,
                                   step_label="synthesis: compose briefing from tool results")
            total_input_tokens += response.usage.prompt_tokens
            total_output_tokens += response.usage.completion_tokens

            print(f"\n  ── Agent Response ──")
            print(f"  {response.choices[0].message.content}")

        # Record totals on agent span
        agent_span.set_attribute("gen_ai.usage.input_tokens", total_input_tokens)
        agent_span.set_attribute("gen_ai.usage.output_tokens", total_output_tokens)

    tracer_provider.force_flush()

    print(f"\n" + "─" * 70)
    print("SPAN HIERARCHY GENERATED:")
    print("─" * 70)
    print(f"""
  └── invoke_agent CustomerSuccessAgent
      ├── chat {model}  (planning — LLM chose tools)
      ├── execute_tool lookup_customer
      ├── execute_tool get_purchase_history
      ├── execute_tool get_weather
      └── chat {model}  (synthesis — final briefing)
    """)
    print(f"  Total tokens: {total_input_tokens} in / {total_output_tokens} out")
    print("─" * 70)


if __name__ == "__main__":
    run_agent_workflow()
    tracer_provider.shutdown()
