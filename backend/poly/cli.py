"""`poly` command line.

  poly serve              run the API (uvicorn) on POLY_HOST:POLY_PORT
  poly worker             run the Huey background worker (jobs + daily schedule)
  poly init-db            create tables and seed principles/feeds
  poly detect             scan local AI runtimes and print what Poly will use
  poly ingest             run the news pipeline now
  poly import-principles  import knowledge/political_operating_system.md
  poly export-principles  export principles to the markdown file
  poly reembed            re-embed content with the current best local embedding model
"""
from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="poly", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--reload", action="store_true")
    sub.add_parser("worker")
    sub.add_parser("init-db")
    sub.add_parser("detect")
    i = sub.add_parser("ingest")
    i.add_argument("--no-analyze", action="store_true")
    sub.add_parser("import-principles")
    sub.add_parser("export-principles")
    sub.add_parser("reembed")
    args = parser.parse_args(argv)

    from .config import get_settings

    cfg = get_settings()

    if args.cmd == "serve":
        import uvicorn

        uvicorn.run("poly.main:app", host=cfg.host, port=cfg.port, reload=args.reload)
        return 0
    if args.cmd == "worker":
        from huey.consumer_options import ConsumerConfig

        from .jobs.tasks import huey  # noqa: F401 - registers tasks

        from .db import init_db

        init_db()
        config = ConsumerConfig(workers=2, worker_type="thread", periodic=True)
        config.setup_logger()
        consumer = huey.create_consumer(**config.values)
        consumer.run()
        return 0

    from .db import init_db, session_scope

    init_db()
    if args.cmd == "init-db":
        from .main import startup_tasks

        print(json.dumps(startup_tasks(), indent=2, default=str))
        return 0
    if args.cmd == "detect":
        from .providers.registry import detect_and_register

        with session_scope() as db:
            print(json.dumps(detect_and_register(db), indent=2, default=str))
        return 0
    if args.cmd == "ingest":
        from .services.ingest import run_ingest

        with session_scope() as db:
            res = run_ingest(db, analyze=not args.no_analyze, progress=lambda f, m: print(f"[{f:5.0%}] {m}", file=sys.stderr))
            print(json.dumps(res, indent=2, default=str))
        return 0
    if args.cmd == "import-principles":
        from .services.principles import import_markdown, list_principles
        from .services.search import embed_entity

        with session_scope() as db:
            print(import_markdown(db))
            for p in list_principles(db):
                embed_entity(db, "principle", p)
        return 0
    if args.cmd == "export-principles":
        from .services.principles import export_markdown

        with session_scope() as db:
            print(export_markdown(db))
        return 0
    if args.cmd == "reembed":
        from .services.search import reembed_stale

        with session_scope() as db:
            print({"reembedded": reembed_stale(db, limit=100000)})
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
