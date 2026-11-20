---
layout: home
hero:
  name: pii-airlock
  text: Use AI without sharing real personal data
  tagline: Names, emails, phone numbers and passwords are swapped for placeholders before your text leaves your computer, then put back in the answer.
  image:
    src: /logo.svg
    alt: pii-airlock
  actions:
    - theme: brand
      text: I use Claude Code or Copilot
      link: /guide/quick-start
    - theme: brand
      text: I use another AI app or SDK
      link: /guide/quick-start-gateway
    - theme: alt
      text: I want to clean a file
      link: /use/files-and-text
    - theme: alt
      text: What is it?
      link: /guide/what-is-it
features:
  - icon:
      src: /icons/shield-lock.svg
      alt: ''
      width: 28
      height: 28
    title: Stays on your computer
    details: Detection runs locally. The AI provider only ever sees placeholders such as <code>&lt;PERSON_482913&gt;</code>.
  - icon:
      src: /icons/restore.svg
      alt: ''
      width: 28
      height: 28
    title: Reversible
    details: The answer comes back with your real names and emails in place, so you read it as usual.
  - icon:
      src: /icons/plug.svg
      alt: ''
      width: 28
      height: 28
    title: Works with your tools
    details: Claude Code, GitHub Copilot, Cursor, Codex, Aider, Continue and anything that lets you set a base URL.
  - icon:
      src: /icons/sliders.svg
      alt: ''
      width: 28
      height: 28
    title: You decide what counts
    details: Tell it which words are never sensitive (your company) or always sensitive (a code name), in one command.
---

## See it in one picture

```text
You write:            Email John Smith (john@acme.com) about the invoice.
The AI receives:      Email <PERSON_482913> (<EMAIL_ADDRESS_093117>) about the invoice.
The AI answers:       Dear <PERSON_482913>, regarding the invoice…
You read:             Dear John Smith, regarding the invoice…
```

<p align="center">
  <img src="/demo.gif"
       alt="Terminal demo: pii-airlock scrubs a name and an email from a prompt, then restores them in the reply"
       width="760" loading="lazy">
</p>

## Which tool do you use?

<SetupPicker />

::: tip New here?
Read [What is pii-airlock?](/guide/what-is-it), then [pick your setup](/use/pick-your-setup) and follow its
quick start. You do not need to know Python. You do need to be comfortable pasting a few commands into a terminal.
:::
