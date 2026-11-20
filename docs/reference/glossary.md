# Glossary

The words used across these docs, including the aliases you may meet in command names and settings.

| Term | Also called | Meaning |
|---|---|---|
| **Gateway** | proxy (the command is `pii-airlock proxy`) | A small server on your computer. Your AI tool talks to it instead of the provider; it swaps placeholders in and out automatically. |
| **Hook** | | A checkpoint inside Claude Code or Copilot. It inspects a prompt or a tool call before it is sent and can block it or ask you. |
| **Placeholder** | token | What replaces a real value in the text the AI sees, for example `<PERSON_482913>`. [Placeholders explained](/customize/placeholders). |
| **Map** | mapping, mapping file | The file pairing each placeholder with the original value. It is what makes restoring possible, and it is sensitive. [Data handling](/reference/data-handling). |
| **Helper** | daemon (the command is `pii-airlock daemon`) | The background process that keeps the detection models loaded so hook checks take ~60 ms. |
| **Type** | entity (settings use `entities`, `entity_actions`) | A category of personal data: `PERSON`, `EMAIL_ADDRESS`, `IBAN_CODE`… [What it detects](/reference/detected-types). |
| **Base URL** | | The address a tool sends its AI requests to. Pointing it at the gateway is how the gateway intercepts traffic. |
| **Project home** | `.pii-airlock/` | The folder `init` creates. Its presence switches the hooks on for that project. |
| **Policy** | project policy, rules | Your allow/deny lists, actions and patterns, stored in `.pii-airlock/config.yaml`. [The policy file](/customize/policy-file). |
| **Threshold** | `score_threshold` | The minimum confidence (0 to 1) before a detection counts. Lower catches more, with more false alarms. |
| **Fail closed** | | When detection cannot run, treat the input as sensitive (the default). "Fail open" means letting it through instead. |
| **Scrub / restore** | clean / put back | `scrub` replaces personal data with placeholders; `restore` puts the originals back in a reply. |
| **Recognizer** | | One detector for one type, for example the checksum check for French social security numbers. |
| **Trust** | | Accepting a downloaded project's policy after reviewing it, so its loosening settings apply too. [Trust](/customize/policy-file#trusting-a-project-you-downloaded). |
