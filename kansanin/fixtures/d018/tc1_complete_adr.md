# ADR-001: Database Selection

## Context

The system requires persistent storage for user profiles, transactions,
and analytics data. Current SQLite deployment cannot handle projected
load of 10k concurrent connections.

## Decision

We will use PostgreSQL 15 as the primary relational database because
it provides the best balance of performance, reliability, and ecosystem
support for our use case.

## Alternatives Considered

- **MySQL 8**: Good performance, but weaker JSON support and window functions.
- **CockroachDB**: Excellent horizontal scaling, but higher operational complexity.
- **MongoDB**: Document model doesn't fit our relational access patterns.

## Consequences

- Migration from SQLite requires schema rewrite and data migration tooling.
- Team needs PostgreSQL operational expertise (monitoring, vacuuming, replication).
- We gain JSONB support for semi-structured metadata without a separate store.
