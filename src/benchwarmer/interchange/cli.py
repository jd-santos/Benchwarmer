"""``benchwarmer-validate``: check conversation files without a database.

Exit status 0 when every file is valid, 1 when any file has issues, 2 when a
file could not be read or converted. Issues are printed one per line as
``<file>\\t<json path>\\t<message>``; content is never echoed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from benchwarmer.interchange.agent_log import AgentLogError, convert_agent_log
from benchwarmer.interchange.format import (
    ConversationFileError,
    Issue,
    normalized_preview,
    parse_conversation_file,
    validate_conversation_file,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchwarmer-validate",
        description=(
            "Validate Benchwarmer conversation files (format v1) or convert a "
            "synthetic example-agent-log to one. Reads files only; never opens "
            "the database."
        ),
    )
    parser.add_argument("files", nargs="+", type=Path, help="conversation files")
    parser.add_argument(
        "--agent-log",
        action="store_true",
        help="treat each input as an example-agent-log and convert it first",
    )
    parser.add_argument(
        "--normalized",
        action="store_true",
        help="print the normalized conversation a valid file imports as",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="with one input, write the (converted) conversation file here",
    )
    return parser


def _load(path: Path, *, agent_log: bool) -> dict[str, Any]:
    document = parse_conversation_file(path.read_bytes())
    if agent_log:
        return convert_agent_log(document)
    return document


def _print_issues(path: Path, issues: list[Issue], out: Any) -> None:
    for issue in issues:
        print(f"{path}\t{issue.path}\t{issue.message}", file=out)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.output is not None and len(args.files) != 1:
        print("--output takes exactly one input file", file=sys.stderr)
        return 2
    status = 0
    for path in args.files:
        try:
            document = _load(path, agent_log=args.agent_log)
        except OSError as error:
            print(f"{path}\t$\tcould not be read ({error.strerror})", file=sys.stderr)
            status = max(status, 2)
            continue
        except ConversationFileError as error:
            _print_issues(path, error.issues, sys.stderr)
            status = max(status, 2 if not args.agent_log else 1)
            continue
        except AgentLogError as error:
            print(f"{path}\t$\t{error}", file=sys.stderr)
            status = max(status, 2)
            continue
        issues = validate_conversation_file(document)
        if issues:
            _print_issues(path, issues, sys.stderr)
            status = max(status, 1)
            continue
        print(f"{path}\tok\t{len(document['events'])} events", file=sys.stdout)
        if args.output is not None:
            args.output.write_text(
                json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True)
                + "\n"
            )
        if args.normalized:
            print(json.dumps(normalized_preview(document), indent=2, sort_keys=True))
    return status


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
