# ADR-003: API Versioning

## Context

External consumers depend on stable API contracts. Breaking changes
have caused integration failures in the past.

## Decision

We will use URL-based versioning (v1, v2) because it provides clear
separation and is easily understood by API consumers.

## Alternatives Considered

- **Header-based versioning**: Cleaner URLs but harder to test in browser.
- **Query parameter versioning**: Non-standard, poor caching behavior.
