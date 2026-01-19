"""Distributed tracing for Gorgon workflows.

Provides W3C Trace Context compatible tracing with:
- Trace and span ID generation
- Context propagation across functions and async calls
- Integration with structured logging
- HTTP header propagation (traceparent, tracestate)
"""

from test_ai.tracing.context import (
    TraceContext,
    Span,
    get_current_trace,
    get_current_span,
    start_trace,
    start_span,
    trace_context,
    span_context,
)
from test_ai.tracing.propagation import (
    extract_trace_context,
    inject_trace_headers,
    TRACEPARENT_HEADER,
    TRACESTATE_HEADER,
)
from test_ai.tracing.middleware import TracingMiddleware

__all__ = [
    "TraceContext",
    "Span",
    "get_current_trace",
    "get_current_span",
    "start_trace",
    "start_span",
    "trace_context",
    "span_context",
    "extract_trace_context",
    "inject_trace_headers",
    "TRACEPARENT_HEADER",
    "TRACESTATE_HEADER",
    "TracingMiddleware",
]
