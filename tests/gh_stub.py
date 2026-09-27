"""A stub `gh` executable for testing the .github/scripts release scripts.

Each call is answered from a routes dict, the way the real gh answers,
including on failure: exit 1, the raw error JSON on stdout (``--jq`` only
applies to a successful response) and ``gh: <message> (HTTP <status>)`` on
stderr. Every call's arguments are recorded.

Route keys:
  "GET <path>" / "POST <path>" / "PATCH <path>"  gh api (method from -X,
                                                  else POST when -f/-F given)
  "GRAPHQL"                                      gh api graphql
  "PR <subcommand>"                              gh pr list / gh pr create

Route values: {"stdout": "..."} for success (what gh prints after --jq), or
{"status": 404, "message": "Not Found"} for an HTTP error.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

_STUB = r"""
import json, os, sys

args = sys.argv[1:]
with open(os.environ["GH_STUB_LOG"], "a") as log:
    log.write(json.dumps(args) + "\n")

if args[0] == "pr":
    key = f"PR {args[1]}"
    if args[1] == "create":
        sys.stdin.read()
elif args[1] == "graphql":
    key = "GRAPHQL"
else:
    if "-X" in args:
        method = args[args.index("-X") + 1]
        path = args[args.index("-X") + 2]
    else:
        method = "POST" if ("-f" in args or "-F" in args) else "GET"
        path = args[1]
    key = f"{method} {path}"

response = json.loads(os.environ["GH_STUB_ROUTES"]).get(key)

if response is None:
    sys.stderr.write(f"stub gh: no route for {key}\n")
    sys.exit(2)

if "status" in response:
    status, message = response["status"], response["message"]
    print(json.dumps({"message": message, "status": str(status)}, indent=2))
    sys.stderr.write(f"gh: {message} (HTTP {status})\n")
    sys.exit(1)

print(response["stdout"])
"""


def http_error(status, message):
    return {"status": status, "message": message}


def not_found():
    return http_error(404, "Not Found")


# Non-404 failures that must never be read as "doesn't exist".
API_ERRORS = [
    (401, "Bad credentials"),
    (403, "API rate limit exceeded"),
    (502, "Bad Gateway"),
]


def run_with_stub_gh(tmp_path, command, routes, env, cwd=None):
    """Run command with the stub gh first on PATH; return (result, calls)."""

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(f"#!{sys.executable}\n{_STUB}")
    gh.chmod(0o755)

    log = tmp_path / "gh-calls.log"
    log.touch()

    full_env = {
        **os.environ,
        **env,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "GH_STUB_LOG": str(log),
        "GH_STUB_ROUTES": json.dumps(routes),
    }
    result = subprocess.run(
        [str(part) for part in command],
        env=full_env,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
    )
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    return result, calls


REPO_ROOT = Path(__file__).resolve().parent.parent
