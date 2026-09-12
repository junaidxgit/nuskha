"""Generate the MedLens UI as a single self-contained HTML file.

Why one file with the data embedded: a demo that needs a server, a port and a
working CORS setup is a demo that can fail on stage. This opens from the
filesystem, works offline, and can equally be dropped on a static host to
produce the live demo link.

The data is a compact projection of medlens.db - only the fields the UI renders,
with short keys, because the full records would triple the file size.

Run:
    python ui/build_ui.py
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "processed" / "medlens.db"
OUT = ROOT / "ui" / "index.html"


def build_payload() -> dict:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    nsq = [{
        "p": r["product_name"], "b": r["batch_no"] or "",
        "m": r["manufacturer"] or "", "r": r["nsq_reason"] or "",
        "s": r["series"], "y": r["alert_year"], "mo": r["alert_month"],
        "u": r["source_url"] or "", "t": r["alert_type"],
    } for r in con.execute(
        "SELECT product_name, batch_no, manufacturer, nsq_reason, series,"
        " alert_year, alert_month, source_url, alert_type FROM nsq_records")]

    who = [{
        "l": r["alert_label"], "n": r["alert_number"], "y": r["alert_year"],
        "d": r["alert_date"] or "", "p": r["products"] or "",
        "m": r["manufacturers"] or "", "u": r["news_url"] or "",
        "i": r["mentions_india"],
    } for r in con.execute(
        "SELECT alert_label, alert_number, alert_year, alert_date, products,"
        " manufacturers, news_url, mentions_india FROM who_alerts")]

    nppa = [{
        "f": r["formulation"], "c": r["composition"] or "",
        "u": r["unit"] or "", "m": r["manufacturer"] or "",
        "pr": r["retail_price_inr"], "nr": r["notice_ref"] or "",
        "y": r["notice_year"], "mo": r["notice_month"],
    } for r in con.execute(
        "SELECT formulation, composition, unit, manufacturer, retail_price_inr,"
        " notice_ref, notice_year, notice_month FROM nppa_prices")]

    ja = [{
        "g": r["generic_name"], "u": r["unit_size"] or "",
        "pr": r["mrp_inr"], "c": r["drug_code"],
    } for r in con.execute(
        "SELECT generic_name, unit_size, mrp_inr, drug_code"
        " FROM janaushadhi_prices WHERE mrp_inr > 0")]

    con.close()
    return {"nsq": nsq, "who": who, "nppa": nppa, "ja": ja}


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MedLens - what is on your prescription, and what it should cost</title>
<style>
  :root {
    --bg:#12130f; --panel:#1c1e18; --panel2:#23261e; --line:#33362b;
    --text:#e8e6df; --dim:#a8a599; --faint:#7d7a70;
    --amber:#ef9f27; --amber-bg:#3a2c0c;
    --teal:#5dcaa5; --teal-bg:#0d3b2e;
    --blue:#85b7eb; --blue-bg:#122a45;
    --red:#f09595; --red-bg:#3d1a1a;
  }
  * { box-sizing:border-box; }
  body {
    margin:0; background:var(--bg); color:var(--text);
    font:15px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif;
  }
  .wrap { max-width:840px; margin:0 auto; padding:40px 20px 80px; }
  h1 { font-size:22px; font-weight:600; margin:0 0 6px; letter-spacing:-.01em; }
  .sub { color:var(--dim); font-size:14px; margin:0 0 28px; }
  .searchrow { display:flex; gap:10px; flex-wrap:wrap; }
  input, select {
    background:var(--panel); color:var(--text); border:1px solid var(--line);
    border-radius:10px; padding:12px 14px; font-size:15px; font-family:inherit;
  }
  input { flex:1 1 260px; }
  input:focus, select:focus { outline:none; border-color:var(--teal); }
  .hint { color:var(--faint); font-size:13px; margin:10px 0 0; }
  .card {
    background:var(--panel); border:1px solid var(--line);
    border-radius:14px; padding:20px; margin-top:22px;
  }
  .card h2 {
    font-size:12px; font-weight:600; letter-spacing:.08em; text-transform:uppercase;
    color:var(--faint); margin:0 0 16px;
  }
  .tier { border-radius:12px; padding:16px; margin-top:14px; border:1px solid; }
  .tier.t1 { background:var(--amber-bg); border-color:#5c4715; }
  .tier.t2 { background:var(--blue-bg); border-color:#25456b; }
  .tier h3 { margin:0 0 4px; font-size:14px; font-weight:600; }
  .tier .src { font-size:12px; color:var(--dim); margin:0 0 12px; }
  .rec { border-top:1px solid rgba(255,255,255,.07); padding:12px 0; }
  .rec:first-of-type { border-top:none; padding-top:0; }
  .rec .name { font-weight:500; }
  .rec dl { margin:8px 0 0; display:grid; grid-template-columns:84px 1fr; gap:3px 10px; }
  .rec dt { color:var(--faint); font-size:12.5px; }
  .rec dd { margin:0; font-size:13.5px; color:var(--dim); word-break:break-word; }
  .pricegrid { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
  @media (max-width:620px) { .pricegrid { grid-template-columns:1fr; } }
  .pricebox { border-radius:12px; padding:16px; border:1px solid; }
  .pricebox.ceil { background:var(--amber-bg); border-color:#5c4715; }
  .pricebox.floor { background:var(--teal-bg); border-color:#17594a; }
  .pricebox .lbl { font-size:11.5px; letter-spacing:.07em; text-transform:uppercase; color:var(--dim); }
  .pricebox .amt { font-size:26px; font-weight:600; margin:6px 0 2px; }
  .pricebox .per { font-size:13px; color:var(--dim); }
  .pricebox .who { font-size:12.5px; color:var(--faint); margin-top:10px; }
  .compare {
    margin-top:14px; padding:12px 16px; border-radius:10px;
    background:var(--panel2); font-size:14px;
  }
  .note {
    font-size:12.5px; color:var(--faint); margin-top:16px;
    padding-top:14px; border-top:1px solid var(--line);
  }
  .warn { color:var(--amber); font-size:13px; margin-top:12px; }
  .prov { color:var(--faint); font-size:12.5px; margin-top:10px; font-style:italic; }
  .empty { color:var(--dim); font-size:14px; }
  a { color:var(--blue); text-decoration:none; }
  a:hover { text-decoration:underline; }
  .none { color:var(--faint); font-size:13.5px; font-style:italic; }
</style>
</head>
<body>
<div class="wrap">
  <h1>MedLens</h1>
  <p class="sub">Type the salt written on your prescription. See what the law says it may
     cost, and whether the regulator has a quality record for it.</p>

  <div class="searchrow">
    <input id="q" placeholder="atorvastatin" autocomplete="off" autofocus>
    <select id="form">
      <option value="">any form</option>
      <option value="tablet">tablet</option>
      <option value="capsule">capsule</option>
      <option value="syrup">syrup / liquid</option>
      <option value="injection">injection</option>
      <option value="gel">gel / cream</option>
    </select>
  </div>
  <p class="hint">Composition first, not brand names &mdash; a brand cannot be resolved to a
     composition without a dataset that does not exist publicly. Try
     <a href="#" data-fill="atorvastatin">atorvastatin</a>,
     <a href="#" data-fill="metformin">metformin</a>,
     <a href="#" data-fill="paracetamol">paracetamol</a>, or
     <a href="#" data-fill="coldrif">coldrif</a>.</p>

  <div id="out"></div>
</div>

<script>
const DATA = __DATA__;

const NOISE = /\\b(m\\/s|ms|pvt|private|ltd|limited|llp|inc|co|company|pharmaceuticals|pharmaceutical|pharma|pharmacia|laboratories|laboratory|labs|lab|industries|healthcare|biotech|sciences|unit|plot|no|phase)\\b/g;
function key(s) {
  return (s || "").toLowerCase()
    .replace(/[,.;:\\-()\\/&'"]/g, " ")
    .replace(NOISE, " ")
    .replace(/\\b\\d{4,}\\b/g, " ")
    .replace(/\\s+/g, " ").trim();
}
// Ported from medlens/units.py so the UI compares like the CLI does.
const KINDS = [
  ["tablet", /\\btablet/], ["capsule", /\\bcapsule/],
  ["ml", /\\bml\\b|\\binjection\\b|\\bsyrup\\b|\\bsuspension\\b|\\bsolution\\b|\\bdrop/],
  ["g", /\\bg\\b|\\bgm\\b|\\bgram|\\bgel\\b|\\bcream\\b|\\bointment\\b|\\bpowder\\b/],
  ["sachet", /\\bsachet\\b/], ["patch", /\\bpatch\\b/],
];
function unitKind(text, fallback) {
  const t = ((text || "") + " " + (fallback || "")).toLowerCase();
  for (const [k, re] of KINDS) if (re.test(t)) return k;
  return "unit";
}
function parseUnit(raw, name) {
  const s = (raw || "").trim();
  const m = s.match(/^(\\d+(?:\\.\\d+)?)\\s*'?s?\\s*(.*)$/);
  if (!m) return [1, unitKind(s, name)];
  const qty = parseFloat(m[1]) || 1;
  const tail = (m[2] || "").trim();
  let kind = tail ? unitKind(tail, name) : unitKind(name);
  if (kind === "unit") kind = unitKind(name);
  return [qty, kind];
}
const FORM_MAP = {tablet:"tablet", tablets:"tablet", tab:"tablet", capsule:"capsule",
  capsules:"capsule", syrup:"ml", suspension:"ml", solution:"ml", injection:"ml",
  liquid:"ml", drops:"ml", gel:"g", cream:"g", ointment:"g", powder:"g"};
const STRENGTH = /(\\d+(?:\\.\\d+)?)\\s*(mg|mcg|µg|g|gm|ml|iu|%|w\\/w|w\\/v)\\b/gi;
const TO_MG = {mg:1, mcg:.001, "µg":.001, g:1000, gm:1000};
function strengthsOf(text) {
  const out = new Set(); let m;
  STRENGTH.lastIndex = 0;
  while ((m = STRENGTH.exec(text || "")) !== null) {
    const v = parseFloat(m[1]), u = m[2].toLowerCase();
    out.add(u in TO_MG ? (v * TO_MG[u]) + "mg" : v + u);
  }
  return out;
}
function hasAll(hay, want) { for (const w of want) if (!hay.has(w)) return false; return true; }
const COMB = /\\s(?:&|and)\\s|,/i;
const esc = s => (s || "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const money = v => "\\u20b9" + Number(v).toLocaleString("en-IN", {minimumFractionDigits:2, maximumFractionDigits:2});

function render() {
  const raw = document.getElementById("q").value.trim();
  const formSel = document.getElementById("form").value;
  const out = document.getElementById("out");
  if (raw.length < 3) { out.innerHTML = ""; return; }

  // Separate the name from the dose: "10mg" is not a name token, and requiring
  // it to appear in a product's key silently excludes plain "Atorvastatin".
  const nameOnly = raw.replace(/(\\d+(?:\\.\\d+)?)\\s*(?:mg|mcg|µg|g|gm|ml|iu|%|w\\/w|w\\/v)\\b/gi, " ");
  const k = key(nameOnly), toks = k.split(" ").filter(t => t.length > 2);
  const hit = s => { const h = key(s); return toks.every(t => h.includes(t)); };
  const wantStr = strengthsOf(raw);
  const wantForm = FORM_MAP[formSel] || formSel || null;

  let nppa = DATA.nppa.filter(r => hit(r.f) || hit(r.c));
  let ja = DATA.ja.filter(r => hit(r.g));
  if (wantStr.size) {
    nppa = nppa.filter(r => hasAll(strengthsOf(r.c + " " + r.f), wantStr));
    ja = ja.filter(r => hasAll(strengthsOf(r.g), wantStr));
  }
  if (wantForm) {
    nppa = nppa.filter(r => parseUnit(r.u, r.f)[1] === wantForm);
    ja = ja.filter(r => parseUnit(r.u, r.g)[1] === wantForm);
  }
  const rank = a => a.sort((x, y) => (COMB.test(x.f || x.g) - COMB.test(y.f || y.g)) || (x.pr - y.pr));
  rank(nppa); rank(ja);

  const nsq = DATA.nsq.filter(r => hit(r.p) || hit(r.m)).slice(0, 6);
  const who = DATA.who.filter(r => hit(r.l) || hit(r.p) || hit(r.m)).slice(0, 4);

  let html = "";

  if (nppa.length || ja.length) {
    const c = nppa[0], f = ja[0];
    html += '<div class="card"><h2>What it should cost</h2><div class="pricegrid">';
    html += '<div class="pricebox ceil"><div class="lbl">Legal maximum</div>' +
      (c ? `<div class="amt">${money(c.pr)}</div><div class="per">per ${esc(c.u)}</div>
        <div class="who">${esc(c.f)}${c.nr ? " &middot; " + esc(c.nr) : ""}</div>`
        : '<div class="none">No same-strength NPPA ceiling on record</div>') + "</div>";
    html += '<div class="pricebox floor"><div class="lbl">Government generic</div>' +
      (f ? `<div class="amt">${money(f.pr)}</div><div class="per">per ${esc(f.u)}</div>
        <div class="who">${esc(f.g)}</div>`
        : '<div class="none">No same-strength Jan Aushadhi product on record</div>') + "</div>";
    html += "</div>";

    if (c && f) {
      const [cq, ck] = parseUnit(c.u, c.f), [fq, fk] = parseUnit(f.u, f.g);
      // A ratio against a combination product is meaningless - it is not the
      // same medicine, so no multiple is shown at all.
      if (COMB.test(c.f) || COMB.test(f.g)) {
        html += '<div class="compare">No ratio shown: one of the matches is a combination product, so the two figures are not the same medicine.</div>';
      } else if (ck === fk && cq && fq) {
        const pc = c.pr / cq, pf = f.pr / fq;
        html += `<div class="compare">Per <strong>${esc(ck)}</strong>: government generic
          <strong>${money(pf)}</strong> against a legal ceiling of
          <strong>${money(pc)}</strong> &mdash; <strong>${(pc / pf).toFixed(1)}&times;</strong>
          ${pf <= pc ? "" : " <span style='color:var(--red)'>(check: floor above ceiling)</span>"}</div>`;
      } else {
        html += '<div class="compare">The two sources quote different units, so no per-unit comparison is shown.</div>';
      }
    }
    if (c && COMB.test(c.f)) html += '<div class="warn">The ceiling shown is a combination product that contains this ingredient &mdash; it is not the price of the ingredient alone.</div>';
    if (f && COMB.test(f.g)) html += '<div class="warn">The generic shown is a combination product that contains this ingredient.</div>';
    html += '<div class="prov">Both figures come from third-party mirrors of the official documents, not from the issuing bodies. Verify against the primary source before relying on it. NPPA prices exclude GST.</div>';
    html += '<div class="note">Charging above the NPPA ceiling for a scheduled formulation is illegal. This is not medical advice, and composition match is not proven therapeutic equivalence &mdash; ask your prescriber before changing anything.</div>';
    html += "</div>";
  }

  html += '<div class="card"><h2>Quality records</h2>';
  html += '<div class="tier t1"><h3>Tier 1 &mdash; CDSCO NSQ batch alerts</h3>' +
    '<p class="src">Batches that failed laboratory testing. Recorded by the regulator.</p>';
  if (!nsq.length) html += '<p class="none">No batch alert on record.</p>';
  for (const r of nsq) {
    html += `<div class="rec"><div class="name">${esc(r.p)}</div><dl>
      <dt>batch</dt><dd>${esc(r.b) || "&mdash;"}</dd>
      <dt>maker</dt><dd>${esc(r.m)}</dd>
      <dt>reason</dt><dd>${esc(r.r)}</dd>
      <dt>source</dt><dd>${r.s === "state" ? "state" : "central"} lab alert ${r.y}-${String(r.mo).padStart(2,"0")}</dd>
      ${r.u ? `<dt>document</dt><dd><a href="${esc(r.u)}" target="_blank" rel="noopener">original alert PDF</a></dd>` : ""}
      </dl></div>`;
  }
  html += "</div>";

  html += '<div class="tier t2"><h3>Tier 2 &mdash; WHO Medical Product Alerts</h3>' +
    '<p class="src">Recalls, suspensions and contamination events. Published by WHO.</p>';
  if (!who.length) html += '<p class="none">No WHO alert on record.</p>';
  for (const r of who) {
    html += `<div class="rec"><div class="name">${esc(r.l)}</div><dl>
      ${r.d ? `<dt>date</dt><dd>${esc(r.d)}</dd>` : ""}
      ${r.p ? `<dt>products</dt><dd>${esc(r.p)}</dd>` : ""}
      ${r.m ? `<dt>makers</dt><dd>${esc(r.m)}</dd>` : ""}
      ${r.u ? `<dt>source</dt><dd><a href="${esc(r.u)}" target="_blank" rel="noopener">WHO alert</a></dd>` : ""}
      </dl></div>`;
  }
  html += "</div>";

  html += '<div class="note">An NSQ finding is <strong>batch-specific</strong>: one batch failed testing on one date for the stated reason. It is not a statement about the company. Absence of a record is <strong>not</strong> evidence of quality &mdash; only sampled batches are tested. The two tiers are never merged: Tier 1 is a regulator record, Tier 2 is a WHO publication. Not medical advice &mdash; never change a prescribed medicine without asking the prescriber.</div>';
  html += "</div>";

  out.innerHTML = html;
}

document.getElementById("q").addEventListener("input", render);
document.getElementById("form").addEventListener("change", render);
document.querySelectorAll("[data-fill]").forEach(a => a.addEventListener("click", e => {
  e.preventDefault();
  document.getElementById("q").value = a.dataset.fill;
  render();
}));
</script>
</body>
</html>
"""


def main() -> int:
    if not DB.exists():
        print(f"{DB} not found - run pipeline/build_db.py first")
        return 1
    payload = build_payload()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    html = HTML.replace("__DATA__", json.dumps(payload, ensure_ascii=False,
                                               separators=(",", ":")))
    bad = {c for c in html if ord(c) < 32 and c not in "\n\t"}
    if bad:
        codes = ", ".join(f"0x{ord(c):02x}" for c in sorted(bad))
        raise SystemExit(
            f"refusing to write: generated HTML contains control characters ({codes}). "
            "An unescaped \\b or \\f in a Python string literal becomes a control "
            "character and silently breaks the JS regexes."
        )
    OUT.write_text(html, encoding="utf-8")
    print(f"nsq {len(payload['nsq']):,} | who {len(payload['who'])} | "
          f"nppa {len(payload['nppa'])} | janaushadhi {len(payload['ja']):,}")
    print(f"-> {OUT.relative_to(ROOT)}  ({OUT.stat().st_size / 1024:.0f} KB, self-contained)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
