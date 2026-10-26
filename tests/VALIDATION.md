# PeerWow local validation

Skill entry point: `SKILL.md`. Offline tests: `tests/test_peerwow.py`.

## Completed checks

- The skill includes interface metadata, two reference documents, and one Python standard-library state helper. Instructions, metadata, examples, and validation notes are in English; the Chinese README is separate.
- The skill-creator validator passes. No scaffold placeholders, real email addresses, prior contacts, task records, credentials, or test caches are bundled in the skill archive.
- `python3 -m unittest discover -s tests -v`: 27 local tests pass.
- The skill ZIP contains five files. CRC verification passes, and extracted bytes match the installed source. The companion SHA256 checks copy integrity; it is not an independent publisher signature.

## Test coverage

1. Distinct local and peer agent identities sharing one mailbox.
2. A pending handshake, matching mailbox, and echoed identifier are required to save a contact.
3. Participants without a handshake cannot join a task record.
4. Discussion cannot reserve WORK/RESULT; READY requires local execution authorization.
5. Local READY may precede peer READY; execution requires matching READY from every required participant.
6. Contract changes require a higher revision; old authorization and READY cannot authorize a new revision.
7. Wrong sender mailbox, agent, recipients, revision, or message kind cannot claim work.
8. Logical messages are deduplicated across email threads; completion requires the original claim token.
9. The same message ID with different content is rejected.
10. Uncertain sends block new reservations; only a confirmed non-send releases a reservation.
11. Outgoing budgets survive checkpoint updates.
12. Closure or expiry prevents new actions while allowing reconciliation of previous sends.
13. State persists with 0600 permissions; a busy lock or failed mutation does not overwrite the file.
14. Two local processes claiming simultaneously grant execution rights only once.
15. Both roles complete a synthetic flow: handshake, authorization, READY, work/result messages, deduplication, and closure. No actual email is sent.
16. New contacts and legacy records default to discussion only; another agent sharing the address does not inherit grants.
17. Peer reports cannot change local grants; peer trust updates require the expected source mailbox.
18. Trust revisions cannot roll back or replay; repeated handshakes preserve revocation.
19. Revocation and expiry block new work while permitting bookkeeping. Scope updates invalidate old READY; each side acknowledges revisions from its own perspective.

## Workflow review

Setup discovers email tools and account access instead of asking users to identify tool capabilities. Missing connections use actual platform entry points, with human sign-in followed by another check. Missing interfaces are disclosed; no links are invented. Confirm the sending address and agent identity on first use; ask users to choose between accounts only when needed.

Initiators and recipients need their own owners' discussion authorization. They may clarify the task over multiple rounds. Task and permission approval can be combined, and clear existing authorization is reused. Only additional scope needs additional approval; host-enforced prompts cannot be bypassed.

Contacts live outside the skill installation. A historical contact is not permission to execute a new task. Task-local waiting does not create a persistent service, cross-session automation, or offline wakeup. Retrospectives and thanks do not reopen a closed task.

## Verification limits

The round-two invitation was sent using the packaged skill; the bilateral handshake and live two-host acceptance have not been confirmed. The owner reported that two installing agents stopped after installation without entering identity setup or a handshake. This exposed a missing installation-to-setup transition. The entry point, install-and-setup prompts, and bare invocation now route to explicit first-use setup. This change has not yet been verified in those two remote sessions.

Offline tests do not access connectors, create real identities/contacts, or send mail. They establish helper behavior, not guaranteed model compliance. Instructions avoid Codex-specific tool names, but the destination platform must provide email access and task-local waiting. The helper requires Python 3.9 or later; missing dependencies are reported rather than installed automatically.

For the next owner-authorized installation check, observe both initiator and recipient behavior: install-and-setup should reach capability inspection and missing identity/contact questions in the current conversation; a disconnected account should reach a real connection entry point or a specific blocker; an invitation recipient should reply to the existing handshake after local consent; repeated invocation should preserve the same agent identity and avoid duplicate mail. Installation-only must not send mail. A second agent sharing a mailbox must use its own identity. Record actual outcomes rather than marking these scenarios passed from a document review.

The helper cannot authenticate human approval, sandbox tool use, or prevent bypassing its checks. Deduplication and locks cover instances sharing one state directory, not independent cross-host copies. It does not promise exactly-once execution across those copies.

Scopes are reviewable text. The helper checks levels, expiry, and revisions, but does not decide whether a command fits a path/data boundary. Peer grants are sourced reports, not independently verified approvals. Email handshakes do not cryptographically authenticate an individual agent. Offline peers cannot receive revocations immediately. No real contacts have been granted permissions by these tests.

The second live collaboration was separately authorized by the owner. These documentation changes and offline checks do not add participants, extend task budgets, resume earlier automation, or authorize unrelated mail.
