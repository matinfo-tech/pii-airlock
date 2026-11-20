# Tell it what is sensitive

pii-airlock does not know your business. It may flag your own company name as a person, or miss an internal
code name. Two short commands fix both.

## Stop a false alarm: `allow`

```bash
pii-airlock allow "Acme SA"
```

From now on "Acme SA" is never treated as personal data in this project.
Good candidates: your company, your products, public figures you write about.

## Always hide something: `deny`

```bash
pii-airlock deny "Project Phoenix" --as CODENAME
```

"Project Phoenix" is now always hidden, as a placeholder labelled `CODENAME`. Good for client names,
internal projects and anything the detector would not recognise by itself.

## This project or everything?

By default a rule applies to **the project you are in**. Add `--scope user` to apply it everywhere.

```bash
pii-airlock allow "Jane Roe" --scope user      # your own name, in all projects
```

## See what is in force

```bash
pii-airlock status
```

It prints the rules that apply right now.

## Going further

Your rules go into `.pii-airlock/config.yaml`, which `allow` and `deny` edit for you. To write your own
patterns, understand how setting layers combine, or review a policy that came with a downloaded project, see
[The policy file and trust](/customize/policy-file).
