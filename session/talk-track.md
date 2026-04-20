# From Traces to Trust — Speaker Talk Track

## 24xAI APAC | April 21, 2026 | 60 minutes

---

## Opening (5 min) — "The Black Box Problem"

### Slide: Title + Hook

> "Raise your hand if you've deployed an AI agent to production.
> Now keep it raised if you can tell me exactly why it called a specific tool last Thursday at 3 PM.
> That gap — between deploying and understanding — is what we're closing today."

**Key points:**
- Traditional software: request → response, well-understood observability
- AI agents: request → plan → tool calls → reasoning → response — opaque by default
- The gap creates trust issues: governance teams can't audit, SREs can't debug, customers can't verify
- **Thesis: Standardized traces are the bridge from "it works" to "we trust it"**

### Your Story — Cognizant AppDynamics → App Insights Journey
- "I've been on this journey with Cognizant — they had 100+ apps on AppDynamics, adopted App Insights for agent observability on AKS"
- "The first question their governance team asked: 'Can we see what the agent accessed and why?'"
- That question drove everything we'll cover today

---

## Section 1 (10 min) — "Why Agent Observability is Different"

### Slide: Traditional vs. Agentic

| Dimension | Traditional App | AI Agent |
|-----------|----------------|----------|
| Execution path | Deterministic | Non-deterministic |
| Tool calls | Predefined | LLM-decided at runtime |
| Data access | Code-controlled | Agent-initiated |
| Failure mode | Exception → stack trace | Wrong tool → wrong answer |
| Latency profile | Predictable | Variable (thinking time) |

**Talk track:**
> "When your agent decides to call `lookup_customer` instead of `get_weather`, that's not a bug — it's the agent reasoning. But without traces, you can't distinguish good reasoning from bad."

### Slide: The Trust Pyramid

```
                    ┌─────────┐
                    │  TRUST  │   ← Governance sign-off
                   ┌┴─────────┴┐
                   │ GOVERNANCE │   ← Audit trails, compliance
                  ┌┴───────────┴┐
                  │  DEBUGGING   │   ← Root cause analysis
                 ┌┴─────────────┴┐
                 │   MONITORING   │   ← Dashboards, alerts
                ┌┴───────────────┴┐
                │    TRACING       │   ← OTel spans, attributes
               ┌┴─────────────────┴┐
               │  INSTRUMENTATION   │   ← Code-level integration
               └───────────────────┘
```

> "Trust is built bottom-up. You can't have governance without debugging, and you can't debug without traces."

---

## Section 2 (15 min) — "OTel GenAI Semantic Conventions Deep Dive"

### Slide: The Three Span Types

1. **`invoke_agent`** — The agent invocation (root span)
   - `gen_ai.agent.name`, `gen_ai.agent.id`, `gen_ai.agent.version`
   - `gen_ai.provider.name`: identifies the AI platform
   - Aggregates total token usage

2. **`chat`** — Model inference calls
   - `gen_ai.request.model`, `gen_ai.response.model`
   - `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`
   - Multiple per agent invocation (planning + synthesis)

3. **`execute_tool`** — Tool execution
   - `gen_ai.tool.name`, `gen_ai.tool.call.id`
   - `gen_ai.tool.call.arguments` (opt-in)
   - `gen_ai.tool.call.result` (opt-in)

### Slide: Span Hierarchy (show Demo 2 output)

```
└── invoke_agent CustomerSuccessAgent    [CLIENT]
    ├── chat gpt-4o-mini                 [CLIENT] — planning
    ├── execute_tool lookup_customer     [INTERNAL]
    ├── execute_tool get_purchase_history [INTERNAL]
    ├── execute_tool get_weather          [INTERNAL]
    └── chat gpt-4o-mini                 [CLIENT] — synthesis
```

> "This is the Rosetta Stone of agent debugging. Every tool call, every model inference, every decision — captured in a standard format that any OTel-compatible backend can render."

### 🔴 DEMO 1 — Basic Tracing (3 min)
Run `demo/01_basic_tracing.py`
- Show the console span output
- Point out key attributes: `gen_ai.operation.name`, `gen_ai.system`, token usage
- "This is the atomic unit — a single model call. Now let's compose them."

### 🔴 DEMO 2 — Agent Workflow (5 min)
Run `demo/02_agent_workflow.py`
- Walk through the span hierarchy in console
- "Notice: invoke_agent is the parent, chat and execute_tool are children"
- "The trace ID ties everything together — one request, one trace"
- Show `gen_ai.tool.call.arguments` and `gen_ai.tool.call.result`
- "Opt-in content capture — you control what's recorded"

---

## Section 3 (10 min) — "From Console to Cloud: App Insights + Governance"

### Slide: The Governance Gap

> "Your CISO doesn't read console logs. Your compliance team needs queryable audit trails."

**What governance teams need:**
- Who triggered the agent?
- What data did it access? Why?
- What actions did it take? Who approved?
- Was PII handled correctly?
- What did it cost?

### Slide: Custom Governance Attributes

```python
# Standard OTel attributes
"gen_ai.operation.name": "invoke_agent"
"gen_ai.agent.name": "GovernedCSAgent"

# Custom governance layer
"governance.user.id": "navg@microsoft.com"
"governance.data.classification": "confidential"
"governance.compliance.tags": ["SOC2", "HIPAA"]
"governance.action.requires_approval": True
"governance.action.approved_by": "navg@microsoft.com"
"governance.pii.handling": "redacted"
```

> "OTel gives you the structure. You add the governance semantics your org needs."

### 🔴 DEMO 3 — App Insights + Governance (5 min)
Run `demo/03_appinsights.py`
- Show governance attributes on agent span
- Show `data.access.audit` event with user, table, operation
- Show `content.safety.check` event
- Show `action.audit` event with approval tracking
- If App Insights configured: show traces in Azure Portal
- Show KQL queries from `05_dashboard_queries.kql`

---

## Section 4 (10 min) — "MCP Tracing: The Cross-Process Bridge"

### Slide: Why MCP Changes Everything

> "MCP is becoming the USB for AI agents — a universal tool protocol. But without trace propagation, each MCP call is a black box."

**The problem:**
- Agent calls MCP server → new process, new context
- Without propagation: disconnected traces, no parent-child link
- With propagation: unified trace across agent ↔ MCP server

### Slide: W3C Traceparent in params._meta

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_weather",
    "arguments": {"location": "Singapore"},
    "_meta": {
      "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    }
  }
}
```

> "One line in `_meta` — that's all it takes to stitch together a distributed trace across MCP boundaries."

### 🔴 DEMO 4 — MCP Tracing (5 min)
Run `demo/04_mcp_tracing.py`
- Show the JSON-RPC request with traceparent in _meta
- Show CLIENT span (MCP client) → SERVER span (MCP server)
- "Same trace ID on both sides — that's the magic"
- Point out `mcp.method.name`, `mcp.protocol.version`, `mcp.session.id`

---

## Section 5 (5 min) — "Real-World Patterns from the Field"

### Slide: What We Learned at Scale

**From Cognizant (100+ apps, AKS):**
- Replaced AppDynamics with App Insights for agent workloads
- LangChain OTel instrumentation for Python agents
- Key insight: "Sampling is critical — 100% trace capture kills perf at scale"

**From Trizetto (Healthcare, Multi-tenant):**
- Semantic Kernel agents with per-tenant isolation
- Traces must include tenant ID for compliance
- HIPAA requires audit of every data access

**From Infosys (Agentic AI platform):**
- 150+ tools, multi-agent orchestration
- Copilot Studio's 15-tool limit vs. custom orchestrator
- Token cost attribution across business units

### Slide: Anti-Patterns to Avoid

1. ❌ **Logging everything** — PII in traces, storage explosion
2. ❌ **Missing trace context** — disconnected spans across services
3. ❌ **No sampling strategy** — 100% capture in production
4. ❌ **Custom-only attributes** — use standard GenAI conventions first
5. ❌ **Traces without dashboards** — data without visibility

---

## Closing (5 min) — "The Path Forward"

### Slide: Your Monday Checklist

1. **Instrument** — Add `opentelemetry-instrumentation-openai-v2` to your agent
2. **Export** — Configure `azure-monitor-opentelemetry` for App Insights
3. **Standardize** — Use GenAI semantic conventions, not custom spans
4. **Govern** — Add governance attributes for audit trails
5. **Dashboard** — Deploy KQL queries for real-time monitoring

### Slide: Resources

- Demo code: [link to this repo]
- OTel GenAI SemConv: https://opentelemetry.io/docs/specs/semconv/gen-ai/
- OTel MCP SemConv: https://opentelemetry.io/docs/specs/semconv/gen-ai/mcp/
- Azure Foundry Tracing: https://learn.microsoft.com/azure/ai-foundry/concepts/trace
- Azure Foundry Observability: https://learn.microsoft.com/azure/ai-foundry/concepts/observability

### Closing Line

> "Traces are the receipts of trust. When your governance team can query exactly what your agent did, when it did it, and why — that's when AI moves from prototype to production."

---

## Q&A Prep — Likely Questions

| Question | Answer |
|----------|--------|
| "What about PII in traces?" | Use opt-in content capture (`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`). Default is OFF. Add PII scrubbing processors. |
| "How does sampling work?" | Use `TraceIdRatioBased` sampler. Start at 10% in production, 100% in dev. App Insights also has adaptive sampling. |
| "Can I use Jaeger/Prometheus?" | Yes — OTel is backend-agnostic. Add exporters for any OTLP-compatible backend. |
| "What about streaming responses?" | OTel events capture streaming chunks. Total tokens counted at stream completion. |
| "Correlation ID across multi-agent?" | Trace ID propagates automatically. For multi-agent: each agent gets an `invoke_agent` span under the same trace. |
| "Cost of running App Insights?" | Log Analytics pricing. Typically $2-5/GB ingested. Use sampling to control volume. |
