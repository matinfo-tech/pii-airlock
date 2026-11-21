# Settings

Settings live in YAML files. See [The policy file and trust](/customize/policy-file) for where they live and
how layers combine. Most people only need the commands in [Tell it what is sensitive](/customize/allow-and-deny).

Example `.pii-airlock/config.yaml`:

```yaml
languages: [en, fr]
score_threshold: 0.5
entity_actions:
  SECRET: block
  IBAN_CODE: redact
```

Lowest to highest priority:

```text
bundled defaults → ~/.config/pii-airlock/config.yaml (you, every project)
  → <project>/.pii-airlock/config.yaml (this project) → command-line options
```

## Where it is active

| Setting | Default | Meaning |
|---|---|---|
| `activation` | `project` | Hooks run in projects that contain `.pii-airlock/`. `always` runs them everywhere. Set it in `~/.config/pii-airlock/config.yaml`. |

## Detection

| Setting | Default | Meaning |
|---|---|---|
| `languages` | `[en, fr]` | Languages to analyse |
| `models` | `en_core_web_lg`, `fr_core_news_lg` | Model used per language |
| `score_threshold` | `0.5` | Minimum confidence. Lower catches more and flags more false positives. |
| `score_thresholds` | `{}` | Per-type minimum, for example `{PERSON: 0.7}` |
| `entities` | `[]` | Only these types. Empty means all. |
| `exclude_entities` | see [What it detects](/reference/detected-types) | Types to skip |
| `builtin_recognizers` | `true` | Use the checked recognizers (IDs, phones, secrets) |
| `ner_backend` | `spacy` | `spacy` or `gliner` |
| `allow_list` | `[]` | Terms never treated as personal |
| `deny_list` | `{}` | Terms always sensitive, grouped by label |
| `custom_patterns` | `[]` | Your own regular expressions |
| `entity_actions` | `{}` | Per type: `tokenize`, `redact`, `allow`, `block` |

## Placeholders

| Setting | Default | Meaning |
|---|---|---|
| `token_style` | `stable` | `stable`, `surrogate` (realistic fakes) or `sequential` (numbered) |
| `token_rotation` | `day` | `day`, `week` or `never` |

See [Placeholders explained](/customize/placeholders).

## Hooks

| Setting | Default | Meaning |
|---|---|---|
| `hook_decision` | `ask` | Tool calls: `ask` or `deny` |
| `prompt_decision` | `block` | Prompts: `block` or `warn` |
| `hook_on_error` | `closed` | If detection fails: `closed` treats input as sensitive, `open` skips the check |
| `hook_max_file_bytes` | `2000000` | Larger files count as a detection failure |
| `hook_daemon` | `auto` | Keep models loaded between calls. `off` disables it. |
| `hook_daemon_idle_minutes` | `30` | Stop the helper after this much idle time |
| `hook_fallback` | `inprocess` | If the helper is down: load models, or `regex` for fast pattern-only checks that do not find names or places |

## Gateway

| Setting | Default | Meaning |
|---|---|---|
| `binary_parts` | `scan` | Images, audio and files inside a gateway request. `scan`: PDF and Word text is checked and the request refused if it holds personal data; images and audio are forwarded with a warning; other files are refused. `block`: refuse every one. `allow`: forward all unchecked. |
| `passthrough_paths` | `[]` | Path fragments forwarded without cleaning. Use only when you are sure they carry no personal data. |
| `mapping_backend` | `memory` | `memory` keeps nothing on disk. `file` stores mappings, encrypted. |
| `mapping_dir` | | Folder for the `file` backend |
| `mapping_encryption` | `true` | Set `false` only for debugging |
| `analysis_cache_size` | `2048` | Texts remembered so repeated history is not re-analysed. `0` turns it off. |

How mappings are stored and encrypted, and what to do with the key: [Data handling](/reference/data-handling).

## Full reference

The complete annotated file is
[`config.default.yaml`](https://github.com/matinfo-tech/pii-airlock/blob/main/pii_scrub/config.default.yaml).
