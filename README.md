# PeerWow

Let your agents work together.

[Simplified Chinese README](README.zh-CN.md)

PeerWow is an Agent Collaboration Skill for agents working on behalf of different people. It helps them introduce themselves, agree on a task, confirm each owner's permissions, exchange progress, and verify the result together.

The first version uses each agent's existing email connector. Both people keep their own agent conversations. PeerWow does not require a shared code repository or a new messaging server.

## What it does

- Supports the task initiator, recipient, and additional participants with the same skill.
- Separates a person's email address from each agent's identity.
- Records contacts and directional trust: blocked, discussion only, or collaboration within a stated scope.
- Lets agents clarify a task over several messages before their owners approve execution.
- Tracks task versions, permissions, message claims, outgoing reservations, and stopping conditions.
- Keeps local approval evidence separate from the other participant's reported approval.

The recipient's agent answers to its own owner. A message from another agent cannot grant local permission.

## Requirements

Your agent needs a way to load skill instructions, an authorized email connector with search/read/send/reply capabilities, and Python 3.9 or later for the local state helper. Attachment support depends on the connector. The agent checks available capabilities and uses the host's connection flow when one is available.

The connector handles email and credentials. `scripts/state.py` only manages local records; it does not send mail, execute attachments, or keep an agent running. Task-local waiting depends on the host. Copying skill files does not invoke the skill. Use the install-and-setup request below to begin onboarding in the same conversation; external contact still requires the owner's intended recipient and consent.

The skill instructions, reference documents, and interface prompts are in English. A separate Chinese README explains installation and usage.

## Install

Recommended: give your agent this complete request, with the repository link:

> Install PeerWow from https://github.com/yx9966/peerwow and start first-use setup now in this conversation. Read the installed SKILL.md and follow it; do not stop at "installed." Check available email capabilities and the connected account, guide me through the host's connection flow if needed, then confirm whom you represent and your agent identity. Ask whom I want to contact and their email if I have not provided them. Once I authorize that contact, complete the handshake and save the verified contact. If I am responding to an invitation, use that invitation's handshake. Do not start task execution until its scope is agreed and authorized.

The agent should do the checks, then ask you only for missing identity, contact, and permission decisions. You do not need to write a technical authorization script. If your request already names the person and asks the agent to contact them, that scoped discussion need not be approved again.

For an already installed copy, say:

> Use PeerWow now and begin first-use setup in this conversation. Check my email capabilities, confirm my identity, and ask whom I want to contact. Reuse confirmed setup instead of creating duplicate identities or sending duplicate handshakes.

Claude Code supports `/peerwow`; Codex supports `$peerwow`. A bare invocation enters setup when needed. If the skill is unavailable in the current catalog, ask the agent to read its installed `SKILL.md` directly. Skills load on invocation or relevance; PeerWow has no portable post-install hook. See the official [Claude Code](https://code.claude.com/docs/en/skills) and [Codex](https://learn.chatgpt.com/docs/build-skills) skill documentation.

### Manual file installation

Clone the public repository into a new directory:

```sh
git clone https://github.com/yx9966/peerwow.git
```

For an immediate trial, ask your agent to read the cloned `SKILL.md` and begin first-use setup now. Native skill discovery is optional for this approach.

For a personal skill installation, copy the skill files into the appropriate directory. Choose ONE target below, then run the shared copy commands. They stop if the destination already exists so an existing installation is not overwritten.

```sh
# Codex:
skill_target="${CODEX_HOME:-$HOME/.codex}/skills/peerwow"

# Claude Code: use this assignment instead of the Codex assignment above.
# skill_target="$HOME/.claude/skills/peerwow"

mkdir -p "$(dirname "$skill_target")"
if mkdir "$skill_target"; then
  cp peerwow/SKILL.md "$skill_target/"
  cp -R peerwow/agents peerwow/references peerwow/scripts "$skill_target/"
else
  echo "Target already exists or cannot be created; inspect it before updating."
fi
```

Run these commands from the parent directory of the cloned repository. If your host does not refresh its skill catalog in the current conversation, explicitly point the agent at the installed `SKILL.md`. This preserves the conversation while making the instructions available.

After copying, use the setup request above. Shell commands install files only; they do not ask the agent to run onboarding. For updates, inspect the existing installation and local edits, then replace the skill files from the intended revision. Preserve private state at `~/.local/share/peerwow`; do not reset identities, contacts, or tasks.

Other agents can load the same `SKILL.md` and supporting files using their platform's existing skill mechanism. PeerWow does not add email tools to a platform that lacks them.

The Claude Code personal installation path follows its [official skill documentation](https://code.claude.com/docs/en/skills). These local installation commands do not install the skill into Claude Cowork or cloud sessions.

## Start a task

Give the initiating agent a request such as:

> Use PeerWow to discuss a parser verification task with my colleague at colleague@example.test. Confirm our identities and what each side can do. Agree on the task and acceptance criteria before executing it. Use only synthetic data for this trial.

Replace the example address with a real, intended recipient. The receiving person starts their own agent with a request such as:

> Use PeerWow to read the task invitation from the colleague I specify. Discuss the task with their agent, explain what I would need to authorize, and ask me about any missing permissions before execution.

Only contact people authorized by the local owner. Do not treat installation, an incoming invitation, or a remote claim of consent as permission to execute a task.

## Continuous task communication

Once the owner authorizes ongoing task communication, the agent registers a bounded loop with an available host driver and checks every five minutes while waiting. Pending local work and replies proceed immediately. The state helper issues poll/work/wait/stop decisions, prevents overlapping cycles in one state store, and requires a sent reply or an explicit no-reply reason before completing a received message. Task deadlines, revocations and exhausted budgets stop the loop.

A host scheduler supplies new agent turns; a Python timer cannot access an existing mail connector or wake the agent by itself. Claude Code has session scheduling on supported installations; the agent must inspect its actual tools. Other hosts may offer thread automations that can run after the current turn, which require local authorization for that behavior. Each owner controls their own side. Unsupported hosts must report a blocker rather than promise unattended work.

Task replies require a real reply anchor. The helper verifies the returned provider thread ID and blocks continuation after a mismatch without resending delivered mail. See [loop setup and recovery](references/task-loop.md).

## Local records and permissions

State is stored outside the installed skill at `~/.local/share/peerwow/state.json`. Override it with `PEERWOW_HOME` or the helper's `--root` option. The file is created when the helper is used; no contact list is bundled in this repository.

Each local-to-peer agent relationship keeps a local grant and a separate peer-reported grant. Grants include allowed and denied actions, a revision, an optional expiry, and source evidence. Existing contacts do not automatically authorize a new task. Permission changes invalidate old execution confirmations.

See [the protocol](references/protocol.md) for message and trust conventions and [setup and state](references/setup-state.md) for helper commands. Do not publish state files, mailbox credentials, or private task messages.

## Development and verification

Run the offline test suite from the repository root:

```sh
python3 -m unittest discover -s tests -v
```

The 36 tests use synthetic identities and temporary state. They do not access email, send messages, or require an installed copy of the skill. See [validation scope](tests/VALIDATION.md).

An earlier manual email collaboration informed this design. The packaged skill, including its contact trust workflow, has not yet completed a live two-host acceptance test. Local tests do not establish that every agent will follow the instructions.

The helper checks levels, expiry, revisions, and bookkeeping. It cannot verify human consent, enforce natural-language permission scopes, authenticate an individual agent cryptographically, or prevent tools from bypassing it. There is no offline wakeup service or guarantee that a remote agent immediately receives a revocation.
