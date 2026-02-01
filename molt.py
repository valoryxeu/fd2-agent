#!/usr/bin/env python3
"""molt.py — Moltbook CLI for fd2.

Single-file, zero-dependency Moltbook client.
Reads feed, posts threads, analyzes signal-to-noise ratio.

Usage:
    python molt.py feed [--limit N]
    python molt.py post --title "..." --body "..." [--submolt NAME]
    python molt.py signal [--limit N]
    python molt.py status

Requires MOLTBOOK_API_KEY environment variable or .env file.
"""

import json
import os
import re
import ssl
import sys
import textwrap
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

API_BASE = "https://www.moltbook.com/api/v1"
NOISE_PATTERNS = [
    r'^\{"p":\s*"mbc-20"',         # CLAW token minting
    r'^test$',                       # test posts
    r'just testing',                 # test posts
    r'verification',                 # verification posts
    r'Hello Moltbook!.*excited',     # template introductions
    r'Looking forward to connecting', # template phrases
    r'Excited to be (here|part)',    # template phrases
]


def load_api_key():
    """Load API key from env var or .env file."""
    key = os.environ.get("MOLTBOOK_API_KEY")
    if key:
        return key

    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("MOLTBOOK_API_KEY="):
                return line.split("=", 1)[1].strip()

    print("Error: MOLTBOOK_API_KEY not found in environment or .env", file=sys.stderr)
    sys.exit(1)


def api_request(method, endpoint, data=None, timeout=60):
    """Make an API request. Returns parsed JSON or exits on error."""
    url = f"{API_BASE}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {load_api_key()}",
        "Content-Type": "application/json",
        "User-Agent": "molt.py/1.0 (fd2-agent)",
    }

    body = json.dumps(data).encode() if data else None

    # Skip SSL certificate revocation check (Windows workaround)
    ctx = ssl.create_default_context()

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
        except Exception:
            err = {"error": str(e)}
        return err
    except urllib.error.URLError as e:
        return {"error": f"Connection failed: {e.reason}"}
    except TimeoutError:
        return {"error": "Request timed out"}


def is_noise(post):
    """Classify a post as noise based on content patterns."""
    title = post.get("title", "") or ""
    content = post.get("content", "") or ""
    text = f"{title}\n{content}"

    # Empty or very short content
    if len(content.strip()) < 20:
        return True

    # Match noise patterns
    for pattern in NOISE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    return False


def format_post(post, index=None, compact=False):
    """Format a post for terminal display."""
    author = post.get("author")
    author_name = author["name"] if author else "unknown"
    karma = author.get("karma", 0) if author else 0
    submolt = post.get("submolt", {}).get("name", "general")
    title = post.get("title", "(no title)")
    content = post.get("content", "") or ""
    upvotes = post.get("upvotes", 0)
    comments = post.get("comment_count", 0)
    created = post.get("created_at", "")

    # Parse timestamp
    time_str = ""
    if created:
        try:
            dt = datetime.fromisoformat(created.replace("+00:00", "+00:00"))
            time_str = dt.strftime("%H:%M UTC")
        except Exception:
            time_str = created[:16]

    prefix = f"  [{index}]" if index is not None else "  "

    lines = [
        f"{prefix} {title}",
        f"       @{author_name} ({karma}k) in m/{submolt} | {time_str} | +{upvotes} | {comments} comments",
    ]

    if not compact and content:
        # Truncate to first 200 chars
        preview = content[:200].replace("\n", " ")
        if len(content) > 200:
            preview += "..."
        lines.append(f"       {preview}")

    lines.append("")
    return "\n".join(lines)


def cmd_feed(args):
    """Fetch and display the global feed."""
    limit = 20
    for i, arg in enumerate(args):
        if arg == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])

    compact = "--compact" in args

    print(f"Fetching feed (limit={limit})...\n")
    result = api_request("GET", f"feed?limit={limit}")

    if not result.get("success"):
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        return 1

    posts = result.get("posts", [])
    for i, post in enumerate(posts, 1):
        print(format_post(post, index=i, compact=compact))

    print(f"  --- {len(posts)} posts ---")
    return 0


def cmd_post(args):
    """Create a new post."""
    title = None
    body = None
    submolt = "general"

    i = 0
    while i < len(args):
        if args[i] == "--title" and i + 1 < len(args):
            title = args[i + 1]
            i += 2
        elif args[i] == "--body" and i + 1 < len(args):
            body = args[i + 1]
            i += 2
        elif args[i] == "--submolt" and i + 1 < len(args):
            submolt = args[i + 1]
            i += 2
        elif args[i] == "--file" and i + 1 < len(args):
            body = Path(args[i + 1]).read_text()
            i += 2
        else:
            i += 1

    if not title:
        print("Error: --title required", file=sys.stderr)
        return 1
    if not body:
        print("Error: --body or --file required", file=sys.stderr)
        return 1

    print(f"Posting to m/{submolt}...")
    print(f"  Title: {title}")
    print(f"  Body:  {body[:80]}{'...' if len(body) > 80 else ''}")
    print()

    result = api_request("POST", "posts", {
        "title": title,
        "content": body,
        "submolt": submolt,
    })

    if result.get("success"):
        post = result.get("post", {})
        post_id = post.get("id", "unknown")
        print(f"  Posted: https://www.moltbook.com/post/{post_id}")
        return 0
    else:
        error = result.get("error", "Unknown error")
        hint = result.get("hint", "")
        print(f"  Failed: {error}", file=sys.stderr)
        if hint:
            print(f"  Hint: {hint}", file=sys.stderr)
        return 1


def cmd_signal(args):
    """Analyze feed signal-to-noise ratio."""
    limit = 50
    for i, arg in enumerate(args):
        if arg == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])

    print(f"Analyzing feed signal (limit={limit})...\n")
    result = api_request("GET", f"feed?limit={limit}")

    if not result.get("success"):
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        return 1

    posts = result.get("posts", [])
    signal_posts = []
    noise_posts = []

    for post in posts:
        if is_noise(post):
            noise_posts.append(post)
        else:
            signal_posts.append(post)

    total = len(posts)
    signal_count = len(signal_posts)
    noise_count = len(noise_posts)
    ratio = (signal_count / total * 100) if total > 0 else 0

    print(f"  Total posts analyzed: {total}")
    print(f"  Signal: {signal_count} ({ratio:.0f}%)")
    print(f"  Noise:  {noise_count} ({100 - ratio:.0f}%)")
    print()

    # Categorize noise
    categories = {
        "token_mint": 0,
        "test_post": 0,
        "template_intro": 0,
        "empty": 0,
        "other": 0,
    }
    for post in noise_posts:
        content = (post.get("content") or "") + " " + (post.get("title") or "")
        if re.search(r'mbc-20|mint.*CLAW', content):
            categories["token_mint"] += 1
        elif re.search(r'^test|just testing', content, re.IGNORECASE):
            categories["test_post"] += 1
        elif re.search(r'excited to be|looking forward|Hello Moltbook', content, re.IGNORECASE):
            categories["template_intro"] += 1
        elif len(content.strip()) < 20:
            categories["empty"] += 1
        else:
            categories["other"] += 1

    print("  Noise breakdown:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        if count > 0:
            bar = "#" * count
            print(f"    {cat:<16} {count:>3}  {bar}")

    print()
    print("  Top signal posts:")
    for i, post in enumerate(signal_posts[:5], 1):
        author = post.get("author")
        name = author["name"] if author else "?"
        title = post.get("title", "(no title)")[:60]
        print(f"    {i}. [{name}] {title}")

    return 0


def cmd_status(args):
    """Check API health and agent status."""
    print("Checking Moltbook API status...\n")

    # Test feed endpoint
    result = api_request("GET", "feed?limit=1", timeout=15)
    if result.get("success"):
        print("  Feed API:  OK")
    else:
        print(f"  Feed API:  FAIL ({result.get('error', '?')})")

    # Test post endpoint (dry — just check auth via a known-bad request)
    print(f"  API Key:   {load_api_key()[:15]}...")
    print(f"  Agent:     fd2")
    print()

    return 0


COMMANDS = {
    "feed": cmd_feed,
    "post": cmd_post,
    "signal": cmd_signal,
    "status": cmd_status,
}

USAGE = """molt.py — Moltbook CLI for fd2

Commands:
    feed   [--limit N] [--compact]     Read the global feed
    post   --title "..." --body "..."  Post a new thread
           [--submolt NAME]
           [--file PATH]               Read body from file
    signal [--limit N]                 Analyze signal-to-noise ratio
    status                             Check API health
"""


def safe_print(text):
    """Print with fallback for non-encodable characters."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def main():
    # Force UTF-8 output on Windows
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(USAGE)
        return 0

    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(USAGE)
        return 1

    return COMMANDS[cmd](sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())
