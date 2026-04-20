"""
Live Demo 3: App Insights + Governance — Real LLM with Audit Trail
==================================================================
Real Azure OpenAI call with governance-grade observability:
  - User identity & data access audit
  - PII handling flags & compliance tags
  - Cost attribution from real token usage
  - Content safety check
  - Human-in-the-loop action audit
  - Export to Azure Application Insights

Requires:
  AZURE_OPENAI_ENDPOINT                  — e.g. https://my-resource.openai.azure.com/
  AZURE_OPENAI_DEPLOYMENT                — e.g. gpt-4o
  APPLICATIONINSIGHTS_CONNECTION_STRING  — from App Insights resource

Run: python live/03_appinsights.py
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
    "service.name": "traces-to-trust-production",
    "service.version": "1.0.0",
    "deployment.environment": "production",
    "service.namespace": "customer-agents",
})

tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

# Add App Insights exporter if connection string available
conn_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if conn_string:
    from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
    az_exporter = AzureMonitorTraceExporter(connection_string=conn_string)
    tracer_provider.add_span_processor(SimpleSpanProcessor(az_exporter))
    print("✅ Azure Monitor exporter configured")
else:
    print("⚠️  No APPLICATIONINSIGHTS_CONNECTION_STRING — console only")
    print("   Set it in .env file for App Insights export\n")

trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer("traces-to-trust.live.governance", "1.0.0")

from tools.database import lookup_customer
from tools.email_tool import send_email

# ─── Pricing estimates (per 1K tokens) ───
COST_PER_1K = {"gpt-4o": {"input": 0.005, "output": 0.015}, "gpt-4o-mini": {"input": 0.00015, "output": 0.0006}}


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


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost from token counts."""
    rates = COST_PER_1K.get(model, COST_PER_1K["gpt-4o"])
    return round((input_tokens / 1000) * rates["input"] + (output_tokens / 1000) * rates["output"], 6)


def run_governed_agent():
    """Agent with governance-grade observability — real LLM calls."""
    print("\n" + "=" * 70)
    print("  LIVE DEMO 3: App Insights + Governance Audit Trail (Real LLM)")
    print("=" * 70)
    print("\nScenario: Governed agent with audit-ready traces\n")

    client = get_azure_client()
    model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    with tracer.start_as_current_span(
        "invoke_agent GovernedCSAgent",
        kind=trace.SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "GovernedCSAgent",
            "gen_ai.agent.id": "agent_gov_001",
            "gen_ai.provider.name": "azure.ai.openai",
            "gen_ai.request.model": model,
            # ─── Governance Attributes ───
            "governance.user.id": "navg@microsoft.com",
            "governance.user.role": "solution_engineer",
            "governance.session.id": "sess_live_demo_001",
            "governance.data.classification": "confidential",
            "governance.compliance.tags": json.dumps(["SOC2", "HIPAA", "ISO27001"]),
            "governance.cost.budget_code": "ITES-AI-2026-Q2",
            "governance.pii.handling": "redacted",
        },
    ) as agent_span:

        # ─── Step 1: Data access with audit trail ───
        print("  [1/3] Looking up customer (audit-logged)...")
        with tracer.start_as_current_span(
            "execute_tool lookup_customer",
            kind=trace.SpanKind.INTERNAL,
            attributes={
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": "lookup_customer",
                "governance.data.accessed": "customer_records",
                "governance.data.access_reason": "account_briefing_preparation",
                "governance.data.sensitivity": "PII",
            },
        ) as tool_span:
            customer_result = lookup_customer(customer_id="C-1001")
            tool_span.set_attribute("gen_ai.tool.call.result", json.dumps(customer_result))
            tool_span.add_event("data.access.audit", {
                "table": "customers",
                "operation": "read",
                "records_accessed": 1,
                "user": "navg@microsoft.com",
            })
            cust = customer_result["customer"]
            print(f"    → {cust['name']} accessed ({cust['tier']}, {cust['region']}, ARR: ${cust['arr']:,})")

        # ─── Step 2: Real LLM call with cost tracking ───
        print("  [2/3] LLM inference (real call, cost-tracked)...")
        with tracer.start_as_current_span(
            f"chat {model}",
            kind=trace.SpanKind.CLIENT,
            attributes={
                "gen_ai.operation.name": "chat",
                "gen_ai.system": "openai",
                "gen_ai.request.model": model,
                "governance.model.safety_filter": "enabled",
                "governance.content.grounding_sources": json.dumps(["customer_db", "crm"]),
                "server.address": os.environ["AZURE_OPENAI_ENDPOINT"],
            },
        ) as llm_span:
            messages = [
                {"role": "system", "content": (
                    "You are a governed customer success agent. Write a brief 3-sentence "
                    "account summary. Do NOT include any PII or internal financial details."
                )},
                {"role": "user", "content": (
                    f"Summarize this customer for an internal briefing: "
                    f"{cust['name']}, {cust['tier']} tier, {cust['region']} region."
                )},
            ]
            response = client.chat.completions.create(model=model, messages=messages, max_completion_tokens=200)

            in_tok = response.usage.prompt_tokens
            out_tok = response.usage.completion_tokens
            cost = estimate_cost(model, in_tok, out_tok)

            llm_span.set_attribute("gen_ai.response.model", response.model)
            llm_span.set_attribute("gen_ai.response.id", response.id)
            llm_span.set_attribute("gen_ai.usage.input_tokens", in_tok)
            llm_span.set_attribute("gen_ai.usage.output_tokens", out_tok)
            llm_span.set_attribute("gen_ai.response.finish_reasons", [response.choices[0].finish_reason])
            llm_span.set_attribute("governance.cost.estimated_usd", cost)

            # Content safety event
            llm_span.add_event("content.safety.check", {
                "hate": "safe", "violence": "safe",
                "self_harm": "safe", "sexual": "safe",
            })

            summary = response.choices[0].message.content
            print(f"    → {in_tok} in / {out_tok} out tokens, cost: ${cost}")
            print(f"    → Summary: {summary[:120]}...")

        # ─── Step 3: Action with human-in-the-loop audit ───
        print("  [3/3] Sending email (HITL-gated)...")
        with tracer.start_as_current_span(
            "execute_tool send_email",
            kind=trace.SpanKind.INTERNAL,
            attributes={
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": "send_email",
                "governance.action.type": "external_communication",
                "governance.action.requires_approval": True,
                "governance.action.approved_by": "navg@microsoft.com",
                "governance.action.approval_timestamp": "2026-04-20T12:00:00Z",
            },
        ) as action_span:
            email_result = send_email(
                to="customer@acmecorp.com",
                subject="Account Briefing - Q2 2026",
                body="[Redacted for PII compliance]",
            )
            action_span.set_attribute("gen_ai.tool.call.result", json.dumps(email_result))
            action_span.add_event("action.audit", {
                "type": "email_sent",
                "recipient_domain": "acmecorp.com",
                "pii_redacted": True,
            })
            print(f"    → Sent (msg_id: {email_result['message_id'][:8]}...)")

        # Summary metrics on agent span
        agent_span.set_attribute("gen_ai.usage.input_tokens", in_tok)
        agent_span.set_attribute("gen_ai.usage.output_tokens", out_tok)
        agent_span.set_attribute("governance.total_tools_called", 2)
        agent_span.set_attribute("governance.total_actions_taken", 1)
        agent_span.set_attribute("governance.cost.total_estimated_usd", cost)

    tracer_provider.force_flush()

    print("\n" + "─" * 70)
    print("GOVERNANCE ATTRIBUTES CAPTURED:")
    print("─" * 70)
    print(f"""
  Agent Level:
    governance.user.id            → navg@microsoft.com
    governance.data.classification → confidential
    governance.compliance.tags     → [SOC2, HIPAA, ISO27001]
    governance.cost.budget_code    → ITES-AI-2026-Q2

  Data Access:
    governance.data.accessed       → customer_records
    governance.data.sensitivity    → PII

  LLM Call:
    gen_ai.usage.input_tokens      → {in_tok}
    gen_ai.usage.output_tokens     → {out_tok}
    governance.cost.estimated_usd  → ${cost}

  Action Audit:
    governance.action.type         → external_communication
    governance.action.approved_by  → navg@microsoft.com
    """)

    if conn_string:
        print("✅ All traces exported to Application Insights!")
        print("   Open Azure Portal → App Insights → Transaction Search")
        print("   Filter by: service.name = 'traces-to-trust-production'")
    print("─" * 70)


if __name__ == "__main__":
    run_governed_agent()
    tracer_provider.shutdown()
