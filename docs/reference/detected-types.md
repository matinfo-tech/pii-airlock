# What it detects

pii-airlock combines [Microsoft Presidio](https://microsoft.github.io/presidio/), a language model for names, and its own
checked recognizers. Use these type names with [`pii-airlock action`](/customize/actions).

## Common types

| Type | Examples |
|---|---|
| `PERSON` | Names |
| `EMAIL_ADDRESS` | `jean@acme.fr` |
| `PHONE_NUMBER` | `+33 6 12 34 56 78`, `079 123 45 67` |
| `CREDIT_CARD` | Card numbers |
| `IBAN_CODE` | Bank account numbers |
| `IP_ADDRESS` | `192.168.1.10` (not `127.0.0.1`, `0.0.0.0`, link-local or a version number such as `v1.2.3.4`) |
| `LOCATION` | Cities, addresses |
| `SECRET` | API keys, tokens, private keys, `password=…` values |

## Extra recognizers that work in any language

These check the number's built-in check digit, so a random number does not trigger them.

| Type | What it is | How it is checked |
|---|---|---|
| `FR_NIR` | French social security number | mod-97 key (including Corsica 2A/2B) |
| `CH_AHV` | Swiss AHV/AVS number `756.xxxx.xxxx.xx` | EAN-13 check digit |
| `FR_SIRET`, `FR_SIREN` | French business IDs (sole traders count as people) | Luhn. SIREN needs a keyword. |
| `DE_TAX_ID` | German tax ID (needs a nearby keyword such as `Steuer-ID` or `IdNr`) | ISO 7064 MOD 11,10 |
| `DE_TAX_NUMBER` | German `Steuernummer`, for example `21/815/08150` (needs a keyword) | format |
| `IT_VAT_CODE` | Italian Partita IVA (with the `IT` prefix or a `P.IVA` keyword) | Luhn |
| `ES_NIF`, `ES_NIE` | Spanish DNI/NIF `12345678Z` and foreigner NIE `X1234567L` (with or without `.`/`-`) | mod-23 check letter |
| `PHONE_NUMBER` | International `+CC …` in any language, plus FR, CH, DE and IT national formats such as `06 12 34 56 78`, `079 123 45 67`, `030 12345678`, `333 1234567` | format |
| `SECRET` | Keys for AWS, GitHub, Slack, OpenAI, Anthropic, Google and Stripe, JWTs, private keys, passwords in URLs, `password=…` values | format |

## Disguised values

Every type above is also found when it is disguised: invisible (zero-width) characters, look-alike letters
from other alphabets, fullwidth digits, `%40` / `&#64;` / `\u0040` escapes, `[at]` `(dot)` and
`at … dot …` spellings, letters separated by spaces, and base64 that decodes to personal data. The
disguised text as written is what gets replaced. Only text that contains such a disguise is analysed a
second time, so clean text costs nothing extra.

## Ignored by default

These fire on almost every date and web link, so they are off unless you ask:

`DATE_TIME`, `URL`, `NRP`, `US_DRIVER_LICENSE`, `US_BANK_NUMBER`, `US_PASSPORT`, `IN_VEHICLE_REGISTRATION`

An email or name inside a link is still caught by its own recognizer.

To turn one on, set `exclude_entities` to a list without it, or an `action` for that type.
To turn off all the extra recognizers: `builtin_recognizers: false`.
