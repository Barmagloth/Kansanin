# Architecture Overview

## Design Decisions

Data is encrypted at rest using AES-256.

The system was designed to handle high throughput scenarios.

Sessions are managed through a distributed cache.

Requests are routed through the API gateway layer.
