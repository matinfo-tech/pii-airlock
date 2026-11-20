# What is pii-airlock?

When you paste text into an AI assistant, that text travels to the company running the AI.
If it contains a customer's name, an email address, a phone number or a password, that data
leaves your computer too.

**pii-airlock is a small program that runs on your own computer and sits between you and the AI.**
Think of it as an airlock: personal details cannot pass through it in the clear.

## How it works

1. **You write** your question as usual.
2. **pii-airlock finds** names, emails, phone numbers, bank numbers, secret keys and similar items.
3. **It swaps each one** for a placeholder, for example `<PERSON_482913>`.
4. **The AI sees only placeholders** and answers using them.
5. **pii-airlock swaps the originals back** into the answer before you read it.

The same person always gets the same placeholder, so the AI can still follow who is who.
You can read more in [Placeholders explained](/customize/placeholders).

## What it is good for

- Asking an AI to draft or summarise something that mentions real people.
- Letting a coding assistant work in a project that contains customer data.
- Cleaning a file (text, CSV, JSON, Word, PDF) before you share it.

## What it is not

- **Not a guarantee.** Detection is smart but not perfect. It can miss a name or flag a word that is not personal.
  Read [Safety and limits](/guide/safety) before you rely on it for sensitive work.
- **Not a cloud service.** Nothing is uploaded to pii-airlock's authors. Detection runs on your machine.
- **Not an AI itself.** It does not answer questions. It only protects what you send to the AI you already use.

## Two ways to use it

There are two modes: **hooks** (checkpoints inside Claude Code and Copilot that stop you before personal data
is sent) and the **gateway** (a local address any other AI app talks to, with automatic swap and restore).
[Pick your setup](/use/pick-your-setup) tells you which one fits your tool.

## The project folder: `.pii-airlock/`

Like `.git/`, one folder holds everything pii-airlock knows about a project, and its presence is the on switch.
`pii-airlock init` creates it.

```text
my-project/.pii-airlock/
  config.yaml   your rules: allow/deny lists, actions, patterns    shared with the team (committed)
  .gitignore    ignores everything else                            committed
  maps/         the keys to undo a cleanup (real values, encrypted)  local only
  off           present while paused (`pii-airlock off`)             local only
```

- The hooks are installed once for your user and **do nothing outside a project folder**, so unrelated projects are
  untouched. The folder is found from any subdirectory.
- The secret key behind your placeholders and your trust decisions stay in `~/.local/state/pii-airlock/`, never in
  the project. Encrypted maps next to their key would protect nothing.
- To guard every directory instead, set `activation: always` in `~/.config/pii-airlock/config.yaml`.
- The gateway has no notion of project: it cleans whatever is sent to it.

## Next step

[Quick start (5 minutes)](/guide/quick-start)
