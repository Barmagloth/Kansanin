# Design Decisions

## Rationale

We chose PostgreSQL because we believe that the system needs strong consistency guarantees.

The team agreed that we should use container orchestration.

It is clear that the current architecture cannot scale beyond 10k users.

Analysis shows that each component must handle its own state.
