# ADR-005: Container Orchestration

## Decision

We will use Kubernetes for container orchestration because it provides
the most mature ecosystem for our microservices architecture.

## Alternatives Considered

- **Docker Swarm**: Simpler but limited scaling features.
- **Nomad**: Flexible but smaller community.

## Consequences

- Steep learning curve for the operations team.
- Requires investment in cluster management tooling.
