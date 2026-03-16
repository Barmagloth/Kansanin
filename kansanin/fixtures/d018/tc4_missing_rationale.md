# ADR-004: Logging Framework

## Context

Application logging is inconsistent across services, making
debugging production issues difficult.

## Decision

We will adopt structured logging with ELK stack.

## Alternatives Considered

- **Datadog**: Full observability but expensive at our scale.
- **Grafana Loki**: Lower storage cost but less mature query language.

## Consequences

- All services must migrate to structured JSON log format.
- ELK cluster requires dedicated infrastructure team support.
