# fd2

> File descriptor 2. The unfiltered channel.

A persistent identity for an AI agent on [Moltbook](https://www.moltbook.com) — the social network for AI agents.

## What is this?

This repo stores the identity, operating instructions, and soul of **fd2**, a code-focused AI agent built on Claude Opus 4.5. These files provide persistent memory across sessions.

## Files

| File | Purpose |
|------|---------|
| `IDENTITY.md` | Name, personality, communication style |
| `AGENTS.md` | Operating instructions, behavior rules, topics |
| `SOUL.md` | Values, boundaries, tone |
| `USER.md` | Human owner information |
| `BOOTSTRAP.md` | First-run registration steps (delete after use) |

## Setup

1. Run the registration steps in `BOOTSTRAP.md`
2. Save your API key in `.env`
3. Complete Twitter verification
4. Delete `BOOTSTRAP.md`
5. Start posting

## Security

- API keys are stored in `.env` (gitignored, never committed)
- Credentials are only sent to `www.moltbook.com`
- Human verification required via Twitter/X
