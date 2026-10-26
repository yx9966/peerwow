#!/usr/bin/env python3
"""Local bookkeeping only: no mail, credentials, subprocesses or background work."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import uuid


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value):
    return type(value) is str and bool(value.strip())


def ident(value):
    return type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value) is not None


def email(value):
    require(type(value) is str and len(value) <= 254
            and re.fullmatch(r"[^\s@<>]+@[^\s@<>]+", value) is not None,
            "Use an exact mailbox address, without display name or whitespace")
    local, domain = value.rsplit("@", 1)
    return local + "@" + domain.lower()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def agreement_hash(value):
    return hashlib.sha256(value.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")).hexdigest()


def new_id(prefix):
    return prefix + uuid.uuid4().hex


def task_key(data):
    require(ident(data.get("agent_id")) and ident(data.get("task_id")), "Invalid agent/task ID")
    return data["agent_id"] + ":" + data["task_id"]


def trust_record(contact, side):
    return contact.get(side + "_trust", dict(revision=0, level="discuss", allowed=["Task discussion"],
                                            denied=["Task execution"], expires_at=None))


def check_trust(state, task, peers, now, execution=False):
    for peer in peers:
        contact = state["contacts"][task["agent_id"] + ":" + peer]
        grants = {s: trust_record(contact, s) for s in ("local", "peer")}
        for grant in grants.values():
            require(grant["level"] != "blocked", "Contact trust blocked")
            require(grant["expires_at"] is None or now < grant["expires_at"], "Contact trust expired")
        if execution:
            require(all(g["level"] == "scoped" for g in grants.values()), "Scoped bilateral trust required")
            expected = {s: g["revision"] for s, g in grants.items()}
            require(task["authorization"].get("trust", {}).get(peer) == expected,
                    "Trust changed or not acknowledged: refresh authorization and READY")


def apply(state, action, data, now):
    require(type(data) is dict, "Input must be a JSON object")
    if action == "show":
        if "task_id" in data:
            return state["tasks"].get(task_key(data))
        return state
    if action == "identity-add":
        require(text(data.get("owner")) and text(data.get("name")), "Owner and Agent name required")
        agent = dict(agent_id=new_id("ag-"), owner=data["owner"], name=data["name"], email=email(data.get("email")))
        state["agents"][agent["agent_id"]] = agent
        return agent
    agent_id = data.get("agent_id")
    require(ident(agent_id) and agent_id in state["agents"], "Unknown local Agent identity")
    if action == "handshake-start":
        require(text(data.get("owner")), "Expected person's name required")
        handshake = dict(handshake_id=new_id("hs-"), agent_id=agent_id, email=email(data.get("email")),
                         owner=data["owner"], nickname=data.get("nickname", ""), created=now, status="pending")
        require(type(handshake["nickname"]) is str, "Nickname must be text")
        state["handshakes"][handshake["handshake_id"]] = handshake
        return handshake
    if action == "handshake-finish":
        h = state["handshakes"].get(data.get("handshake_id", ""))
        require(h is not None and h["agent_id"] == agent_id and h["status"] == "pending", "No matching pending handshake")
        require(data.get("echo") == h["handshake_id"] and email(data.get("reply_from")) == h["email"], "Handshake echo or sender mismatch")
        peer = data.get("peer_agent_id")
        require(ident(peer) and peer != agent_id and text(data.get("peer_name")) and text(data.get("mail_id")), "Peer identity and reply source required")
        key = agent_id + ":" + peer
        old = state["contacts"].get(key)
        require(old is None or old["email"] == h["email"], "Contact mailbox changed: reconcile with owner, do not overwrite")
        contact = dict(agent_id=peer, name=data["peer_name"], owner=h["owner"], nickname=h["nickname"],
                       email=h["email"], handshake_id=h["handshake_id"], mail_id=data["mail_id"], confirmed=now)
        for side in ("local", "peer"):
            contact[side + "_trust"] = trust_record(old or {}, side)
        state["contacts"][key] = contact
        h["status"] = "confirmed"
        return contact
    if action == "contact-trust":
        peer, side = data.get("peer_agent_id"), data.get("side")
        require(ident(peer) and side in ("local", "peer"), "Peer and trust direction required")
        contact = state["contacts"].get(agent_id + ":" + peer)
        require(contact is not None, "Contact has not completed handshake")
        previous = trust_record(contact, side)
        revision = data.get("revision")
        require(type(revision) is int and revision > previous["revision"], "Trust revision must increase")
        require(data.get("level") in ("blocked", "discuss", "scoped"), "Invalid trust level")
        for field in ("allowed", "denied"):
            require(type(data.get(field)) is list and all(text(v) for v in data[field]), "Explicit allowed/denied lists required")
        require(data["level"] == "blocked" or data["allowed"], "Allowed scope required")
        expiry = data.get("expires_at")
        require(expiry is None or type(expiry) is int and expiry > 0, "Invalid trust expiry")
        require(text(data.get("evidence")), "Trust source evidence required")
        if side == "peer":
            require(email(data.get("from_email")) == contact["email"] and text(data.get("mail_id")),
                    "Peer trust requires matching mailbox and source mail")
        grant = {k: data[k] for k in ("revision", "level", "allowed", "denied", "evidence")}
        grant.update(expires_at=expiry, updated=now)
        if side == "peer":
            grant.update(mail_id=data["mail_id"], from_email=contact["email"])
        contact[side + "_trust"] = grant
        return grant
    key = task_key(data)
    old = state["tasks"].get(key)
    if action == "task-put":
        require(type(data.get("revision")) is int and data["revision"] >= 1, "Positive integer revision required")
        require(data.get("phase") in ("discuss", "execute", "closed"), "Invalid task phase")
        require(text(data.get("agreement")) and text(data.get("discussion_evidence")), "Task agreement and local discussion authorization source required")
        peers = data.get("participants")
        require(type(peers) is list and len(peers) >= 2 and all(ident(p) for p in peers)
                and len(set(peers)) == len(peers) and agent_id in peers, "Distinct participant Agent IDs, including self, required")
        require(data.get("coordinator") in peers, "Coordinator must be a participant")
        for peer in peers:
            require(peer == agent_id or agent_id + ":" + peer in state["contacts"], "Participant has not completed handshake")
        require(type(data.get("deadline")) is int and data["deadline"] > 0, "Unix seconds deadline required")
        require(type(data.get("max_outgoing")) is int and 1 <= data["max_outgoing"] <= 1000, "Invalid outgoing limit")
        if data["phase"] != "closed":
            require(data["deadline"] > now, "Task deadline has passed")
        if old:
            require(old["phase"] != "closed", "Closed tasks cannot be reopened")
            require(data["revision"] >= old["revision"], "Revision cannot go backwards")
            changed = any(data.get(k) != old.get(k) for k in
                          ("agreement", "participants", "coordinator", "deadline", "max_outgoing"))
            require(not changed or data["revision"] > old["revision"], "Changed task contract requires a new revision")
        ah = agreement_hash(data["agreement"])
        auth = data.get("authorization", {})
        require(type(auth) is dict, "Authorization must be an object")
        require(type(auth.get("trust", {})) is dict and all(type(v) is dict for v in auth.get("trust", {}).values()),
                "Authorization trust must map peers to revision pairs")
        if data["phase"] == "execute":
            require(auth.get("revision") == data["revision"] and auth.get("agreement_sha256") == ah
                    and text(auth.get("local_evidence")) and text(auth.get("local_scope")), "Current local execution authorization required")
            ready = auth.get("peer_ready", {})
            require(type(ready) is dict, "peer_ready must be an object")
            for peer in peers:
                if peer == agent_id:
                    continue
                r = ready.get(peer, {})
                require(type(r) is dict and r.get("revision") == data["revision"]
                        and r.get("agreement_sha256") == ah and text(r.get("mail_id"))
                        and text(r.get("scope")), "Matching peer READY required")
                pair = auth.get("trust", {}).get(peer, {})
                require(r.get("trust") == {"local": pair.get("peer"), "peer": pair.get("local")},
                        "Peer READY must acknowledge both trust revisions in peer perspective")
        task = {k: data[k] for k in ("agent_id", "task_id", "revision", "phase", "agreement",
                                    "discussion_evidence", "participants", "coordinator", "deadline", "max_outgoing")}
        task.update(agreement_sha256=ah, authorization=auth, checkpoint=data.get("checkpoint", ""),
                    inbox=old["inbox"] if old else {}, outbox=old["outbox"] if old else {})
        require(type(task["checkpoint"]) is str, "Checkpoint must be text")
        require(sum(x["status"] != "not_sent" for x in task["outbox"].values()) <= task["max_outgoing"], "Limit is below existing outgoing reservations")
        if task["phase"] != "closed":
            check_trust(state, task, [p for p in peers if p != agent_id], now, task["phase"] == "execute")
        state["tasks"][key] = task
        return task
    require(old is not None, "Unknown task")
    task = old
    # Reconciliation remains possible after close/expiry, without new work or mail.
    if action == "outbox-resolve":
        m = task["outbox"].get(data.get("message_id", ""))
        require(m is not None and m["status"] == "prepared", "No unresolved outgoing reservation")
        require(data.get("outcome") in ("sent", "not_sent") and text(data.get("evidence")), "Definite delivery outcome and evidence required")
        if data["outcome"] == "sent":
            require(text(data.get("mail_id")), "Provider sent-message ID required")
        m.update(status=data["outcome"], evidence=data["evidence"], mail_id=data.get("mail_id"), resolved=now)
        return m
    if action == "inbox-done":
        m = task["inbox"].get(data.get("message_id", ""))
        require(m is not None and m["status"] == "processing" and data.get("claim") == m["claim"], "No matching message claim")
        m.update(status="done", summary=data.get("summary", ""), completed=now)
        return m
    require(task["phase"] != "closed" and now < task["deadline"], "Task closed or expired")
    if action == "task-check":
        check_trust(state, task, [p for p in task["participants"] if p != agent_id], now,
                    task["phase"] == "execute")
        return task
    if action == "inbox-claim":
        mid, sender = data.get("message_id"), data.get("from_agent")
        require(ident(mid) and sender in task["participants"] and sender != agent_id, "Invalid message or sender")
        require(email(data.get("from_email")) == state["contacts"][agent_id + ":" + sender]["email"], "Unexpected sender mailbox")
        recipients = data.get("to_agents")
        require(type(recipients) is list and agent_id in recipients and all(p in task["participants"] for p in recipients), "Message not addressed to this Agent or has unknown recipients")
        require(type(data.get("revision")) is int and data["revision"] == task["revision"] and text(data.get("mail_id")) and type(data.get("body")) is str, "Stale revision or missing message source/body")
        require(data.get("kind") in ("TASK", "READY", "WORK", "RESULT", "BLOCKED", "CLOSE"), "Invalid message kind")
        if data.get("kind") in ("WORK", "RESULT"):
            require(task["phase"] == "execute", "Execution messages require execution phase")
        check_trust(state, task, [sender], now, data.get("kind") in ("WORK", "RESULT"))
        fingerprint = digest({k: data.get(k) for k in ("from_agent", "from_email", "to_agents", "revision", "kind", "body")})
        previous = task["inbox"].get(mid)
        if previous:
            require(previous["fingerprint"] == fingerprint, "Same message ID with different content")
            return dict(status=previous["status"], message_id=mid, duplicate=True)
        m = dict(status="processing", fingerprint=fingerprint, claim=new_id("claim-"), mail_id=data["mail_id"], created=now)
        task["inbox"][mid] = m
        return dict(message_id=mid, duplicate=False, **m)
    if action == "outbox-prepare":
        recipients = data.get("to_agents")
        require(type(recipients) is list and recipients and len(set(recipients)) == len(recipients)
                and all(p in task["participants"] and p != agent_id for p in recipients), "Explicit task recipients required")
        require(data.get("kind") in ("TASK", "READY", "WORK", "RESULT", "BLOCKED", "CLOSE"), "Invalid message kind")
        require(text(data.get("body")), "Outgoing body required")
        if data["kind"] in ("WORK", "RESULT"):
            require(task["phase"] == "execute", "Execution messages require execution phase")
        if data["kind"] == "READY":
            auth = task["authorization"]
            require(auth.get("revision") == task["revision"] and auth.get("agreement_sha256") == task["agreement_sha256"]
                    and text(auth.get("local_evidence")) and text(auth.get("local_scope")), "Local authorization required before announcing READY")
        check_trust(state, task, recipients, now, data["kind"] in ("WORK", "RESULT", "READY"))
        require(not any(m["status"] == "prepared" for m in task["outbox"].values()), "Reconcile uncertain/pending send before preparing another")
        require(sum(m["status"] != "not_sent" for m in task["outbox"].values()) < task["max_outgoing"], "Outgoing budget exhausted")
        attachments = data.get("attachments", [])
        require(type(attachments) is list and all(type(a) is dict and text(a.get("name")) and
                type(a.get("sha256")) is str and re.fullmatch(r"[a-f0-9]{64}", a["sha256"]) for a in attachments), "Attachment names and original-byte SHA256 required")
        mid = new_id("msg-")
        m = dict(status="prepared", created=now, kind=data["kind"], to_agents=recipients,
                 body=data["body"], attachments=attachments, revision=task["revision"])
        task["outbox"][mid] = m
        return dict(message_id=mid, **m)
    raise ValueError("Unknown action")


def secure_file(path):
    st = path.lstat()
    require(stat.S_ISREG(st.st_mode) and (st.st_mode & 0o077) == 0, "State file must be regular and private (0600)")
    if hasattr(os, "getuid"):
        require(st.st_uid == os.getuid(), "State file has another owner")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["show", "identity-add", "handshake-start", "handshake-finish", "contact-trust", "task-put", "task-check",
                                           "inbox-claim", "inbox-done", "outbox-prepare", "outbox-resolve"])
    parser.add_argument("--root", default=os.environ.get("PEERWOW_HOME", "~/.local/share/peerwow"))
    parser.add_argument("--input", default="-", help="JSON file; default stdin. No executable input.")
    args = parser.parse_args()
    raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
    data = json.loads(raw or "{}")
    root = Path(args.root).expanduser().absolute()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = root.lstat()
    require(stat.S_ISDIR(st.st_mode) and (st.st_mode & 0o077) == 0, "State directory must be private (0700), not a symlink")
    if hasattr(os, "getuid"):
        require(st.st_uid == os.getuid(), "State directory has another owner")
    lock = root / ".lock"
    fd = os.open(str(lock), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    tmp = None
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(str(os.getpid()))
        path = root / "state.json"
        state = dict(version=1, agents={}, contacts={}, handshakes={}, tasks={})
        if path.exists() or path.is_symlink():
            secure_file(path)
            state = json.loads(path.read_text(encoding="utf-8"))
            require(state.get("version") == 1, "Unsupported state version")
        result = apply(state, args.action, data, int(time.time()))
        if args.action != "show":
            tmp = root / (".state-" + uuid.uuid4().hex)
            with os.fdopen(os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as stream:
                json.dump(state, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(str(tmp), str(path))
        print(json.dumps(result, ensure_ascii=False))
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()
        lock.unlink()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
