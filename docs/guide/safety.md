# Safety and limits

Read this page once. It explains what you can rely on and what you cannot.

## What pii-airlock does well

- **Exact restoring.** Anything it hid comes back byte for byte.
- **Consistency.** Once a value is found anywhere in a conversation, every other mention is hidden too, even ones the
  detector would have missed alone, and even earlier ones.
- **Local detection.** Spotting personal data never uses the network. Only the gateway forwards traffic, and only after cleaning.
- **Safe defaults.** If detection fails, hooks treat the input as sensitive. The gateway refuses requests it does not understand.
- **Same value, same placeholder.** Within a mapping, and with stable placeholders across requests, so the AI can follow who is who.
- **Disguised data.** An e-mail written `jean [at] acme [dot] ch` or `jean%40acme.ch`, an IBAN with invisible
  characters in it, a phone number in fullwidth digits, look-alike Cyrillic letters, HTML or JSON escapes, letters
  spaced out (`j e a n @ …`) and base64 that decodes to personal data are all found. The whole disguised text is
  what gets hidden.
- **Safe re-insertion.** Restored values go back through proper JSON encoding. A value with quotes, newlines or `<…>`
  cannot corrupt a request.

## What it cannot promise

::: warning Detection is best effort
The detector is statistical. It will sometimes miss a name or an unusual phone format, and sometimes flag a word
that is not personal. **It reduces exposure; it does not guarantee that nothing personal is sent.**
For truly sensitive material, review the cleaned text yourself.
:::

Specific gaps:

- **Images, audio and attachments** inside a request are forwarded as they are.
- **Output of tools** such as the result of `cat file` is not seen by hooks. The gateway does cover it.
- **Copilot's default models and inline suggestions** cannot be protected at all.
- **Websites and mobile apps** cannot be pointed at the gateway.
- **Claude's `thinking` blocks** are signed, so they are neither cleaned nor restored.
- **Word files:** formatting inside changed paragraphs is lost (they are rewritten as a single run). **PDFs:** you get text out, not a PDF.
- **Other gateway endpoints** that carry a body are refused unless you list them in `passthrough_paths`.
- **Gemini array streaming** (without `alt=sse`) is buffered, then restored as one response.
- **Every configured language** is analysed for every text and the results merged, so mixed English/French text is
  covered, at the cost of one pass per language.

## The map file holds the real data

When you clean a file with `scrub`, the mapping stores the original values so that `restore` can put them back.
By default it is encrypted and kept out of Git; a plain `--map` file is not. **Never commit, email or upload a
map file.** Everything about maps, keys and encryption is on one page:
[Data handling](/reference/data-handling).

## Ways to improve accuracy

1. Use the larger models (the default `_lg`) or [GLiNER](/customize/languages#many-languages-with-one-model-gliner).
2. [Deny](/customize/allow-and-deny) your internal names, so they are always caught.
3. Set the [action](/customize/actions) for critical types to `block`.
4. Lower the threshold (for example `score_threshold: 0.4`, see [Settings](/reference/settings#detection))
   to catch more, accepting more false alarms.

## Reporting a vulnerability

See the [security policy](https://github.com/matinfo-tech/pii-airlock/blob/main/SECURITY.md).
