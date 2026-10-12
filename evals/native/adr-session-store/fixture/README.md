# shop-api

HTTP API for the Acme web shop: catalogue, cart, checkout and the admin console.

## Infrastructure

- One managed Postgres 15 instance (`shop-db`) is the only datastore. See ADR 001.
- The API runs as three replicas behind the cloud load balancer (config/app.yaml).
- Peak traffic is about 400 requests per second; roughly 85% of requests are
  authenticated and read the session on every call.

## Known issues

- Since the move to three replicas on 2026-10-05, users are logged out at
  random: a request that reaches a replica that did not create the session
  gets a 401.
