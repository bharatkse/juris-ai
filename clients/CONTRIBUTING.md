# Contributing to clients/

This directory is a placeholder — no client application exists yet.

When a first client is added (web, mobile, CLI, etc.), it should live
in its own subdirectory here (e.g. `clients/web/`), with:

- Its own dependency management, isolated from `server/`'s Poetry
  environment.
- Its own Dockerfile under [`docker/clients/`](../docker/clients/) if
  it needs containerizing, following the same pattern as
  [`docker/server/`](../docker/server/).
- Its own documentation under [`docs/clients/`](../docs/clients/),
  following the same pattern as `docs/server/`.
- A `CONTRIBUTING.md` of its own once its dev workflow (install,
  test, lint) is established — don't retrofit this file to cover it.

Until then, there's nothing to contribute here beyond proposing what
the first client should be.
