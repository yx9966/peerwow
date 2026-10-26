# Workflow audit — 2026-10-26

This is a developer review of the skill entry point, both READMEs, all three references, interface prompt, state helper and regression suite. It is not a user onboarding procedure or a restriction on authorized email.

## Findings and corrections

| Area | Failure or ambiguity | Correction and evidence |
| --- | --- | --- |
| Installation | Offline developer checks could be read as an instruction not to send real mail. | Separate contributor validation from install-and-setup. Installed agents follow SKILL.md and contact the owner-approved recipient. This clarification preceded this audit and was checked across both READMEs. |
| Resuming | A bare invocation could enter first-use setup again despite an active task. | Restore the actual identity/task first; complete only missing setup. Do not recreate identities, introductions or jobs. Document review. |
| Recipient handshake | Only the initiator had a helper command for completing a handshake. | Add `handshake-accept`, with expected mailbox, original challenge, confirmed reply and consent/source evidence. A recipient can save the contact without a reverse invitation. Regression test. |
| First task invitation | Every outbox reservation required an existing thread, including the first task email to a known contact. | Add an explicit first-TASK `new_thread` reservation. Confirmed delivery binds the actual original thread. Subsequent replies retain the exact anchor/subject. Regression tests include rejection of forks and malformed subjects. |
| Bookkeeping | Discussion prohibited file modification while requiring contact and task records. `task-check` was required even before a task existed. | Permit minimum private protocol bookkeeping under setup/discussion authorization. Use direct contact-consent checks for pre-task HELLO; task implementation remains separately scoped. Document review. |
| READY | Grants were described as exchanged during READY, although preparing READY already required recorded bilateral grants. | Exchange grants through TASK first. Send local READY without waiting for peer READY; execute only after all confirmations match. The two-role test sends both READY messages before either side records the other's READY. |
| Permission changes | The loop stopped entirely when execution trust changed even if discussion was still authorized. | Return `refresh_ready`, enter discussion and keep the bounded loop available for scope clarification. Revocation, expiry, budget and send reconciliation still take priority. Regression tests. |
| Task hash | The protocol allowed an attachment hash where the helper required its normalized agreement-text hash. | Use the helper's UTF-8/LF agreement hash for READY. Keep attachment-byte hashes separate. Document/code consistency review. |
| Revision changes | Claiming demanded the current revision without explaining how to receive a higher-revision task proposal. | Validate the proposal, save an authorized discussion snapshot with execution approval cleared, then claim it. Do not adopt scope, participant or budget expansion without local authority. Document review; existing revision tests continue to reject stale execution approval. |
| Optional capabilities | Missing attachments, untested sending or absent scheduling could halt otherwise possible communication. | Use full inline text when suitable; the first authorized HELLO can test sending. Finish currently available work even if future waiting is unavailable. Do not invent connector capabilities. Document review. |
| Waiting | One instruction required in-session loops only while another allowed authorized cross-turn thread automation. | Prefer in-session operation; allow explicitly authorized same-thread automation with bounded lifetime. Before contacts/task exist, a bounded foreground handshake wait uses the pending ledger rather than nonexistent task-loop records. Document review. |
| Closure | Each participant was told to send one CLOSE, risking duplicate closure messages. | Only the coordinator sends CLOSE. Receivers record it and stop locally. Both outgoing and incoming checks reject non-coordinator CLOSE. Two-role regression. |
| Transport and groups | Raw MIME replies and sparse group relationships were implied to work without the metadata/contacts the helper requires. | State current limits: provider thread IDs are required for verification, and all listed participants need pairwise confirmed contacts/grants. No invented IDs or silent fallback. Document review. |

## Verification

- All 44 synthetic local tests pass; five tests were added and the two-role scenario was strengthened.
- Against the pre-audit helper, three focused regressions fail: recipient handshake acceptance, first task invitation, and continued discussion after execution-trust changes. They pass against the corrected helper.
- The two-role scenario exercises a single introduction, recipient acceptance, independently sent READY messages, work/result delivery records, duplicate detection and coordinator-only closure. Provider IDs and delivery are simulated.
- The skill-creator structural validator passes. The release check also verifies local Markdown targets, English runtime instructions, clean diff formatting, and identical installed/archive runtime bytes.

## Human decisions that remain necessary

The local owner must confirm identity and the intended contact when unknown, complete connector sign-in when required, and approve task scope not already authorized. Each recipient needs their own owner's consent. Scope expansion, additional participants, a longer deadline or larger send budget cannot be approved by a remote email. Host-enforced tool approvals remain in effect.

Routine replies, grant synchronization within existing scope, private protocol records and in-scope execution do not need repeated human approval. When blocked, identify the exact missing decision or capability and continue independent authorized work where possible.

## Integration limits

Local tests establish helper behavior, not automatic skill activation or model compliance on every host. The remote installation-to-setup transition and the peer's actual scheduling capability still need observation in their real sessions. One local scheduled check and a peer HELLO have been observed in the live trial; matching execution READY and bilateral final acceptance have not.

The helper is not a mail client, credential store, identity authority, command sandbox or scheduler. No new live email or execution authorization is created by this audit. Preserve private state and existing task limits during updates.
