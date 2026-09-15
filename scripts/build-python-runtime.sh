#!/bin/sh
set -eu

PYTHON_VERSION=3.13.15
PYTHON_SHA256=1e66a7945a48390ee4c2a4268a0e4185884059a13c4aab6d148aa208deea4a76
SQLITE_VERSION=3.53.4
SQLITE_ARCHIVE_VERSION=3530400
SQLITE_SHA256=0e9483900e92cd5de8fd48d16bf9200145a61f7fd5be542a5ac81d8a9516eb9c

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
runtime_validator="$project_root/scripts/validate-python-runtime.py"
rename_noreplace_source="$project_root/scripts/rename-noreplace.c"
custom_runtime_root=false
if [ -n "${BENCHWARMER_RUNTIME_ROOT:-}" ]; then
    custom_runtime_root=true
fi
runtime_root=${BENCHWARMER_RUNTIME_ROOT:-"$project_root/.benchwarmer"}
tmp_root=${TMPDIR:-/tmp}

reject_unsafe_path() {
    variable=$1
    value=$2
    case $value in
        *[[:space:]]* | *'*'* | *'?'* | *'['* | *']'*)
            printf '%s contains unsupported whitespace or glob characters: %s\n' \
                "$variable" "$value" >&2
            exit 1
            ;;
    esac
}

reject_unsafe_path BENCHWARMER_RUNTIME_ROOT "$runtime_root"
reject_unsafe_path TMPDIR "$tmp_root"
mkdir -p "$runtime_root"
runtime_root=$(CDPATH= cd -- "$runtime_root" && pwd)
runtime_name="python-$PYTHON_VERSION-sqlite-$SQLITE_VERSION"
runtime="$runtime_root/$runtime_name"
python="$runtime/bin/python3.13"
lock_dir="$runtime_root/.$runtime_name.lock"
owner_token="pid=$$"
runtime_owner=benchwarmer-python-runtime-v1
runtime_owner_file=.benchwarmer-runtime-owner
lock_recovery_owner=benchwarmer-runtime-lock-v1
staging_recovery_owner=benchwarmer-runtime-publication-v1
lock_owned=false
build_dir=
staging_dir=
publication_started=false

shell_quote() {
    quoted=$(printf '%s' "$1" | sed "s/'/'\\\\''/g")
    printf "'%s'" "$quoted"
}

print_uv_python_guidance() {
    if [ "$custom_runtime_root" = true ]; then
        printf '%s\n' \
            'Every subsequent uv command using this custom root needs this interpreter:'
        printf '  export UV_PYTHON='
        shell_quote "$python"
        printf '\n'
    fi
}

has_exact_marker() {
    marker=$1
    expected=$2
    marker_line=
    extra_line=
    [ -f "$marker" ] && [ ! -L "$marker" ] &&
        {
            IFS= read -r marker_line &&
                [ "$marker_line" = "$expected" ] &&
                ! { IFS= read -r extra_line || [ -n "$extra_line" ]; }
        } <"$marker"
}

runtime_is_owned() {
    [ -d "$runtime" ] && [ ! -L "$runtime" ] &&
        has_exact_marker "$runtime/$runtime_owner_file" "$runtime_owner"
}

validate_runtime() {
    interpreter=$1
    python_home=${2:-}
    [ -x "$interpreter" ] || return 1
    if [ -n "$python_home" ]; then
        (
            PYTHONHOME=$python_home
            export PYTHONHOME
            "$interpreter" "$runtime_validator" \
                "$PYTHON_VERSION" "$SQLITE_VERSION"
        )
    else
        (
            unset PYTHONHOME
            "$interpreter" "$runtime_validator" \
                "$PYTHON_VERSION" "$SQLITE_VERSION"
        )
    fi
}

owned_directory() {
    directory=$1
    ownership_marker=$2
    [ -d "$directory" ] && [ ! -L "$directory" ] &&
        has_exact_marker "$directory/.owner" "$owner_token" &&
        has_exact_marker "$directory/.recovery-owner" "$ownership_marker"
}

cleanup() {
    status=$?
    trap - EXIT HUP INT TERM
    set +e
    if [ -n "$build_dir" ] && [ -d "$build_dir" ]; then
        rm -rf "$build_dir"
    fi
    if [ "$publication_started" = true ]; then
        printf 'publication needs inspection; preserved final, staging, and lock. See docs/runtime-recovery.md\n' >&2
        printf '  final: %s\n  staging: %s\n  lock: %s\n' \
            "$runtime" "$staging_dir" "$lock_dir" >&2
    else
        if [ -n "$staging_dir" ] &&
            owned_directory "$staging_dir" "$staging_recovery_owner"
        then
            rm -rf "$staging_dir"
        fi
        if [ "$lock_owned" = true ] &&
            owned_directory "$lock_dir" "$lock_recovery_owner"
        then
            rm -rf "$lock_dir"
        fi
    fi
    exit "$status"
}

handle_signal() {
    exit 1
}

trap cleanup EXIT
trap handle_signal HUP INT TERM

recovery_found=false
for artifact in "$lock_dir" "$runtime_root"/."$runtime_name".staging.*; do
    if [ -e "$artifact" ] || [ -L "$artifact" ]; then
        if [ "$recovery_found" = false ]; then
            printf 'runtime recovery artifacts exist; refusing to proceed:\n' >&2
        fi
        recovery_found=true
        printf '  %s\n' "$artifact" >&2
    fi
done
if [ "$recovery_found" = true ]; then
    printf 'Verify and archive exact owned paths using docs/runtime-recovery.md.\n' >&2
    exit 1
fi

if [ -e "$runtime" ] || [ -L "$runtime" ]; then
    if ! runtime_is_owned; then
        printf 'final runtime exists but is not an owned runtime; left untouched: %s\n' \
            "$runtime" >&2
        exit 1
    fi
    if validate_runtime "$python"; then
        printf 'WAL-safe runtime already provisioned: Python %s, SQLite %s\n' \
            "$PYTHON_VERSION" "$SQLITE_VERSION"
        print_uv_python_guidance
        exit 0
    fi
    printf 'owned final runtime is invalid; left untouched. Archive it manually using docs/runtime-recovery.md: %s\n' \
        "$runtime" >&2
    exit 1
fi

if ! mkdir "$lock_dir" 2>/dev/null; then
    printf 'provisioning lock appeared; left untouched: %s\n' "$lock_dir" >&2
    printf 'See docs/runtime-recovery.md.\n' >&2
    exit 1
fi
lock_owned=true
printf '%s\n' "$owner_token" >"$lock_dir/.owner"
printf '%s\n' "$lock_recovery_owner" >"$lock_dir/.recovery-owner"

# Refuse a final path created between the initial check and lock acquisition.
if [ -e "$runtime" ] || [ -L "$runtime" ]; then
    printf 'final runtime appeared during lock acquisition; left untouched: %s\n' \
        "$runtime" >&2
    exit 1
fi

for command in cc curl make pkg-config tar; do
    if ! command -v "$command" >/dev/null 2>&1; then
        printf 'missing build prerequisite: %s\n' "$command" >&2
        exit 1
    fi
done
if ! command -v sha256sum >/dev/null 2>&1 &&
    ! command -v shasum >/dev/null 2>&1
then
    printf 'missing build prerequisite: sha256sum or shasum\n' >&2
    exit 1
fi

verify_sha256() {
    expected=$1
    file=$2
    if command -v sha256sum >/dev/null 2>&1; then
        printf '%s  %s\n' "$expected" "$file" | sha256sum -c -
    else
        printf '%s  %s\n' "$expected" "$file" | shasum -a 256 -c -
    fi
}

linux_preflight() {
    probe_source="$build_dir/linux-build-preflight.c"
    probe_binary="$build_dir/linux-build-preflight"
    cat >"$probe_source" <<'EOF'
#include <bzlib.h>
#include <curses.h>
#include <ffi.h>
#include <lzma.h>
#include <openssl/opensslv.h>
#include <openssl/ssl.h>
#include <readline/readline.h>
#include <zlib.h>
#if OPENSSL_VERSION_MAJOR != 3
#error "Benchwarmer requires exactly OpenSSL major 3"
#endif
int main(void) { return 0; }
EOF
    openssl_flags=$(pkg-config --cflags --libs openssl 2>/dev/null || :)
    # Intentional word splitting allows conventional user-supplied build flags.
    if ! ${CC:-cc} ${CPPFLAGS:-} ${CFLAGS:-} $openssl_flags \
        "$probe_source" ${LDFLAGS:-} -o "$probe_binary"
    then
        printf '%s\n' \
            'Linux build preflight failed: install the required development headers and OpenSSL 3, or supply their paths with CPPFLAGS/LDFLAGS/PKG_CONFIG_PATH.' \
            >&2
        return 1
    fi
}

python_configure_extra=
build_dir=$(mktemp -d "$tmp_root/benchwarmer-runtime.XXXXXX")
case $(uname -s) in
    Darwin)
        if ! command -v brew >/dev/null 2>&1; then
            printf 'missing macOS build prerequisite: brew\n' >&2
            exit 1
        fi
        for formula in openssl@3 bzip2 xz readline ncurses libffi; do
            if ! prefix=$(brew --prefix "$formula" 2>/dev/null); then
                printf 'missing Homebrew build prerequisite: %s\n' "$formula" >&2
                exit 1
            fi
            CPPFLAGS="${CPPFLAGS:+$CPPFLAGS }-I$prefix/include"
            LDFLAGS="${LDFLAGS:+$LDFLAGS }-L$prefix/lib -Wl,-rpath,$prefix/lib"
            PKG_CONFIG_PATH="$prefix/lib/pkgconfig:$prefix/share/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
        done
        export CPPFLAGS LDFLAGS PKG_CONFIG_PATH
        openssl_prefix=$(brew --prefix openssl@3)
        python_configure_extra="--with-openssl=$openssl_prefix --with-openssl-rpath=auto"
        ;;
    Linux) linux_preflight ;;
    *)
        printf 'unsupported build platform: %s\n' "$(uname -s)" >&2
        exit 1
        ;;
esac

rename_helper="$build_dir/rename-noreplace"
if ! ${CC:-cc} ${CPPFLAGS:-} ${CFLAGS:-} "$rename_noreplace_source" \
    ${LDFLAGS:-} -o "$rename_helper"
then
    printf 'failed to build the atomic rename-no-replace helper\n' >&2
    exit 1
fi

jobs=${JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || printf '2')}
staging_dir=$(mktemp -d "$runtime_root/.$runtime_name.staging.XXXXXX")
printf '%s\n' "$owner_token" >"$staging_dir/.owner"
printf '%s\n' "$staging_recovery_owner" >"$staging_dir/.recovery-owner"

# Exercise no-replace on the publication filesystem. An existing directory must
# remain unchanged and must never receive the source as a nested child.
rename_probe="$staging_dir/rename-probe"
mkdir "$rename_probe" "$rename_probe/source" "$rename_probe/existing"
printf '%s\n' source >"$rename_probe/source/marker"
printf '%s\n' destination >"$rename_probe/existing/marker"
if "$rename_helper" "$rename_probe/source" "$rename_probe/existing"; then
    printf 'atomic rename-no-replace helper clobbered an existing destination\n' >&2
    exit 1
else
    rename_status=$?
fi
IFS= read -r existing_marker <"$rename_probe/existing/marker"
if [ "$rename_status" -ne 73 ] ||
    [ ! -r "$rename_probe/source/marker" ] ||
    [ "$existing_marker" != destination ] ||
    [ -e "$rename_probe/existing/source" ]
then
    printf 'atomic rename-no-replace helper failed its no-clobber self-check\n' >&2
    exit 1
fi
"$rename_helper" "$rename_probe/source" "$rename_probe/published"
[ ! -e "$rename_probe/source" ]
[ "$(cat "$rename_probe/published/marker")" = source ]
rm -rf "$rename_probe"

install_root="$staging_dir/root"
python_archive="$build_dir/Python-$PYTHON_VERSION.tar.xz"
sqlite_archive="$build_dir/sqlite-autoconf-$SQLITE_ARCHIVE_VERSION.tar.gz"

curl --fail --location --silent --show-error \
    "https://www.python.org/ftp/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tar.xz" \
    --output "$python_archive"
curl --fail --location --silent --show-error \
    "https://sqlite.org/2026/sqlite-autoconf-$SQLITE_ARCHIVE_VERSION.tar.gz" \
    --output "$sqlite_archive"
verify_sha256 "$PYTHON_SHA256" "$python_archive"
verify_sha256 "$SQLITE_SHA256" "$sqlite_archive"
tar -xf "$python_archive" -C "$build_dir"
tar -xf "$sqlite_archive" -C "$build_dir"

sqlite_prefix="$build_dir/sqlite"
(
    cd "$build_dir/sqlite-autoconf-$SQLITE_ARCHIVE_VERSION"
    CFLAGS="${CFLAGS:-} -fPIC" ./configure \
        --prefix="$sqlite_prefix" --disable-shared --enable-static
    make -j "$jobs"
    make install
)

case $(uname -s) in
    Darwin) sqlite_libs="$sqlite_prefix/lib/libsqlite3.a -lm" ;;
    Linux) sqlite_libs="$sqlite_prefix/lib/libsqlite3.a -ldl -lpthread -lm" ;;
esac

(
    cd "$build_dir/Python-$PYTHON_VERSION"
    LIBSQLITE3_CFLAGS="-I$sqlite_prefix/include" \
    LIBSQLITE3_LIBS="$sqlite_libs" \
        ./configure \
        --prefix="$runtime" \
        --with-ensurepip=no \
        $python_configure_extra
    make -j "$jobs"
    make install DESTDIR="$install_root"
)

candidate="$install_root$runtime"
candidate_python="$candidate/bin/python3.13"
printf '%s\n' "$runtime_owner" >"$candidate/$runtime_owner_file"
validate_runtime "$candidate_python" "$candidate"

publication_started=true
if "$rename_helper" "$candidate" "$runtime"; then
    :
else
    status=$?
    publication_started=false
    printf 'final runtime appeared before publication; left untouched: %s\n' \
        "$runtime" >&2
    exit "$status"
fi

# FINAL is immutable after publication. A failed check preserves all recovery
# evidence for explicit operator inspection.
validate_runtime "$python"
rm -rf "$project_root/.venv"
publication_started=false
printf 'Published WAL-safe runtime: Python %s, SQLite %s\n' \
    "$PYTHON_VERSION" "$SQLITE_VERSION"
print_uv_python_guidance
