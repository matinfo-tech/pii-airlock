# Claude Code

Claude Code reads files and runs commands for you. pii-airlock adds checkpoints called **hooks**
that look at what is about to be sent and stop you when it contains personal data.

## Set it up: `pii-airlock init`

First install the program ([Install](/guide/install)). Then, in your project:

```bash
pii-airlock init
```

This creates a `.pii-airlock/` folder in the project and installs the hooks for your user, once.
The hooks only act in projects that have this folder, so your other projects are left alone.
Run `pii-airlock init` in each project you want guarded. Restart Claude Code after the first
`init` so it loads the hooks.

```bash
pii-airlock status   # is this project guarded, by which hooks
pii-airlock off      # pause it here (pii-airlock on resumes)
```

At the start of each session, Claude is told the project's rules: use placeholders, never work
around a block, never open the mapping files.

## Or: the plugin

Inside Claude Code:

```text
/plugin marketplace add matinfo-tech/pii-airlock
/plugin install pii-airlock@pii-airlock
```

You also get a `/pii-airlock:setup` helper. You still run `pii-airlock init` in each project: it
sees the plugin and does not install the hooks a second time.

::: warning If the program is missing
In a guarded project, the plugin **blocks every prompt and tool call** while the `pii-airlock`
command cannot be found, and says why. Install the program to fix it.
:::

To let prompts and tool calls through while the program is missing, set `PII_AIRLOCK_PLUGIN_FAIL_OPEN=1`.

The plugin's launcher is a shell script, so on Windows use `pii-airlock init` without the plugin.

## Register the hooks by hand

`init` does this for you. To do it manually:

```bash
pii-airlock install-hook --scope project   # writes the repo's .claude/settings.json
pii-airlock install-hook --event tool      # or --event prompt: only one of the two
```

With `--scope project`, every teammate then needs the program installed.

## What you will see

| What you did | What happens |
|---|---|
| Typed a prompt containing personal data | The prompt is **blocked**. You get a scrubbed version to send instead. |
| Claude wants to read a file containing personal data | Claude Code **asks you** to confirm. |
| Claude wants to run a command, edit a file, search or fetch a URL containing personal data | Claude Code **asks you** to confirm. |
| Claude calls an MCP tool with personal data in its arguments | Claude Code **asks you** to confirm. |

Under the hood these are three Claude Code events: `UserPromptSubmit` (your prompts), `PreToolUse` (tool calls,
including file reads, whose content is scanned) and `SessionStart` (tells Claude the project's rules).

The hooks **detect and block or ask**. They do not silently rewrite what you send, because the hook interface
does not allow it. For a silent, reversible rewrite use the [gateway](/use/gateway) or
[`scrub`](/use/files-and-text).

Every message tells you what type was found (for example "2 emails") but never repeats the value itself.

### A false alarm?

If pii-airlock flags something that is not personal, such as your company name, tell it once:

```bash
pii-airlock allow "Acme SA"
```

See [Tell it what is sensitive](/customize/allow-and-deny).

## Change how strict it is

Put these in your project's `.pii-airlock/config.yaml` (all hook settings:
[Settings](/reference/settings#hooks)).

| Setting | Effect |
|---|---|
| `hook_decision: deny` | Block risky tool calls outright instead of asking. |
| `prompt_decision: warn` | Let prompts through with a warning instead of blocking. |
| `hook_on_error: open` | If detection breaks (for example a missing model), carry on instead of treating the input as sensitive. |

By default the hooks **fail closed**: when detection cannot run, the input counts as sensitive.

## What hooks cannot see

Hooks check what goes **into** a tool. They cannot see what a tool **prints back**. If Claude runs `cat customers.csv`,
the output reaches the AI unchecked. Images and PDFs are not inspected either.

For full coverage, also send Claude Code's traffic through the gateway:

```bash
pii-airlock proxy
```
```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:8745/anthropic
claude
```

The gateway hides personal data in tool output too and restores it in the commands Claude writes back.

## Why does the first prompt feel slow?

The name-spotting models take a few seconds to load. pii-airlock starts a small background helper on the first
call that keeps them loaded, so later checks take about 60 milliseconds. It stops after 30 idle minutes.

```bash
pii-airlock daemon status   # also shown by `pii-airlock status`
pii-airlock daemon start    # warm it up now, for example from your shell profile
pii-airlock daemon stop
```

### The helper in detail

- **Why it exists.** Claude Code starts a new process for every hook call, and loading the models costs 0.5 to 3
  seconds each time.
- **Who can talk to it.** On macOS and Linux it listens on a Unix socket (mode `0600`, in a folder only you can
  write to). On Windows it listens on `127.0.0.1` with a random secret kept in a file only you can read. The hook
  checks that the helper knows that secret before it sends any text.
- **Policy.** It reloads your project policy on every call, so edits to `.pii-airlock/config.yaml` apply at once.
- **Lifetime.** It exits after `hook_daemon_idle_minutes` (default 30) without calls. Nothing leaves your machine.
- **When it is down.** With `hook_fallback: inprocess` (default) the hook loads the models itself. With
  `hook_fallback: regex` it uses patterns only, in milliseconds: emails, phones, IBANs, cards, IPs, FR/CH IDs,
  secrets and your deny list. **Names and places are not detected in that mode.**
- **Turn it off.** `hook_daemon: off`.
