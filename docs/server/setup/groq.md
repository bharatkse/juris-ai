# Groq API Key Setup

This guide explains how to obtain a Groq API key for the Juris-AI development environment.

## 1. Open Groq Console

Open the Groq Console:

https://console.groq.com/

Sign in or create a Groq account.

## 2. Open API Keys

After signing in:

1. Open the **API Keys** section.
2. Select **Create API Key**.
3. Give the key a recognizable name, for example:

```text
juris-ai-dev
```

## 3. Create the API Key

Create the key and copy it immediately.

The generated key is a secret credential and should be treated like a password.

**Do not paste the key into GitHub, documentation, source code, or chat messages.**

## 4. Add the Key to `.env`

In the Juris-AI project `.env` file, configure:

```env
GROQ_API_KEY=gsk_...
```

Replace `gsk_...` with your actual Groq API key.

## 5. Keep `.env` Out of Git

Make sure `.env` is included in `.gitignore`:

```gitignore
.env
```

Commit only the example configuration:

```text
.env.example
```

For example:

```env
GROQ_API_KEY=
```

## 6. Verify

Restart the Juris-AI application after updating `.env` so the new environment variable is loaded.

Then run a Juris-AI request that uses the Groq model.

If the request completes successfully without an authentication error, the Groq API key is configured correctly.

## Security Notes

- Never commit `GROQ_API_KEY` to source control.
- Never expose the API key in logs.
- Never share the actual API key in documentation.
- If the key is accidentally exposed, revoke/rotate it from the Groq Console.
