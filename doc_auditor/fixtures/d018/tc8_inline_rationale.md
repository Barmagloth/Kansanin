# ADR-007: Authentication Provider

## Context

The platform needs centralized authentication for all client applications.

## Decision

We will integrate with Auth0 as our identity provider. Since our team
lacks deep security expertise, delegating authentication to a managed
service reduces risk. The reason is that building custom auth would
require 3+ months and ongoing maintenance.

## Alternatives Considered

- **Keycloak**: Self-hosted, more control but higher ops burden.
- **Firebase Auth**: Tightly coupled to Google ecosystem.

## Consequences

- Vendor lock-in risk with Auth0 pricing model.
- Simplified onboarding for new developers.
