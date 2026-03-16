# ADR-006: Message Format

## Context

Services need a common serialization format for inter-service communication
over the message bus.

## Decision

We will use Protocol Buffers because they offer compact binary encoding
and strong schema evolution guarantees.

## Alternatives Considered

OK.

## Consequences

- All services must include protobuf code generation in their build pipeline.
- Schema registry needed for version management.
- Binary format makes debugging harder without tooling.
