# ADR 0001: Initial Architecture

**Status**: Accepted
**Date**: 2025-01-01
**Decision Makers**: James C. Young

## Context

AI-Orchestra needs to provide a unified platform for orchestrating AI-powered automation workflows across multiple services (OpenAI, GitHub, Notion, Gmail). The system must support both programmatic access and interactive use by non-developers.

Key requirements:
- Multi-step workflow execution with variable interpolation
- Support for multiple external service integrations
- Both API and visual interfaces
- Complete audit trails for compliance

## Decision

We will implement a layered architecture with:

1. **Dual Interface Layer**: FastAPI REST API + Streamlit Dashboard
2. **Core Engine Layer**: Workflow engine, prompt manager, authentication
3. **Integration Layer**: Pluggable clients for each external service

Workflow definitions will use JSON for declarative configuration rather than imperative code.

## Alternatives Considered

### Alternative 1: Code-based workflows (Python DSL)
- **Pros**: More flexible, type-safe at development time
- **Cons**: Requires Python knowledge, harder to visualize, no UI editing
- **Rejected**: Non-developers need to create/edit workflows

### Alternative 2: Visual-only workflow builder (no API)
- **Pros**: Easy for non-technical users
- **Cons**: Can't integrate with CI/CD, no programmatic access
- **Rejected**: Both programmatic and interactive access required

### Alternative 3: Single interface (API only)
- **Pros**: Simpler implementation
- **Cons**: Excludes users who prefer visual interaction
- **Rejected**: Dual interface serves broader user base

## Consequences

### Positive
- Non-developers can create workflows via dashboard
- Programmatic access enables CI/CD integration
- Pluggable architecture allows adding new services without core changes
- JSON definitions are version-controllable and diffable

### Negative
- Two interfaces require parallel maintenance
- JSON workflows have limited expressiveness vs. code
- In-memory storage (v1) loses data on restart

### Risks
- Dashboard may diverge from API capabilities
- JSON schema needs careful versioning as features evolve

## Follow-up Actions

1. Implement database persistence (PostgreSQL) for production use
2. Add workflow versioning and migration tooling
3. Create visual workflow builder component for dashboard
