# GitHub Copilot

Copilot has three parts, and only some can be protected.

| Part of Copilot | Protected? | How |
|---|---|---|
| Copilot CLI and cloud agent: tool calls | Yes | Hook |
| Agent mode in VS Code: tool calls | Yes | Hook |
| Copilot Chat in VS Code with **your own model and API key** | Yes | Gateway |
| Default Copilot models, inline suggestions, prompts typed into the CLI | **No** | GitHub offers no way to intercept them |

::: warning Be clear about the gap
Inline suggestions and the default Copilot models send data through GitHub's own servers. pii-airlock cannot
sit in front of that. Do not rely on it there.
:::

## Protect tool calls (hook)

```bash
pii-airlock init
```

Run in a project, `init` installs the Copilot hook for your user (in `~/.copilot/hooks/`) when it
finds Copilot, and guards this project. The hook only acts in projects that have a `.pii-airlock/`
folder. It checks shell commands, file reads and edits, web fetches and MCP calls, and asks you
before anything containing personal data goes ahead.

The cloud agent runs on GitHub's machines and does not see your user hooks. For it, write the hook
into the repository:

```bash
pii-airlock install-hook --target copilot   # .github/hooks/pii-airlock.json
```

## Chat in VS Code

Copilot hooks cannot block what you type in chat. Instead, add your own model that goes through the gateway.

1. Start the gateway: `pii-airlock proxy`
2. In VS Code open **Manage Models** and add a custom endpoint model, using `chatLanguageModels.json`.

```json
[
  {
    "name": "OpenAI via pii-airlock",
    "vendor": "customendpoint",
    "apiKey": "${input:openaiKey}",
    "apiType": "chat-completions",
    "models": [{
      "id": "gpt-4o", "name": "GPT-4o", "toolCalling": true,
      "url": "http://127.0.0.1:8745/openai/v1/chat/completions",
      "maxInputTokens": 100000, "maxOutputTokens": 16000
    }]
  }
]
```

For Claude models use `"apiType": "messages"` and the URL `http://127.0.0.1:8745/anthropic/v1/messages`
(for example model id `claude-sonnet-4-6`). `"apiType": "responses"` also works, with
`http://127.0.0.1:8745/openai/v1/responses`.
Your own API key is forwarded to the provider and never logged.

## How the hook behaves (details)

- **Same checks as Claude Code.** `hook_decision`, `entity_actions: block` and `hook_on_error` all apply.
  Shell commands, `grep` and `glob` patterns, paths and source files get the same
  [code filter](/use/claude-code#shell-commands-and-code), so `npm test` is not stopped.
  The hook registers `preToolUse` with no matcher, so it sees every tool call.
- **What it reads.** Copilot's tools are `bash`, `powershell`, `view`, `edit`, `create`, `glob`, `grep`,
  `web_fetch`, `web_search`, `task`, `ask_user`, `update_todo`, `str_replace_editor`, `apply_patch`, `rg`, plus MCP
  tools. GitHub does not document their argument names, so **every string argument of every tool is scanned**.
  `view` also scans the file's content. Both payload shapes are accepted: camelCase (`toolName`, with `toolArgs` as
  an object or as JSON text) and snake_case (`tool_name`, `tool_input`).
- **Only guarded projects.** As with Claude Code, the hook stays silent in a folder that has no `.pii-airlock/`.
  Run `pii-airlock init` in each project you want checked.
- **Project-scope hooks need a trusted folder.** Copilot CLI skips a repository's `.github/hooks/` until the folder is
  listed under `trustedFolders` in `~/.copilot/config.json`. The user-level hook that `init` installs
  (`~/.copilot/hooks/pii-airlock.json`) needs no trust.
- **Non-interactive runs.** `copilot -p` cannot ask, so an `ask` decision denies the call.
- **Failure modes** (from GitHub's hooks reference). A hook that errors or exits with code 2 denies the tool call, so
  detection failures fail closed. A hook **timeout is fail-open**, so keep the helper on (`hook_daemon: auto`, the
  default) to stay far below the 30 second default. The cloud agent treats `ask` as `deny` and honours only the
  `bash` command.
- **One install is enough.** Copilot CLI also reads a repository's `.claude/settings.json`. If you registered the
  Claude Code hook there by hand (`install-hook --scope project`), do not add the Copilot file as well, or every call is
  scanned twice. `init` writes neither.
- **Reply format.** One JSON object carries both Copilot's top-level `permissionDecision` and Claude Code's nested
  `hookSpecificOutput`. Each side reads its own part.

## Honest status

The Claude Code hook is tested end to end. The Copilot hook was checked against live Copilot CLI sessions
(version 1.0.114, November 2026, non-interactive `copilot -p`, user-level hook):

| Checked live | Result |
| --- | --- |
| `~/.copilot/hooks/pii-airlock.json` is loaded | yes |
| A top-level `permissionDecision` with exit code 0 stops the call | yes |
| `bash`, `view`, `create`, `edit`, `grep` calls carrying personal data | stopped |
| Clean `bash`, `view`, `create`, `glob` calls | run untouched |

Not yet checked live: the interactive `ask` dialog, a trusted project-scope hook, the timeout and exit-code-2
paths, the cloud agent, and Copilot in VS Code. Those still rest on GitHub's and VS Code's published specifications.
If a tool call slips through, please [open an issue](https://github.com/matinfo-tech/pii-airlock/issues/new/choose)
with the hook payload.
