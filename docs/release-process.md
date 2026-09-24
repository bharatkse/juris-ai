# Release process

How Juris-AI container images are built, released and verified. The model
is **build once, promote**: every image is built exactly once, on `develop`,
as a release candidate. A release doesn't build anything. It takes the
candidate you validated and adds release tags to the **same image** (same
digest, same signature, same SBOM).

Everything runs in GitHub Actions; nobody pushes images or tags by hand.

- Workflow: [`.github/workflows/ci-server.yml`](../.github/workflows/ci-server.yml)
- The only image build: [`.github/workflows/publish-image.yaml`](../.github/workflows/publish-image.yaml)
- Scripts it runs (all runnable locally): [`.github/scripts/`](../.github/scripts/)
- Image: `ghcr.io/bharatkse/juris-ai`

## At a glance

| Event | What happens | Image tags |
|---|---|---|
| Merge to `develop` | CI gates → build → scan → push → sign → SBOM attestation → rc git tag | `X.Y.Z-rc.N` (if a release is pending), `develop`, `sha-<7>` |
| Validate | You pull `:develop` or `:X.Y.Z-rc.N` and test it. No pipeline step. | |
| Merge `develop` → `main` | CI gates → verify and **re-scan** the candidate → **retag** it → git tag + GitHub Release → sync PR to `develop`. **No build.** | `X.Y.Z`, `X.Y`, `X` (from 1.0), `latest` added to the candidate's digest |
| PR into `develop` | CI gates on every push; build + scan dry run once the PR is ready for review (not on drafts) | none |
| PR from `develop` into `main` | CI gates, then (unless it's a draft) the promotion checks as a dry run: which rc and digest would ship, that its signature verifies, and that it still passes the image scan | none |

Nothing is published unless **all** CI gates pass: actionlint, code quality
(pre-commit + ruff), type check (mypy), backend unit tests, and coverage
config validation. The image scan is an additional gate on the build.

## 1. Develop: build once, as a release candidate

```
merge PR -> develop
     |
  CI gates
     |
  rc-version:   next-rc.sh -> X.Y.Z-rc.N (or none: nothing releasable yet)
     |
  publish-image: build -> Trivy gate -> push -> cosign sign
                 -> SPDX SBOM -> cosign attest (SBOM)
     |
  rc-tag:       annotated git tag vX.Y.Z-rc.N on this commit,
                recording the digest that was pushed
```

This is the only image build in the whole process. A running develop build
is never cancelled by a newer merge, so it can't stop between pushing an
image and tagging it, and rc numbers stay in order. If several merges land
while one build runs, GitHub keeps only the newest waiting run: the commits
in between aren't built on their own, and the newest one becomes the next
rc.

### Release candidate numbers

[python-semantic-release](https://python-semantic-release.readthedocs.io/)
(config: `[tool.semantic_release]` in `server/pyproject.toml`) reads the
Conventional Commits since the last release and decides **whether a release
is pending, and its version**:

| Commits since the last release | Next version (while on 0.x) | From 1.0 |
|---|---|---|
| only `docs:`, `chore:`, `refactor:`, `test:`, `ci:`, ... | none (no rc) | none |
| at least one `fix:` or `perf:` | patch, `0.1.0 -> 0.1.1` | patch |
| at least one `feat:` | minor, `0.1.1 -> 0.2.0` | minor |
| a breaking change (`feat!:` / `BREAKING CHANGE:`) | minor (stays on 0.x) | major |

The rc number is then **one more than the highest existing rc of that
version**, on every develop build
([`next-rc.sh`](../.github/scripts/next-rc.sh)). So each develop build of a
pending release is its own candidate, docs-only merges included. For
example:

| Merged to develop | Build | rc |
|---|---|---|
| `fix: ...` (first change after v0.1.0) | 1 | `0.1.1-rc.1` |
| `docs: ...` | 2 | `0.1.1-rc.2` |
| `feat: ...` | 3 | `0.2.0-rc.1` (version moves up, rc restarts) |
| `fix: ...` | 4 | `0.2.0-rc.2` |

(semantic-release on its own only moves to a new rc for releasable commits.
That would leave a docs-only build with no rc, and then the image at the tip
of `develop`, the one that gets released, would never have been a
candidate.)

Squash-merge titles are what count, so PR titles must follow
`type(scope): summary`. Moving to 1.0 is a deliberate decision, not
something a commit triggers. The first release is `v0.1.0`, the version
already in `pyproject.toml`.

No GitHub Release is created for release candidates: one per develop merge
would bury real releases on the Releases page and notify watchers every
time. Each candidate is visible as its git tag, its image tag, and the
`Release Candidate Version` job summary.

## 2. Validate

Pull and test the candidate:

```bash
docker pull ghcr.io/bharatkse/juris-ai:0.2.0-rc.2
```

What gets released is whatever is at the tip of `develop` when you merge
the release PR. If something else lands on `develop` after you validated,
it becomes a new rc; the release PR tells you which rc it will ship (next
section).

## 3. Release: promote by retag (merge `develop` into `main`)

Open a PR from `develop` into `main`. Its `Promote Release Candidate` job
(dry run) shows exactly what merging will release, for example *"Merging
this releases v0.2.0 = v0.2.0-rc.2 built from `<sha>`, digest `sha256:...`"*,
and fails if that can't be done safely. Use **Create a merge commit** to
merge it.

```
merge release PR -> main
     |
  CI gates
     |
  promote:  find the develop commit (the PR's head)
            check main's tree == that commit's tree
            resolve-release.sh: its rc tag -> version + recorded digest
            promote-image.sh:   verify -> re-scan by digest
                                -> crane tag X.Y.Z, X.Y, X, latest
     |
  release:  git tag vX.Y.Z (on the develop commit) + GitHub Release
            sync PR -> develop (CHANGELOG.md + pyproject version)
```

What the promotion checks before tagging anything (any failure stops it):

1. **The source.** The commit being released is the head of the merged
   `develop -> main` PR, and `main` now has exactly that commit's tree. So
   the image, built from that commit, matches `main`'s source. (If `main`
   ever gets a commit that isn't on `develop`, promotion refuses; fix on
   `develop` and release again.)
2. **The candidate.** That commit has an rc git tag (its develop build
   finished and published). The release version is the rc without the
   suffix, cross-checked against semantic-release. No rc and nothing
   releasable means nothing is released; no rc but a release pending means
   the build hasn't finished (wait, then re-run the job).
3. **The digest.** The digest recorded in the rc git tag is what
   `:X.Y.Z-rc.N` resolves to in GHCR now. Two independent records must
   agree, so a moved image tag can't slip a different image in.
4. **The image.** Its `org.opencontainers.image.revision` label is the
   commit being released, and its signature and SBOM attestation verify:
   made by `publish-image.yaml` on `develop`, for that exact commit.
5. **A fresh scan.** The candidate is pulled by digest onto the runner and
   scanned again with the same gate as the build (`trivy-gate.sh`: no
   fixable HIGH/CRITICAL). The candidate may be days old; if a fixable
   vulnerability has been disclosed since it was built, the release is
   refused (merge the fix to `develop`, which builds a new rc) and the
   findings appear in the job summary. If the scan itself can't run (Trivy
   or database error), the release is refused too, reported as a scan
   error rather than a vulnerability. Nothing is rebuilt or pushed: the pull
   only feeds the scanner.

Then `crane tag` adds `X.Y.Z`, `X.Y`, `X` (from 1.0) and `latest` to that
digest. `crane tag` stores the **identical manifest bytes** under the new
tag, so the digest is unchanged and so is everything attached to it. The
promotion re-checks each new tag's digest and verifies the signature
through `:X.Y.Z` afterwards. (`:sha-<7>` is the develop commit's tag the
image already had.)

**Re-scanned, but not rebuilt or re-signed.** cosign stores signatures
and attestations against the digest (`sha256-<digest>.sig` / `.att` in the
same repository), not against tags, so a new tag on the same digest is
covered by the existing signature. The re-scan reads the image; it never
changes it.

### Why the version and changelog arrive on `develop` as a PR

`main` and `develop` both require signed commits, so the workflow can't
push a "bump version" commit. Instead:

1. semantic-release updates `pyproject.toml` and regenerates `CHANGELOG.md`
   in the runner's workspace only (`--no-commit --no-tag --no-push`). rc
   tags are deleted **in that workspace only** first, so the changelog lists
   releases rather than every candidate.
2. The tag `vX.Y.Z` is created on the develop commit that was promoted: it
   is the image's exact source, the merge makes it reachable from `main`,
   and semantic-release on `develop` needs to see it to start the next
   version.
3. A branch `release/sync-vX.Y.Z` is created from `develop` with one commit,
   made through GitHub's `createCommitOnBranch` API (signed by GitHub),
   changing only `develop`'s own `version` line and replacing
   `CHANGELOG.md`.
4. A PR `chore(release): sync vX.Y.Z to develop` is opened. Merge it like
   any other PR; it contains no code.

## Image scanning

Every build is scanned with Trivy **before** anything is pushed, and every
release candidate is scanned **again** at promotion, with the same gate
([`trivy-gate.sh`](../.github/scripts/trivy-gate.sh)):

- **Blocks:** HIGH or CRITICAL vulnerabilities that have a fixed version.
- **Doesn't block:** findings with no upstream fix yet. They're still listed
  in the Security tab and start blocking automatically once a fix is
  released.
- **Suppressions:** `.trivyignore.yaml` at the repo root is honoured if it
  exists. There is none today. Only add an entry for a finding that has a
  fix you deliberately can't take yet, scoped to the exact package version,
  with a reason and an `expired_at` no more than 90 days out.

Results: the `Publish Image` job summary (blocking findings), **Security →
Code scanning**, category `trivy-image` (all HIGH/CRITICAL findings, from
the build), and the `Promote Release Candidate` job summary for the re-scan.

`trivy-gate.sh` exits 0 when the gate passes, 1 for gating findings, and 2
when the scan itself failed, so a broken scan is never mistaken for a pass
or reported as a vulnerability.

Locally (needs Docker):

```bash
docker build -f docker/server/Dockerfile -t juris-ai-scan:local server
.github/scripts/trivy-gate.sh juris-ai-scan:local trivy-results   # exit 1 = gate fails
```

## Verifying an image

Images are signed with [cosign](https://docs.sigstore.dev/) using
**keyless** signing: the signature is tied to the GitHub Actions workflow
run that built the image (via GitHub's OIDC token) and recorded in
Sigstore's public transparency log. There are no keys to manage.

Every image, **including releases**, was built and signed by the develop
build, so the identity to check is always `publish-image.yaml` on
`refs/heads/develop`. Prefer verifying and deploying by **digest** (on the
GitHub Release page and in the job summaries); tags can move.

```bash
cosign verify ghcr.io/bharatkse/juris-ai@sha256:<digest> \
  --certificate-identity "https://github.com/bharatkse/juris-ai/.github/workflows/publish-image.yaml@refs/heads/develop" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com"
```

To also pin it to the commit it was built from (for a release, the commit
the `vX.Y.Z` tag points at):

```bash
  --certificate-github-workflow-sha "$(git rev-list -n 1 v0.2.0)"
```

Verifying through a tag works too (`ghcr.io/bharatkse/juris-ai:0.2.0`);
cosign resolves it to the digest first. A successful check prints the
verified payload; anything else (including "no matching signatures") means
don't deploy that image.

## Finding the SBOM

Every image carries:

- A **signed SPDX SBOM attestation** (cosign), which proves the SBOM came
  from the build:

  ```bash
  cosign verify-attestation ghcr.io/bharatkse/juris-ai@sha256:<digest> \
    --type spdxjson \
    --certificate-identity "https://github.com/bharatkse/juris-ai/.github/workflows/publish-image.yaml@refs/heads/develop" \
    --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
    | jq -r .payload | base64 -d | jq .predicate > sbom.spdx.json
  ```

- **Buildx SBOM and build provenance** attestations:

  ```bash
  docker buildx imagetools inspect ghcr.io/bharatkse/juris-ai:<tag> --format '{{ json .SBOM }}'
  docker buildx imagetools inspect ghcr.io/bharatkse/juris-ai:<tag> --format '{{ json .Provenance }}'
  ```

Releases also have **`juris-ai-X.Y.Z.spdx.json`** attached to the GitHub
Release (Assets). It is extracted from the signed attestation above during
promotion, so it is exactly the SBOM that was signed.

## Testing without publishing

The fast CI gates (actionlint, code quality, type check, unit tests,
coverage config) run on **every** push to every PR. The image dry run
(about 20 minutes for a build) is scoped to when it's useful:

| PR state | Image dry run? |
|---|---|
| Draft, any push | no |
| Marked **Ready for review**, or opened as ready | yes |
| Ready, every later push | yes |
| Ready, title/body edited, or an unrelated label added | no |
| Draft with the **`run-image-scan`** label (on demand) | yes, on adding the label and every push while it's on |
| PR into any branch other than `develop` / `main` | no |

So the usual flow (open as a draft, push while working, mark ready, merge)
builds and scans once, when you mark it ready, and again only if you push
after that. The image that gets published is always built and scanned in
full by the merge to `develop` itself, whatever happened on the PR.

- **A ready PR into `develop`** builds and scans the image (dry run).
- **A ready PR from `develop` into `main`** runs the promotion checks as a
  dry run: it names the rc, version and digest that merging would release,
  verifies the candidate's signature and re-scans it, without tagging
  anything. This is the pre-release check to read before merging.
- **On demand on a draft:** add the `run-image-scan` label (create it once
  under Issues → Labels). Remove it to stop.
- **Manual run:** Actions → CI → Run workflow, pick a branch, leave
  **dry_run** ticked. On `develop` (or any branch) it builds and scans; on
  `main` it re-checks the latest release merge. Unticking `dry_run` only
  publishes on `develop` (same as a merge there); releases only happen by
  merging. GitHub offers Run workflow only for workflows on the default
  branch (`main`), so this is available after the first release that
  includes it.

  ```bash
  gh workflow run ci-server.yml --ref develop -f dry_run=true
  ```

- **The next rc, locally** (full history needed):

  ```bash
  pip install python-semantic-release==10.7.0
  git checkout develop && .github/scripts/next-rc.sh     # empty = nothing pending
  ```

  It resets a local `develop` branch to your current HEAD, so run it with
  `develop` checked out.

## Known limitations

- **CI does not run on the version-sync PR.** GitHub doesn't trigger
  workflows for events created by `GITHUB_TOKEN`. If `develop` requires
  status checks, merge it as an administrator, or close and reopen it to
  trigger CI. It only changes `CHANGELOG.md` and the version line.
- **A failed `release` job after a successful `promote`** leaves the image
  tagged with no git tag or GitHub Release. Re-run the failed job from the
  Actions UI (it reuses the promotion's version and digest). If
  `release/sync-vX.Y.Z` already exists from the failed attempt, delete it
  first.
- **rc git tags accumulate** on `develop` (one per develop build of a
  pending release). They're what gives each candidate its number and
  records its digest; don't delete them.
- The image is `linux/amd64` only.
