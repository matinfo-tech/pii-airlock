# Pick your setup

Find the tool you use in the table, then follow its quick start. Each "In depth" page has the details.

| I use… | Start with | In depth |
|---|---|---|
| **Claude Code** (terminal, desktop or IDE) | [Quick start](/guide/quick-start) — hooks, plus the gateway if you want tool output covered | [Claude Code](/use/claude-code) |
| **GitHub Copilot** CLI or agent mode | [Quick start](/guide/quick-start) — hook | [GitHub Copilot](/use/copilot) |
| **Copilot Chat** in VS Code with my own API key | [Gateway quick start](/guide/quick-start-gateway) | [GitHub Copilot](/use/copilot#chat-in-vs-code) |
| **Cursor**, **Continue**, **Aider**, **Codex CLI** | [Gateway quick start](/guide/quick-start-gateway) | [Other AI apps and SDKs](/use/gateway) |
| My own script using the **OpenAI**, **Anthropic** or **Gemini** SDK | [Gateway quick start](/guide/quick-start-gateway) | [Other AI apps and SDKs](/use/gateway) |
| A **file or some text** I want to clean by hand | [Clean a file or some text](/use/files-and-text) | |
| **ChatGPT.com**, **claude.ai** or other websites and phone apps | Not supported | See below |

## Why websites and phone apps are not covered

pii-airlock works by changing where a program sends its requests. Websites and mobile apps give you no
setting for that. For those, use [Clean a file or some text](/use/files-and-text) before you paste.

## Gateway or hooks: which one?

**Gateway** means your tool talks to a local address, and pii-airlock swaps placeholders in and out automatically.
Nothing to approve, nothing interrupts you. It works with any tool that lets you set a "base URL".

**Hooks** are checkpoints inside Claude Code and Copilot. When something personal is about to be sent,
they stop and tell you, and you decide. They do not rewrite anything.

If you use Claude Code a lot, many people use hooks as the everyday safety net. The gateway is the better pick
when you want everything handled silently, or when the tool has no hook system.

## One thing to know before you start

None of these setups makes detection perfect. Read [Safety and limits](/guide/safety) once.
