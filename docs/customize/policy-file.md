# The policy file and trust

For when the two commands on [Tell it what is sensitive](/customize/allow-and-deny) are not enough:
your own patterns, how setting layers combine, and what happens with a policy someone else wrote.

## The project policy file

`pii-airlock init` creates `.pii-airlock/config.yaml`. It is a plain YAML file, committed with the
project, so your team shares it. `allow`, `deny` and `action` edit it; you can also edit it by hand:

```yaml
allow_list: [Acme SA]
deny_list:
  CODENAME: [Project Phoenix]
custom_patterns:
  - {entity: CONTRACT_ID, regex: 'CT-\d{6}'}
```

`custom_patterns` hides anything that matches a regular expression. The example hides contract numbers
like `CT-123456`, under the label `CONTRACT_ID`.

The file takes any setting from the [settings reference](/reference/settings), not just lists.

## Where settings live

pii-airlock combines several layers. Later ones win:

1. Built-in defaults
2. Your personal file `~/.config/pii-airlock/config.yaml`
3. The project policy `.pii-airlock/config.yaml`
4. Command-line options

Allow lists, deny lists and custom patterns **add up** across layers. Every other setting is replaced by the later layer.

## Trusting a project you downloaded

A project's settings can *loosen* protection, for example by allowing a name. So for a repository you did not
write, pii-airlock only applies the settings that **tighten** protection until you say otherwise.

After reading `.pii-airlock/config.yaml`, accept it:

```bash
pii-airlock trust
```

Do this again after a `git pull` that changes it. `pii-airlock status` tells you what is currently being ignored.
Your own rules in `~/.config/pii-airlock/config.yaml` are always trusted.

What counts as "tightening": deny-list terms, custom patterns, `block` and `redact` actions, and the `deny`, `block`
and `closed` decisions. What counts as "loosening": `allow_list`, `hook_on_error: open`,
`entity_actions: {PERSON: allow}` and the like. A policy that `init` created, and your own `allow`, `deny` and
`action` edits, are trusted already. A teammate who clones the repo runs `pii-airlock init` too: the shared file then
applies, but only the tightening part, until they review it and run `pii-airlock trust`.
