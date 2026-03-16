# ADR-007: Message Broker Selection

## Context

The platform requires asynchronous communication between microservices.
Current message volume is approximately 50,000 events per second.

## Decision

We will use Kafka as the message broker for inter-service communication.

## Alternatives Considered

RabbitMQ was evaluated but does not meet throughput requirements at scale.
ActiveMQ was rejected due to limited community support and operational complexity.
NATS was considered but lacks built-in persistence guarantees.

## Consequences

Teams must learn Kafka administration and monitoring.
We accept vendor lock-in for the messaging layer in exchange for proven scalability.
