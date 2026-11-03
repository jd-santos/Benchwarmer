# Deploy and verify the private application

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Serve the central application privately on the target host with verified supervision and access controls.

## Dependencies and order

Blocked on [the application foundation](../application-foundation/README.md). The image this record deploys is built by [one-command start and packaging](../one-command-start/README.md), which also decides whether the image carries Node for app-started harness runs. This is required for operational rollout, but does not block fixture development or local importer implementation.

## Acceptance criteria

The [procedure below](#deployment-verification-procedure) validates
[ADR 0003](../../../docs/decisions/0003-serving-supervision.md) with sanitized
target-host evidence. A design or rendered configuration alone is not a deployment
claim. Run from the deployment checkout only after its Compose services and
private route are implemented; these are not runnable local-app instructions.

## Work

- [ ] Implement and validate private deployment
  - Dependencies:
    [Integrate the initial decision records](../../../docs/decisions.md)
    (already recorded),
    [Document development and final integration](../application-foundation/README.md)
  - Output: build the Svelte application into the image at
    `/opt/benchwarmer/ui`, set `BENCHWARMER_UI_ROOT` to that immutable path,
    implement the application container and declarative Tailscale Serve route,
    then record sanitized deployment verification in the same PR
  - Verify: render Compose, confirm no published app port, test
    authorized/unauthorized reachability, compare Alembic head, and exercise
    crash restart, operator stop, and unhealthy alert
  - Acceptance: all checks in ADR 0003 pass on the Mac mini before deployment is
    called operational

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Deployment verification procedure

These target-host checks remain unexecuted. Set the private
`BENCHWARMER_PUBLIC_ORIGIN` to the operator-selected HTTPS origin (no trailing
slash) without retaining it in committed evidence. Record only sanitized outcomes.
The port 8443 and service names below follow ADR 0003; confirm them against the
actual deployment before the maintenance window.

### Build checks

Run build and static-fallback checks from a clean checkout:

```sh
set -eu
npm --prefix web ci
npm --prefix web run check
npm --prefix web run build
test -f web/build/200.html
```

### Target-host exposure and readiness

After [foundation integration verification](../application-foundation/README.md),
implement the deployment and render the merged configuration on the target host
before startup. Verify that `benchwarmer` has no `ports` entry:

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
  "import json,urllib.request; data=json.load(urllib.request.urlopen(\
'http://127.0.0.1:8000/api/v1/health')); assert data['status'] == 'ok'"
docker compose exec -T tailscale-hermes tailscale serve status --json |
  python3 -c '
import json, sys
payload = json.load(sys.stdin)
web = payload.get("Web", {})
assert isinstance(web, dict)
routes = [route for host, route in web.items() if host.endswith(":8443")]
assert len(routes) == 1
assert routes[0]["Handlers"]["/"]["Proxy"] == "http://127.0.0.1:8000"
assert not any(payload.get("AllowFunnel", {}).values())
'
: "${BENCHWARMER_PUBLIC_ORIGIN:?set the private HTTPS origin first}"
curl --fail --silent --output /dev/null \
  "$BENCHWARMER_PUBLIC_ORIGIN/api/v1/health"
curl --fail --silent --output /dev/null "$BENCHWARMER_PUBLIC_ORIGIN/"
```

The Serve assertion checks the port-to-handler relationship, not unrelated
substring matches. Fail on unknown status shapes rather than weakening it; update
the verifier with sanitized fixtures when the target's CLI schema changes.
Compare the health response's Alembic revision with `alembic heads` privately.
From a LAN peer and an unauthorized tailnet identity, verify that port 8000 and
the HTTPS
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

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
