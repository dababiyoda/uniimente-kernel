"""#49 Join actual owned-company machinery; external operation stays gated.

Uses the existing charter, TerritoryGraph, stores, media, portal, community,
journeys, offers, accounting and distribution mechanism. Fixture consideration
is isolated from real money. Neither assembly nor a tested loop ratifies a
charter or grants publishing/payment/agent authority.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3

from foundry.company import MediaCompanyCharter
from foundry.distribution import DistributionLoop
from foundry.systems import accounting, cas, community, journeys, media, offers, portal, versions
from greg.artifacts import ArtifactStore
from greg.capabilities import CapabilityError

VERSION = "owned-company/1"


def _stores(root):
    return Path(root).parent


def _charter(spec):
    if not isinstance(spec, dict) or set(spec) != {"charter", "canon", "territory", "offers"}:
        raise ValueError("owned company needs charter, canon, territory and executable offers")
    charter = MediaCompanyCharter(**spec["charter"])
    problems = charter.validate()
    if problems:
        raise ValueError("invalid existing company charter: " + str(problems))
    if charter.authored_by != "machine" or charter.synthetic_disclosure is not True:
        raise ValueError("machine authorship/disclosure required")
    community.identifier(charter.name); community.identifier(charter.community)
    value = media.canon(spec["canon"])
    graph = journeys.territory_graph(spec["territory"])
    if graph.name != charter.name:
        raise ValueError("territory belongs to a different company")
    if not isinstance(spec["offers"], list) or not 1 <= len(spec["offers"]) <= 32:
        raise ValueError("bounded executable product offers required")
    names = []
    for offer in spec["offers"]:
        if not isinstance(offer, dict) or set(offer) != {"id", "price_cents", "currency", "description"}:
            raise ValueError("invalid company offer")
        community.identifier(offer["id"]); names.append(offer["id"])
    if len(set(names)) != len(names) or sorted(names) != sorted(charter.products):
        raise ValueError("every charter product must have one executable offer")
    if any(o["currency"] != spec["offers"][0]["currency"] for o in spec["offers"]):
        raise ValueError("this company's fixture book requires a single currency")
    return charter, value, graph


def assemble(root, spec, expected_spec=None):
    charter, value, graph = _charter(spec)
    root = Path(root)
    path = root / "assembly.json"
    digest = "sha256:" + hashlib.sha256(community.canonical(spec)).hexdigest()
    if path.exists():
        current = json.loads(path.read_text())
        observed(root, strict=True)
        if current["spec_hash"] == digest:
            return current["output"]
        if expected_spec != current["spec_hash"]:
            raise ValueError("company revision requires its expected prior input hash")
        if (spec["charter"]["name"], spec["charter"]["community"]) != (
                current["spec"]["charter"]["name"], current["spec"]["charter"]["community"]):
            raise ValueError("member/company identity migration requires a separate workspace")
        if sorted(spec["charter"]["products"]) != sorted(current["spec"]["charter"]["products"]):
            raise ValueError("product identity migration requires a separate workspace")
        if spec["offers"][0]["currency"] != current["spec"]["offers"][0]["currency"]:
            raise ValueError("book currency migration requires a separate workspace")
    else:
        current = None
        if expected_spec is not None:
            raise ValueError("company expected prior inputs are missing")
    stores = _stores(root)
    version = versions.commit(root / "charter", charter.name, spec["charter"], reason="private unratified assembly" if current is None else "private unratified revision",
                              evidence=value["source_refs"], expected_parent=None if current is None else current["output"]["charter"])
    produced = media.produce(stores / "system-35", value)
    page = portal.build(stores / "system-31", value, "owned company canonical page")
    published = [offers.publish(stores / "system-54", {**offer, "manifest": produced["manifest"]},
                                "company native delivery offer") for offer in spec["offers"]]
    # Initialize real executable community/journey substrates without creating
    # any fake people or outcomes. Signed/observed records arrive separately.
    members = community.ingest(stores / "system-32", charter.community, [])
    journeys.ingest(stores / "system-34", [])
    books = root / "fixture-books"
    for account, kind in (("fixture_consideration", "asset"), ("fixture_receipts", "revenue")):
        accounting.open_account(books, account, kind, spec["offers"][0]["currency"])
    if any(o["currency"] != spec["offers"][0]["currency"] for o in spec["offers"]):
        raise ValueError("this company's fixture book requires a single currency")
    output = {"version": VERSION, "company": charter.name, "charter": version["address"],
              "charter_hash": charter.hash(), "territory_hash": graph.hash(),
              "media": produced, "portal": page, "offers": published, "community": members,
              "operational_ratification": False, "public_activation": False, "authority_created": False}
    root.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"spec": spec, "spec_hash": digest, "output": output,
                               "reconciled_orders": current["reconciled_orders"] if current else []},
                               sort_keys=True))
    return output


def ingest(root, community_events, journey_events):
    root = Path(root)
    state = json.loads((root / "assembly.json").read_text())
    observed(root, strict=True)
    if any(e.get("tier") != "fixture" for e in journey_events):
        raise ValueError("synthetic company loop accepts fixture evidence only; observed evidence stays separate")
    stores = _stores(root)
    members = community.ingest(stores / "system-32", state["spec"]["charter"]["community"], community_events)
    memory = journeys.ingest(stores / "system-34", journey_events)
    return {"community": members, "performance_memory": memory, "mode": "fixture", "authority_created": False}


def reconcile(root):
    root = Path(root)
    path = root / "assembly.json"
    state = json.loads(path.read_text())
    observed(root, strict=True)
    rows = offers.history(_stores(root) / "system-54")
    names = set(state["spec"]["charter"]["products"])
    new = []
    for row in rows:
        receipt, acceptance = row["receipt"], row["acceptance"]
        if not acceptance or acceptance["verdict"] != "accept" or receipt["offer"] not in names:
            continue
        if receipt["id"] in state["reconciled_orders"]:
            continue
        consideration = receipt["consideration"]
        accounting.post(root / "fixture-books", date=acceptance["at"],
                        memo="fixture only accepted order:" + receipt["id"], currency=consideration["currency"],
                        lines=[{"account": "fixture_consideration", "debit": consideration["amount_cents"]},
                               {"account": "fixture_receipts", "credit": consideration["amount_cents"]}])
        state["reconciled_orders"].append(receipt["id"]); new.append(receipt["id"])
    path.write_text(json.dumps(state, sort_keys=True))
    return {"newly_reconciled": new, "book": accounting.trial_balance(root / "fixture-books"),
            "mode": "fixture", "money_moved": False}


def observed(root, strict=False):
    try:
        root = Path(root)
        path = root / "assembly.json"
        if not path.exists():
            return {"intact": False, "reason": "not assembled", "authority_created": False}
        state = json.loads(path.read_text())
        spec, output = state["spec"], state["output"]
        charter, value, graph = _charter(spec)
        if output["version"] != VERSION or output["company"] != charter.name or any(
                output[k] is not False for k in ("operational_ratification", "public_activation", "authority_created")):
            raise ValueError("company output authority or identity changed")
        if sorted(r["offer"] for r in output["offers"]) != sorted(charter.products):
            raise ValueError("company product coverage changed")
        if state["spec_hash"] != "sha256:" + hashlib.sha256(community.canonical(spec)).hexdigest():
            raise ValueError("company inputs changed")
        if versions.content(root / "charter", charter.name) != spec["charter"] or output["charter_hash"] != charter.hash() or \
                versions.history(root / "charter", charter.name)[0]["address"] != output["charter"]:
            raise ValueError("retained company charter changed")
        if output["territory_hash"] != graph.hash():
            raise ValueError("retained territory changed")
        stores = _stores(root)
        media.inspect(stores / "system-35", output["media"]["manifest"])
        source = ArtifactStore(stores / "system-35" / "artifacts")
        manifest = json.loads(source.read(output["media"]["manifest"]))
        if source.read(manifest["canon"]) != media._json(value) or manifest["assets"] != output["media"]["assets"]:
            raise ValueError("company media diverges from frozen canon")
        page = portal.retrieve(stores / "system-31", value["canon_id"], output["portal"]["version"])
        if (page["address"], page["version_address"]) != (output["portal"]["address"], output["portal"]["version_address"]):
            raise ValueError("company page changed")
        for ref in output["offers"]:
            offer = offers.discover(stores / "system-54", ref["offer"], ref["version"])
            if offer["version_address"] != ref["version_address"] or offer["manifest"] != output["media"]["manifest"]:
                raise ValueError("company offer changed")
        member_state = community.view(stores / "system-32", charter.community)
        performance = journeys.report(stores / "system-34", "fixture")
        transactions = offers.inspect(stores / "system-54")
        if not transactions["intact"]:
            raise ValueError("company delivery history failed integrity")
        rows = offers.history(stores / "system-54")
        ids = state["reconciled_orders"]
        if not isinstance(ids, list) or len(set(ids)) != len(ids):
            raise ValueError("duplicate reconciled order")
        accepted = {r["receipt"]["id"]: r for r in rows if r["acceptance"] and
                    r["acceptance"]["verdict"] == "accept" and r["receipt"]["offer"] in charter.products}
        if set(ids) - set(accepted):
            raise ValueError("fixture finance names an unaccepted or missing delivery")
        currency = spec["offers"][0]["currency"]
        books = root / "fixture-books"
        if accounting.chart(books) != {"currency": currency, "accounts": {
                "fixture_consideration": "asset", "fixture_receipts": "revenue"}}:
            raise ValueError("fixture book chart changed")
        entries = accounting.journal(books)
        if len(entries) != len(ids):
            raise ValueError("fixture journal diverges from accepted delivery receipts")
        for order_id, entry in zip(ids, entries):
            row = accepted[order_id]
            cents = row["receipt"]["consideration"]["amount_cents"]
            if entry["date"] != row["acceptance"]["at"] or entry["memo"] != "fixture only accepted order:" + order_id or \
                    entry["currency"] != currency or entry["reverses"] is not None or entry["lines"] != [
                        {"account": "fixture_consideration", "debit": cents, "credit": 0},
                        {"account": "fixture_receipts", "debit": 0, "credit": cents}]:
                raise ValueError("fixture posting diverges from its signed acceptance")
        book = accounting.trial_balance(books)
        expected = sum(accepted[id]["receipt"]["consideration"]["amount_cents"] for id in ids)
        if not book["equation_holds"] or book["totals"]["revenue"] != expected:
            raise ValueError("fixture finance does not reconcile")
        distribution = DistributionLoop(charter.name)
        window = distribution.open_window("retained-fixture")
        window.record_impressions(performance["views"])
        window.record_qualified_visit(performance["viewers"])
        window.record_owned_relationship(member_state["active_members"])
        window.record_returning_visitor(performance["returning_on_later_utc_day"])
        for kind, count in performance["useful_actions"].items():
            window.record_useful_action(kind, count)
        return {"intact": True, "company": charter.name, "members": member_state["active_members"],
                "products": len(output["offers"]), "accepted_deliveries": transactions["accepted"],
                "performance": performance, "fixture_finance": book,
                "distribution": {"behavior_changes": window.behavior_changes,
                                 "informed_return": window.informed_return()},
                "mode": "fixture", "money_moved": False, "operational_ratification": False,
                "public_activation": False, "authority_created": False}
    except (ValueError, KeyError, FileNotFoundError, TypeError, CapabilityError, versions.VersionError,
            cas.IntegrityError, accounting.AccountingError, sqlite3.DatabaseError) as exc:
        if strict:
            raise
        return {"intact": False, "reason": type(exc).__name__, "authority_created": False}


QUERY_OPS = {"inspect": lambda a, r: observed(r)}
APPLY_OPS = {"assemble": lambda a, r: assemble(r, a["spec"], a.get("expected_spec")),
             "ingest": lambda a, r: ingest(r, a["community_events"], a["journey_events"]),
             "reconcile": lambda a, r: reconcile(r)}
