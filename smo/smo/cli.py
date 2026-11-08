"""Ligne de commande SMO (`uv run smo --help`)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config


def cmd_doctor(a, s):
    from . import doctor
    probes = list(doctor.PROBES) if a.probe == ["all"] else a.probe or []
    return 0 if doctor.run(s, probes) else 1


def cmd_new(a, s):
    from .models import CaptureMeta
    from .runs import Run
    if not (a.url or s.site_url):
        raise config.MissingConfig("Donne --url, ou SITE_URL dans smo/.env")
    meta = CaptureMeta(task=a.task, software_kind=a.kind, software_url=a.url or s.site_url, software_name=a.software_name,
                       owner=a.owner, language=a.lang, sample=a.sample)
    run = Run.create(s.runs_dir, meta, [Path(f) for f in a.files])
    print(run.id)
    if a.go:
        return _pipeline(run, a, s)
    return 0


def cmd_run(a, s):
    from .runs import Run
    return _pipeline(Run.open(s.runs_dir, a.run_id), a, s)


def _pipeline(run, a, s):
    from .pipeline.orchestrator import run_pipeline
    state = run_pipeline(run, s, start=getattr(a, "start", None), stop=getattr(a, "stop", None),
                         only=getattr(a, "only", None), force=getattr(a, "force", False),
                         auto=a.auto, wait=not a.no_wait, guided=a.guided)
    print(f"→ {state} ({run.path})")
    return 0 if state in ("done", "waiting") else 1


def cmd_approve(a, s):
    from .runs import Run
    run = Run.open(s.runs_dir, a.run_id)
    run.write_text("skill.approved", "ok\n")
    print(f"Skill approuvée. Suite : uv run smo run {run.id}")
    return 0


def cmd_status(a, s):
    from .runs import Run
    run = Run.open(s.runs_dir, a.run_id)
    from .pipeline.orchestrator import NAMES
    status = run.status()
    for name in NAMES:
        st = status.get(name, {})
        extra = st.get("error") or st.get("missing") or (f"{st['seconds']}s" if "seconds" in st else "")
        print(f"{name:<11} {st.get('state', '—'):<8} {st.get('at', ''):<20} {extra}")
    return 0


def cmd_trace(a, s):
    from .clients import h
    s.require("hai_api_key")
    out = Path(a.out or s.runs_dir / "_traces" / a.session_id)
    trace = h.build_trace(h.client(s.hai_api_key), a.session_id, out, s.hai_api_key)
    (out / "trace.json").write_text(trace.model_dump_json(indent=2), encoding="utf-8")
    print(f"{len(trace.steps)} étapes → {out / 'trace.json'}")
    return 0


def cmd_repair(a, s):
    from .pipeline.compile import repair
    repair(a.tool, a.session, a.details, s)
    return 0


def cmd_tools(a, s):
    from .runtime.tools import call_tool, for_site, input_schema, load_tools
    for t in load_tools(s.tools_dir).values():
        print(f"{t.name} : {t.description}")
        print(f"  params : {json.dumps(input_schema(t.params).get('properties', {}), ensure_ascii=False)[:300]}")
        if a.precheck:   # avec l'élément du vault H de SITE_URL, comme un appel de l'agent
            print(f"  precheck : {call_tool('precheck', t, for_site(s, s.site_url))}")
    return 0


def cmd_webhook(a, s):
    from .clients import h
    s.require("hai_api_key")
    url = a.url or (s.server_url and f"{s.server_url}/webhooks/h")
    if not url:
        raise config.MissingConfig("Donne --url ou SMO_SERVER_URL")
    hook = h.client(s.hai_api_key).webhooks.create_webhook(url=url, enabled_events=["*"],
                                                          description="SMO : sessions en attente de tools")
    print(f"Webhook créé → {url}\nÀ mettre dans H_WEBHOOK_SECRET (affiché une seule fois) : {hook.secret}")
    return 0


def cmd_serve(a, s):
    import uvicorn
    uvicorn.run("smo.runtime.server:app", host=a.host, port=a.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="smo", description="Show me once : de la capture à l'agent custom H.")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="vérifie les clés et les API ; --probe teste les capacités (crédits H)")
    d.add_argument("--probe", nargs="*", choices=["skill", "guided", "tool", "devin", "desktop-tool", "all"])
    d.set_defaults(fn=cmd_doctor)

    def pipeline_flags(sp):
        sp.add_argument("--auto", action="store_true", help="approuve la Skill sans relecture (parcours Catherine)")
        sp.add_argument("--no-wait", action="store_true", help="n'attend pas Devin (relancer `smo run` pour suivre)")
        sp.add_argument("--guided", action="store_true",
                        help="trial : l'agent est guidé phrase par phrase au lieu de suivre seul sa Skill")

    n = sub.add_parser("new", help="crée un run à partir d'une capture (vidéo, audio, images)")
    n.add_argument("files", nargs="+")
    n.add_argument("--task", required=True, help="ex. « Saisir une facture fournisseur »")
    n.add_argument("--url", help="web : l'adresse (défaut : SITE_URL) ; desktop : le nom de l'application ouverte")
    n.add_argument("--kind", choices=["web", "desktop"], default="web", help="un agent H par type de logiciel")
    n.add_argument("--software-name", help="nom public du logiciel, pour chercher sa doc (ex. Odoo)")
    n.add_argument("--owner", default="demo")
    n.add_argument("--sample", help="la pièce traitée pendant la démo (ex. INV-001)")
    n.add_argument("--lang", default="fr")
    n.add_argument("--go", action="store_true", help="enchaîne tout le pipeline")
    pipeline_flags(n)
    n.set_defaults(fn=cmd_new)

    r = sub.add_parser("run", help="lance ou reprend le pipeline d'un run")
    r.add_argument("run_id")
    r.add_argument("--from", dest="start")
    r.add_argument("--to", dest="stop")
    r.add_argument("--only", nargs="+")
    r.add_argument("--force", action="store_true", help="refait les étapes même si elles sont faites")
    pipeline_flags(r)
    r.set_defaults(fn=cmd_run)

    for name, fn, help_ in [("approve", cmd_approve, "approuve la Skill relue"),
                            ("status", cmd_status, "état des étapes d'un run")]:
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("run_id")
        sp.set_defaults(fn=fn)

    t = sub.add_parser("trace", help="trace d'une session H quelconque (events, captures, étapes)")
    t.add_argument("session_id")
    t.add_argument("--out")
    t.set_defaults(fn=cmd_trace)

    rp = sub.add_parser("repair", help="relance Devin sur un tool dont l'interface a changé")
    rp.add_argument("tool")
    rp.add_argument("--session", required=True, help="session H où l'agent a fini la tâche à la main")
    rp.add_argument("--details", required=True)
    rp.set_defaults(fn=cmd_repair)

    tl = sub.add_parser("tools", help="liste les tools compilés")
    tl.add_argument("--precheck", action="store_true")
    tl.set_defaults(fn=cmd_tools)

    w = sub.add_parser("webhook", help="abonne le serveur SMO aux statuts des sessions H")
    w.add_argument("--url")
    w.set_defaults(fn=cmd_webhook)

    sv = sub.add_parser("serve", help="serveur SMO (worker des tools + API de test)")
    sv.add_argument("--host", default="0.0.0.0")
    sv.add_argument("--port", type=int, default=8000)
    sv.set_defaults(fn=cmd_serve)

    a = p.parse_args(argv)
    try:
        return a.fn(a, config.load())
    except config.MissingConfig as err:
        print(f"■ {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
