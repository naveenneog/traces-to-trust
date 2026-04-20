# From Traces to Trust: Agentic Observability with OpenTelemetry

**24xAI APAC Session — April 21, 2026 | 11:30 AM – 12:30 PM IST**

## Session Overview

This session demonstrates end-to-end observability for modern multi-step AI agents using OpenTelemetry GenAI semantic conventions and Azure Monitor Application Insights. Attendees will learn how standardized spans for agent invocations, tool execution, and model calls enable consistent dashboards, faster root-cause analysis, and governance-ready audit trails.

## Repository Structure

```
traces-to-trust/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── session/
│   ├── session-guide.html       # Speaker notes & session flow (open in browser)
│   └── talk-track.md            # Detailed speaker talk track
├── demo/
│   ├── 01_basic_tracing.py      # Demo 1: Basic OTel tracing with console exporter
│   ├── 02_agent_workflow.py     # Demo 2: Multi-step agent with OTel GenAI spans
│   ├── 03_appinsights.py        # Demo 3: Export to Application Insights
│   ├── 04_mcp_tracing.py        # Demo 4: MCP tool call tracing
│   ├── 05_dashboard_queries.kql # KQL queries for App Insights dashboards
│   └── tools/
│       ├── __init__.py
│       ├── weather.py           # Mock weather tool
│       ├── database.py          # Mock database retrieval tool
│       └── email_tool.py        # Mock email sending tool
└── .env.example                 # Environment variable template
```

## Quick Start

```bash
# 1. Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows
source .venv/bin/activate     # Linux/Mac

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run Demo 1 (no Azure needed — console output)
python demo/01_basic_tracing.py

# 4. For App Insights demos, set env vars
copy .env.example .env
# Edit .env with your App Insights connection string

# 5. Run Demo 2-4
python demo/02_agent_workflow.py
python demo/03_appinsights.py
python demo/04_mcp_tracing.py
```

## Prerequisites

- Python 3.10+
- Azure OpenAI endpoint with Entra ID access (uses `DefaultAzureCredential` — no API key needed)
- Azure Application Insights resource (for Demo 3+)
- Azure AI Foundry project (optional, for portal tracing view)

## Key Concepts Covered

| Concept | OTel Convention | Demo |
|---------|----------------|------|
| Agent invocation | `gen_ai.operation.name: invoke_agent` | Demo 2 |
| Model inference | `gen_ai.operation.name: chat` | Demo 1, 2 |
| Tool execution | `gen_ai.operation.name: execute_tool` | Demo 2, 4 |
| MCP context propagation | `params._meta.traceparent` | Demo 4 |
| Token tracking | `gen_ai.usage.input_tokens` | All |
| Governance audit | Custom span attributes | Demo 3 |

## Speaker

**Naveen Gopalakrishna** — Solution Engineer, Microsoft
