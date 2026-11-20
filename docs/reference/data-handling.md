# Data handling: maps, keys and encryption

The single page about where real values are kept, how they are protected, and what you must not do with them.

## The map file holds the real data

When you clean something with `scrub`, the mapping (also called the map) pairs every placeholder with the
**original value**. It is what makes `restore` possible, and it is the most sensitive file pii-airlock writes.

- By default it goes to the project's `.pii-airlock/maps/` (outside a project:
  `~/.local/state/pii-airlock/maps/`), **encrypted**, in an owner-only folder. The folder's own
  `.gitignore` keeps it out of Git. `restore` tries these maps automatically, so no option is needed.
- `--map FILE` writes plain JSON where you say (add `--encrypt-map` to encrypt it). Never commit,
  email or upload such a file. This repository's `.gitignore` also excludes `*.pii-map.json` and `*.pii-map.*`.
- Delete mappings when you are done. Use `--no-map` if you will never need to restore.

The **gateway** keeps its mapping in memory only and forgets it after each response. It writes no personal
data to disk.

## The key

Maps are encrypted with **AES-256-GCM**, with a key derived from `token.key` in `~/.local/state/pii-airlock/`
(the same key that makes [placeholders](/customize/placeholders) stable). The key never leaves your machine
and is never stored in the project: encrypted maps next to their key would protect nothing.

- A copied, synced or backed-up project folder is useless without the key. Keep `token.key` out of backups
  and never in the repository.
- Losing the key makes the maps unreadable. Delete `token.key` to rotate it immediately.
- Plain map files written by older versions still load.

## Storage settings

For the gateway's optional on-disk mapping backend (`mapping_backend: file`, `mapping_dir`,
`mapping_encryption`), see [Settings](/reference/settings#gateway). `memory` stays the safest default for
local use because mappings are ephemeral; `file` is for debugging or operational inspection on self-hosted,
higher-volume setups. `mapping_encryption: false` writes readable JSON for debugging and is ignored in a
project you have not trusted.

## Windows note

On Windows, files cannot be set to owner-only the way they are on macOS and Linux (maps are created with mode
`0600` on POSIX). They inherit your account's default permissions, which are normally private in your home
folder. Treat mapping files as secrets regardless.
