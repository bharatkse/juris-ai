# Commit Signing (Required)

Both `develop` and `main` branches require every commit to have a
verified signature before it can be merged, enforced via GitHub
rulesets. This applies to every contributor, including the repo owner
— if you plan to open a PR against either branch, complete this setup
first, or your commits will be blocked from merging.

## Setup (SSH-based signing)

1. Generate an SSH key if you don't already have one:

```bash
ssh-keygen -t ed25519 -C "your-email@example.com"
```

Accept the default path (`~/.ssh/id_ed25519`), set a passphrase or
skip it.

2. Configure git to sign with it:

```bash
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub
git config --global commit.gpgsign true
```

3. Add the public key to GitHub as a **Signing Key** (not an
   Authentication Key) at https://github.com/settings/keys:

```bash
cat ~/.ssh/id_ed25519.pub
```

Paste the output when adding the key. Set "Key type" to
"Signing Key" specifically — an Authentication Key won't satisfy
this requirement.

4. From this point on, every new commit is signed automatically.
   Confirm on GitHub: your commits will show a green "Verified" badge.

## Fixing already-pushed unsigned commits

If you've already pushed commits before completing setup, they need
to be re-signed and force-pushed:

```bash
git log --oneline -N   # confirm how many commits need re-signing
git rebase --exec 'git commit --amend --no-edit -S -n' -i HEAD~N
git push --force-with-lease origin <your-branch-name>
```

Only safe on a branch you're the sole owner of — never force-push
`develop`/`main` directly, and never force-push a shared branch
without confirming no one else has it checked out.

## Troubleshooting

- `error: Couldn't load public key ... No such file or directory` —
  you don't have an SSH key yet; complete step 1 first.
- Commit still shows unverified after setup — confirm the key was
  added as a "Signing Key" on GitHub, not an "Authentication Key"
  (these are separate key-type slots even if you upload the same
  public key to both).
