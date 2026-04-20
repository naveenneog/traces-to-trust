"""
Demo 1: Basic OTel Tracing with Console Exporter
=================================================
No Azure needed — traces output to console.
Shows: GenAI semantic conventions for model inference spans.

This uses MANUAL instrumentation to teach the OTel concepts explicitly.
In production, you'd use opentelemetry-instrumentation-openai-v2 for auto-instrumentation.

Run: python demo/01_basic_tracing.py
"""
import os
import sys
import time
import json
sys.path.insert(0, os.path.dirname(__file__))

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource

os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"

# ─── Configure OTel with Console Exporter ───
resource = Resource.create({
    "service.name": "traces-to-trust-demo",
    "service.version": "1.0.0",
    "deployment.environment": "demo",
})

tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)

tracer = trace.get_tracer("traces-to-trust.demo1", "1.0.0")


def traced_chat_completion(client, model, messages, **kwargs):
    """Wrap a chat completion call with OTel GenAI semantic conventions."""
    with tracer.start_as_current_span(
        f"chat {model}",
        kind=trace.SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "chat",
            "gen_ai.system": "openai",
            "gen_ai.request.model": model,
            "gen_ai.request.max_tokens": kwargs.get("max_tokens", 0),
            "gen_ai.request.temperature": kwargs.get("temperature", 1.0),
            "server.address": getattr(client, '_base_url', 'api.openai.com'),
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
    """Simple chat completion with GenAI span."""
    base_url = os.getenv("AZURE_OPENAI_ENDPOINT")

    if not base_url:
        print("\n" + "=" * 60)
        print("  DEMO 1: Basic OTel Tracing (Simulated)")
        print("=" * 60)
        print("\nNo AZURE_OPENAI_ENDPOINT — simulating spans for demo...\n")
        _simulate_basic_spans()
        return

    print("\n" + "=" * 60)
    print("  DEMO 1: Basic OTel Tracing (Live)")
    print("=" * 60)

    from openai import AzureOpenAI
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
    client = AzureOpenAI(
        azure_endpoint=base_url,
        azure_ad_token_provider=token_provider,
        api_version="2025-03-01-preview",
    )
    model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")

    print(f"\nSending chat request to {model}...\n")
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is OpenTelemetry and why is it important for AI agents?"},
    ]
    response = traced_chat_completion(client, model, messages, max_tokens=150)
    print(f"Response: {response.choices[0].message.content}\n")
    _print_key_attributes(model)


def _simulate_basic_spans():
    """Generate synthetic spans without an API key."""
    with tracer.start_as_current_span(
        "chat gpt-4o-mini",
        kind=trace.SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "chat",
            "gen_ai.system": "openai",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.request.max_tokens": 150,
            "gen_ai.request.temperature": 0.7,
            "server.address": "api.openai.com",
        },
    ) as span:
        time.sleep(0.5)
        span.set_attribute("gen_ai.response.model", "gpt-4o-mini-2025-07-18")
        span.set_attribute("gen_ai.response.id", "chatcmpl-demo-12345")
        span.set_attribute("gen_ai.response.finish_reasons", ("stop",))
        span.set_attribute("gen_ai.usage.input_tokens", 42)
        span.set_attribute("gen_ai.usage.output_tokens", 128)
        print("  Simulated chat span generated!")

    tracer_provider.force_flush()
    _print_key_attributes("gpt-4o-mini")


def _print_key_attributes(model):
    print("\n" + "─" * 60)
    print("KEY ATTRIBUTES in the span above:")
    print("  gen_ai.operation.name  : chat")
    print("  gen_ai.system          : openai")
    print(f"  gen_ai.request.model   : {model}")
    print("  gen_ai.usage.input_tokens  : (captured)")
    print("  gen_ai.usage.output_tokens : (captured)")
    print("  server.address         : (captured)")
    print("─" * 60)


if __name__ == "__main__":
    run_basic_demo()
    tracer_provider.shutdown()
