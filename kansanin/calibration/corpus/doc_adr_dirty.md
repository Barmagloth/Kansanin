# ADR-001: Message Queue Technology Selection

**Status:** Accepted  
**Date:** 2024-01-15  
**Authors:** Platform Team

## Context

The system needs to decouple order processing from notification dispatch.
We evaluated several options including Kafka, RabbitMQ, and AWS SQS, etc.
The choice affects scalability, operational complexity, and cost.

Current throughput: ~500 msg/sec peak.
Expected growth: TBD.

## Decision

We will use Apache Kafka as the primary message broker.

Integration with downstream services shall be implemented if feasible.
Schema evolution will be handled using Avro, where applicable.
Dead letter queue strategy: to be determined.

## Options Considered

### Option A: Apache Kafka

Pros:
- High throughput
- Good ecosystem support (Kafka Connect, Streams, etc.)
- Mature tooling

Cons:
- Operational complexity is higher
- Requires Zookeeper (or KRaft) — see section X for details

### Option B: RabbitMQ

Pros:
- Simpler operational model
- Good for task queues

Cons: TBD

### Option C: AWS SQS

Not evaluated in depth. Assessment: TODO.

## Consequences

**Positive:**
- Decouples services effectively
- Enables event sourcing patterns where appropriate
- Scales horizontally as needed

**Negative / Risks:**
- Increased operational burden
- Team needs Kafka expertise (training plan: TBD)
- Message ordering guarantees apply where feasible per partition

**Migration plan:** [ ? ]

## Notes

This decision supersedes any prior informal agreements.
Kafka version selection: to be specified before implementation.
Monitoring approach: if possible, use Grafana dashboards.

## Appendix: Kafka Configuration Reference

```
bootstrap.servers=kafka:9092
acks=all
retries=3
# TBD: adjust batch.size for throughput
```

Here `TBD` is a code comment, not a document defect.
Also `if possible` in code context is irrelevant.
