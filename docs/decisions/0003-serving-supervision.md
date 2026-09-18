# ADR 0003: Private serving and process supervision

- Status: Accepted
- Work: [Finish the application foundation](../../todo/work/application-foundation/README.md)
  and [deploy the private application](../../todo/work/private-deployment/README.md)
- Date: 2026-09-08

## Context and evidence

Benchwarmer is a single-user application whose Python service owns domain rules,
SQLite access, imports, and jobs. Browser requests must remain on a same-origin
`/api` boundary. The first production deployment is an always-on Mac mini that
already runs Docker Compose and a Tailscale sidecar for private services.
Data-root, backup, restore, and retention choices belong to [the data and recovery decision](0002-data-recovery.md) and are not
made here.

The inspected deployment has three relevant properties:

- application containers share the Tailscale sidecar's network namespace with
  `network_mode: service:tailscale-hermes` and use `restart: unless-stopped`;
- its declarative Tailscale Serve JSON terminates HTTPS and proxies handlers to
  `http://127.0.0.1:<port>` in that shared namespace; and
- the Hermes container uses s6 for built-in long-running services and
  reconciled profile gateways. Its runtime `/run/service` entries are ephemeral
  container state, so an unrelated application would need extra reconciliation
  or an image-level s6 service to survive container recreation.

No application code currently requires SvelteKit server-side rendering, server
load functions, or Node-only endpoints. The planned pages can load typed data
from the Python API in the browser. Future routes contain record identifiers, so
not every URL can be enumerated at build time.

The following official documentation was checked on 2026-09-08:

- [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve) is
  tailnet-only, terminates HTTPS, proxies to a localhost service, and adds
  identity headers. Tailscale recommends localhost binding when those headers
  might be trusted.
- The [Serve CLI reference](https://tailscale.com/docs/reference/tailscale-cli/serve)
  supports an alternate HTTPS port and an HTTP reverse-proxy target at
  `127.0.0.1`.
- [SvelteKit adapter-static](https://svelte.dev/docs/kit/adapter-static) supports
  an SPA fallback for routes that were not prerendered and recommends avoiding
  `index.html` as the fallback when the home page is prerendered.
- [Uvicorn settings](https://www.uvicorn.org/settings/) restrict trusted
  forwarded headers with `--forwarded-allow-ips`; its default trusted address is
  `127.0.0.1`, while `*` trusts every peer.
- [Docker restart policies](https://docs.docker.com/engine/containers/start-containers-automatically/)
  restart an exited container. A Docker
  [health check](https://docs.docker.com/reference/dockerfile/#healthcheck)
  records health status; it does not itself make a running but unhealthy
  container exit.
- [s6-supervise](https://skarnet.org/software/s6/s6-supervise.html) restarts a
  terminated long-running service unless told not to. The inspected Hermes run
  scripts use a foreground `exec`, drop privileges, and use finish exit status
  125 only for intentional or permanent stops.

The current agent container can inspect the Compose, Serve, and s6 shapes, but
it does not have the Docker Compose plugin. Target-host rendering and live route
checks therefore remain owned by [private deployment verification](../../todo/work/private-deployment/README.md) before deployment can be called
operational; they do not block acceptance of this design record.

## Decision

### One loopback application process

Build the SvelteKit UI with `@sveltejs/adapter-static`. Configure a `200.html`
SPA fallback and disable SSR for the application shell. Prerender routes that
are genuinely static, but retain the fallback for identifier-based routes.
Package the generated assets in the application image rather than the Python
wheel. The image copies `web/build` to `/opt/benchwarmer/ui` and sets
`BENCHWARMER_UI_ROOT=/opt/benchwarmer/ui`. The Uvicorn factory requires an
absolute UI root containing `200.html` and fails startup when that contract is
missing or invalid. Tests and local tools may inject another explicit absolute
root; the application never discovers assets from its current working directory
or private data root.

In production, the Python ASGI service serves both the generated UI and
`/api/v1/*`. Register API routes before a GET/HEAD-only UI fallback; `/api`,
unknown API paths, non-GET requests, and missing static assets must never fall
through to `200.html`. This keeps one same-origin boundary and avoids a Node
runtime. The static frontend has no independently supervised process.

Run one foreground Uvicorn process on `127.0.0.1:8000` in a dedicated
`benchwarmer` container. Do not publish a Docker host port. Join the existing
Tailscale sidecar's network namespace so Serve and Uvicorn share the same
loopback interface. The production Compose shape is:

```yaml
services:
  benchwarmer:
    build: <benchwarmer-source>
    environment:
      BENCHWARMER_UI_ROOT: /opt/benchwarmer/ui
    restart: unless-stopped
    network_mode: service:tailscale-hermes
    depends_on:
      - tailscale-hermes
    command:
      - uv
      - run
      - uvicorn
      - benchwarmer.api.app:create_app
      - --factory
      - --host
      - 127.0.0.1
      - --port
      - "8000"
      - --proxy-headers
      - --forwarded-allow-ips
      - 127.0.0.1
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - >-
          import json, urllib.request;
          d=json.load(urllib.request.urlopen(
          'http://127.0.0.1:8000/api/v1/health', timeout=3));
          assert d['status']=='ok' and d['data_root_writable']
          and d['alembic_revision'] is not None
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s
```

The final image may invoke its installed Uvicorn executable instead of
`uv run`, but it must use exec-form startup, remain in the foreground, honor
SIGTERM, and retain the binding and proxy restrictions above. [the data and recovery decision](0002-data-recovery.md) and the
integration decision supply the omitted data-root mount and environment.

### Dedicated tailnet HTTPS origin

Merge an HTTPS listener on port 8443 into the existing declarative Serve
configuration and proxy its root to the application loopback port:

```json
{
  "TCP": {
    "8443": {
      "HTTPS": true
    }
  },
  "Web": {
    "<node>.<tailnet>.ts.net:8443": {
      "Handlers": {
        "/": {
          "Proxy": "http://127.0.0.1:8000"
        }
      }
    }
  }
}
```

This is a merge fragment, not a replacement for existing handlers. The
standalone CLI equivalent used to validate the route shape is:

```sh
tailscale serve --bg --https=8443 http://127.0.0.1:8000
```

The deployed sidecar continues to load the checked-in declarative Serve file;
do not mix ad hoc CLI state into that deployment. Port 8443 gives Benchwarmer a
root origin, so browser calls remain `/api/v1/*` rather than introducing a base
path, and it avoids the HTTPS ports already used by the inspected services.

Tailscale Serve, not Funnel, is the only non-loopback ingress. Tailnet policy
must grant port 8443 only to the intended user or group and deny broader access.
Do not publish port 8000, bind it to a LAN or Tailscale address, enable Funnel,
or add a public reverse proxy. The exact private node name and policy principals
remain deployment configuration and must not be committed here.

### Authentication and trusted proxies

For the initial single-user deployment, the access-control boundary is an
approved Tailscale identity plus the tailnet grant for this node and port. There
is no unauthenticated non-loopback listener. Benchwarmer does not treat
`Tailscale-User-*`, `X-Forwarded-*`, `Forwarded`, or client-supplied equivalents
as application authorization.

Uvicorn accepts proxy metadata only from `127.0.0.1`; never configure
`--forwarded-allow-ips '*'`. This assumption is valid only while Serve and the
application share the network namespace and Uvicorn remains loopback-only. If a
later topology changes the proxy source, acceptance requires identifying a
narrow replacement address rather than broadening trust. Tailscale identity
headers may be recorded for audit only after a separate schema/privacy decision.
Any future cookie-authenticated mutation must also add Origin/CSRF protection;
tailnet reachability alone is not CSRF protection.

### Supervision, health, and restart behavior

Docker Compose supervises the dedicated application container with
`restart: unless-stopped`. If Uvicorn crashes or exits non-zero, the container
exits and Docker restarts it. An operator stop remains stopped. A health-check
failure marks the still-running container unhealthy but does not trigger an
automatic restart; the existing host health-check pattern should alert, after
which the operator inspects logs and runs:

```sh
docker compose restart benchwarmer
```

Do not add an autoheal container or place Benchwarmer in Hermes's ephemeral s6
scan directory. Both add moving parts, and the latter couples application
availability to Hermes-specific reconciliation. The existing Tailscale sidecar
keeps its Compose restart policy. Its health is checked independently because a
healthy Uvicorn process does not prove the tailnet route works.

The application probe parses `/api/v1/health`, not merely its HTTP 200 status.
Production is healthy only when the data root is writable and an Alembic
revision is present. Deployment verification must additionally compare that
revision with the packaged Alembic head before routing user traffic. UI health
is a successful root document and static-asset fetch through HTTPS; there is no
frontend process to restart.

When a real background worker is implemented, run it as a second foreground
Compose service from the same image, with no listener or published port and the
same crash restart policy. Do not add an idle worker stub now. Worker startup
must recover from durable job state. A restart must never blindly repeat a paid
or externally mutating attempt; uncertain trials remain `outcome_unknown` until
reconciled. A worker-specific heartbeat or stalled-job check is required before
that process is deployed.

## Alternatives considered

### `adapter-node` as a second production process

Rejected for the initial application. It adds Node installation, memory,
health, logs, restart behavior, and a second reverse-proxy target without a
current SSR or Node endpoint requirement. Reconsider only if a concrete feature
needs request-time SvelteKit server execution and cannot live in the Python API.

### Tailscale Serve directly serving the static build

Rejected. It would split `/api` and SPA-fallback behavior across Serve handlers,
while the Python process is already required. Serving the build from Python
keeps fallback exclusions testable and preserves one origin and one application
process.

### A path beneath the existing port 443 origin

Rejected because the existing root belongs to another service and a path mount
would either collide with its `/api` namespace or force a SvelteKit base path.
A dedicated HTTPS port is smaller than a new Tailscale node and keeps
Benchwarmer at `/` with same-origin `/api`.

### Bind Uvicorn to `0.0.0.0` or the Tailscale address

Rejected. Either creates a direct non-loopback path that can bypass Serve TLS,
policy routing, and trusted identity headers. Sharing a network namespace makes
loopback sufficient.

### Register Benchwarmer under the existing Hermes s6 tree

Rejected. A static service would require a custom Hermes image; a dynamic
`/run/service` slot is lost on recreation unless another reconciler owns it.
A dedicated single-process container already has an appropriate supervisor in
Docker and keeps application lifecycle independent of the agent gateway.

### Add Caddy, nginx, or an autoheal sidecar

Rejected for the first deployment. Python can safely serve the private static
bundle, Tailscale already terminates TLS, and crash restart plus explicit health
alerting covers the required behavior with fewer long-running processes.

## Consequences

- Production has one new long-running application process and no Node server.
- The API and UI share one origin and one availability unit. An API restart also
  briefly interrupts static UI delivery.
- Dynamic SvelteKit pages run as an SPA. This is acceptable for a private app but
  gives up SSR and requires tested loading and error states.
- Tailnet access depends on the existing Tailscale sidecar and policy. If that
  sidecar is down, the application may be healthy on loopback but unavailable
  remotely.
- Loopback binding and no Docker port publication prevent LAN or direct tailnet
  bypass. Local processes in the shared namespace remain inside the trusted
  host boundary.
- Crash recovery is automatic; health-only failures are visible but deliberately
  not auto-restarted. This avoids restart loops hiding migration, storage, or
  configuration failures.
- Logs go to the container log stream. Persistent data and backup behavior are
  unchanged and remain governed by [the data and recovery decision](0002-data-recovery.md).
- A future worker adds a second service only when it has real work and a durable
  recovery contract. Frontend changes alone never add another process.

## Unresolved questions

- [private deployment verification](../../todo/work/private-deployment/README.md) must confirm that HTTPS port 8443 is unused on the target Tailscale
  node and select the private tailnet grant principals.
- The application image and static-file integration must define cache headers:
  immutable hashed assets may be cached long-term, while HTML and `200.html`
  must revalidate so deployments do not strand old asset references.
- The accepted foundation decision must pin the Svelte CLI and adapter versions.
- Before deployment, implementation must define the expected Alembic head used
  by the production readiness check. This does not choose the data-root or
  backup policy.
- If a later feature truly needs SSR, streaming from SvelteKit, or Node-only
  server hooks, a replacement ADR must define the extra process and routing.

## Verification

### Decide private serving and supervision design verification

Run build and static-fallback checks from a clean checkout:

```sh
npm --prefix web ci
npm --prefix web run check
npm --prefix web run build
test -f web/build/200.html
```

The scaffold/build commands become executable in [Scaffold SvelteKit with the selected adapter and checks](../../todo/work/application-foundation/plan.md). Syntax, configuration
shape, and the absence of a Node/SSR requirement are sufficient to accept this
record through [the accepted foundation decisions](../decisions.md).

### Implement and validate private deployment target-host verification

After [foundation integration verification](../../todo/work/application-foundation/README.md), implement the deployment and render the merged configuration on
the target host before startup. Verify that `benchwarmer` has no `ports` entry:

```sh
set -eu
docker compose config --format json | python3 -c '
import json, sys
service = json.load(sys.stdin)["services"]["benchwarmer"]
assert not service.get("ports"), "benchwarmer must not publish ports"
assert service.get("network_mode") == "service:tailscale-hermes"
'
docker compose up -d --build --wait benchwarmer
docker compose ps benchwarmer
container_id="$(docker compose ps -q benchwarmer)"
test -n "$container_id"
docker inspect --format '{{json .HostConfig.PortBindings}}' "$container_id" |
  python3 -c '
import json, sys
assert json.load(sys.stdin) in (None, {}), "container published a host port"
'
docker inspect --format '{{json .State.Health}}' "$container_id" |
  python3 -c '
import json, sys
assert json.load(sys.stdin)["Status"] == "healthy"
'
```

The rendered-config assertion must pass before startup. The post-start
port-binding inspection must then return `null` or an empty mapping as defense in
depth. Check the loopback application and declarative Serve route without
printing identity headers or private configuration:

```sh
set -eu
docker compose exec -T benchwarmer python -c \
  "import json,urllib.request; print(json.load(urllib.request.urlopen(\
'http://127.0.0.1:8000/api/v1/health')))"
docker compose exec -T tailscale-hermes tailscale serve status --json |
  python3 -c '
import json, sys
payload = json.dumps(json.load(sys.stdin), sort_keys=True)
assert "8443" in payload
assert "http://127.0.0.1:8000" in payload
'
curl --fail --show-error \
  https://<node>.<tailnet>.ts.net:8443/api/v1/health
curl --fail --show-error https://<node>.<tailnet>.ts.net:8443/
```

Compare the health response's Alembic revision with `alembic heads`. From a LAN
peer and an unauthorized tailnet identity, verify that port 8000 and the HTTPS
origin respectively are unreachable. Confirm that `tailscale funnel status`
does not list Benchwarmer. These checks must emit only pass/fail status in the
deployment record; never retain raw Serve/Funnel JSON, node names, identities,
or the complete private routing configuration.

Exercise process behavior in a maintenance window:

```sh
set -eu
restore_service() {
  docker compose start benchwarmer >/dev/null 2>&1 || true
}
trap restore_service EXIT HUP INT TERM

container_id="$(docker compose ps -q benchwarmer)"
test -n "$container_id"
restart_before="$(docker inspect --format '{{.RestartCount}}' "$container_id")"
docker compose exec -T benchwarmer sh -c 'kill -KILL 1' || true
attempt=0
restart_after="$restart_before"
health=""
while [ "$attempt" -lt 30 ]; do
  restart_after="$(docker inspect --format '{{.RestartCount}}' "$container_id")"
  health="$(docker inspect --format '{{.State.Health.Status}}' "$container_id")"
  if [ "$restart_after" -gt "$restart_before" ] && [ "$health" = healthy ]; then
    break
  fi
  attempt=$((attempt + 1))
  sleep 1
done
test "$restart_after" -gt "$restart_before"
test "$health" = healthy
docker compose stop benchwarmer
test "$(docker inspect --format '{{.State.Status}}' "$container_id")" = exited
sleep 5
test "$(docker inspect --format '{{.State.Status}}' "$container_id")" = exited
docker compose start benchwarmer
trap - EXIT HUP INT TERM
```

Killing PID 1 from an exec process simulates an application crash rather than a
Docker stop operation. The restart count must increase after that crash and the
service must return to healthy. An operator stop must remain stopped through the
explicit delay. `set -eu` makes every assertion fail closed, while the trap
restores the service if the block exits early. Finally, make the health probe
fail in a disposable deployment and confirm Docker reports `unhealthy` without
claiming it automatically restarted; restore the configuration, inspect logs,
and verify HTTPS recovery.
