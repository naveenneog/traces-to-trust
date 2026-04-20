"""
Live Demo 1: Basic OTel Tracing — Real LLM with Managed Identity
================================================================
Calls Azure OpenAI via DefaultAzureCredential (managed identity / az login).
Manual instrumentation with GenAI semantic conventions.

Requires:
  AZURE_OPENAI_ENDPOINT    — e.g. https://my-resource.openai.azure.com/
  AZURE_OPENAI_DEPLOYMENT  — e.g. gpt-4o

Run: python live/01_basic_tracing.py
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

# ─── Configure OTel with Console Exporter ───
resource = Resource.create({
    "service.name": "traces-to-trust-live",
    "service.version": "1.0.0",
    "deployment.environment": "live",
})

tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)

tracer = trace.get_tracer("traces-to-trust.live.demo1", "1.0.0")


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


def traced_chat_completion(client, model, messages, **kwargs):
    """Wrap a chat completion call with OTel GenAI semantic conventions."""
    with tracer.start_as_current_span(
        f"chat {model}",
        kind=trace.SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "chat",
            "gen_ai.system": "openai",
            "gen_ai.request.model": model,
            "gen_ai.request.max_tokens": kwargs.get("max_completion_tokens", kwargs.get("max_tokens", 0)),
            "gen_ai.request.temperature": kwargs.get("temperature", 1.0),
            "server.address": os.environ["AZURE_OPENAI_ENDPOINT"],
        },
    ) as span:
        # Opt-in: capture input messages
        span.set_attribute("gen_ai.input.messages", json.dumps(
            [{"role": m["role"], "parts": [{"type": "text", "content": m["content"]}]} for m in messages]
        ))

        response = client.chat.completions.create(model=model, messages=messages, **kwargs)

        # Record response attributes per GenAI semconv
        span.set_attribute("gen_ai.response.model", response.model)
        span.set_attribute("gen_ai.response.id", response.id)
        span.set_attribute("gen_ai.response.finish_reasons", [c.finish_reason for c in response.choices])
        span.set_attribute("gen_ai.usage.input_tokens", response.usage.prompt_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", response.usage.completion_tokens)

        return response


def run_basic_demo():
    """Simple chat completion with GenAI span — real LLM call."""
    print("\n" + "=" * 60)
    print("  LIVE DEMO 1: Basic OTel Tracing (Real LLM)")
    print("=" * 60)

    client = get_azure_client()
    model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    print(f"\n  Sending chat request to {model}...\n")
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Keep responses under 2 sentences."},
        {"role": "user", "content": "What is OpenTelemetry and why is it important for AI agents?"},
    ]
    response = traced_chat_completion(client, model, messages, max_completion_tokens=150, temperature=0.7)

    print(f"  Response: {response.choices[0].message.content}\n")
    print(f"  Tokens: {response.usage.prompt_tokens} in / {response.usage.completion_tokens} out")

    print("\n" + "─" * 60)
    print("KEY ATTRIBUTES in the span above:")
    print(f"  gen_ai.operation.name  : chat")
    print(f"  gen_ai.system          : openai")
    print(f"  gen_ai.request.model   : {model}")
    print(f"  gen_ai.response.model  : {response.model}")
    print(f"  gen_ai.usage.input_tokens  : {response.usage.prompt_tokens}")
    print(f"  gen_ai.usage.output_tokens : {response.usage.completion_tokens}")
    print(f"  server.address         : {os.environ['AZURE_OPENAI_ENDPOINT']}")
    print("─" * 60)


if __name__ == "__main__":
    run_basic_demo()
    tracer_provider.shutdown()
