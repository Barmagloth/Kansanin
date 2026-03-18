# ADR-055: Logging Framework

## Status

Accepted

## Context

The platform needs a unified logging approach across all microservices.

## Decision

We will use structured JSON logging with ELK stack.

## Alternatives

We looked at Fluentd, Datadog, Splunk, etc. and decided ELK was the best fit among others.

## Consequences

ELK requires dedicated infrastructure. Log volume may incur storage costs.
