# Add a language

By default pii-airlock looks for names in **English and French**. It checks every configured language on every
text and combines the results, so mixed text is handled. Where a model reads text in another language, only what
looks like a name is kept from it: the English model would otherwise tag ordinary French phrases as organizations.

## Add German as an example

1. In your project's `.pii-airlock/config.yaml`:

   ```yaml
   languages: [en, fr, de]
   models:
     de: de_core_news_md
   ```

2. Download the models and check:

   ```bash
   pii-airlock download-models
   pii-airlock doctor
   ```

   `download-models` picks up the new language from your file.

More models: [spaCy models list](https://spacy.io/models).

## Many languages with one model (GLiNER)

If you work in many languages, one multilingual model can replace one model per language.

```bash
pipx inject pii-airlock 'pii-airlock[gliner]'
```

```yaml
ner_backend: gliner
```

```bash
pii-airlock download-models
```

| | Standard spaCy models | GLiNER |
|---|---|---|
| Download size | small | about 1.1 GB, plus PyTorch |
| Speed per message | about 6 ms | about 40 ms |
| Names found correctly | good | better, with far fewer false alarms |

Emails, phone numbers, IDs and secrets are found by patterns in both modes.

### Measured quality

On the bundled English and French evaluation corpus (`python -m tests.eval.run_eval --backend gliner`):

| | spaCy `_sm` models | GLiNER |
|---|---|---|
| Names (`PERSON`): recall / precision | 0.96 / 0.68 | 1.00 / 0.95 |
| All types: precision | 0.67 | 0.98 |
| Time per message (CPU) | about 6 ms | about 40 ms |

Fewer false positives means fewer needless hook prompts.

How it behaves:

- Long texts are scanned in overlapping windows, because GLiNER itself truncates past a few hundred words.
- Organizations and places must be capitalized to count. This drops common nouns GLiNER tags, such as "la société"
  or "client". Names are kept in any case.
- With the hook helper, the model is loaded once.
