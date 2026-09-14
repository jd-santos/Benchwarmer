# Runtime recovery

`scripts/build-python-runtime.sh` never changes an existing final runtime. It also
stops when its exact lock or a matching staging directory exists. Recovery is an
operator action that validates and archives exact Benchwarmer-owned paths. Never
use a glob, delete these paths recursively, add an ownership marker, or move a
foreign final.

First confirm that no `build-python-runtime.sh` process is running. Run these
commands from the repository root.

## Set exact paths

```bash
PROJECT_ROOT=$PWD
RUNTIME_ROOT_INPUT=${BENCHWARMER_RUNTIME_ROOT:-"$PROJECT_ROOT/.benchwarmer"}
ROOT=$(CDPATH= cd -- "$RUNTIME_ROOT_INPUT" && pwd)
NAME=python-3.13.15-sqlite-3.53.4
FINAL="$ROOT/$NAME"
LOCK="$ROOT/.$NAME.lock"
STAGE="$ROOT/.$NAME.staging.REPLACE_WITH_EXACT_LISTED_SUFFIX"
VALIDATOR="$PROJECT_ROOT/scripts/validate-python-runtime.py"
HELPER=$(mktemp "${TMPDIR:-/tmp}/benchwarmer-recovery.XXXXXX")
cc -std=c11 -Wall -Wextra -Werror \
  "$PROJECT_ROOT/scripts/rename-noreplace.c" -o "$HELPER"
```

Set `STAGE` only to one exact path reported by the provisioner. Choose unique,
absent archive paths without shell metacharacters:

```bash
FINAL_ARCHIVE="$ROOT/archive-$NAME-REPLACE_WITH_UNIQUE_SUFFIX"
LOCK_ARCHIVE="$ROOT/archive-lock-$NAME-REPLACE_WITH_UNIQUE_SUFFIX"
STAGE_ARCHIVE="$ROOT/archive-stage-$NAME-REPLACE_WITH_UNIQUE_SUFFIX"
```

The helper refuses an existing archive destination. Do not work around that
refusal by deleting or replacing the destination.

## Validate ownership

This check uses `lstat`, so it does not follow path or marker symlinks. Pass only
exact paths that exist. `FINAL` has one permanent runtime marker. Lock and staging
paths have separate recovery markers and one `pid=<digits>` owner file.

```bash
python3 - "$FINAL" "$LOCK" "$STAGE" <<'PY'
import os
import re
import stat
import sys

FINAL_OWNER = b"benchwarmer-python-runtime-v1\n"
RECOVERY_OWNERS = {
    ".lock": b"benchwarmer-runtime-lock-v1\n",
    ".staging": b"benchwarmer-runtime-publication-v1\n",
}


def regular_bytes(path: bytes) -> bytes:
    assert stat.S_ISREG(os.lstat(path).st_mode), f"not a regular file: {path!r}"
    with open(path, "rb") as stream:
        return stream.read()


def real_directory(path: bytes) -> None:
    assert stat.S_ISDIR(os.lstat(path).st_mode), f"not a real directory: {path!r}"


final, lock, stage = map(os.fsencode, sys.argv[1:])
for path, kind in ((final, "final"), (lock, ".lock"), (stage, ".staging")):
    if not os.path.lexists(path):
        continue
    real_directory(path)
    if kind == "final":
        marker = os.path.join(path, b".benchwarmer-runtime-owner")
        assert regular_bytes(marker) == FINAL_OWNER, "foreign final marker"
    else:
        marker = os.path.join(path, b".recovery-owner")
        owner = os.path.join(path, b".owner")
        assert regular_bytes(marker) == RECOVERY_OWNERS[kind]
        assert re.fullmatch(rb"pid=[0-9]+\n", regular_bytes(owner))
        if kind == ".lock":
            assert set(os.listdir(path)) == {b".owner", b".recovery-owner"}
PY
```

A failed ownership check means the path is foreign. Stop and leave it untouched.
For an owned `FINAL`, run its exact validator:

```bash
"$FINAL/bin/python3.13" "$VALIDATOR" 3.13.15 3.53.4
```

## Stale lock or staging with FINAL absent

After the ownership check passes for each present lock or staging path, archive
those exact paths. Do not publish anything found inside staging.

```bash
"$HELPER" "$STAGE" "$STAGE_ARCHIVE"  # only if this exact STAGE exists
"$HELPER" "$LOCK" "$LOCK_ARCHIVE"   # only if LOCK exists
scripts/build-python-runtime.sh
```

## Stale lock or staging with an owned valid FINAL

Require the final ownership check and successful runtime validation. Archive each
exact owned staging path and the owned lock with the commands above. Rerun the
provisioner to exercise its valid fast path.

## Owned invalid FINAL

Require the final ownership check and a failed runtime validation. Archive the
exact final using no-replace, then archive any separately validated exact staging
and lock paths. A later provisioner run creates a new runtime from source.

```bash
"$HELPER" "$FINAL" "$FINAL_ARCHIVE"
"$HELPER" "$STAGE" "$STAGE_ARCHIVE"  # only if this exact STAGE exists
"$HELPER" "$LOCK" "$LOCK_ARCHIVE"   # only if LOCK exists
scripts/build-python-runtime.sh
```

## Foreign FINAL

Do not validate it as trusted, mark it, move it, replace it, or delete it. If lock
or staging paths also exist, archive only those exact paths after their ownership
checks pass. The provisioner continues to refuse the foreign final until the
operator resolves it outside this procedure.

Remove the temporary helper after recovery:

```bash
rm -f -- "$HELPER"
```

Keep archives until the retained or rebuilt runtime passes validation and
`uv sync --locked --dev` succeeds.
