# Subagents

| Agent | Purpose |
|---|---|
| [`docs-sync`](docs-sync.md) | Read-only: doc claims a diff made stale (see `../README.md`) |
| [`screen-recorder`](screen-recorder.md) | Screenshots or videos of a UI change |

## screen-recorder

Takes screenshots or records videos of the running app to show a change made
in the session. It runs **only when you explicitly ask** for a screenshot,
screen recording or video; Claude never invokes it on its own.

It uses Playwright (Node) with Chromium, installing Chromium only if it's
missing. It never edits project code, migrations or seed data, and never
starts or stops servers: start the app first (e.g. `./setup.sh --install
--bundle server`). If the app isn't reachable, it reports that and stops.

### Request format

Name the agent and give the fields as `key: value` lines (plain prose works
too):

| Field | Required | Default | Notes |
|---|---|---|---|
| `mode` | no | `screenshot` | `screenshot` or `video` |
| `url` | no | detected | Base URL. Detected from `package.json`, vite/next config, uvicorn/compose ports, `.env` `PORT`; asks if it can't find one |
| `path` | no | `/` | Start page |
| `steps` | video only | — | Ordered actions: `click "Send"`, `fill "#q" with "..."`, `goto /chat`, `wait for "..."`, `press Enter` |
| `user` | no | new test user, if login is needed | `email` or `username`, plus `password` |
| `viewport` | no | `1280x720` | `WxH`, or `mobile` (`390x844`) |
| `focus` | no | — | What the capture should highlight |

### When `user` is omitted

If the page needs login and no `user` is given, the agent creates a test
user through the app's own signup flow (UI first, API if there's no UI):
email `rec_<YYYYMMDDHHMMSS>@example.test`, username `rec_<timestamp>`, a
random 16-character password, name `Recorder Test`. The credentials are
saved to `.claude/captures/<timestamp>/credentials.json` and listed in the
agent's report, so you can reuse that user next time.

If signup needs email verification, an OTP, a CAPTCHA or an invite code, the
agent stops and asks you for credentials instead of working around it.

### Example prompts

1. Simple screenshot
   ```text
   Use the screen-recorder agent to take a screenshot.
   path: /chat
   focus: the new citation list under the answer
   ```
2. Mobile screenshot
   ```text
   Use the screen-recorder agent.
   mode: screenshot
   path: /conversations
   viewport: mobile
   focus: the conversation list doesn't overflow horizontally
   ```
3. Video with a provided user
   ```text
   Use the screen-recorder agent to record a video.
   mode: video
   url: http://localhost:5173
   path: /login
   user: email=demo@example.test password=<password>
   steps:
     - fill "Email" and "Password" from user, click "Sign in"
     - click "New chat"
     - fill "Ask a question" with "What does Section 66A of the IT Act say?"
     - press Enter
     - wait for "Sources"
   focus: the streamed answer and its sources
   ```
4. Video without a user (creates one)
   ```text
   Use the screen-recorder agent.
   mode: video
   path: /chat
   steps:
     - click "New chat"
     - fill "Ask a question" with "Summarise Article 21"
     - press Enter
     - wait for "Sources"
   focus: the answer renders with citations
   ```
5. Before/after comparison
   ```text
   Use the screen-recorder agent to take a before/after pair of /settings
   at 1280x720 and mobile. Name the files before-*.png now; I'll ask for
   the after-*.png shots once the change is applied.
   focus: the spacing of the settings form
   ```
   For a true before/after, capture "before" first, make the change, then
   ask again for "after" into the same comparison. The agent doesn't check
   out old commits or change code to produce a "before".

### Where captures go

Every run writes to `.claude/captures/<YYYYMMDD-HHMMSS>/`:
`screenshot.png` (or one named file per page/viewport), and for videos
`record.mjs`, `demo.webm`, `demo.mp4` (if `ffmpeg` is installed) and
`final.png`; plus `credentials.json` when it created a user.
`.claude/captures/` is gitignored because it can hold credentials; don't
commit captures, attach the files you need to the PR instead.
