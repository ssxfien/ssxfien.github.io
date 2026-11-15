
import os, re, json, html, hashlib, subprocess, bz2, gzip, lzma, functools
from urllib.parse import quote
 
BASE = os.environ.get("REPO_URL", "https://ssxfien.github.io").rstrip("/")
DEBS, DEPS = "debs", "depictions"
TINT = "#2cd5ff"
IMG = (".png", ".jpg", ".jpeg", ".webp", ".gif")
os.makedirs(DEBS, exist_ok=True)
os.makedirs(DEPS, exist_ok=True)
for f in os.listdir(DEPS):                      # depictions are regenerated every run
    os.remove(os.path.join(DEPS, f))
 
def parse_control(path):
    raw = subprocess.check_output(["dpkg-deb", "-f", path]).decode("utf-8", "replace")
    fields = []
    for line in raw.split("\n"):
        if not line.strip():
            continue
        if line[0] in " \t" and fields:
            fields[-1][1] += "\n" + line
        elif ":" in line:
            k, v = line.split(":", 1)
            fields.append([k.strip(), v.strip()])
    return fields
 
def get(fields, key, default=""):
    for k, v in fields:
        if k.lower() == key.lower():
            return v
    return default
 
def vcmp(a, b):
    if subprocess.call(["dpkg", "--compare-versions", a, "gt", b]) == 0: return 1
    if subprocess.call(["dpkg", "--compare-versions", a, "lt", b]) == 0: return -1
    return 0
 
files = sorted(os.listdir(DEBS))
lower = {f.lower(): f for f in files}
 
def find_asset(pid, suffixes, exts):
    for s in suffixes:
        for e in exts:
            n = (pid + s + e).lower()
            if n in lower:
                return lower[n]
    return None
 
def screenshots(pid):
    pre = (pid + "-screenshot").lower()
    return sorted(f for f in files if f.lower().startswith(pre) and f.lower().endswith(IMG))
 
def url(name):
    return BASE + "/" + DEBS + "/" + quote(name)
 
def md_to_html(text):
    out, in_list = [], False
    for line in text.split("\n"):
        s = html.escape(line.rstrip())
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
        m = re.match(r"^(#{1,3})\s+(.*)", s)
        if re.match(r"^\s*[-*]\s+", s):
            if not in_list: out.append("<ul>"); in_list = True
            out.append("<li>" + re.sub(r"^\s*[-*]\s+", "", s) + "</li>"); continue
        if in_list: out.append("</ul>"); in_list = False
        if m: out.append("<h%d>%s</h%d>" % (len(m.group(1)) + 1, m.group(2), len(m.group(1)) + 1))
        elif s.strip(): out.append("<p>" + s + "</p>")
    if in_list: out.append("</ul>")
    return "\n".join(out)
 
debs = []
for f in files:
    if f.lower().endswith(".deb"):
        p = os.path.join(DEBS, f)
        try:
            debs.append((f, p, parse_control(p)))
        except Exception as e:
            print("skipping", f, e)
 
debs.sort(key=lambda d: (get(d[2], "Package").lower(), ))
by_pkg = {}
for f, p, fl in debs:
    by_pkg.setdefault(get(fl, "Package"), []).append((f, p, fl))
 
default_icon = find_asset("default-icon", [""], IMG)
stanzas, archs = [], set()
for pid, items in by_pkg.items():
    items.sort(key=functools.cmp_to_key(lambda a, b: vcmp(get(a[2], "Version"), get(b[2], "Version"))))
    icon = find_asset(pid, ["", "-icon"], IMG) or default_icon
    banner = find_asset(pid, ["-banner", "-header"], IMG)
    shots = screenshots(pid)
    mdf = find_asset(pid, [""], (".md",))
    chf = find_asset(pid, ["-changelog"], (".md",))
    latest = items[-1][2]
    name = get(latest, "Name", pid)
    desc_full = get(latest, "Description")
    short, _, rest = desc_full.partition("\n")
    long_text = open(os.path.join(DEBS, mdf), encoding="utf-8").read() if mdf else (
        short + ("\n\n" + "\n".join(l.strip(" ") if l.strip() != "." else "" for l in rest.split("\n")) if rest else ""))
    changelog = open(os.path.join(DEBS, chf), encoding="utf-8").read() if chf else ""
    author = re.sub(r"\s*<.*?>", "", get(latest, "Author", get(latest, "Maintainer", "")))
    info = [("Version", get(latest, "Version")), ("Author", author), ("Package ID", pid),
            ("Section", get(latest, "Section")), ("Architecture", get(latest, "Architecture"))]
    info = [(k, v) for k, v in info if v]
    # ---- Sileo native depiction
    tab1 = [{"class": "DepictionSubheaderView", "title": "Description", "useBoldText": True, "useBottomMargin": False},
            {"class": "DepictionMarkdownView", "markdown": long_text, "useSpacing": True}]
    if shots:
        tab1.append({"class": "DepictionScreenshotsView", "itemCornerRadius": 8, "itemSize": "{160, 275}",
                     "screenshots": [{"accessibilityText": "Screenshot", "url": url(s)} for s in shots]})
    tab1.append({"class": "DepictionSeparatorView"})
    tab1.append({"class": "DepictionSubheaderView", "title": "Information", "useBoldText": True, "useBottomMargin": False})
    tab1 += [{"class": "DepictionTableTextView", "title": k, "text": v} for k, v in info]
    tabs = [{"tabname": "Details", "class": "DepictionStackView", "views": tab1}]
    if changelog:
        tabs.append({"tabname": "Changelog", "class": "DepictionStackView",
                     "views": [{"class": "DepictionMarkdownView", "markdown": changelog, "useSpacing": True}]})
    native = {"minVersion": "0.1", "class": "DepictionTabView", "tintColor": TINT, "tabs": tabs}
    if banner: native["headerImage"] = url(banner)
    json.dump(native, open(os.path.join(DEPS, pid + ".json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    # ---- web depiction (Cydia / Zebra fallback)
    hero = ('background-image:linear-gradient(rgba(10,14,28,.15),#0a0e1c),url(%s)' % url(banner)) if banner else "background:linear-gradient(135deg,#12203a,#0a0e1c)"
    rows = "".join("<tr><td>%s</td><td>%s</td></tr>" % (html.escape(k), html.escape(v)) for k, v in info)
    shot_html = "".join('<img src="%s">' % url(s) for s in shots)
    page = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(name)s</title><style>
body{margin:0;background:#0a0e1c;color:#e8ecf5;font-family:-apple-system,Helvetica,sans-serif}
.hero{%(hero)s;background-size:cover;background-position:center;padding:90px 18px 18px;display:flex;gap:14px;align-items:flex-end}
.hero img{width:64px;height:64px;border-radius:14px}.hero h1{margin:0;font-size:24px}.hero small{color:#9fb0cc}
.c{padding:6px 18px 30px}h2,h3{color:%(tint)s}code{background:#16203a;padding:1px 5px;border-radius:5px}
table{width:100%%;border-collapse:collapse}td{padding:9px 0;border-bottom:1px solid #1a2442}td:last-child{text-align:right;color:#9fb0cc}
.s{display:flex;gap:10px;overflow-x:auto}.s img{height:260px;border-radius:12px}
</style></head><body><div class="hero">%(icon)s<div><h1>%(name)s</h1><small>%(short)s</small></div></div>
<div class="c"><h2>Description</h2>%(body)s<div class="s">%(shots)s</div><h2>Information</h2><table>%(rows)s</table>%(cl)s</div></body></html>""" % dict(
        name=html.escape(name), hero=hero, tint=TINT, short=html.escape(short),
        icon=('<img src="%s">' % url(icon)) if icon else "", body=md_to_html(long_text), shots=shot_html, rows=rows,
        cl=("<h2>Changelog</h2>" + md_to_html(changelog)) if changelog else "")
    open(os.path.join(DEPS, pid + ".html"), "w", encoding="utf-8").write(page)
    # ---- Packages stanzas (one per deb, all versions kept)
    for f, p, fl in items:
        data = open(p, "rb").read()
        have = {k.lower() for k, _ in fl}
        add = []
        if "name" not in have: add.append(("Name", name))
        if "icon" not in have and icon: add.append(("Icon", url(icon)))
        if "depiction" not in have: add.append(("Depiction", BASE + "/" + DEPS + "/" + quote(pid) + ".html"))
        if "sileodepiction" not in have: add.append(("SileoDepiction", BASE + "/" + DEPS + "/" + quote(pid) + ".json"))
        add += [("Filename", DEBS + "/" + quote(f)), ("Size", str(len(data))),
                ("MD5sum", hashlib.md5(data).hexdigest()), ("SHA1", hashlib.sha1(data).hexdigest()),
                ("SHA256", hashlib.sha256(data).hexdigest())]
        drop = {"filename", "size", "md5sum", "sha1", "sha256"}
        lines = []
        for k, v in [x for x in fl if x[0].lower() not in drop] + add:
            vv = v.split("\n")
            lines.append("%s: %s" % (k, vv[0]) + "".join("\n" + l for l in vv[1:]))
        stanzas.append("\n".join(lines))
        a = get(fl, "Architecture")
        if a: archs.add(a)
 
pk = ("\n\n".join(stanzas) + "\n").encode("utf-8") if stanzas else b""
open("Packages", "wb").write(pk)
open("Packages.bz2", "wb").write(bz2.compress(pk))
open("Packages.gz", "wb").write(gzip.compress(pk, mtime=0))
open("Packages.xz", "wb").write(lzma.compress(pk))
 
arch_line = " ".join(sorted(archs)) or "iphoneos-arm64"
rel = ["Origin: ssxfien", "Label: ssxfien", "Suite: stable", "Version: 1.0", "Codename: ios",
       "Architectures: " + arch_line, "Components: main", "Description: da fckin repo", "SHA256:"]
for n in ("Packages", "Packages.bz2", "Packages.gz", "Packages.xz"):
    d = open(n, "rb").read()
    rel.append(" %s %d %s" % (hashlib.sha256(d).hexdigest(), len(d), n))
open("Release", "w").write("\n".join(rel) + "\n")
print("packages:", len(by_pkg), "debs:", len(debs), "archs:", arch_line)
 
