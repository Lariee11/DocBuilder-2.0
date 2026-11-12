"""
Leitura de diagramas simplificados de automação feitos no draw.io (.drawio / .xml).

Extrai os textos, blocos e ligações do desenho e interpreta, por regras:
- equipamentos (disjuntores 52-x, transformadores TR-x, alimentadores AL-x) e nomes associados;
- relés (imagens) ligados a cada disjuntor;
- setas de TRIP entre relés;
- seleção de grupos (GP1, GP2...) e textos como "52-3 assume o ajuste do 52-1" ou "Sem ajuste";
- anotações livres associadas ao equipamento mais próximo (ex.: "Sinaliza fluxo inverso").
"""
import base64
import html
import math
import re
import urllib.parse
import xml.etree.ElementTree as ET
import zlib

BREAKER_RE = re.compile(r"^\s*52\s*-\s*(\d+)\s*$")
TRAFO_RE = re.compile(r"^\s*TR\s*-\s*(\d+)\s*$", re.I)
FEEDER_RE = re.compile(r"^\s*AL\s*-\s*(\d+)\s*$", re.I)
GROUP_RE = re.compile(r"^\s*GP\s*(\d)\s*$", re.I)
ASSUME_RE = re.compile(r"(52\s*-\s*\d+)\s+assume\s+o\s+ajuste\s+do\s+(52\s*-\s*\d+)", re.I)
NO_SETTING_RE = re.compile(r"^\s*sem\s+ajuste\s*$", re.I)
TRIP_RE = re.compile(r"^\s*trip\s*$", re.I)

NEAR_EDGE = 45      # distância máxima (px) de um texto até a linha para ser considerado rótulo dela
NEAR_ITEM = 260     # distância máxima (px) para associar anotações a um equipamento


def equipment_key(name: str) -> str:
    """Chave comum para nomes do diagrama, do .rdb e do .scd ('ARE 52-2', 'ARE_52_2' -> '52-2'; 'ARE_T1' -> 'TR-1')."""
    n = (name or "").upper().replace("_", " ")
    m = re.search(r"52\s*-?\s*(\d+)", n)
    if m:
        return f"52-{int(m.group(1))}"
    m = re.search(r"(?<![A-Z0-9])TR?\s*-?\s*(\d+)\b", n)
    if m:
        return f"TR-{int(m.group(1))}"
    m = re.search(r"(?<![A-Z0-9])AL\s*-?\s*(\d+)\b", n)
    if m:
        return f"AL-{int(m.group(1))}"
    return n.strip()


def _clean_text(value: str) -> str:
    text = re.sub(r"<br\s*/?>|</div>|</p>", " ", value or "", flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _model_root(content: bytes) -> ET.Element:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError(f"O diagrama não é um arquivo .drawio/.xml válido: {exc}") from exc
    if root.tag == "mxGraphModel":
        return root
    diagram = root.find("diagram") if root.tag == "mxfile" else None
    if diagram is None:
        raise ValueError("O arquivo não contém um diagrama do draw.io.")
    model = diagram.find("mxGraphModel")
    if model is not None:
        return model
    data = (diagram.text or "").strip()
    if not data:
        raise ValueError("O diagrama do draw.io está vazio.")
    try:
        xml_text = urllib.parse.unquote(zlib.decompress(base64.b64decode(data), -15).decode("utf-8"))
        return ET.fromstring(xml_text)
    except Exception as exc:  # formato compactado inesperado
        raise ValueError("Não foi possível descompactar o diagrama do draw.io.") from exc


def parse_drawio(content: bytes) -> dict:
    model = _model_root(content)
    cells = {}
    for cell in model.iter("mxCell"):
        geo = cell.find("mxGeometry")
        cells[cell.get("id")] = {"el": cell, "geo": geo}
    # Células dentro de <object>/<UserObject> (rótulo fica no objeto pai)
    for obj in list(model.iter("object")) + list(model.iter("UserObject")):
        cell = obj.find("mxCell")
        if cell is not None:
            cells[obj.get("id")] = {"el": cell, "geo": cell.find("mxGeometry"), "label": obj.get("label", "")}

    def offset(cid, depth=0):
        """Posição absoluta do canto superior esquerdo de um contêiner (grupos usam coordenadas relativas)."""
        c = cells.get(cid)
        if not c or depth > 20 or c["el"].get("vertex") != "1" or c["geo"] is None:
            return 0.0, 0.0
        px, py = offset(c["el"].get("parent"), depth + 1)
        return px + float(c["geo"].get("x", 0)), py + float(c["geo"].get("y", 0))

    vertices, edges = {}, {}
    for cid, c in cells.items():
        el, geo = c["el"], c["geo"]
        text = _clean_text(c.get("label") or el.get("value", ""))
        style = el.get("style", "") or ""
        parent = el.get("parent")
        if el.get("edge") == "1":
            pts = {"src": None, "tgt": None, "way": []}
            if geo is not None:
                for p in geo.findall("mxPoint"):
                    if p.get("as") == "sourcePoint":
                        pts["src"] = (float(p.get("x", 0)), float(p.get("y", 0)))
                    elif p.get("as") == "targetPoint":
                        pts["tgt"] = (float(p.get("x", 0)), float(p.get("y", 0)))
                arr = geo.find("Array")
                if arr is not None:
                    pts["way"] = [(float(p.get("x", 0)), float(p.get("y", 0))) for p in arr.findall("mxPoint")]
            edges[cid] = {"id": cid, "text": text, "style": style, "source": el.get("source"),
                          "target": el.get("target"), "pts": pts, "parent": parent}
        elif el.get("vertex") == "1" and geo is not None:
            px, py = offset(parent)
            x, y = px + float(geo.get("x", 0)), py + float(geo.get("y", 0))
            w, h = float(geo.get("width", 0)), float(geo.get("height", 0))
            vertices[cid] = {"id": cid, "text": text, "style": style, "x": x, "y": y, "w": w, "h": h,
                             "cx": x + w / 2, "cy": y + h / 2, "parent": parent,
                             "is_image": "image" in style or "shape=image" in style}

    # Rótulos de linha criados como filhos da linha
    for v in list(vertices.values()):
        if v["parent"] in edges:
            if v["text"]:
                edges[v["parent"]]["text"] = (edges[v["parent"]]["text"] + " " + v["text"]).strip()
            del vertices[v["id"]]

    # Pontos das linhas (centro do bloco ligado, quando houver)
    for e in edges.values():
        src = vertices.get(e["source"])
        tgt = vertices.get(e["target"])
        a = (src["cx"], src["cy"]) if src else e["pts"]["src"]
        b = (tgt["cx"], tgt["cy"]) if tgt else e["pts"]["tgt"]
        e["poly"] = [p for p in [a, *e["pts"]["way"], b] if p is not None]
        e["start"], e["end"] = (e["poly"][0], e["poly"][-1]) if e["poly"] else (None, None)
    return {"vertices": vertices, "edges": edges}


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _dist_point_segment(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return _dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
    return _dist(p, (ax + t * dx, ay + t * dy))


def _dist_point_poly(p, poly):
    if len(poly) == 1:
        return _dist(p, poly[0])
    return min(_dist_point_segment(p, poly[i], poly[i + 1]) for i in range(len(poly) - 1))


def interpret(diagram: dict) -> dict:
    vertices, edges = diagram["vertices"], diagram["edges"]
    equipment = {}   # chave -> vértice
    groups = {}      # número do grupo -> vértice com o texto GPn
    texts = []       # textos livres
    for v in vertices.values():
        t = v["text"]
        if not t:
            continue
        if BREAKER_RE.match(t) or TRAFO_RE.match(t) or FEEDER_RE.match(t):
            equipment.setdefault(equipment_key(t), v)
        elif GROUP_RE.match(t):
            groups[int(GROUP_RE.match(t).group(1))] = v
        else:
            texts.append(v)
    breakers = {k: v for k, v in equipment.items() if k.startswith("52-")}

    # Relés (imagens) -> disjuntor: primeiro pelas linhas que os ligam, depois pela proximidade
    owner = {k: k for k in breakers}
    by_id = {v["id"]: k for k, v in breakers.items()}
    images = [v for v in vertices.values() if v["is_image"]]
    for e in edges.values():
        for a, b in ((e["source"], e["target"]), (e["target"], e["source"])):
            if a in vertices and vertices[a]["is_image"] and b in by_id:
                owner[a] = by_id[b]
    for img in images:
        if img["id"] not in owner and breakers:
            k = min(breakers, key=lambda b: _dist((img["cx"], img["cy"]), (breakers[b]["cx"], breakers[b]["cy"])))
            owner[img["id"]] = k
    anchors = [(owner[img["id"]], (img["cx"], img["cy"])) for img in images if img["id"] in owner]
    anchors += [(k, (v["cx"], v["cy"])) for k, v in equipment.items()]

    def nearest_equipment(point, only_breakers=False, max_dist=NEAR_ITEM):
        best = None
        for k, p in anchors:
            if only_breakers and not k.startswith("52-"):
                continue
            d = _dist(point, p)
            if d <= max_dist and (best is None or d < best[1]):
                best = (k, d)
        return best[0] if best else None

    def endpoint_owner(cell_id, point):
        if cell_id in owner:
            return owner[cell_id]
        if cell_id in vertices:
            v = vertices[cell_id]
            point = (v["cx"], v["cy"])
        return nearest_equipment(point, only_breakers=True) if point else None

    # Textos livres próximos a uma linha viram rótulo dessa linha
    used = set()
    for t in texts:
        center = (t["cx"], t["cy"])
        best = None
        for e in edges.values():
            if len(e["poly"]) < 2:
                continue
            d = _dist_point_poly(center, e["poly"])
            if d <= NEAR_EDGE and (best is None or d < best[1]):
                best = (e, d)
        if best and (TRIP_RE.match(t["text"]) or ASSUME_RE.search(t["text"])):
            best[0]["text"] = (best[0]["text"] + " " + t["text"]).strip()
            used.add(t["id"])

    facts = {"trips": [], "group_assignments": [], "groups_without_settings": [], "annotations": [], "names": {},
             "equipment": sorted(equipment)}

    for e in edges.values():
        if not e["poly"]:
            continue
        if re.search(r"\btrip\b", e["text"], re.I):
            a = endpoint_owner(e["source"], e["start"])
            b = endpoint_owner(e["target"], e["end"])
            if a and b and a != b and (a, b) not in facts["trips"]:
                facts["trips"].append((a, b))
        m = ASSUME_RE.search(e["text"])
        if m:
            relay, source = equipment_key(m.group(1)), equipment_key(m.group(2))
            group = None
            if groups and e["end"]:
                ends = [e["end"], e["start"]]
                n, v = min(groups.items(), key=lambda g: min(_dist(p, (g[1]["cx"], g[1]["cy"])) for p in ends))
                if min(_dist(p, (v["cx"], v["cy"])) for p in ends) <= NEAR_ITEM:
                    group = n
            facts["group_assignments"].append({"relay": relay, "source": source, "group": group})

    # Texto solto "52-3 assume o ajuste do 52-1" sem linha associada
    for t in texts:
        if t["id"] in used:
            continue
        m = ASSUME_RE.search(t["text"])
        if m:
            used.add(t["id"])
            entry = {"relay": equipment_key(m.group(1)), "source": equipment_key(m.group(2)), "group": None}
            if entry not in facts["group_assignments"]:
                facts["group_assignments"].append(entry)
        elif TRIP_RE.match(t["text"]):
            used.add(t["id"])

    for t in texts:
        if t["id"] in used:
            continue
        center = (t["cx"], t["cy"])
        if NO_SETTING_RE.match(t["text"]) and groups:
            n, v = min(groups.items(), key=lambda g: _dist(center, (g[1]["cx"], g[1]["cy"])))
            relay = nearest_equipment((v["cx"], v["cy"]), only_breakers=True, max_dist=NEAR_ITEM * 2)
            facts["groups_without_settings"].append({"relay": relay, "group": n})
            used.add(t["id"])
            continue
        # Anotação ligada por seta a um equipamento
        target = None
        for e in edges.values():
            ends = [(e["source"], e["target"]), (e["target"], e["source"])]
            for a, b in ends:
                if a == t["id"] and b and (b in owner or b in vertices):
                    target = endpoint_owner(b, None)
        target = target or nearest_equipment(center)
        if t["text"].isupper() and len(t["text"]) <= 40 and target and target.startswith("AL-"):
            facts["names"][target] = t["text"]
        else:
            facts["annotations"].append({"equipment": target, "text": t["text"]})
        used.add(t["id"])

    # Alimentador ligado a cada disjuntor (bloco AL-x mais próximo do disjuntor)
    facts["feeder_of"] = {}
    for k, v in breakers.items():
        feeders = [(f, equipment[f]) for f in equipment if f.startswith("AL-")]
        if feeders:
            f, fv = min(feeders, key=lambda x: _dist((v["cx"], v["cy"]), (x[1]["cx"], x[1]["cy"])))
            if _dist((v["cx"], v["cy"]), (fv["cx"], fv["cy"])) <= NEAR_ITEM:
                facts["feeder_of"][k] = f
    return facts
