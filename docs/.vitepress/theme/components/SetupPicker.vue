<script setup lang="ts">
import { ref } from 'vue'

type Tool = {
  id: string
  label: string
  intro: string
  code?: string
  lang?: string
  link: string
  linkText: string
}

const tools: Tool[] = [
  {
    id: 'claude-code',
    label: 'Claude Code',
    intro: 'Hooks guard prompts and tool calls. One command in your project:',
    code: 'cd my-project\npii-airlock init',
    lang: 'bash',
    link: '/use/claude-code',
    linkText: 'Claude Code in depth',
  },
  {
    id: 'copilot',
    label: 'GitHub Copilot',
    intro: 'The hook guards Copilot’s tool calls. Same command:',
    code: 'cd my-project\npii-airlock init',
    lang: 'bash',
    link: '/use/copilot',
    linkText: 'Copilot in depth (chat needs the gateway)',
  },
  {
    id: 'codex',
    label: 'Codex / OpenAI SDK',
    intro: 'Point the tool at the gateway, in the terminal you start it from:',
    code: 'pii-airlock proxy   # keep running\nexport OPENAI_BASE_URL=http://127.0.0.1:8745/openai',
    lang: 'bash',
    link: '/use/gateway',
    linkText: 'All gateway tools',
  },
  {
    id: 'anthropic',
    label: 'Anthropic SDK',
    intro: 'Same idea, Anthropic route:',
    code: 'pii-airlock proxy\nexport ANTHROPIC_BASE_URL=http://127.0.0.1:8745/anthropic',
    lang: 'bash',
    link: '/use/gateway',
    linkText: 'All gateway tools',
  },
  {
    id: 'cursor',
    label: 'Cursor',
    intro: 'Settings → Models → Override OpenAI Base URL:',
    code: 'http://127.0.0.1:8745/openai',
    lang: 'text',
    link: '/use/gateway#cursor',
    linkText: 'Cursor details',
  },
  {
    id: 'file',
    label: 'A file or text',
    intro: 'Clean it by hand, paste anywhere, restore the answer:',
    code: 'pii-airlock scrub notes.txt -o notes.clean.txt\npii-airlock restore answer.txt',
    lang: 'bash',
    link: '/use/files-and-text',
    linkText: 'Clean a file or some text',
  },
]

const active = ref(tools[0])
</script>

<template>
  <div class="setup-picker">
    <div class="picker-tabs" role="tablist" aria-label="Pick your tool">
      <button
        v-for="t in tools"
        :key="t.id"
        role="tab"
        :aria-selected="active.id === t.id"
        :class="{ active: active.id === t.id }"
        @click="active = t"
      >
        {{ t.label }}
      </button>
    </div>
    <div class="picker-panel" role="tabpanel">
      <p>{{ active.intro }}</p>
      <pre v-if="active.code"><code>{{ active.code }}</code></pre>
      <p class="picker-link">
        <a :href="active.link">{{ active.linkText }} →</a>
      </p>
    </div>
  </div>
</template>

<style scoped>
.setup-picker {
  margin: 24px 0;
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  overflow: hidden;
}
.picker-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 10px 12px;
  background: var(--vp-c-bg-soft);
  border-bottom: 1px solid var(--vp-c-divider);
}
.picker-tabs button {
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 0.88em;
  font-weight: 500;
  color: var(--vp-c-text-2);
  transition: all 0.2s;
}
.picker-tabs button:hover {
  color: var(--vp-c-brand-1);
}
.picker-tabs button.active {
  background: var(--vp-c-brand-1);
  color: #fff;
}
.picker-panel {
  padding: 16px 20px;
}
.picker-panel p {
  margin: 0 0 10px;
}
.picker-panel pre {
  margin: 0 0 10px;
  padding: 14px 16px;
  border-radius: 8px;
  background: var(--vp-code-block-bg);
  overflow-x: auto;
}
.picker-panel code {
  font-family: var(--vp-font-family-mono);
  font-size: 0.86em;
  line-height: 1.6;
  color: var(--vp-code-color, var(--vp-c-text-1));
}
.picker-link {
  font-size: 0.92em;
}
.picker-link a {
  color: var(--vp-c-brand-1);
  font-weight: 500;
  text-decoration: none;
}
.picker-link a:hover {
  text-decoration: underline;
}
</style>
