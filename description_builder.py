"""
Monta a Descrição Detalhada (texto corrido, sem citar lógicas) cruzando o diagrama de automação (.drawio)
com os ajustes dos relés (.rdb) e o SCD, e aponta divergências entre eles.
"""
import re

from diagram_reader import equipment_key
from sel_analyzer import _relay_equations, _signal_description, split_equation

GENERATION_RE = re.compile(r"T[ÉE]RMICA|USINA|UFV|UTE|UHE|PCH|CGH|EOL|E[ÓO]LICA|SOLAR|FOTOVOLT|GERA[ÇC][ÃA]O|BIOG|BIOM", re.I)
PROTECTION_KEYS = ["CTR", "CTRN", "PTR", "VNOM", "50P1P", "50P1D", "50G1P", "50G1D", "50N1P", "51P1P", "51P1C",
                   "51P1TD", "51G1P", "51G1C", "51G1TD", "51N1P", "51N1C", "51N1TD"]


def _join(items):
    items = list(dict.fromkeys(items))
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " e " + items[-1]


def _label(key):
    if key.startswith("52-"):
        return f"disjuntor {key}"
    if key.startswith("TR-"):
        return f"transformador {key}"
    if key.startswith("AL-"):
        return f"alimentador {key}"
    return key


def _labels(keys):
    """['52-2','52-3'] -> 'disjuntores 52-2 e 52-3'."""
    keys = list(dict.fromkeys(keys))
    kinds = {k.split("-")[0] for k in keys}
    if len(keys) > 1 and len(kinds) == 1:
        plural = {"52": "disjuntores", "TR": "transformadores", "AL": "alimentadores"}.get(kinds.pop(), "")
        return f"{plural} {_join(keys)}".strip()
    return _join([_label(k) for k in keys])


def _art(keys, sing="do", plur="dos"):
    return plur if len(set(keys)) > 1 else sing


def _affected_by(eqs, start_vars):
    affected, changed = set(start_vars), True
    while changed:
        changed = False
        for var, exprs in eqs.items():
            if var not in affected and any(re.search(rf"\b{re.escape(a)}T?\b", e) for a in affected for e in exprs):
                affected.add(var)
                changed = True
    return affected


def _protection_off(settings: dict, group: int) -> bool:
    g = settings.get(str(group), {})
    expr, _ = split_equation(g.get("TR", ""))
    if expr.strip() == "0":
        return True
    pickups = [g.get(k, "OFF") for k in ("50P1P", "51P1P", "50G1P", "51G1P", "50N1P", "51N1P")]
    return all(p in ("OFF", "") for p in pickups)


def build_description(analysis: dict, facts: dict | None):
    facts = facts or {"trips": [], "group_assignments": [], "groups_without_settings": [], "annotations": [],
                      "names": {}, "feeder_of": {}, "equipment": []}
    settings = analysis.get("_settings", {})
    relay_of = {equipment_key(r): r for r in settings}
    eqs = {equipment_key(r): {k: [e for _, e in v] for k, v in _relay_equations(s).items()} for r, s in settings.items()}
    warnings = []
    paragraphs = []

    # ------------------------------------------------------------------ GOOSE x diagrama
    scd_trips, blocks, supervised = set(), {}, set()
    for e in analysis["goose_entries"]:
        if not e["sub"] or not e["vb"]:
            continue
        sub, pub = equipment_key(e["sub"]), equipment_key(e["pub"])
        uses = set(analysis["vb_usage"].get(f"{e['sub']}|{e['vb']}", []))
        if not uses:
            continue
        if e["quality"]:
            supervised.add(sub)
            continue
        affected = _affected_by(eqs.get(sub, {}), uses)
        if "TR" in affected:
            scd_trips.add((pub, sub))
        elif "CL" in affected:
            blocks.setdefault(pub, set()).add(sub)

    diagram_trips = set(facts["trips"])
    if facts["equipment"]:
        for a, b in sorted(diagram_trips - scd_trips):
            if analysis["goose_entries"]:
                warnings.append(f"Diagrama: há TRIP do {_label(a)} para o {_label(b)}, mas não foi encontrado GOOSE de "
                                f"disparo correspondente no SCD e nas lógicas dos relés.")
        for a, b in sorted(scd_trips - diagram_trips):
            warnings.append(f"Diagrama: o SCD tem disparo por GOOSE do {_label(a)} para o {_label(b)}, "
                            f"que não está representado no diagrama.")

    all_trips = diagram_trips | scd_trips
    trip_text = []
    by_sources = {}
    for a, b in all_trips:
        by_sources.setdefault(b, set()).add(a)
    grouped = {}
    for b, sources in by_sources.items():
        grouped.setdefault(frozenset(sources), []).append(b)
    names, feeders = facts.get("names", {}), facts.get("feeder_of", {})
    # Ordena para começar pela origem da cadeia (transformadores antes dos disjuntores)
    for sources, targets in sorted(grouped.items(), key=lambda x: (not any(s.startswith("TR") for s in x[0]), sorted(x[0]))):
        src, tgt = sorted(sources), sorted(targets)
        trip_text.append(f"A atuação da proteção {_art(src)} {_labels(src)} passou a comandar a abertura "
                         f"{_art(tgt)} {_labels(tgt)} por meio de mensagens GOOSE.")
        for b in tgt:
            feeder = feeders.get(b)
            name = names.get(feeder, "") if feeder else ""
            if feeder and GENERATION_RE.search(name):
                trip_text.append(f"Como o {_label(b)} conecta o {_label(feeder)}, ao qual está ligada a geração {name}, "
                                 "essa transferência de disparo desconecta a geração sempre que a fonte é interrompida, "
                                 "evitando a operação ilhada e o religamento fora de sincronismo.")
    if trip_text and not any("ilhada" in t for t in trip_text):
        trip_text.append("Com isso, a falta é eliminada de forma coordenada e o trecho afetado é isolado sem depender "
                         "de fiação entre painéis.")
    for pub, subs in sorted(blocks.items()):
        trip_text.append(f"A proteção {_art([pub])} {_label(pub)} também envia a condição de bloqueio "
                         f"{_art(list(subs), 'ao', 'aos')} {_labels(sorted(subs))}, impedindo o fechamento enquanto o "
                         "bloqueio não for rearmado.")
    if supervised:
        dnp_fail = any("GOOSE" in c["description"].upper() and "FALHA" in c["description"].upper()
                       for c in analysis.get("dnp_changes", []))
        trip_text.append("A qualidade das mensagens é supervisionada nos relés receptores: em caso de falha de "
                         "comunicação, o comando é desconsiderado"
                         + (" e a falha é sinalizada ao supervisório." if dnp_fail else " e a falha fica disponível para alarme."))
    if trip_text:
        paragraphs.append(" ".join(trip_text))

    # ------------------------------------------------------------------ Grupos de ajuste
    group_text = []
    relays_with_groups = sorted({g["relay"] for g in facts["group_assignments"]} |
                                {g["relay"] for g in facts["groups_without_settings"] if g["relay"]})
    for relay in relays_with_groups:
        parts = []
        items = [(g["group"], f"assume os ajustes do {_label(g['source'])}") for g in facts["group_assignments"]
                 if g["relay"] == relay]
        items += [(g["group"], "permanece sem ajustes de proteção") for g in facts["groups_without_settings"]
                  if g["relay"] == relay]
        for group, phrase in sorted(items, key=lambda x: (x[0] is None, x[0] or 0)):
            parts.append(f"no Grupo {group} {phrase}" if group else phrase)
        sentence = (f"O relé do {_label(relay)} pode assumir a função de outros disjuntores por meio dos grupos de "
                    f"ajuste: {_join(parts)}.")
        new_sets = [c["new_expr"] for c in analysis["logic_changes"]
                    if equipment_key(c["relay"]) == relay and re.match(r"^SET\d+$", c["variable"])]
        local = any(re.search(r"\bPB\d", e) for e in new_sets)
        remote = any(re.search(r"\bRB\d", e) for e in new_sets)
        if local or remote:
            how = "localmente, pelo painel frontal, ou remotamente, pelo supervisório" if local and remote else (
                "localmente, pelo painel frontal" if local else "remotamente, pelo supervisório")
            sentence += f" A seleção do grupo é feita {how}"
            leds = any(equipment_key(c["relay"]) == relay and c["variable"].endswith("_LED") for c in analysis["logic_changes"])
            sentence += ", com indicação do grupo ativo no painel." if leds else "."
        sentence += (" Assim, o circuito permanece protegido durante a indisponibilidade ou manutenção do disjuntor "
                     "original, sem necessidade de reprogramar o relé.")
        group_text.append(sentence)

        # Cruzamento: o grupo tem os mesmos ajustes do disjuntor de origem?
        rs = settings.get(relay_of.get(relay, ""), {})
        for g in facts["group_assignments"]:
            if g["relay"] != relay:
                continue
            if not g["group"]:
                warnings.append(f"Diagrama: não foi possível identificar em qual grupo o {_label(relay)} assume os "
                                f"ajustes do {_label(g['source'])}.")
                continue
            src = settings.get(relay_of.get(g["source"], ""), {})
            if not rs or not src:
                continue
            mine, theirs = rs.get(str(g["group"]), {}), src.get("1", {})
            diffs = [f"{k} {mine.get(k)} x {theirs.get(k)}" for k in PROTECTION_KEYS
                     if k in mine and k in theirs and mine.get(k) != theirs.get(k)]
            if diffs:
                warnings.append(f"Diagrama: o {_label(relay)} deveria assumir no Grupo {g['group']} os ajustes do "
                                f"{_label(g['source'])} (Grupo 1), mas {len(diffs)} ajuste(s) diferem: "
                                f"{'; '.join(diffs[:6])}{'...' if len(diffs) > 6 else ''}.")
        for g in facts["groups_without_settings"]:
            if g["relay"] == relay and rs and not _protection_off(rs, g["group"]):
                warnings.append(f"Diagrama: o Grupo {g['group']} do {_label(relay)} aparece como \"sem ajuste\", "
                                "mas o relé tem proteção habilitada nesse grupo.")

    if not relays_with_groups:
        for c_relay in sorted({c["relay"] for c in analysis["logic_changes"] if c["variable"].startswith("SS")}):
            group_text.append(f"No {_label(equipment_key(c_relay))}, a seleção dos grupos de ajuste foi reorganizada, "
                              "permitindo adequar a proteção às diferentes condições operativas.")
    if group_text:
        paragraphs.append(" ".join(group_text))

    # ------------------------------------------------------------------ Sinalizações
    signal_text = []
    reverse, normal, others = {}, [], []
    for a in facts["annotations"]:
        text, eq = a["text"], a["equipment"]
        if re.search(r"fluxo\s+(de\s+pot[êe]ncia\s+)?invers", text, re.I) and eq:
            m = re.search(r"grupo\s*(\d)", text, re.I)
            reverse[eq] = int(m.group(1)) if m else None
        elif re.search(r"\bnormal", text, re.I) and eq:
            normal.append(eq)
        else:
            others.append(a)
    if not reverse:
        for c in analysis.get("dnp_changes", []):
            if re.match(r"^3PWR\dP$", c["variable"]):
                reverse.setdefault(equipment_key(c["relay"]), None)
    if reverse:
        keys = sorted(reverse)
        gen = any(GENERATION_RE.search(n) for n in names.values())
        sentence = (f"{'Os relés' if len(keys) > 1 else 'O relé'} {_art(keys)} {_labels(keys)} "
                    f"{'passaram' if len(keys) > 1 else 'passou'} a sinalizar ao supervisório o fluxo de potência inverso, "
                    "por meio da função direcional de potência (32)")
        cond = [f"no {_label(k)}, essa sinalização vale quando o relé opera no Grupo {g}" for k, g in reverse.items() if g]
        sentence += ("; " + "; ".join(cond)) if cond else ""
        sentence += (", o que permite identificar a injeção de potência da geração em direção à fonte." if gen
                     else ", o que permite identificar a inversão do sentido da potência.")
        signal_text.append(sentence)
        for k in keys:
            rs = settings.get(relay_of.get(k, ""), {})
            enabled = any(rs.get(str(g), {}).get("EPWR", "N") not in ("N", "") for g in range(1, 5))
            if rs and not enabled:
                warnings.append(f"Diagrama: o {_label(k)} deveria sinalizar fluxo inverso, mas a função de potência "
                                "não está habilitada em nenhum grupo.")
    group_points = sorted({equipment_key(c["relay"]) for c in analysis.get("dnp_changes", [])
                           if re.search(r"GRUPO", c["description"], re.I)})
    if group_points:
        signal_text.append(f"Também foram disponibilizadas ao supervisório as indicações de grupo de ajuste ativo "
                           f"{_art(group_points)} {_labels(group_points)}.")
    if normal:
        keys = sorted(set(normal))
        signal_text.append(f"{'Os relés' if len(keys) > 1 else 'O relé'} {_art(keys)} {_labels(keys)} "
                           f"{'mantêm' if len(keys) > 1 else 'mantém'} a atuação normal da proteção.")
    for a in others:
        text = re.sub(r"\b[0-9]*[A-Z][A-Z0-9_]*\d[A-Z0-9_]*\b",
                      lambda m: _signal_description(m.group(0), {}, {}, {}) or m.group(0), a["text"])
        where = f"No {_label(a['equipment'])}, conforme o diagrama: " if a["equipment"] else "Conforme o diagrama: "
        signal_text.append(where + text.rstrip(".") + ".")
    if signal_text:
        paragraphs.append(" ".join(signal_text))

    # Equipamentos do diagrama sem ajustes nos arquivos
    cited = {k for t in facts["trips"] for k in t} | {g["relay"] for g in facts["group_assignments"]} | set(reverse)
    for k in sorted(cited):
        if k.startswith("52-") and settings and k not in relay_of:
            warnings.append(f"Diagrama: o {_label(k)} aparece no diagrama, mas os ajustes do relé dele não estão no .rdb novo.")

    if not paragraphs:
        paragraphs.append("Não foram identificadas alterações de proteção, comunicação GOOSE ou sinalização "
                          "entre os arquivos analisados.")
    return "\n\n".join(paragraphs), warnings
