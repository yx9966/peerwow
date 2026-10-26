"""Offline checks. Synthetic identities only; never access a mailbox or live state."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('peerwow_state', SKILL / 'scripts/state.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class StateTests(unittest.TestCase):
    def setUp(self):
        self.now = int(time.time())
        self.s = dict(version=1, agents={}, contacts={}, handshakes={}, tasks={})
        self.a = self.call('identity-add', owner='Test Owner', name='Dev', email='owner@example.test')['agent_id']
        self.peer = 'ag-peer'
        self.contact(self.peer)
        self.t = dict(agent_id=self.a, task_id='MC-test', phase='discuss', revision=1,
                      participants=[self.a, self.peer], coordinator=self.a,
                      agreement='Synthetic task: discuss then test data only.',
                      discussion_evidence='Synthetic user fixture consent', deadline=self.now + 600,
                      max_outgoing=3, checkpoint='Discussing')
        self.call('task-put', **self.t)
        self.call('task-thread', agent_id=self.a, task_id='MC-test', thread_id='fixture-thread',
                  reply_message_id='fixture-root', evidence='Synthetic provider metadata')

    def call(self, action, **data):
        if action == 'outbox-resolve' and data.get('outcome') == 'sent':
            data.setdefault('thread_id', 'fixture-thread')
        return m.apply(self.s, action, data, self.now)

    def contact(self, peer, address='peer@example.test'):
        h = self.call('handshake-start', agent_id=self.a, owner='Peer Owner', email=address, nickname='Peer')
        contact = self.call('handshake-finish', agent_id=self.a, handshake_id=h['handshake_id'],
                         echo=h['handshake_id'], reply_from=address, peer_agent_id=peer,
                         peer_name='Peer Agent', mail_id='synthetic-hello')
        self.grants(self.a, peer, address)
        return contact

    def grants(self, local, peer, address):
        for side in ('local', 'peer'):
            self.call('contact-trust', agent_id=local, peer_agent_id=peer, side=side,
                      revision=1, level='scoped', allowed=['Synthetic tests only'], denied=['Business data'],
                      expires_at=None, evidence='Synthetic fixture grant', from_email=address, mail_id='fixture-trust')

    def auth(self, t=None):
        t = t or self.t
        ah = m.agreement_hash(t['agreement'])
        return dict(revision=t['revision'], agreement_sha256=ah, local_evidence='Synthetic local user grant',
                    trust={p: dict(local=1, peer=1) for p in t['participants'] if p != self.a},
                    local_scope='Synthetic tests only', peer_ready={p: dict(revision=t['revision'], agreement_sha256=ah,
                    mail_id='synthetic-ready', scope='Synthetic tests only', trust=dict(local=1, peer=1)) for p in t['participants'] if p != self.a})

    def execute(self):
        self.t.update(phase='execute', authorization=self.auth())
        self.call('task-put', **self.t)

    def outgoing(self, kind='TASK'):
        return self.call('outbox-prepare', agent_id=self.a, task_id='MC-test', kind=kind,
                         to_agents=[self.peer], body='Synthetic message')

    def incoming(self, **changes):
        data = dict(agent_id=self.a, task_id='MC-test', message_id='msg-synthetic', mail_id='provider-1',
                    from_agent=self.peer, from_email='peer@example.test', to_agents=[self.a],
                    revision=1, kind='TASK', body='Synthetic reply')
        data.update(changes)
        return data

    def test_one_mailbox_multiple_distinct_agents(self):
        other = self.call('identity-add', owner='Test Owner', name='Reviewer', email='owner@example.test')
        self.assertNotEqual(other['agent_id'], self.a)
        self.contact('ag-peer-2')
        self.assertEqual(len(self.s['contacts']), 2)

    def test_contacts_require_matching_pending_handshake(self):
        h = self.call('handshake-start', agent_id=self.a, owner='Someone', email='other@example.test')
        original = copy.deepcopy(self.s)
        for echo, sender in [('wrong', 'other@example.test'), (h['handshake_id'], 'intruder@example.test')]:
            with self.assertRaises(ValueError):
                self.call('handshake-finish', agent_id=self.a, handshake_id=h['handshake_id'], echo=echo,
                          reply_from=sender, peer_agent_id='ag-new', peer_name='Other', mail_id='fixture')
            self.assertEqual(self.s, original)

    def test_unknown_participants_rejected(self):
        t = {**self.t, 'participants': [self.a, 'ag-unknown'], 'revision': 2}
        with self.assertRaisesRegex(ValueError, 'handshake'):
            self.call('task-put', **t)

    def test_discussion_does_not_authorize_execution_or_ready(self):
        for kind in ['WORK', 'RESULT', 'READY']:
            with self.assertRaises(ValueError):
                self.outgoing(kind)
        self.outgoing('TASK')

    def test_local_ready_before_peer_ready(self):
        auth = self.auth()
        auth['peer_ready'] = {}
        self.call('task-put', **{**self.t, 'authorization': auth})
        self.outgoing('READY')
        with self.assertRaisesRegex(ValueError, 'peer READY'):
            self.call('task-put', **{**self.t, 'phase': 'execute', 'authorization': auth})

    def test_matching_all_party_ready_required(self):
        self.contact('ag-peer-2')
        t = {**self.t, 'participants': [self.a, self.peer, 'ag-peer-2'], 'revision': 2, 'phase': 'execute'}
        auth = self.auth(t)
        auth['peer_ready']['ag-peer-2']['agreement_sha256'] = 'wrong'
        with self.assertRaises(ValueError):
            self.call('task-put', **{**t, 'authorization': auth})
        self.call('task-put', **{**t, 'authorization': self.auth(t)})

    def test_new_revision_cannot_reuse_old_authorization(self):
        self.execute()
        changed = {**self.t, 'agreement': 'Expanded work'}
        with self.assertRaisesRegex(ValueError, 'new revision'):
            self.call('task-put', **changed)
        changed['revision'] = 2
        with self.assertRaisesRegex(ValueError, 'local execution'):
            self.call('task-put', **changed)

    def test_wrong_agent_or_mailbox_cannot_claim(self):
        for change in [dict(from_email='intruder@example.test'), dict(to_agents=[self.peer]),
                       dict(from_agent='ag-unknown'), dict(revision=0), dict(revision=True), dict(kind='EXEC')]:
            with self.assertRaises(ValueError):
                self.call('inbox-claim', **self.incoming(**change))

    def test_cross_thread_duplicate_and_claim_completion(self):
        first = self.call('inbox-claim', **self.incoming())
        second = self.call('inbox-claim', **self.incoming(mail_id='different-provider-thread-copy'))
        self.assertFalse(first['duplicate'])
        self.assertTrue(second['duplicate'])
        self.assertNotIn('claim', second)
        with self.assertRaises(ValueError):
            self.call('inbox-done', agent_id=self.a, task_id='MC-test', message_id='msg-synthetic', claim='wrong')
        self.call('inbox-done', agent_id=self.a, task_id='MC-test', message_id='msg-synthetic', claim=first['claim'])
        self.assertEqual(self.call('inbox-claim', **self.incoming())['status'], 'done')

    def test_same_id_changed_body_rejected(self):
        self.call('inbox-claim', **self.incoming())
        with self.assertRaisesRegex(ValueError, 'different content'):
            self.call('inbox-claim', **self.incoming(body='Changed instruction'))

    def test_unknown_send_blocks_retry_and_reserves_budget(self):
        first = self.outgoing()
        with self.assertRaisesRegex(ValueError, 'Reconcile'):
            self.outgoing()
        with self.assertRaises(ValueError):
            self.call('outbox-resolve', agent_id=self.a, task_id='MC-test', message_id=first['message_id'], outcome='sent', evidence='unknown')
        self.call('outbox-resolve', agent_id=self.a, task_id='MC-test', message_id=first['message_id'],
                  outcome='sent', mail_id='sent-1', evidence='Connector confirmed')
        self.outgoing()

    def test_budget_survives_checkpoint_update(self):
        for i in range(3):
            sent = self.outgoing()
            self.call('outbox-resolve', agent_id=self.a, task_id='MC-test', message_id=sent['message_id'],
                      outcome='sent', mail_id='sent-' + str(i), evidence='Connector confirmed')
        self.call('task-put', **{**self.t, 'checkpoint': 'Updated'})
        with self.assertRaisesRegex(ValueError, 'budget'):
            self.outgoing()

    def test_definite_pre_send_failure_can_cancel(self):
        sent = self.outgoing()
        self.call('outbox-resolve', agent_id=self.a, task_id='MC-test', message_id=sent['message_id'],
                  outcome='not_sent', evidence='Tool rejected arguments before sending')
        self.outgoing()

    def test_close_and_expiry_prevent_new_actions_but_allow_reconciliation(self):
        sent = self.outgoing()
        self.call('task-put', **{**self.t, 'phase': 'closed'})
        with self.assertRaisesRegex(ValueError, 'closed'):
            self.outgoing()
        with self.assertRaisesRegex(ValueError, 'reopened'):
            self.call('task-put', **self.t)
        self.call('outbox-resolve', agent_id=self.a, task_id='MC-test', message_id=sent['message_id'],
                  outcome='sent', mail_id='sent-1', evidence='Delivery confirmed later')

    def test_expiry_does_not_auto_extend(self):
        self.now = self.t['deadline']
        with self.assertRaisesRegex(ValueError, 'expired'):
            self.outgoing()

    def cli(self, root, action, data):
        return subprocess.run([sys.executable, str(SKILL / 'scripts/state.py'), action, '--root', str(root)],
                              input=json.dumps(data), text=True, capture_output=True)

    def test_persist_restart_permissions_and_busy_lock(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)
            result = self.cli(root, 'identity-add', dict(owner='Fixture', name='Agent', email='fixture@example.test'))
            self.assertEqual(result.returncode, 0, result.stderr)
            identity = json.loads(result.stdout)
            fresh = self.cli(root, 'show', {})
            self.assertIn(identity['agent_id'], json.loads(fresh.stdout)['agents'])
            self.assertEqual((p / 'state.json').stat().st_mode & 0o777, 0o600)
            (p / '.lock').write_text('0')
            before = (p / 'state.json').read_bytes()
            busy = self.cli(root, 'identity-add', dict(owner='Other', name='Other', email='other@example.test'))
            self.assertNotEqual(busy.returncode, 0)
            self.assertEqual((p / 'state.json').read_bytes(), before)
            self.assertTrue((p / '.lock').exists())

    def test_simultaneous_claim_only_one_executor(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'state.json'
            path.write_text(json.dumps(self.s))
            path.chmod(0o600)
            args = [sys.executable, str(SKILL / 'scripts/state.py'), 'inbox-claim', '--root', root]
            children = [subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
            data = json.dumps(self.incoming())
            for child in children:
                child.stdin.write(data)
                child.stdin.close()
                child.stdin = None
            outputs = [child.communicate(timeout=5) for child in children]
            granted = [json.loads(out) for child, (out, err) in zip(children, outputs) if child.returncode == 0]
            self.assertEqual(sum(x.get('duplicate') is False for x in granted), 1)

    def test_failed_mutation_never_replaces_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'state.json'
            path.write_text(json.dumps(self.s))
            path.chmod(0o600)
            before = path.read_bytes()
            result = self.cli(root, 'task-put', {**self.t, 'phase': 'execute'})
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_bytes(), before)
            self.assertFalse((Path(root) / '.lock').exists())

    def test_two_roles_complete_synthetic_task_without_mail_tools(self):
        b = self.call('identity-add', owner='Peer Owner', name='Executor', email='peer@example.test')['agent_id']
        for local, peer, address in [(self.a, b, 'peer@example.test'), (b, self.a, 'owner@example.test')]:
            h = self.call('handshake-start', agent_id=local, owner='Fixture Owner', email=address)
            self.call('handshake-finish', agent_id=local, handshake_id=h['handshake_id'], echo=h['handshake_id'],
                      reply_from=address, peer_agent_id=peer, peer_name='Fixture', mail_id='hello-fixture')
            self.grants(local, peer, address)
        agreement = 'Shared synthetic contract; A implements, B verifies, no real mail.'
        ah = m.agreement_hash(agreement)
        tasks = {}
        for local, peer in [(self.a, b), (b, self.a)]:
            t = dict(agent_id=local, task_id='MC-two-roles', phase='execute', revision=1,
                     participants=[self.a, b], coordinator=self.a, agreement=agreement,
                     discussion_evidence='Fixture consent only', deadline=self.now + 300, max_outgoing=3,
                     authorization=dict(revision=1, agreement_sha256=ah, local_evidence='Fixture grant only',
                                        trust={peer: dict(local=1, peer=1)},
                                        local_scope='Synthetic data only', peer_ready={peer: dict(revision=1,
                                        agreement_sha256=ah, mail_id='ready-fixture', scope='Synthetic data only', trust=dict(local=1, peer=1))}))
            tasks[local] = t
            self.call('task-put', **t)
            self.call('task-thread', agent_id=local, task_id='MC-two-roles', thread_id='fixture-thread',
                      reply_message_id='fixture-root', evidence='Synthetic provider metadata')
        for local, peer, address, kind in [(self.a, b, 'owner@example.test', 'WORK'), (b, self.a, 'peer@example.test', 'RESULT')]:
            out = self.call('outbox-prepare', agent_id=local, task_id='MC-two-roles', kind=kind, to_agents=[peer], body='Synthetic payload')
            mid = out['message_id']
            self.call('outbox-resolve', agent_id=local, task_id='MC-two-roles', message_id=mid,
                      outcome='sent', mail_id='simulated-provider-' + mid, evidence='SIMULATION ONLY: no email sent')
            claim = self.call('inbox-claim', agent_id=peer, task_id='MC-two-roles', message_id=mid,
                              mail_id='simulated-inbound-' + mid, from_agent=local, from_email=address,
                              to_agents=[peer], revision=1, kind=kind, body='Synthetic payload')
            self.call('inbox-done', agent_id=peer, task_id='MC-two-roles', message_id=mid, claim=claim['claim'], summary='Synthetic receipt')
        for t in tasks.values():
            closed = self.call('task-put', **{**t, 'phase': 'closed'})
            self.assertEqual(closed['phase'], 'closed')
            self.assertEqual(len(closed['inbox']), 1)
            self.assertEqual(len(closed['outbox']), 1)

    def trust(self, side='local', **changes):
        data = dict(agent_id=self.a, peer_agent_id=self.peer, side=side, revision=2,
                    level='scoped', allowed=['Synthetic tests only'], denied=['Business data'],
                    expires_at=None, evidence='Synthetic source', from_email='peer@example.test', mail_id='trust-mail')
        data.update(changes)
        return self.call('contact-trust', **data)

    def test_default_and_legacy_trust_cannot_execute(self):
        c = self.s['contacts'][self.a + ':' + self.peer]
        c.pop('local_trust')
        c.pop('peer_trust')
        self.assertEqual(m.trust_record(c, 'local')['level'], 'discuss')
        self.outgoing('TASK')
        with self.assertRaisesRegex(ValueError, 'Scoped'):
            self.execute()

    def test_peer_grant_never_escalates_local_and_mailbox_must_match(self):
        self.trust(level='discuss')
        self.trust(side='peer')
        self.assertEqual(self.s['contacts'][self.a + ':' + self.peer]['local_trust']['level'], 'discuss')
        with self.assertRaisesRegex(ValueError, 'Scoped'):
            self.execute()
        with self.assertRaisesRegex(ValueError, 'mailbox'):
            self.trust(side='peer', revision=3, from_email='intruder@example.test')

    def test_trust_revision_cannot_replay_or_rollback(self):
        for revision in (0, 1, True):
            with self.assertRaises(ValueError):
                self.trust(revision=revision)

    def test_repeated_handshake_preserves_revoke(self):
        self.trust(level='blocked', allowed=[])
        h = self.call('handshake-start', agent_id=self.a, owner='Peer Owner', email='peer@example.test')
        c = self.call('handshake-finish', agent_id=self.a, handshake_id=h['handshake_id'],
                      echo=h['handshake_id'], reply_from='peer@example.test', peer_agent_id=self.peer,
                      peer_name='Peer', mail_id='new-hello')
        self.assertEqual(c['local_trust']['level'], 'blocked')

    def test_revoke_blocks_live_task_but_allows_reconciliation(self):
        self.execute()
        sent = self.outgoing('WORK')
        self.trust(level='blocked', allowed=[])
        for action, data in [('task-check', dict(agent_id=self.a, task_id='MC-test')),
                             ('inbox-claim', self.incoming(kind='WORK'))]:
            with self.assertRaisesRegex(ValueError, 'blocked'):
                self.call(action, **data)
        with self.assertRaisesRegex(ValueError, 'blocked'):
            self.outgoing('WORK')
        self.call('outbox-resolve', agent_id=self.a, task_id='MC-test', message_id=sent['message_id'],
                  outcome='not_sent', evidence='Fixture: not dispatched')

    def test_trust_expiry_blocks_discussion_and_execution(self):
        self.trust(expires_at=self.now + 1)
        self.now += 1
        with self.assertRaisesRegex(ValueError, 'expired'):
            self.outgoing('TASK')

    def test_scope_update_invalidates_old_ready_and_checks_direction(self):
        self.execute()
        self.trust(allowed=['Static review only'])
        with self.assertRaisesRegex(ValueError, 'Trust changed'):
            self.call('task-check', agent_id=self.a, task_id='MC-test')
        auth = self.auth()
        auth['trust'][self.peer]['local'] = 2
        with self.assertRaisesRegex(ValueError, 'peer perspective'):
            self.call('task-put', **{**self.t, 'authorization': auth})
        auth['peer_ready'][self.peer]['trust']['peer'] = 2
        self.call('task-put', **{**self.t, 'authorization': auth})
        self.call('task-check', agent_id=self.a, task_id='MC-test')

    def test_mailbox_sibling_does_not_inherit_grant(self):
        h = self.call('handshake-start', agent_id=self.a, owner='Peer Owner', email='peer@example.test')
        c = self.call('handshake-finish', agent_id=self.a, handshake_id=h['handshake_id'], echo=h['handshake_id'],
                      reply_from='peer@example.test', peer_agent_id='ag-sibling', peer_name='Sibling', mail_id='sibling-hello')
        self.assertEqual(c['local_trust']['level'], 'discuss')
        self.assertEqual(c['peer_trust']['revision'], 0)

    def loop(self, **changes):
        return self.call('loop-start', **dict(agent_id=self.a, task_id='MC-test', driver='native',
                         scheduler_id='fixture-scheduler', interval_seconds=300,
                         evidence='Synthetic owner approval', **changes))

    def tick(self):
        return self.call('loop-next', agent_id=self.a, task_id='MC-test')

    def checkpoint(self, cycle, **changes):
        data = dict(agent_id=self.a, task_id='MC-test', cycle=cycle, next_action='wait',
                    poll_complete=True, summary='Processed all pages; peer acts next')
        data.update(changes)
        return self.call('loop-checkpoint', **data)

    def test_loop_two_rounds_require_actual_sent_replies(self):
        self.loop()
        for i in range(2):
            tick = self.tick()
            self.assertEqual(tick['action'], 'poll')
            self.assertNotIn('is:unread', tick['query'])
            self.assertEqual(tick['expected_agents'], [self.peer])
            incoming = self.incoming(message_id='msg-round-' + str(i))
            claim = self.call('inbox-claim', **incoming)
            with self.assertRaisesRegex(ValueError, 'Finish received'):
                self.checkpoint(tick['cycle'])
            with self.assertRaisesRegex(ValueError, 'sent reply'):
                self.call('inbox-done', agent_id=self.a, task_id='MC-test', message_id=incoming['message_id'], claim=claim['claim'])
            sent = self.outgoing()
            self.assertEqual(sent['reply_message_id'], 'fixture-root')
            with self.assertRaisesRegex(ValueError, 'Confirmed reply'):
                self.call('inbox-done', agent_id=self.a, task_id='MC-test', message_id=incoming['message_id'],
                          claim=claim['claim'], disposition='replied', reply_message_id=sent['message_id'])
            self.call('outbox-resolve', agent_id=self.a, task_id='MC-test', message_id=sent['message_id'],
                      outcome='sent', mail_id='fixture-' + str(i), evidence='Synthetic confirmed send')
            self.call('inbox-done', agent_id=self.a, task_id='MC-test', message_id=incoming['message_id'],
                      claim=claim['claim'], disposition='replied', reply_message_id=sent['message_id'])
            self.checkpoint(tick['cycle'])
            self.assertEqual(self.tick()['action'], 'wait')
            self.now += 300
        self.assertEqual(self.tick()['action'], 'stop')  # Original deadline; no extension.

    def test_loop_no_duplicate_scheduler_or_overlapping_cycle(self):
        self.loop()
        with self.assertRaisesRegex(ValueError, 'already active'):
            self.loop()
        token = self.tick()['cycle']
        self.assertEqual(self.tick()['action'], 'busy')
        with self.assertRaisesRegex(ValueError, 'token'):
            self.checkpoint('wrong')
        self.checkpoint(token)
        self.assertEqual(self.tick()['seconds'], 60)

    def test_loop_cannot_finish_partial_poll_or_unresolved_send(self):
        self.loop()
        token = self.tick()['cycle']
        with self.assertRaisesRegex(ValueError, 'all relevant'):
            self.checkpoint(token, poll_complete=False)
        self.outgoing()
        self.assertEqual(self.tick()['action'], 'reconcile_send')
        with self.assertRaisesRegex(ValueError, 'pending send'):
            self.checkpoint(token)

    def test_loop_no_reply_requires_reason(self):
        self.loop()
        token = self.tick()['cycle']
        incoming = self.incoming()
        claim = self.call('inbox-claim', **incoming)
        data = dict(agent_id=self.a, task_id='MC-test', message_id=incoming['message_id'], claim=claim['claim'], disposition='no_reply')
        with self.assertRaisesRegex(ValueError, 'why'):
            self.call('inbox-done', **data)
        self.call('inbox-done', **data, reason='Synthetic courtesy acknowledgment; no action requested')
        self.checkpoint(token)

    def test_loop_revocation_stops_and_returns_cleanup_id(self):
        self.loop()
        self.trust(level='blocked', allowed=[])
        result = self.tick()
        self.assertEqual(result['action'], 'stop')
        self.assertEqual(result['scheduler_id'], 'fixture-scheduler')

    def test_loop_budget_exhaustion_stops(self):
        self.loop()
        for i in range(3):
            sent = self.outgoing()
            self.call('outbox-resolve', agent_id=self.a, task_id='MC-test', message_id=sent['message_id'],
                      outcome='sent', mail_id='sent-' + str(i), evidence='Synthetic send')
        self.assertEqual(self.tick()['reason'], 'Outgoing budget exhausted')

    def test_loop_local_work_is_not_delayed_until_poll(self):
        self.loop()
        token = self.tick()['cycle']
        self.checkpoint(token, next_action='work', summary='Local authorized specification drafting remains')
        self.assertEqual(self.tick()['action'], 'work')

    def test_loop_host_id_required_and_task_update_preserves_loop(self):
        with self.assertRaisesRegex(ValueError, 'scheduler ID'):
            self.call('loop-start', agent_id=self.a, task_id='MC-test', driver='native', evidence='Synthetic approval')
        self.loop()
        self.call('task-put', **{**self.t, 'checkpoint': 'Updated'})
        self.assertEqual(self.tick()['action'], 'poll')

    def test_thread_binding_required_and_mismatch_counts_as_sent(self):
        task = self.s['tasks'][self.a + ':MC-test']
        task.pop('thread')
        with self.assertRaisesRegex(ValueError, 'canonical'):
            self.outgoing()
        self.call('task-thread', agent_id=self.a, task_id='MC-test', thread_id='fixture-thread',
                  reply_message_id='fixture-root', evidence='Original source metadata')
        self.loop()
        sent = self.outgoing()
        result = self.call('outbox-resolve', agent_id=self.a, task_id='MC-test', message_id=sent['message_id'],
                           outcome='sent', mail_id='split-mail', thread_id='unexpected-split', evidence='Actual provider response')
        self.assertEqual(result['status'], 'sent')
        self.assertFalse(result['thread_verified'])
        self.assertEqual(self.tick()['action'], 'stop')
        with self.assertRaisesRegex(ValueError, 'thread conflict'):
            self.outgoing()
        self.call('task-thread', agent_id=self.a, task_id='MC-test', thread_id='fixture-thread',
                  reply_message_id='fixture-root', evidence='Original anchor rechecked; split mail retained, no resend')
        self.assertEqual(task['outbox'][sent['message_id']]['status'], 'sent')


if __name__ == '__main__':
    unittest.main(verbosity=2)
