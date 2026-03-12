# ADR-002: Cache Strategy

## Context

API response times exceed SLA (p99 > 500ms) due to repeated database
queries for frequently accessed catalog data.

## Decision

We will deploy Redis 7 as an application-level cache with TTL-based
invalidation because it provides sub-millisecond reads and native
support for our data structures.

## Consequences

- Cache invalidation adds complexity to write paths.
- Redis cluster requires additional infrastructure and monitoring.
- Expected p99 improvement: 500ms to 50ms for cached endpoints.
