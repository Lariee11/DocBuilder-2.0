"""
Análise de arquivos SEL (AcSELerator QuickSet .rdb e AcSELerator Architect .scd).

- Extrai os ajustes de cada relé contidos nos .rdb (arquivos OLE com set_*.txt)
- Compara backup x novo e identifica as lógicas desenvolvidas/alteradas
- Lê o .scd e monta a matriz GOOSE (publicador, assinante, MAC, virtual bit, variável)
- Cruza as lógicas com os GOOSEs e aponta inconsistências
"""
import io
import re
import xml.etree.ElementTree as ET

import olefile

SCL_NS = {"s": "http://www.iec.ch/61850/2003/SCL"}

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

LOGIC_OPERATORS = re.compile(r"\b(AND|OR|NOT|R_TRIG|F_TRIG)\b")
VB_RE = re.compile(r"\bVB\d{3}\b")

# Ajustes de grupo/global que são equações SELogic mesmo sem operadores
LOGIC_KEYS = {"TR", "ULTRIP", "CL", "ULCL", "ER", "52A", "52B", "BLKCL", "TDURD_EQ"}
LOGIC_KEY_RE = re.compile(r"^(SV\d+|SET\d+|RST\d+|SS\d|OUT\d{3}|MV\d+|SC\d+\w*|PB\d+[AB]?_LED|LED\d+\w*|TLED_\d+|DP\d+|ER\w*)$")
# Contadores de habilitação da lógica (ELAT, ESV, ...) não são lógica em si
ENABLE_KEYS = {"ELAT", "ESV", "ESC", "EMV", "EMVS", "ELCL", "ESF"}

CLASS_LABELS = {
    "1": "Grupo 1", "2": "Grupo 2", "3": "Grupo 3", "4": "Grupo 4",
    "L1": "Lógica 1", "L2": "Lógica 2", "L3": "Lógica 3", "L4": "Lógica 4",
    "G": "Global", "F": "Painel Frontal",
}
# Classes analisadas na tabela de lógicas
LOGIC_CLASSES = ["G", "1", "2", "3", "4", "L1", "L2", "L3", "L4", "F"]


def normalize_name(name: str) -> str:
    """'ARE 52-2' e 'ARE_52_2' viram 'ARE522' para casar .rdb com .scd."""
    return re.sub(r"[^A-Z0-9]", "", (name or "").upper())


def norm_value(key: str, value: str) -> str:
    v = (value or "").replace('""', '"')
    v = re.sub(r"\s+", " ", v).strip()
    if re.match(r"SER\d", key):
        v = re.sub(r"[ ,]+", ",", v)
    if v in ("NA", ""):
        return ""
    return v


def split_equation(value: str):
    """'EXPR # COMENTARIO' -> ('EXPR', 'COMENTARIO')."""
    value = (value or "").replace('""', '"').strip()
    if "#" in value:
        # "0 # EQ ANTIGA # COMENTARIO": a expressão é o que vem antes do primeiro "#"
        # e o comentário é o que vem depois do último "#"
        expr = value.split("#", 1)[0]
        comment = value.rsplit("#", 1)[1]
        return expr.strip(), comment.strip()
    return value, ""


def is_logic_setting(cls: str, key: str, old: str, new: str) -> bool:
    if key in ENABLE_KEYS:
        return False
    if cls.startswith("L"):
        return True
    if key in LOGIC_KEYS or LOGIC_KEY_RE.match(key):
        return True
    for v in (old, new):
        if v and (LOGIC_OPERATORS.search(v) or "#" in v):
            return True
    return False


def compress_classes(classes):
    """['1','2','3','4'] -> 'Grupos 1–4'; ['L1','L2'] -> 'Lógicas 1, 2'."""
    def fmt(prefix_sing, prefix_plur, nums):
        nums = sorted(int(n) for n in nums)
        if len(nums) == 1:
            return f"{prefix_sing} {nums[0]}"
        if nums == list(range(nums[0], nums[-1] + 1)) and len(nums) > 2:
            return f"{prefix_plur} {nums[0]}–{nums[-1]}"
        return f"{prefix_plur} {', '.join(map(str, nums))}"

    groups = [c for c in classes if c.isdigit()]
    logics = [c[1:] for c in classes if c.startswith("L")]
    others = [CLASS_LABELS.get(c, c) for c in classes if not c.isdigit() and not c.startswith("L")]
    parts = []
    if groups:
        parts.append(fmt("Grupo", "Grupos", groups))
    if logics:
        parts.append(fmt("Lógica", "Lógicas", logics))
    parts.extend(others)
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# .RDB
# ---------------------------------------------------------------------------

def _parse_settings_text(text: str) -> dict:
    data = {}
    for line in text.splitlines():
        m = re.match(r'^([^\[,][^,]*),"(.*)"\s*$', line)
        if m:
            data[m.group(1)] = m.group(2)
    return data


def parse_rdb(content: bytes) -> dict:
    """Retorna {relé: {"info": {...}, "settings": {classe: {ajuste: valor}}}}."""
    if not olefile.isOleFile(io.BytesIO(content)):
        raise ValueError("O arquivo enviado não é um .rdb válido (formato OLE).")
    ole = olefile.OleFileIO(io.BytesIO(content))
    relays = {}
    try:
        for entry in ole.listdir(streams=True, storages=False):
            if len(entry) < 3 or entry[0] != "Relays":
                continue
            relay = entry[1]
            name = entry[-1]
            info = relays.setdefault(relay, {"info": {}, "settings": {}})
            raw = ole.openstream(entry).read().decode("latin-1", errors="replace")
            if len(entry) == 3 and name.startswith("set_") and name.endswith(".txt"):
                cls = name[4:-4]
                info["settings"][cls] = _parse_settings_text(raw)
            elif name == "Cfg.txt":
                for line in raw.splitlines():
                    if "=" in line and not line.startswith("["):
                        k, v = line.split("=", 1)
                        info["info"][k.strip()] = v.strip()
            elif name == "Version":
                info["info"]["Version"] = " | ".join(l.strip() for l in raw.splitlines() if l.strip())
    finally:
        ole.close()
    return relays


def diff_logics(backup: dict, novo: dict):
    """Compara as lógicas de backup x novo e agrupa alterações idênticas entre grupos/lógicas."""
    changes = []      # linhas agregadas
    settings_changes = {}  # ajustes não-lógicos alterados (para contexto da IA)
    for relay in sorted(novo):
        new_sets = novo[relay]["settings"]
        old_sets = backup.get(relay, {}).get("settings", {})
        aggregated = {}
        for cls in LOGIC_CLASSES + [c for c in new_sets if c not in LOGIC_CLASSES]:
            if cls not in new_sets:
                continue
            new_c = new_sets[cls]
            old_c = old_sets.get(cls, {})
            for key, new_v in new_c.items():
                old_v = old_c.get(key, "")
                if key not in old_c and norm_value(key, new_v) in ("", "0", "N", "OFF"):
                    continue  # ajuste criado pela versão nova do software, com valor padrão
                if norm_value(key, old_v) == norm_value(key, new_v):
                    continue
                if cls in LOGIC_CLASSES and is_logic_setting(cls, key, old_v, new_v):
                    sig = (key, norm_value(key, old_v), norm_value(key, new_v))
                    aggregated.setdefault(sig, {"key": key, "old": old_v, "new": new_v, "classes": []})["classes"].append(cls)
                elif cls in ("1", "2", "3", "4", "G") and key in old_c:
                    settings_changes.setdefault(relay, {}).setdefault((key, old_v, new_v), []).append(cls)
        for item in aggregated.values():
            old_expr, old_comment = split_equation(item["old"])
            new_expr, new_comment = split_equation(item["new"])
            old_n, new_n = norm_value("", old_expr), norm_value("", new_expr)
            if old_n == new_n:
                status = "Comentário alterado"
            elif new_n == "":
                status = "Removida"
            elif old_n in ("", "0"):
                status = "Nova"
            elif new_n == "0":
                status = "Desabilitada"
            else:
                status = "Alterada"
            changes.append({
                "relay": relay,
                "variable": item["key"],
                "scope": compress_classes(item["classes"]),
                "classes": item["classes"],
                "status": status,
                "old_expr": old_expr or "NA",
                "new_expr": new_expr or "NA",
                "old_comment": old_comment,
                "comment": new_comment or old_comment,
            })
    settings_list = []
    for relay, items in settings_changes.items():
        for (key, old_v, new_v), classes in items.items():
            settings_list.append({"relay": relay, "setting": key, "scope": compress_classes(classes),
                                  "old": old_v, "new": new_v})
    return changes, settings_list


def logic_rows(changes):
    rows = []
    for i, ch in enumerate(changes):
        desc = ch["comment"]
        status = ch["status"]
        if status in ("Alterada", "Removida", "Desabilitada"):
            detail = f"{status} (antes: {ch['old_expr']})"
        elif status == "Comentário alterado":
            detail = f"Comentário alterado (antes: {ch['old_comment'] or 'sem comentário'})"
        else:
            detail = "Nova lógica"
        rows.append({
            "id": i,
            "Equipamento": ch["relay"],
            "Variável": f"{ch['variable']} ({ch['scope']})",
            "Equação Lógica": ch["new_expr"],
            "Descrição": f"{desc}. {detail}." if desc else f"{detail}.",
        })
    return rows


# ---------------------------------------------------------------------------
# .SCD
# ---------------------------------------------------------------------------

def _ln_key(prefix, ln_class, inst):
    return f"{prefix or ''}{ln_class or ''}{inst or ''}"


def parse_scd(content: bytes) -> dict:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError(f"O arquivo .scd não é um XML válido: {exc}") from exc

    comm = {}
    for ap in root.iterfind(".//s:ConnectedAP", SCL_NS):
        ied = ap.get("iedName")
        addr = {p.get("type"): p.text for p in ap.iterfind("s:Address/s:P", SCL_NS)}
        entry = comm.setdefault(ied, {"ip": addr.get("IP", ""), "gse": {}})
        for gse in ap.iterfind("s:GSE", SCL_NS):
            g = {p.get("type"): p.text for p in gse.iterfind("s:Address/s:P", SCL_NS)}
            entry["gse"][(gse.get("ldInst"), gse.get("cbName"))] = {
                "mac": g.get("MAC-Address", ""), "appid": g.get("APPID", ""),
                "vlan": g.get("VLAN-ID", ""), "priority": g.get("VLAN-PRIORITY", ""),
                "min": gse.findtext("s:MinTime", namespaces=SCL_NS),
                "max": gse.findtext("s:MaxTime", namespaces=SCL_NS),
            }

    ieds = {}
    for ied in root.iterfind("s:IED", SCL_NS):
        name = ied.get("name")
        info = {"type": ied.get("type", ""), "manufacturer": ied.get("manufacturer", ""),
                "configVersion": ied.get("configVersion", ""), "desc": ied.get("desc", ""),
                "saddr": {}, "publications": [], "subscriptions": []}
        # Mapeia DOs para a variável interna do relé (sAddr="db:SV30T")
        for ld in ied.iter(f"{{{SCL_NS['s']}}}LDevice"):
            ld_inst = ld.get("inst")
            for ln in list(ld.iterfind("s:LN", SCL_NS)) + list(ld.iterfind("s:LN0", SCL_NS)):
                lnk = _ln_key(ln.get("prefix"), ln.get("lnClass"), ln.get("inst"))
                for doi in ln.iterfind("s:DOI", SCL_NS):
                    for dai in doi.iter(f"{{{SCL_NS['s']}}}DAI"):
                        if dai.get("name") == "stVal" and dai.get("sAddr"):
                            info["saddr"][(ld_inst, lnk, doi.get("name"))] = dai.get("sAddr").split(":")[-1]
            ln0 = ld.find("s:LN0", SCL_NS)
            if ln0 is None:
                continue
            datasets = {d.get("name"): d for d in ln0.iterfind("s:DataSet", SCL_NS)}
            for gc in ln0.iterfind("s:GSEControl", SCL_NS):
                ds = datasets.get(gc.get("datSet"))
                fcdas = []
                if ds is not None:
                    for f in ds.iterfind("s:FCDA", SCL_NS):
                        fcdas.append({"ld": f.get("ldInst"),
                                      "ln": _ln_key(f.get("prefix"), f.get("lnClass"), f.get("lnInst")),
                                      "do": f.get("doName"), "da": f.get("daName") or "", "fc": f.get("fc")})
                info["publications"].append({"ld": ld_inst, "cb": gc.get("name"), "datSet": gc.get("datSet"),
                                             "desc": gc.get("desc", ""), "confRev": gc.get("confRev"),
                                             "appID": gc.get("appID"), "fcdas": fcdas})
            for ext in ld.iterfind(".//s:Inputs/s:ExtRef", SCL_NS):
                if not ext.get("iedName"):
                    continue
                int_addr = (ext.get("intAddr") or "").split("|")[0]
                info["subscriptions"].append({
                    "vb": int_addr, "pub": ext.get("iedName"), "ld": ext.get("ldInst"),
                    "ln": _ln_key(ext.get("prefix"), ext.get("lnClass"), ext.get("lnInst")),
                    "do": ext.get("doName"), "da": ext.get("daName"),
                    "srcLD": ext.get("srcLDInst"), "cb": ext.get("srcCBName"),
                    "quality_bit": not ext.get("doName"),
                })
        ieds[name] = info
    return {"ieds": ieds, "comm": comm}


def _pub_variable(scd, pub, ld, ln, do):
    var = scd["ieds"].get(pub, {}).get("saddr", {}).get((ld, ln, do))
    ref = f"{ld}/{ln}.{do}"
    return f"{var} ({ref})" if var else ref


def goose_entries(scd: dict):
    """Lista de sinais GOOSE (um por virtual bit assinado + publicações sem assinante)."""
    entries = []
    subscribed = set()
    for sub_name, sub in scd["ieds"].items():
        for s in sub["subscriptions"]:
            gse = scd["comm"].get(s["pub"], {}).get("gse", {}).get((s["srcLD"], s["cb"]), {})
            if s["quality_bit"]:
                variable = f"Falha/qualidade da mensagem {s['cb']}"
                raw_var = "QUALIDADE"
            else:
                variable = _pub_variable(scd, s["pub"], s["ld"], s["ln"], s["do"])
                raw_var = scd["ieds"].get(s["pub"], {}).get("saddr", {}).get((s["ld"], s["ln"], s["do"]), "")
                subscribed.add((s["pub"], s["ld"], s["ln"], s["do"]))
            entries.append({"pub": s["pub"], "sub": sub_name, "cb": s["cb"], "mac": gse.get("mac", ""),
                            "appid": gse.get("appid", ""), "vlan": gse.get("vlan", ""), "vb": s["vb"],
                            "variable": variable, "raw_var": raw_var, "quality": s["quality_bit"]})
    for pub_name, pub in scd["ieds"].items():
        for p in pub["publications"]:
            gse = scd["comm"].get(pub_name, {}).get("gse", {}).get((p["ld"], p["cb"]), {})
            for f in p["fcdas"]:
                if (pub_name, f["ld"], f["ln"], f["do"]) in subscribed:
                    continue
                entries.append({"pub": pub_name, "sub": "", "cb": p["cb"], "mac": gse.get("mac", ""),
                                "appid": gse.get("appid", ""), "vlan": gse.get("vlan", ""), "vb": "",
                                "variable": _pub_variable(scd, pub_name, f["ld"], f["ln"], f["do"]),
                                "raw_var": scd["ieds"][pub_name]["saddr"].get((f["ld"], f["ln"], f["do"]), ""),
                                "quality": False})
    entries.sort(key=lambda e: (e["pub"], e["sub"] or "~", e["vb"]))
    return entries


def goose_rows(entries):
    rows = []
    for e in entries:
        mac = e["mac"] + (f" (APPID {e['appid']})" if e["appid"] else "")
        rows.append({
            "Publicador": f"{e['pub']} ({e['cb']})",
            "Assinante": e["sub"] or "Sem assinante no SCD",
            "MAC Mensagem": mac,
            "Virtual Bit": e["vb"] or "-",
            "Variável": e["variable"],
        })
    return rows


def _goose_signature(e):
    return (e["pub"], e["sub"], e["cb"], e["vb"], e["variable"])


# ---------------------------------------------------------------------------
# Cruzamento lógicas x GOOSE
# ---------------------------------------------------------------------------

def _relay_equations(relay_sets: dict):
    """{variável: [(classe, equação)]} das classes de lógica do arquivo novo."""
    eqs = {}
    for cls in LOGIC_CLASSES:
        for key, val in relay_sets.get(cls, {}).items():
            expr, _ = split_equation(val)
            if norm_value(key, expr):
                eqs.setdefault(key, []).append((cls, expr))
    return eqs


def cross_check(novo_rdb: dict, scd: dict, entries):
    warnings = []
    usage = {}  # (ied scd, vb) -> lista de variáveis que usam o VB
    rdb_by_norm = {normalize_name(r): r for r in novo_rdb}
    scd_by_norm = {normalize_name(i): i for i in scd["ieds"]}

    for n, r in rdb_by_norm.items():
        if n not in scd_by_norm:
            relay_eqs = _relay_equations(novo_rdb[r]["settings"])
            uses_vb = any(VB_RE.search(e) for lst in relay_eqs.values() for _, e in lst)
            if uses_vb:
                warnings.append(f"{r}: usa virtual bits (VB) na lógica, mas não está no SCD.")
    for n, i in scd_by_norm.items():
        if n not in rdb_by_norm:
            warnings.append(f"{i}: está no SCD, mas os ajustes dele não estão no .rdb novo (lógicas não verificadas).")

    for n, ied in scd_by_norm.items():
        relay = rdb_by_norm.get(n)
        if not relay:
            continue
        eqs = _relay_equations(novo_rdb[relay]["settings"])
        mapped = {e["vb"] for e in entries if e["sub"] == ied and e["vb"]}
        used = {}
        for var, lst in eqs.items():
            for cls, expr in lst:
                for vb in VB_RE.findall(expr):
                    used.setdefault(vb, set()).add(var)
        missing = []
        for vb, variables in sorted(used.items()):
            usage[(ied, vb)] = sorted(variables)
            if vb not in mapped:
                missing.append(f"{vb} ({', '.join(sorted(variables))})")
        if missing:
            warnings.append(f"{relay}: virtual bits usados na lógica mas não assinados no SCD (ficam sempre em 0): "
                            f"{'; '.join(missing)}.")
        unused = sorted(mapped - set(used))
        if unused:
            warnings.append(f"{relay}: virtual bits assinados no SCD mas não usados em nenhuma lógica: {', '.join(unused)}.")

        # Variáveis SV publicadas por GOOSE que estão vazias (NA) na lógica do publicador
        for e in entries:
            if e["pub"] != ied or e["quality"] or not re.match(r"^SV\d+T$", e["raw_var"] or ""):
                continue
            sv = e["raw_var"][:-1]
            if sv not in eqs:
                warnings.append(f"{relay}: publica {e['raw_var']} por GOOSE, mas {sv} está vazia (NA) na lógica.")

    # Quem publica mas não tem assinante
    for e in entries:
        if not e["sub"]:
            warnings.append(f"{e['pub']}: publica {e['variable']} ({e['cb']}), mas nenhum IED do SCD assina esse sinal.")
    for ied, info in scd["ieds"].items():
        if not info["publications"] and not info["subscriptions"]:
            warnings.append(f"{ied}: não publica nem assina nenhum GOOSE no SCD.")
    # Remove duplicados mantendo ordem
    seen, unique = set(), []
    for w in warnings:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    return unique, usage


# ---------------------------------------------------------------------------
# Mapa DNP
# ---------------------------------------------------------------------------

DNP_TYPES = {
    "BI": "Entrada binária (BI)",
    "BO": "Saída binária (BO)",
    "AI": "Entrada analógica (AI)",
    "AO": "Saída analógica (AO)",
    "CO": "Contador (CO)",
}

# Descrições de elementos e grandezas comuns dos relés SEL
KNOWN_SIGNALS = [
    (r"^52A$", "Disjuntor fechado"),
    (r"^52B$", "Disjuntor aberto"),
    (r"^OC\d?$", "Comando de abertura do disjuntor"),
    (r"^CC\d?$", "Comando de fechamento do disjuntor"),
    (r"^TRIP$", "Disparo do relé"),
    (r"^IN(\d{3})$", "Entrada digital {0}"),
    (r"^OUT(\d{3})$", "Saída digital {0}"),
    (r"^RB(\d+)$", "Bit remoto {0}"),
    (r"^PB(\d+)$", "Botão {0} do painel frontal"),
    (r"^SG(\d)$", "Grupo de ajuste {0} ativo"),
    (r"^3PWR(\d)P$", "Elemento de potência trifásica nível {0} (32)"),
    (r"^(\d)?PWR(\d)T$", "Disparo do elemento de potência nível {1} (32)"),
    (r"^79RS$", "Religador em reset"),
    (r"^79CY$", "Religador em ciclo"),
    (r"^79LO$", "Religador bloqueado"),
    (r"^(50|51|67)([PNGQ]|[ABC])(\d)?([PT])$", "Elemento {0}{1}{2} {3}"),
    (r"^I([ABCGN])_MAG$", "Corrente da fase {0}"),
    (r"^I([ABCGN])_ANG$", "Ângulo da corrente {0}"),
    (r"^V([ABC]{1,2}|S)_MAG$", "Tensão {0}"),
    (r"^V([ABC]{1,2}|S)_ANG$", "Ângulo da tensão {0}"),
    (r"^P(_F)?$", "Potência ativa trifásica"),
    (r"^Q(_F)?$", "Potência reativa trifásica"),
    (r"^S(_F)?$", "Potência aparente trifásica"),
    (r"^PF(_F)?$", "Fator de potência"),
    (r"^FREQ$", "Frequência"),
    (r"^MV(\d+)$", "Variável matemática {0}"),
]
PICKUP_OR_TRIP = {"P": "(partida)", "T": "(disparo)"}


def _comment_map(relay_sets: dict):
    """{variável: comentário} a partir das lógicas do relé (SVnn, SETnn->LTnn, MVnn, ...)."""
    own, users = {}, {}
    for cls in LOGIC_CLASSES:
        for key, val in relay_sets.get(cls, {}).items():
            expr, comment = split_equation(val)
            if not comment or not norm_value(key, expr):
                continue
            m = re.match(r"^SET(\d+)$", key)
            target = f"LT{m.group(1)}" if m else key
            own.setdefault(target, comment)
            for token in re.findall(r"\b[A-Z0-9_]+\b", expr):
                users.setdefault(token, comment)
    return own, users


def _signal_description(var: str, own: dict, users: dict, goose_by_vb: dict) -> str:
    base = var[:-1] if re.match(r"^SV\d+T$", var) else var
    if base in own:
        return own[base]
    if var in goose_by_vb:
        return goose_by_vb[var]
    for pattern, text in KNOWN_SIGNALS:
        m = re.match(pattern, var)
        if m:
            groups = [g or "" for g in m.groups()]
            if pattern.startswith("^(50|51|67)"):
                return f"Elemento {groups[0]}{groups[1]}{groups[2]} {PICKUP_OR_TRIP.get(groups[3], '')}".strip()
            desc = text.format(*groups)
            if re.match(r"^(RB|PB|IN|OUT)\d", var) and var in users:
                desc += f" - {users[var]}"
            return desc
    if var in users:
        return f"Usado na lógica: {users[var]}"
    return ""


def _dnp_value(value: str):
    """'IA_MAG:10.000:5' -> ('IA_MAG', 'escala 10.000, banda morta 5')."""
    parts = (value or "").split(":")
    extra = []
    if len(parts) > 1 and parts[1]:
        extra.append(f"escala {parts[1]}")
    if len(parts) > 2 and parts[2]:
        extra.append(f"banda morta {parts[2]}")
    return parts[0].strip(), ", ".join(extra)


def diff_dnp(backup: dict, novo: dict, goose: list):
    """Pontos dos mapas DNP (D1, D2, ...) que receberam uma variável nova em relação ao backup."""
    changes = []
    for relay in sorted(novo):
        new_sets = novo[relay]["settings"]
        old_sets = backup.get(relay, {}).get("settings", {})
        own, users = _comment_map(new_sets)
        goose_by_vb = {}
        for e in goose:
            if e["sub"] and normalize_name(e["sub"]) == normalize_name(relay) and e["vb"]:
                goose_by_vb[e["vb"]] = (f"Falha de comunicação GOOSE com {e['pub']}" if e["quality"]
                                        else f"Recebido por GOOSE de {e['pub']}: {e['raw_var'] or e['variable']}")
        aggregated = {}
        for cls in sorted(c for c in new_sets if re.match(r"^D\d+$", c)):
            old_c = old_sets.get(cls, {})
            for key, value in new_sets[cls].items():
                m = re.match(r"^([A-Z]{2})_(\d+)$", key)
                if not m:
                    continue
                var, extra = _dnp_value(value)
                old_var, _ = _dnp_value(old_c.get(key, ""))
                if norm_value(key, var) == "" or var == old_var:
                    continue
                sig = (m.group(1), int(m.group(2)), var, extra)
                aggregated.setdefault(sig, []).append(cls[1:])
        for (ptype, index, var, extra), maps in sorted(aggregated.items(), key=lambda x: (x[0][0], x[0][1])):
            changes.append({"relay": relay, "type": ptype, "index": index, "variable": var, "extra": extra,
                            "maps": maps, "description": _signal_description(var, own, users, goose_by_vb)})
    return changes


def signal_rows(changes):
    rows = []
    for c in changes:
        maps = sorted(int(m) for m in c["maps"])
        if len(maps) == 1:
            maps_txt = f"mapa DNP {maps[0]}"
        elif maps == list(range(maps[0], maps[-1] + 1)) and len(maps) > 2:
            maps_txt = f"mapas DNP {maps[0]}–{maps[-1]}"
        else:
            maps_txt = "mapas DNP " + ", ".join(map(str, maps))
        tipo = DNP_TYPES.get(c["type"], c["type"])
        if c["type"] == "BI":
            func = "Estado enviado ao supervisório (1 = ativo, 0 = inativo)."
        elif c["type"] == "BO":
            func = f"Comando do supervisório que aciona {c['variable']}."
        elif c["type"] == "AI":
            func = "Medição enviada ao supervisório" + (f" ({c['extra']})." if c["extra"] else ".")
        elif c["type"] == "AO":
            func = "Valor analógico recebido do supervisório."
        else:
            func = "Contador enviado ao supervisório."
        rows.append({
            "Equipamento": c["relay"],
            "Tipo do Ponto": f"{tipo} - índice {c['index']} ({maps_txt})",
            "Variável": c["variable"],
            "Descrição": c["description"],
            "Funcionamento": func,
        })
    return rows


# ---------------------------------------------------------------------------
# Análise completa
# ---------------------------------------------------------------------------

def analyze(backup_rdb: bytes | None, novo_rdb: bytes | None, backup_scd: bytes | None, novo_scd: bytes | None):
    result = {"logic_changes": [], "settings_changes": [], "goose_entries": [], "goose_diff": {},
              "warnings": [], "relays": {}, "ieds": {}, "vb_usage": {}, "dnp_changes": []}

    novo = parse_rdb(novo_rdb) if novo_rdb else {}
    backup = parse_rdb(backup_rdb) if backup_rdb else {}
    if novo:
        changes, settings_list = diff_logics(backup, novo)
        result["logic_changes"] = changes
        result["settings_changes"] = settings_list
        for relay, data in novo.items():
            old_info = backup.get(relay, {}).get("info", {})
            result["relays"][relay] = {
                "tipo": data["info"].get("RELAYTYPE", ""), "firmware": data["info"].get("FID", ""),
                "versao_novo": data["info"].get("Version", ""), "versao_backup": old_info.get("Version", ""),
                "no_backup": relay in backup,
            }
        for relay in backup:
            if relay not in novo:
                result["warnings"].append(f"{relay}: existe no .rdb de backup, mas não no .rdb novo.")

    if novo_scd:
        scd = parse_scd(novo_scd)
        entries = goose_entries(scd)
        result["goose_entries"] = entries
        result["ieds"] = {name: {"tipo": i["type"], "ip": scd["comm"].get(name, {}).get("ip", ""),
                                 "modelo_icd": i["configVersion"]} for name, i in scd["ieds"].items()}
        if backup_scd:
            old_entries = goose_entries(parse_scd(backup_scd))
            old_sig = {_goose_signature(e) for e in old_entries}
            new_sig = {_goose_signature(e) for e in entries}
            result["goose_diff"] = {
                "adicionados": [e for e in entries if _goose_signature(e) not in old_sig],
                "removidos": [e for e in old_entries if _goose_signature(e) not in new_sig],
            }
        if novo:
            warnings, usage = cross_check(novo, scd, entries)
            result["warnings"].extend(warnings)
            result["vb_usage"] = {f"{k[0]}|{k[1]}": v for k, v in usage.items()}

    if novo:
        result["dnp_changes"] = diff_dnp(backup, novo, result["goose_entries"])

    result["logic_rows"] = logic_rows(result["logic_changes"])
    result["signal_rows"] = signal_rows(result["dnp_changes"])
    result["goose_rows"] = goose_rows(result["goose_entries"])
    return result


