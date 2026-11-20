# Placeholders explained

A placeholder replaces a real value in the text the AI receives. You choose the style.

## Style 1: stable tokens (default)

```text
Jean Dupont  →  <PERSON_558644>
jean@acme.fr →  <EMAIL_ADDRESS_094087>
```

- The **same value always gets the same token**, in every message, file and session. The AI can follow who is who,
  and caching keeps working.
- Tokens are a keyed hash (HMAC-SHA256) of the value, computed with a secret key kept on your computer
  (`~/.local/state/pii-airlock/token.key`, owner-only, never leaves your machine).
  Without it a token tells nobody anything about the value behind it.
- Because the token is the same everywhere, it holds across conversation turns, subagents and trimmed or compacted
  histories, and prompt caches keep hitting.
- **Tokens change over time.** By default a person gets a new token each day, so a provider cannot follow one person
  across all your conversations.

```yaml
token_rotation: day     # day (default), week, or never
```

Use `never` if you clean one big dataset over several runs and need identical tokens throughout.

To change all tokens immediately, delete `token.key`.

## Style 2: realistic fakes

```yaml
token_style: surrogate
```

```text
Jean Dupont         →  Jasper Iverson
jean.dupont@acme.fr →  jasper.iverson@example.com
```

The text reads naturally, which some models handle better than `<TOKENS>`. Fakes are keyed the same way as tokens,
so they stay stable. Phone numbers keep their shape, cards stay Luhn-valid, IBANs keep a valid checksum, and IP
addresses come from the documentation ranges. A surname on its own gets the surname of the full fake, and is
restored on its own too. Other types, such as IDs, secrets and places, still use tokens.

Trade-off: if the AI invents a name that happens to equal a fake, that name is also swapped back.

## Style 3: numbered

```yaml
token_style: sequential
```

```text
<PERSON_1>, <PERSON_2> …
```

Numbered in reading order, separately for each request or file. This was the default in early versions.

## Where do I put these settings?

In `~/.config/pii-airlock/config.yaml` for yourself, or `.pii-airlock/config.yaml` in a project. See
[Settings](/reference/settings).
