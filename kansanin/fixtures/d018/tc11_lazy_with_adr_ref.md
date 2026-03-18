# ADR-050: Caching Strategy

## Status

Accepted

## Context

We need a caching layer for the API gateway to reduce latency on repeated queries.

## Decision

We will use Redis or equivalent in-memory store as per ADR-031.

## Alternatives

We considered Redis or similar solutions as documented in ADR-031 and ADR-032. Other options were considered but deferred to those ADRs for detailed evaluation.

## Consequences

Caching introduces eventual consistency. TTL policies must be defined per endpoint.
