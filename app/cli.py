"""Administrative command-line interface.

Usage:
    python -m app.cli init-db
    python -m app.cli create-tenant "Acme Corp"
    python -m app.cli create-key --tenant <tenant_id> --name ci
    python -m app.cli revoke-key --tenant <tenant_id> <key_id>
    python -m app.cli list-keys --tenant <tenant_id>
    python -m app.cli research "your topic"     # run once, inline (no queue)
"""

from __future__ import annotations

import argparse
import sys

from app.observability.logging import configure_logging


def _init_db(_: argparse.Namespace) -> int:
    from app.db.base import create_all

    create_all()
    print("Database tables created.")
    return 0


def _create_tenant(args: argparse.Namespace) -> int:
    from app.db import repository as repo
    from app.db.base import session_scope

    with session_scope() as s:
        tenant = repo.create_tenant(s, args.name)
        s.flush()
        print(f"Tenant created: {tenant.id}  ({tenant.name})")
    return 0


def _create_key(args: argparse.Namespace) -> int:
    from app.db import repository as repo
    from app.db.base import session_scope

    with session_scope() as s:
        _, raw = repo.create_api_key(s, args.tenant, args.name)
    print("API key created. Store it now — it will not be shown again:\n")
    print(f"    {raw}\n")
    return 0


def _revoke_key(args: argparse.Namespace) -> int:
    from app.db import repository as repo
    from app.db.base import session_scope

    with session_scope() as s:
        ok = repo.revoke_api_key(s, args.tenant, args.key_id)
    print("Revoked." if ok else "Key not found for that tenant.")
    return 0 if ok else 1


def _list_keys(args: argparse.Namespace) -> int:
    from sqlalchemy import select

    from app.db.base import session_scope
    from app.db.models import ApiKey

    with session_scope() as s:
        rows = s.scalars(
            select(ApiKey).where(ApiKey.tenant_id == args.tenant)
        ).all()
        if not rows:
            print("No keys for that tenant.")
            return 0
        for k in rows:
            state = "revoked" if k.revoked else "active"
            print(f"{k.id}  {k.prefix}…  {k.name:<12} [{state}]")
    return 0


def _research(args: argparse.Namespace) -> int:
    from research_agent.report import save_report
    from research_agent.singletons import get_agent
    from research_agent.trace import format_summary, save_trace

    agent = get_agent(args.model)
    ok, msg = agent.llm.is_available()
    if not ok:
        print(f"Error: {msg}", file=sys.stderr)
        return 1

    result = agent.research(args.topic, verbose=not args.quiet)
    print("\n" + "=" * 70 + f"\n{result.report}\n" + "=" * 70 + "\n")
    if result.trace:
        print(format_summary(result.trace))
        save_trace(result.trace)
    if not args.no_save:
        sources = [(s.title, s.url) for s in result.sources]
        md_path, pdf_path = save_report(result.topic, result.report, sources)
        print(f"Markdown saved to: {md_path}")
        if pdf_path:
            print(f"PDF saved to:      {pdf_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="research-agent", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Create database tables (dev).").set_defaults(
        func=_init_db
    )

    t = sub.add_parser("create-tenant", help="Create a tenant.")
    t.add_argument("name")
    t.set_defaults(func=_create_tenant)

    k = sub.add_parser("create-key", help="Create an API key for a tenant.")
    k.add_argument("--tenant", required=True)
    k.add_argument("--name", default="default")
    k.set_defaults(func=_create_key)

    r = sub.add_parser("revoke-key", help="Revoke an API key.")
    r.add_argument("--tenant", required=True)
    r.add_argument("key_id")
    r.set_defaults(func=_revoke_key)

    lk = sub.add_parser("list-keys", help="List a tenant's API keys.")
    lk.add_argument("--tenant", required=True)
    lk.set_defaults(func=_list_keys)

    rr = sub.add_parser("research", help="Run one research job inline.")
    rr.add_argument("topic")
    rr.add_argument("--model", default=None)
    rr.add_argument("--no-save", action="store_true")
    rr.add_argument("--quiet", action="store_true")
    rr.set_defaults(func=_research)

    return p


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
