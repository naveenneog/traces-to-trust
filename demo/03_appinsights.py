"""
Demo 3: Export to Azure Application Insights + Governance Attributes
====================================================================
Sends traces to App Insights for dashboard visualization.
Adds custom governance attributes for audit trails.

Requires: APPLICATIONINSIGHTS_CONNECTION_STRING env var

Run: python demo/03_appinsights.py
"""
import os
import sys
import json
import time
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

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

# Always add console for demo visibility
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
tracer = trace.get_tracer("traces-to-trust.governance", "1.0.0")

from tools.database import lookup_customer
from tools.email_tool import send_email


def run_governed_agent():
    """
    Agent with governance-grade observability:
    - User identity tracking
    - Data access audit trail
    - PII handling flags
    - Compliance tags
    - Cost attribution
    """
    print("\n" + "=" * 70)
    print("  DEMO 3: App Insights + Governance Audit Trail")
    print("=" * 70)
    print("\nScenario: Governed agent with audit-ready traces\n")

    with tracer.start_as_current_span(
        "invoke_agent GovernedCSAgent",
        kind=trace.SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "GovernedCSAgent",
            "gen_ai.agent.id": "agent_gov_001",
            "gen_ai.provider.name": "azure.ai.openai",
            "gen_ai.request.model": "gpt-4o",
            # ─── Governance Attributes ───
            "governance.user.id": "navg@microsoft.com",
            "governance.user.role": "solution_engineer",
            "governance.session.id": "sess_24xai_demo_001",
            "governance.data.classification": "confidential",
            "governance.compliance.tags": json.dumps(["SOC2", "HIPAA", "ISO27001"]),
            "governance.cost.budget_code": "ITES-AI-2026-Q2",
            "governance.pii.handling": "redacted",
        },
    ) as agent_span:
        print("  [1/3] Looking up customer (audit-logged)...")

        # Tool call with data access audit
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
            result = lookup_customer(customer_id="C-1001")
            tool_span.set_attribute("gen_ai.tool.call.result", json.dumps(result))
            tool_span.add_event("data.access.audit", {
                "table": "customers",
                "operation": "read",
                "records_accessed": 1,
                "user": "navg@microsoft.com",
            })
            print(f"        → {result['customer']['name']} accessed (audit event logged)")

        # LLM call with cost tracking
        print("  [2/3] LLM inference (cost-tracked)...")
        with tracer.start_as_current_span(
            "chat gpt-4o",
            kind=trace.SpanKind.CLIENT,
            attributes={
                "gen_ai.operation.name": "chat",
                "gen_ai.system": "openai",
                "gen_ai.request.model": "gpt-4o",
                "governance.cost.estimated_usd": 0.0045,
                "governance.model.safety_filter": "enabled",
                "governance.content.grounding_sources": json.dumps(["customer_db", "crm"]),
            },
        ) as llm_span:
            time.sleep(0.4)
            llm_span.set_attribute("gen_ai.usage.input_tokens", 520)
            llm_span.set_attribute("gen_ai.usage.output_tokens", 310)
            llm_span.set_attribute("gen_ai.response.finish_reasons", ["stop"])
            # Content safety result
            llm_span.add_event("content.safety.check", {
                "hate": "safe",
                "violence": "safe",
                "self_harm": "safe",
                "sexual": "safe",
            })
            print("        → 520 in / 310 out tokens, safety: all clear")

        # Action with human-in-the-loop audit
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
                "governance.action.approval_timestamp": "2026-04-21T11:42:00Z",
            },
        ) as action_span:
            result = send_email(
                to="customer@acmecorp.com",
                subject="Account Briefing - Q2 2026",
                body="[Redacted for PII compliance]",
            )
            action_span.set_attribute("gen_ai.tool.call.result", json.dumps(result))
            action_span.add_event("action.audit", {
                "type": "email_sent",
                "recipient_domain": "acmecorp.com",
                "pii_redacted": True,
            })
            print(f"        → Sent (msg_id: {result['message_id'][:8]}...)")

        # Summary metrics on agent span
        agent_span.set_attribute("gen_ai.usage.input_tokens", 520)
        agent_span.set_attribute("gen_ai.usage.output_tokens", 310)
        agent_span.set_attribute("governance.total_tools_called", 2)
        agent_span.set_attribute("governance.total_actions_taken", 1)
        agent_span.set_attribute("governance.cost.total_estimated_usd", 0.0045)

    tracer_provider.force_flush()

    print("\n" + "─" * 70)
    print("GOVERNANCE ATTRIBUTES CAPTURED:")
    print("─" * 70)
    print("""
  Agent Level:
    governance.user.id           → navg@microsoft.com
    governance.data.classification → confidential
    governance.compliance.tags    → [SOC2, HIPAA, ISO27001]
    governance.cost.budget_code   → ITES-AI-2026-Q2

  Data Access:
    governance.data.accessed      → customer_records
    governance.data.sensitivity   → PII

  Action Audit:
    governance.action.type        → external_communication
    governance.action.approved_by → navg@microsoft.com

  Events:
    data.access.audit            → table, operation, records count
    content.safety.check          → hate/violence/self_harm/sexual
    action.audit                  → type, recipient, pii_redacted
    """)

    if conn_string:
        print("✅ All traces exported to Application Insights!")
        print("   Open Azure Portal → App Insights → Transaction Search")
        print("   Filter by: service.name = 'traces-to-trust-production'")
    print("─" * 70)


if __name__ == "__main__":
    run_governed_agent()
    tracer_provider.shutdown()
