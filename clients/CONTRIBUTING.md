# Contributing to clients/

Each client lives in its own subdirectory here (e.g. `clients/web/`), with:

- Its own dependency management, isolated from `server/`'s Poetry
  environment.
- Its own Dockerfile under [`docker/clients/web/`](../docker/clients/web/)
  (Compose context is still `clients/web`); Compose lives under
  [`docker/clients/`](../docker/clients/), same network pattern as
  [`docker/server/`](../docker/server/).
- Its own documentation under [`docs/clients/`](../docs/clients/),
  following the same pattern as `docs/server/`.
- A `CONTRIBUTING.md` of its own once its dev workflow (install,
  test, lint) is established — don't retrofit this file to cover it.

The web client is already here. Setup and commands live in
[`web/README.md`](web/README.md).
