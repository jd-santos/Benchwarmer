import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[1]
BUILD_SCRIPT = PROJECT_ROOT / "scripts/build-python-runtime.sh"
VALIDATOR = PROJECT_ROOT / "scripts/validate-python-runtime.py"
RENAME_NOREPLACE = PROJECT_ROOT / "scripts/rename-noreplace.c"
README = PROJECT_ROOT / "README.md"
RECOVERY_DOC = PROJECT_ROOT / "docs/runtime-recovery.md"
PYTHON_VERSION = "3.13.15"
PYTHON_SHA256 = "1e66a7945a48390ee4c2a4268a0e4185884059a13c4aab6d148aa208deea4a76"
SQLITE_VERSION = "3.53.4"
SQLITE_SHA256 = "0e9483900e92cd5de8fd48d16bf9200145a61f7fd5be542a5ac81d8a9516eb9c"
RUNTIME_NAME = f"python-{PYTHON_VERSION}-sqlite-{SQLITE_VERSION}"
RUNTIME_OWNER = "benchwarmer-python-runtime-v1"
RUNTIME_OWNER_FILE = ".benchwarmer-runtime-owner"
LOCK_NAME = f".{RUNTIME_NAME}.lock"


def isolated_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    project = tmp_path / "project"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    for source in (BUILD_SCRIPT, VALIDATOR, RENAME_NOREPLACE):
        shutil.copy2(source, scripts / source.name)
    runtime_root = project / ".benchwarmer"
    return project, runtime_root, runtime_root / RUNTIME_NAME


def write_fake_runtime(
    runtime: Path, scenario: str = "valid", *, owned: bool = True
) -> None:
    python = runtime / "bin/python3.13"
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text(
        textwrap.dedent(
            f"""\
            #!/bin/sh
            FAKE_RUNTIME_SCENARIO={scenario}
            export FAKE_RUNTIME_SCENARIO
            unset PYTHONHOME
            exec "$FAKE_HOST_PYTHON" "$FAKE_PYTHON_LAUNCHER" "$@"
            """
        )
    )
    python.chmod(0o755)
    (runtime / "payload").write_text(scenario)
    if owned:
        (runtime / RUNTIME_OWNER_FILE).write_text(f"{RUNTIME_OWNER}\n")


def write_launcher(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """\
            import importlib
            import os
            import runpy
            import sqlite3
            import ssl
            import sys
            from pathlib import Path

            scenario = os.environ["FAKE_RUNTIME_SCENARIO"]
            sys.version = "3.13.15 (fake runtime)"
            sqlite3.sqlite_version = "3.53.4"
            ssl.OPENSSL_VERSION = "OpenSSL 3.5.0 fake"
            ssl.OPENSSL_VERSION_INFO = (3, 5, 0, 0, 0)
            if scenario == "wrong-python":
                sys.version = "3.13.14 (fake runtime)"
            elif scenario == "wrong-sqlite":
                sqlite3.sqlite_version = "3.53.3"
            elif scenario == "openssl-4":
                ssl.OPENSSL_VERSION = "OpenSSL 4.0.0 fake"
                ssl.OPENSSL_VERSION_INFO = (4, 0, 0, 0, 0)
            elif scenario == "missing-lzma":
                original_import = importlib.import_module

                def import_module(name, package=None):
                    if name == "lzma":
                        raise ImportError("fake missing lzma")
                    return original_import(name, package)

                importlib.import_module = import_module

            race = os.environ.get("FAKE_RACE_FINAL")
            if race and os.environ.get("FAKE_CANDIDATE_VALIDATION") == "1":
                final = Path(race)
                final.mkdir()
                (final / "foreign-content").write_text("raced")

            sys.argv = sys.argv[1:]
            runpy.run_path(sys.argv[0], run_name="__main__")
            """
        )
    )


def install_fake_toolchain(tmp_path: Path) -> tuple[Path, Path, Path]:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    log = tmp_path / "toolchain.log"
    launcher = tmp_path / "fake-python-launcher.py"
    write_launcher(launcher)
    dispatcher = fake_bin / "fake-command"
    dispatcher.write_text(
        textwrap.dedent(
            f'''\
            #!{sys.executable}
            import os
            import subprocess
            import sys
            from pathlib import Path

            command = Path(sys.argv[0]).name
            args = sys.argv[1:]
            log = Path(os.environ["FAKE_TOOLCHAIN_LOG"])

            def record(message):
                with log.open("a") as stream:
                    stream.write(message + "\\n")

            if command == "cc":
                record("cc " + " ".join(args))
                if os.environ.get("FAKE_CC_FAIL"):
                    raise SystemExit(1)
                if any(arg.endswith("rename-noreplace.c") for arg in args):
                    result = subprocess.run([os.environ["REAL_CC"], *args], check=False)
                    raise SystemExit(result.returncode)
                raise SystemExit(0)

            if command == "pkg-config":
                record("pkg-config " + " ".join(args))
                raise SystemExit(0)

            if command == "uname":
                print("Linux")
                raise SystemExit(0)

            if command == "getconf":
                print("2")
                raise SystemExit(0)

            if command == "curl":
                output = Path(args[args.index("--output") + 1])
                output.write_text(output.name)
                record(f"curl {{output.name}}")
                raise SystemExit(0)

            if command in {{"sha256sum", "shasum"}}:
                expected, filename = sys.stdin.read().strip().split(maxsplit=1)
                archive = Path(filename)
                record(f"verify {{expected}} {{archive.name}}")
                if archive.name == os.environ.get("FAKE_BAD_CHECKSUM"):
                    raise SystemExit(1)
                archive.with_suffix(archive.suffix + ".verified").touch()
                raise SystemExit(0)

            if command == "tar":
                archive = Path(args[args.index("-xf") + 1])
                destination = Path(args[args.index("-C") + 1])
                record(f"tar {{archive.name}}")
                if not archive.with_suffix(archive.suffix + ".verified").exists():
                    raise SystemExit("attempted extraction before checksum verification")
                suffix = ".tar.xz" if archive.name.startswith("Python-") else ".tar.gz"
                source = destination / archive.name.removesuffix(suffix)
                source.mkdir()
                configure = source / "configure"
                configure.write_text("""#!/bin/sh
            for argument in "$@"; do
                case "$argument" in
                    --prefix=*) printf '%s\\n' "${{argument#--prefix=}}" > .prefix ;;
                esac
            done
            """)
                configure.chmod(0o755)
                raise SystemExit(0)

            if command == "make":
                record(f"make {{Path.cwd().name}} {{' '.join(args)}}")
                if "install" not in args:
                    raise SystemExit(0)
                prefix = Path((Path.cwd() / ".prefix").read_text().strip())
                if Path.cwd().name.startswith("sqlite-autoconf-"):
                    (prefix / "include").mkdir(parents=True)
                    library = prefix / "lib/libsqlite3.a"
                    library.parent.mkdir()
                    library.touch()
                    raise SystemExit(0)
                destdir = Path(next(a for a in args if a.startswith("DESTDIR=")).split("=", 1)[1])
                candidate = Path(f"{{destdir}}{{prefix}}")
                python = candidate / "bin/python3.13"
                python.parent.mkdir(parents=True)
                python.write_text("""#!/bin/sh
            if [ -n "${{PYTHONHOME:-}}" ]; then
                FAKE_CANDIDATE_VALIDATION=1
                FAKE_RUNTIME_SCENARIO=valid
            else
                FAKE_CANDIDATE_VALIDATION=0
                FAKE_RUNTIME_SCENARIO=${{FAKE_PUBLISHED_SCENARIO:-valid}}
            fi
            export FAKE_CANDIDATE_VALIDATION FAKE_RUNTIME_SCENARIO
            unset PYTHONHOME
            exec "$FAKE_HOST_PYTHON" "$FAKE_PYTHON_LAUNCHER" "$@"
            """)
                python.chmod(0o755)
                (candidate / "complete-payload").write_text("complete")
                raise SystemExit(0)

            raise SystemExit(f"unexpected fake command: {{command}}")
            '''
        )
    )
    dispatcher.chmod(0o755)
    for command in (
        "cc",
        "curl",
        "getconf",
        "make",
        "pkg-config",
        "sha256sum",
        "shasum",
        "tar",
        "uname",
    ):
        (fake_bin / command).symlink_to(dispatcher.name)
    return fake_bin, log, launcher


def environment(fake_bin: Path, log: Path, launcher: Path) -> dict[str, str]:
    result = os.environ.copy()
    result.update(
        {
            "PATH": f"{fake_bin}:{result['PATH']}",
            "FAKE_HOST_PYTHON": sys.executable,
            "FAKE_PYTHON_LAUNCHER": str(launcher),
            "FAKE_TOOLCHAIN_LOG": str(log),
            "REAL_CC": shutil.which("cc", path=os.defpath) or "/usr/bin/cc",
        }
    )
    return result


def run_bootstrap(
    project: Path,
    runtime_root: Path | str | None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy() if env is None else env.copy()
    if runtime_root is None:
        run_env.pop("BENCHWARMER_RUNTIME_ROOT", None)
    else:
        run_env["BENCHWARMER_RUNTIME_ROOT"] = str(runtime_root)
    return subprocess.run(
        [str(project / "scripts/build-python-runtime.sh")],
        cwd=project,
        env=run_env,
        check=False,
        capture_output=True,
        text=True,
    )


def prepared_build(tmp_path: Path) -> tuple[Path, Path, Path, Path, dict[str, str]]:
    project, root, runtime = isolated_project(tmp_path)
    fake_bin, log, launcher = install_fake_toolchain(tmp_path)
    return project, root, runtime, log, environment(fake_bin, log, launcher)


def snapshot(path: Path) -> object:
    stat_result = path.lstat()
    if path.is_symlink():
        return ("symlink", stat_result.st_mode, os.readlink(path))
    if path.is_file():
        return ("file", stat_result.st_mode, path.read_bytes())
    return (
        "directory",
        stat_result.st_mode,
        tuple((child.name, snapshot(child)) for child in sorted(path.iterdir())),
    )


def test_valid_owned_runtime_is_an_untouched_fast_path(tmp_path: Path) -> None:
    project, root, runtime, log, env = prepared_build(tmp_path)
    write_fake_runtime(runtime)
    (project / ".venv").mkdir()
    (project / ".venv/keep").write_text("keep")
    before = snapshot(runtime)

    result = run_bootstrap(project, root, env)

    assert result.returncode == 0, result.stderr
    assert "already provisioned" in result.stdout
    assert snapshot(runtime) == before
    assert (project / ".venv/keep").read_text() == "keep"
    assert not log.exists()


@pytest.mark.parametrize(
    "scenario,error",
    [
        ("wrong-python", "expected Python 3.13.15"),
        ("wrong-sqlite", "expected SQLite 3.53.4"),
        ("openssl-4", "expected OpenSSL major 3"),
        ("missing-lzma", "required module lzma is unavailable"),
    ],
)
def test_full_validator_rejects_invalid_owned_final_untouched(
    tmp_path: Path, scenario: str, error: str
) -> None:
    project, root, runtime, log, env = prepared_build(tmp_path)
    write_fake_runtime(runtime, scenario)
    before = snapshot(runtime)

    result = run_bootstrap(project, root, env)

    assert result.returncode != 0
    assert error in result.stderr
    assert "owned final runtime is invalid; left untouched" in result.stderr
    assert snapshot(runtime) == before
    assert not log.exists()


@pytest.mark.parametrize(
    "kind",
    [
        "file",
        "symlink",
        "empty-directory",
        "nonempty-directory",
        "unmarked-runtime",
        "malformed-marker",
        "symlinked-marker",
    ],
)
def test_every_foreign_final_kind_is_untouched(tmp_path: Path, kind: str) -> None:
    project, root, runtime, log, env = prepared_build(tmp_path)
    root.mkdir()
    if kind == "file":
        runtime.write_bytes(b"foreign")
    elif kind == "symlink":
        target = tmp_path / "target"
        target.write_text("target")
        runtime.symlink_to(target)
    elif kind in {"empty-directory", "nonempty-directory"}:
        runtime.mkdir()
        if kind == "nonempty-directory":
            (runtime / "foreign").write_text("keep")
    else:
        write_fake_runtime(runtime, owned=False)
        marker = runtime / RUNTIME_OWNER_FILE
        if kind == "malformed-marker":
            marker.write_text(f"{RUNTIME_OWNER}\nextra\n")
        elif kind == "symlinked-marker":
            target = tmp_path / "owner-marker"
            target.write_text(f"{RUNTIME_OWNER}\n")
            marker.symlink_to(target)
    before = snapshot(runtime)

    result = run_bootstrap(project, root, env)

    assert result.returncode != 0
    assert "not an owned runtime; left untouched" in result.stderr
    assert snapshot(runtime) == before
    assert not log.exists()
    if runtime.is_dir():
        assert not (runtime / RUNTIME_NAME).exists()


@pytest.mark.parametrize("artifact_kind", ["lock", "staging"])
@pytest.mark.parametrize("final_kind", ["absent", "valid"])
def test_lock_or_staging_refuses_before_fast_path_or_build(
    tmp_path: Path, artifact_kind: str, final_kind: str
) -> None:
    project, root, runtime, log, env = prepared_build(tmp_path)
    root.mkdir()
    if final_kind == "valid":
        write_fake_runtime(runtime)
    artifact = (
        root / LOCK_NAME
        if artifact_kind == "lock"
        else root / f".{RUNTIME_NAME}.staging.stale"
    )
    artifact.mkdir()
    (artifact / "keep").write_text("keep")
    before = snapshot(artifact)
    final_before = snapshot(runtime) if runtime.exists() else None

    result = run_bootstrap(project, root, env)

    assert result.returncode != 0
    assert "runtime recovery artifacts exist" in result.stderr
    assert "docs/runtime-recovery.md" in result.stderr
    assert snapshot(artifact) == before
    assert (snapshot(runtime) if runtime.exists() else None) == final_before
    assert not log.exists()


@pytest.mark.parametrize(
    "configured_root,relative_root",
    [(None, ".benchwarmer"), ("custom-runtime", "custom-runtime")],
)
def test_fresh_build_publishes_exact_complete_candidate(
    tmp_path: Path, configured_root: str | None, relative_root: str
) -> None:
    project, _root, _runtime = isolated_project(tmp_path)
    root = project / relative_root
    runtime = root / RUNTIME_NAME
    fake_bin, log, launcher = install_fake_toolchain(tmp_path)
    env = environment(fake_bin, log, launcher)
    (project / ".venv").mkdir()

    result = run_bootstrap(project, configured_root, env)

    assert result.returncode == 0, result.stderr
    assert "Published WAL-safe runtime" in result.stdout
    assert (runtime / "complete-payload").read_text() == "complete"
    assert (runtime / RUNTIME_OWNER_FILE).read_text() == f"{RUNTIME_OWNER}\n"
    assert not (runtime / ".publication-owner").exists()
    assert not (runtime / RUNTIME_NAME).exists()
    assert not (project / ".venv").exists()
    assert not (root / LOCK_NAME).exists()
    assert not list(root.glob(f".{RUNTIME_NAME}.staging.*"))


@pytest.mark.parametrize(
    "archive",
    [f"Python-{PYTHON_VERSION}.tar.xz", "sqlite-autoconf-3530400.tar.gz"],
)
def test_checksum_failure_stops_before_any_extraction(
    tmp_path: Path, archive: str
) -> None:
    project, root, runtime, log, env = prepared_build(tmp_path)
    env["FAKE_BAD_CHECKSUM"] = archive

    result = run_bootstrap(project, root, env)

    assert result.returncode != 0
    lines = log.read_text().splitlines()
    assert any(line.endswith(f" {archive}") for line in lines)
    assert not any(line.startswith("tar ") for line in lines)
    assert not runtime.exists()
    assert not (root / LOCK_NAME).exists()
    assert not list(root.glob(f".{RUNTIME_NAME}.staging.*"))


def test_both_checksums_are_verified_before_either_extraction(tmp_path: Path) -> None:
    project, root, _runtime, log, env = prepared_build(tmp_path)

    result = run_bootstrap(project, root, env)

    assert result.returncode == 0, result.stderr
    lines = log.read_text().splitlines()
    first_tar = next(
        index for index, line in enumerate(lines) if line.startswith("tar ")
    )
    assert (
        lines.index(f"verify {PYTHON_SHA256} Python-{PYTHON_VERSION}.tar.xz")
        < first_tar
    )
    assert (
        lines.index(f"verify {SQLITE_SHA256} sqlite-autoconf-3530400.tar.gz")
        < first_tar
    )


def test_linux_preflight_honors_flags_and_runs_before_download(tmp_path: Path) -> None:
    project, root, _runtime, log, env = prepared_build(tmp_path)
    env.update(
        {
            "CPPFLAGS": "-I/custom/include",
            "CFLAGS": "-DCUSTOM=1",
            "LDFLAGS": "-L/custom/lib",
        }
    )

    result = run_bootstrap(project, root, env)

    assert result.returncode == 0, result.stderr
    lines = log.read_text().splitlines()
    cc_lines = [line for line in lines if line.startswith("cc ")]
    assert cc_lines
    assert all("-I/custom/include" in line for line in cc_lines)
    assert all("-DCUSTOM=1" in line for line in cc_lines)
    assert any("-L/custom/lib" in line for line in cc_lines)
    assert lines.index(cc_lines[0]) < next(
        index for index, line in enumerate(lines) if line.startswith("curl ")
    )


def test_linux_preflight_failure_stops_before_download(tmp_path: Path) -> None:
    project, root, runtime, log, env = prepared_build(tmp_path)
    env["FAKE_CC_FAIL"] = "1"

    result = run_bootstrap(project, root, env)

    assert result.returncode != 0
    assert "Linux build preflight failed" in result.stderr
    assert not any(line.startswith("curl ") for line in log.read_text().splitlines())
    assert not runtime.exists()
    assert not (root / LOCK_NAME).exists()


def test_publication_race_preserves_destination_without_nesting(tmp_path: Path) -> None:
    project, root, runtime, _log, env = prepared_build(tmp_path)
    env["FAKE_RACE_FINAL"] = str(runtime)

    result = run_bootstrap(project, root, env)

    assert result.returncode == 73
    assert "final runtime appeared before publication; left untouched" in result.stderr
    assert (runtime / "foreign-content").read_text() == "raced"
    assert not (runtime / RUNTIME_NAME).exists()
    assert not (runtime / "complete-payload").exists()
    assert not (root / LOCK_NAME).exists()
    assert not list(root.glob(f".{RUNTIME_NAME}.staging.*"))


def test_post_publication_validation_failure_preserves_every_artifact(
    tmp_path: Path,
) -> None:
    project, root, runtime, _log, env = prepared_build(tmp_path)
    env["FAKE_PUBLISHED_SCENARIO"] = "wrong-sqlite"

    result = run_bootstrap(project, root, env)

    assert result.returncode != 0
    assert "expected SQLite 3.53.4" in result.stderr
    assert "publication needs inspection" in result.stderr
    assert (runtime / "complete-payload").read_text() == "complete"
    assert (runtime / RUNTIME_OWNER_FILE).read_text() == f"{RUNTIME_OWNER}\n"
    lock = root / LOCK_NAME
    assert (lock / ".owner").read_text().startswith("pid=")
    assert (lock / ".recovery-owner").read_text() == ("benchwarmer-runtime-lock-v1\n")
    staging = next(root.glob(f".{RUNTIME_NAME}.staging.*"))
    assert (staging / ".owner").read_text().startswith("pid=")
    assert (staging / ".recovery-owner").read_text() == (
        "benchwarmer-runtime-publication-v1\n"
    )


@pytest.mark.parametrize("variable", ["BENCHWARMER_RUNTIME_ROOT", "TMPDIR"])
@pytest.mark.parametrize(
    "bad_component",
    ["with space", "with*glob", "with?glob", "with[glob", "with]glob"],
)
def test_path_restrictions_fail_before_filesystem_work(
    tmp_path: Path, variable: str, bad_component: str
) -> None:
    project, root, _runtime = isolated_project(tmp_path)
    env = os.environ.copy()
    env[variable] = str(tmp_path / bad_component)
    configured_root = env[variable] if variable == "BENCHWARMER_RUNTIME_ROOT" else root

    result = run_bootstrap(project, configured_root, env)

    assert result.returncode != 0
    assert (
        f"{variable} contains unsupported whitespace or glob characters"
        in result.stderr
    )


@pytest.mark.parametrize(
    "kind", ["file", "symlink", "empty-directory", "nonempty-directory"]
)
def test_real_rename_noreplace_rejects_foreign_destinations(
    tmp_path: Path, kind: str
) -> None:
    helper = tmp_path / "rename-noreplace"
    subprocess.run(
        [
            "cc",
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(RENAME_NOREPLACE),
            "-o",
            str(helper),
        ],
        check=True,
    )
    source = tmp_path / "candidate"
    source.mkdir()
    (source / "candidate-content").write_text("candidate")
    destination = tmp_path / "runtime"
    if kind == "file":
        destination.write_text("foreign-file")
    elif kind == "symlink":
        destination.symlink_to("foreign-target")
    else:
        destination.mkdir()
        if kind == "nonempty-directory":
            (destination / "foreign-content").write_text("foreign-directory")
    before = snapshot(destination)

    result = subprocess.run(
        [str(helper), str(source), str(destination)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 73
    assert snapshot(destination) == before
    assert (source / "candidate-content").read_text() == "candidate"
    if destination.is_dir():
        assert not (destination / source.name).exists()


def test_recovery_document_matches_create_only_model() -> None:
    recovery = RECOVERY_DOC.read_text()
    assert "docs/runtime-recovery.md" in README.read_text()
    assert "Stale lock or staging with FINAL absent" in recovery
    assert "Stale lock or staging with an owned valid FINAL" in recovery
    assert "Owned invalid FINAL" in recovery
    assert "Foreign FINAL" in recovery
    assert "rename-noreplace" in recovery
    for obsolete in ("prior-runtime", "failed-candidate", "quarantine", "rollback"):
        assert obsolete not in recovery
