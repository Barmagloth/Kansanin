# API Gateway Requirements

## 1. Scope

This document defines requirements for the API Gateway component.
It covers authentication, routing, rate limiting, and monitoring.

> **Note:** Requirements marked TBD are pending stakeholder review.
> Do not treat blockquote TBDs as finalized gaps.

## 2. Functional Requirements

The gateway shall authenticate all incoming requests using OAuth2 or similar mechanism.
Rate limiting shall be applied, if feasible, at the per-client level.
The gateway shall route requests to upstream services including Auth, Orders, Inventory, etc.

Request logging shall be enabled where applicable.
Response caching shall be implemented if practical.

Retry logic: the gateway shall retry failed upstream calls as needed.

| Feature         | Status  | Notes                  |
|-----------------|---------|------------------------|
| Auth            | Done    | OAuth2                 |
| Rate limiting   | TBD     | needs capacity plan    |
| Caching         | Planned | TTL: TBD               |

The table above contains TBD as status values — these are table cells, not prose placeholders.

## 3. Non-functional Requirements

### 3.1 Performance

Latency p99: TBD.
Throughput: to be determined based on load testing.
Availability: 99.9% SLA (monthly).

### 3.2 Security

All traffic shall be encrypted in transit using TLS 1.3 or higher.
mTLS shall be enforced between gateway and upstream services where applicable.
Secrets management: see section X.2.
Audit logging retention: TBD.

### 3.3 Observability

Metrics shall be exported to Prometheus (or similar tool, etc.).
Distributed tracing: OpenTelemetry, if feasible.
Alerting rules: TODO define thresholds.

## 4. Constraints

The gateway shall be deployed on Kubernetes.
Helm chart versioning follows SemVer, including but not limited to major/minor/patch labels.

## 5. Open Issues

- [ ] TBD: decide on API versioning strategy
- [ ] if possible: implement request deduplication  
- [ ] Canary release mechanism: TBD

## 6. References

- OAuth2 RFC: [RFC 6749](https://tools.ietf.org/html/rfc6749)
- Rate limiting algorithm: Token Bucket, Leaky Bucket, etc.
- Gateway vendor comparison: see section N.3 (TBD — section not written yet)

## Appendix A: Example Configuration

```yaml
gateway:
  auth:
    provider: oauth2  # TBD: switch to mTLS for internal
  rateLimit:
    enabled: true
    strategy: TBD
  routes:
    - path: /api/v1
      upstream: orders-service
      # if possible: add circuit breaker
```

Config TBDs above are code comments — not document defects.

## Appendix B: Glossary

TBD: To Be Determined — используется для незаполненных значений.
SLA: Service Level Agreement. Etc.
