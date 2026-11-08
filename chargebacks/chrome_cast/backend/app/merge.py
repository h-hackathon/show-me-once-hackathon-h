"""Fusion événements navigateur + transcription → timeline d'étapes (session.json) + skill Markdown."""
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

NAV_AFTER_CLICK_S = 3.0      # une navigation dans les 3 s après un clic est considérée comme son résultat
NARRATION_LEAD_S = 0.5       # on décrit généralement une action juste avant ou pendant qu'on la fait


def host(url: str | None) -> str:
    try:
        return urlparse(url or "").hostname or ""
    except ValueError:
        return ""


def target_label(t: dict | None) -> str:
    if not t:
        return "élément"
    name = t.get("text") or t.get("aria_label") or t.get("label") or t.get("placeholder") or t.get("title") or t.get("name")
    kind = t.get("role") or t.get("tag") or "element"
    if t.get("tag") == "a":
        kind = "link"
    elif t.get("tag") == "input" and t.get("type") in ("submit", "button"):
        kind = "button"
    return f'{kind} "{name}"' if name else f"{kind} ({t.get('selector')})"


IGNORED_URL_PREFIXES = ("chrome://", "chrome-extension://", "about:", "edge://", "devtools://")


# Paramètres de pagination / tracking qui changent à chaque visite et n'ont pas de sens pour l'agent
NOISY_PARAMS = {"ending_before", "starting_after", "cursor", "page_token", "utm_source", "utm_medium",
                "utm_campaign", "utm_content", "utm_term", "gclid", "fbclid", "ref", "_ga"}
REDIRECT_WINDOW_S = 1.5


def clean_url(url: str | None) -> str | None:
    if not url:
        return url
    try:
        u = urlparse(url)
    except ValueError:
        return url
    q = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if k not in NOISY_PARAMS]
    return urlunparse(u._replace(query=urlencode(q, safe="[]:,"), fragment=u.fragment))


def same_page(a: str | None, b: str | None) -> bool:
    return clean_url(a) == clean_url(b)


def ignored(url: str | None) -> bool:
    return not url or url.startswith(IGNORED_URL_PREFIXES)


def _sel(e: dict) -> str | None:
    return (e.get("target") or {}).get("selector")


def build_steps(events: list[dict]) -> list[dict]:
    events = sorted(events, key=lambda e: e.get("t", 0))
    # Le navigateur émet "change" APRÈS le keydown Entrée : on remet la saisie avant la touche.
    for i in range(len(events) - 1):
        a, b = events[i], events[i + 1]
        if a.get("kind") == "key" and b.get("kind") == "input" and _sel(a) == _sel(b) and b["t"] - a["t"] < 0.5:
            events[i], events[i + 1] = b, a
    steps: list[dict] = []
    last_nav_url: dict = {}

    for i, e in enumerate(events):
        kind = e.get("kind")
        if kind in ("page_loaded", "tab_closed"):
            # pas une action de l'utilisateur ; on récupère juste la capture si l'étape précédente n'en a pas
            if kind == "page_loaded" and steps and not steps[-1].get("screenshot") and e.get("screenshot_file"):
                steps[-1]["screenshot_after"] = e["screenshot_file"]
            continue
        if kind == "key" and e.get("key") != "Enter":
            continue
        if kind in ("start", "navigation", "tab_switch", "tab_opened") and ignored(e.get("url")):
            continue
        if kind == "submit" and steps and steps[-1]["action"] == "press_enter" and e["t"] - steps[-1]["t"] < 1.0:
            continue  # Entrée qui soumet le formulaire : une seule étape

        if kind == "click" and steps and steps[-1]["action"] == "click" \
                and _sel(e) and steps[-1].get("target", {}).get("selector") == _sel(e) and e["t"] - steps[-1]["t"] < 3.0:
            steps[-1]["repeated"] = steps[-1].get("repeated", 1) + 1  # double clic / ouvrir-fermer : une seule étape
            continue

        if kind == "click":
            # clic de focus sur un champ suivi d'une saisie dans ce même champ → on ne garde que la saisie
            nxt = next((n for n in events[i + 1:] if n.get("kind") in ("input", "click")), None)
            sel = (e.get("target") or {}).get("selector")
            if nxt and nxt.get("kind") == "input" and (nxt.get("target") or {}).get("selector") == sel:
                continue

        if kind in ("navigation", "tab_opened"):
            url = e.get("url")
            prev = steps[-1] if steps else None
            if same_page(last_nav_url.get(e.get("tab_id")), url) or (prev and same_page(prev.get("url"), url)):
                last_nav_url[e.get("tab_id")] = url
                continue
            last_nav_url[e.get("tab_id")] = url
            # Redirection (ex : /dashboard → /disputes en < 1,5 s sans action) : on remplace l'étape précédente
            if (prev and prev["action"] == "navigate" and prev.get("tab_id") == e.get("tab_id")
                    and e["t"] - prev["t"] <= REDIRECT_WINDOW_S):
                steps.pop()
                prev = steps[-1] if steps else None
            if (prev and prev["action"] in ("click", "press_enter", "submit") and prev.get("tab_id") == e.get("tab_id")
                    and e["t"] - prev["t"] <= NAV_AFTER_CLICK_S):
                prev["result_url"] = clean_url(url)
                continue

        if kind == "tab_switch":
            if steps and steps[-1]["action"] == "switch_tab" and e["t"] - steps[-1]["t"] < 1.0:
                steps.pop()  # changements d'onglet en rafale : on garde le dernier
            if steps and same_page(steps[-1].get("url"), e.get("url")) and steps[-1].get("tab_id") == e.get("tab_id"):
                continue  # on revient sur l'onglet où on était déjà
            last_nav_url[e.get("tab_id")] = e.get("url")

        action = {
            "start": "start", "click": "click", "input": "type", "key": "press_enter", "submit": "submit",
            "navigation": "navigate", "tab_switch": "switch_tab", "tab_opened": "open_tab",
        }.get(kind, kind)

        step = {
            "t": round(e.get("t", 0), 2),
            "action": action,
            "url": clean_url(e.get("url")),
            "app": host(e.get("url")),
            "page_title": e.get("title"),
            "event_id": e.get("id"),
            "tab_id": e.get("tab_id"),
        }
        if e.get("target"):
            step["target"] = e["target"]
            step["target_label"] = target_label(e["target"])
        if kind == "click":
            step["click_xy"] = {"x": e.get("x"), "y": e.get("y"), "viewport": e.get("viewport")}
        if kind == "input":
            step["value"] = e.get("value")
            step["sensitive"] = e.get("sensitive", False)
        if kind == "start":
            step["open_tabs"] = e.get("open_tabs", [])
        if e.get("screenshot_file"):
            step["screenshot"] = e["screenshot_file"]
        steps.append(step)

    for n, s in enumerate(steps, 1):
        s["index"] = n
    return steps


def attach_narration(steps: list[dict], utterances: list[dict]) -> str:
    """Rattache chaque phrase à l'action qu'elle décrit. Renvoie la narration finale (après la dernière action).

    - Si une ou plusieurs actions ont lieu PENDANT la phrase, elle décrit la première d'entre elles
      ("je viens cliquer sur litige" prononcé pendant le clic sur "Litiges").
    - Sinon, la phrase annonce l'action suivante ("je vais regarder le score de risque" → clic juste après).
    """
    closing = []
    actionable = [s for s in steps if s["action"] != "start"] or steps
    for u in utterances:
        during = [s for s in actionable if u["start"] - NARRATION_LEAD_S <= s["t"] <= u["end"] + NARRATION_LEAD_S]
        target = during[0] if during else next((s for s in actionable if s["t"] > u["end"]), None)
        if target is None:
            closing.append(u["text"])
        else:
            target.setdefault("narration", []).append(u["text"])
    for s in steps:
        if isinstance(s.get("narration"), list):
            s["narration"] = " ".join(s["narration"])
    return " ".join(closing)


LOGIN_PATH = re.compile(r"/(login|log-in|signin|sign-in|sign_in|auth|sso|oauth|session/new|account/login|2fa|mfa)(/|\?|$)", re.I)


def accounts_needed(events: list[dict], apps: list[str]) -> list[dict]:
    """Apps sur lesquelles l'agent devra être connecté, et si une page de connexion a été vue pendant l'enregistrement."""
    login_seen: set[str] = set()
    for e in events:
        h = host(e.get("url"))
        if not h:
            continue
        t = e.get("target") or {}
        if (e.get("kind") == "input" and (e.get("sensitive") or t.get("type") == "password")) or LOGIN_PATH.search(urlparse(e.get("url") or "").path + "?"):
            login_seen.add(h)
    return [{"app": a, "login_seen": a in login_seen} for a in dict.fromkeys(apps)]


def apps_sequence(steps: list[dict]) -> list[str]:
    seq: list[str] = []
    for s in steps:
        if s["app"] and (not seq or seq[-1] != s["app"]):
            seq.append(s["app"])
    return seq


def describe_step(s: dict) -> str:
    a = s["action"]
    where = f"[{s['app']}" + (f" — {s['page_title']}" if s.get("page_title") else "") + "]" if s.get("app") else ""
    if a == "start":
        line = f"Start on {s.get('url')}"
    elif a == "click":
        line = f"Click the {s.get('target_label')}"
        t = s.get("target") or {}
        hints = []
        if t.get("href"):
            hints.append(f"link: {t['href']}")
        if t.get("selector"):
            hints.append(f"selector: `{t['selector']}`")
        if hints:
            line += f" ({'; '.join(hints)})"
        if t.get("row_text"):
            line += f'\n   - In the row: "{t["row_text"]}"'
        if t.get("section"):
            line += f'\n   - In section: "{t["section"]}"'
        if s.get("result_url"):
            line += f"\n   - Leads to {s['result_url']}"
    elif a == "type":
        val = "<sensitive value — ask the user / use stored credential>" if s.get("sensitive") else f'"{s.get("value")}"'
        line = f"Fill the {s.get('target_label')} with {val}"
    elif a == "press_enter":
        line = f"Press Enter in the {s.get('target_label')}" + (f" → leads to {s['result_url']}" if s.get("result_url") else "")
    elif a == "submit":
        line = "Submit the form" + (f" → leads to {s['result_url']}" if s.get("result_url") else "")
    elif a == "navigate":
        line = f"Go to {s.get('url')}"
    elif a == "switch_tab":
        line = f"Switch to the tab {s.get('url')}"
    elif a == "open_tab":
        line = f"Open a new tab on {s.get('url')}"
    else:
        line = f"{a} {s.get('url') or ''}"
    out = f"{s['index']}. " + (f"{where} " if where else "") + line
    if s.get("narration"):
        out += f'\n   - User said: "{s["narration"]}"'
    return out


def build_skill_markdown(session: dict) -> str:
    steps = session["steps"]
    goal = session.get("goal") or (
        f"{session['title']} (no goal was given: infer it from the steps below)" if session.get("title")
        else "Reproduce the procedure the user demonstrated.")
    lines = [
        f"# {session.get('title') or 'Recorded procedure'}",
        "",
        "## Goal",
        goal,
        "",
        "## Applications involved (in order)",
        ", ".join(session.get("apps") or []) or "—",
        "",
        "## Accounts needed",
        "This procedure runs on signed-in web apps: " + (", ".join(a["app"] for a in session.get("accounts") or []) or "—") + ".",
        "If a login page appears: use the stored credentials offered for that site (fill them with the secret-filling action, "
        "including the one-time code if requested). If no credential is offered, or a code is sent by SMS/e-mail, "
        "stop and report which site needs a login. Never type or guess passwords yourself.",
        "",
        "## Demonstrated steps",
        "The user performed this task once while narrating. Reproduce the same intent.",
        "Selectors, links and typed values are hints from the recording: if the UI differs, adapt and find the equivalent element.",
        "Values typed during the recording may be example data: when the task gives new inputs (order ID, customer, dispute…), use those instead.",
        "",
    ]
    lines += [describe_step(s) for s in steps]
    if session.get("closing_narration"):
        lines += ["", "## Final remarks from the user", f'"{session["closing_narration"]}"']
    if session.get("transcript"):
        lines += ["", "## Full narration transcript", session["transcript"]]
    lines += [
        "",
        "## Output",
        "When done, report what you found/did for each application, and flag any step that could not be reproduced.",
    ]
    return "\n".join(lines)
