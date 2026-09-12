"""Generate the Nuskha UI as a single self-contained HTML file.

Why one file with the data embedded: a demo that needs a server, a port and a
working CORS setup is a demo that can fail on stage. This opens from the
filesystem, works offline, and drops onto any static host for the live demo link.

The data is a compact projection of nuskha.db - only the fields the UI renders,
with short keys - plus a salt index for autocomplete.

Design notes, after looking at what already exists:
  * sahidawa.in and firstscanit.com both do instant price lookup well. The
    lessons taken: a punchy hero stat, a worked example visible on load,
    suggestion chips, and a visual price comparison rather than two bare numbers.
  * Neither carries the regulatory record. That is the differentiator, so it gets
    equal billing rather than being a footnote under the price.
  * They search brand names; this cannot, and the UI says so rather than
    silently returning nothing.

Run:
    python ui/build_ui.py
"""

from __future__ import annotations

import collections
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "processed" / "nuskha.db"
OUT = ROOT / "ui" / "index.html"

# Words that are not salts: dosage forms, salt forms, device nouns, boilerplate.
# Without this the autocomplete suggests "hydrochloride" and "suture".
NOISE = re.compile(
    r"\b(tablets?|capsules?|syrup|suspension|injections?|injectable|oral|liquid|"
    r"gel|cream|ointment|powder|solution|drops?|sachet|patch|ip|usp|bp|ep|sr|er|"
    r"ds|for|and|with|each|contains?|film|coated|uncoated|hard|soft|gelatin|"
    r"prolonged|release|extended|dispersible|soluble|sterile|non|per|ml|mg|mcg|"
    r"gm|the|of|in|to|as|us|hydrochloride|sodium|potassium|calcium|magnesium|"
    r"succinate|fumarate|tartrate|maleate|citrate|sulfate|sulphate|phosphate|"
    r"acetate|besylate|mesylate|dihydrate|monohydrate|hydrate|sustained|"
    r"chloride|nitrate|oxide|carbonate|bicarbonate|suture|needle|length|"
    r"catheter|syringe|glucose|water|acid|salt|type|size|pack)\b",
    re.I,
)


def salt_tokens(text: str) -> list[str]:
    cleaned = NOISE.sub(" ", (text or "").lower()).replace(",", " ")
    out = []
    for t in cleaned.split():
        t = re.sub(r"[^a-z]", "", t)
        if len(t) > 4:
            out.append(t)
    return out


def build_payload() -> dict:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    nsq = [{
        "p": r["product_name"], "b": r["batch_no"] or "",
        "m": r["manufacturer"] or "", "r": r["nsq_reason"] or "",
        "s": r["series"], "y": r["alert_year"], "mo": r["alert_month"],
        "u": r["source_url"] or "",
    } for r in con.execute(
        "SELECT product_name, batch_no, manufacturer, nsq_reason, series,"
        " alert_year, alert_month, source_url FROM nsq_records")]

    who = [{
        "l": r["alert_label"], "n": r["alert_number"], "y": r["alert_year"],
        "d": r["alert_date"] or "", "p": r["products"] or "",
        "m": r["manufacturers"] or "", "u": r["news_url"] or "",
    } for r in con.execute(
        "SELECT alert_label, alert_number, alert_year, alert_date, products,"
        " manufacturers, news_url FROM who_alerts")]

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

    # Salt index for autocomplete: which molecules actually exist in the data.
    # Suggesting a salt that returns nothing is worse than no suggestion at all.
    counts: collections.Counter = collections.Counter()
    for row in nppa:
        for tok in salt_tokens(row["f"]):
            counts[tok] += 1
    for row in ja:
        for tok in salt_tokens(row["g"]):
            counts[tok] += 1

    salts = [{"t": t, "n": n} for t, n in counts.most_common(600) if n >= 2]

    return {"nsq": nsq, "who": who, "nppa": nppa, "ja": ja, "salts": salts}


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nuskha — what is on your prescription, and what it should cost</title>
<meta name="description" content="Composition-first medicine pricing and India's regulatory quality record, in one lookup.">
<style>
  :root {
    --bg:#101109; --bg2:#16170f; --panel:#1b1d13; --panel2:#22251a;
    --line:#32362a; --line2:#3f4436;
    --text:#eceae2; --dim:#a9a69a; --faint:#7b786e;
    --amber:#f0a63a; --amber-dim:#3b2d0d; --amber-line:#5e4716;
    --teal:#5fd0a8; --teal-dim:#0d3a2d; --teal-line:#1a5b48;
    --blue:#8ab8ee; --blue-dim:#122a45; --blue-line:#27476c;
    --r:12px;
  }
  *{box-sizing:border-box}
  body{
    margin:0;background:var(--bg);color:var(--text);
    font:15px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,sans-serif;
    -webkit-font-smoothing:antialiased;
  }
  a{color:var(--blue);text-decoration:none}
  a:hover{text-decoration:underline}
  .wrap{max-width:900px;margin:0 auto;padding:0 20px}

  header{border-bottom:1px solid var(--line);background:var(--bg2)}
  .bar{display:flex;align-items:center;justify-content:space-between;height:56px}
  .logo{display:flex;align-items:center;gap:9px;font-weight:600;letter-spacing:-.01em}
  .logo svg{display:block}
  .bar .tag{font-size:12.5px;color:var(--faint)}

  .hero{padding:52px 0 30px;text-align:center}
  .hero h1{
    font-size:clamp(26px,4.4vw,40px);line-height:1.18;font-weight:640;
    letter-spacing:-.025em;margin:0 0 14px;
  }
  .hero h1 .hl{color:var(--amber)}
  .hero p{color:var(--dim);font-size:16px;max-width:600px;margin:0 auto}

  .searchwrap{position:relative;margin:30px auto 0;max-width:640px}
  .searchrow{display:flex;gap:10px}
  .field{position:relative;flex:1;min-width:0}
  input[type=text],select{
    width:100%;background:var(--panel);color:var(--text);
    border:1px solid var(--line2);border-radius:var(--r);
    padding:15px 40px 15px 16px;font-size:16px;font-family:inherit;
    transition:border-color .15s,background .15s;
  }
  input[type=text]:focus,select:focus{outline:none;border-color:var(--teal);background:var(--panel2)}
  select{padding-right:34px;cursor:pointer;width:auto;flex:0 0 auto;font-size:14.5px}
  .clear{
    position:absolute;right:12px;top:50%;transform:translateY(-50%);
    background:none;border:none;color:var(--faint);cursor:pointer;
    font-size:19px;line-height:1;padding:4px 7px;border-radius:6px;display:none;
  }
  .clear:hover{color:var(--text);background:var(--panel2)}
  .clear.on{display:block}

  .sug{
    position:absolute;top:calc(100% + 6px);left:0;right:0;z-index:40;
    background:var(--panel2);border:1px solid var(--line2);border-radius:var(--r);
    overflow:hidden;box-shadow:0 16px 40px rgba(0,0,0,.55);display:none;
  }
  .sug.on{display:block}
  .sug button{
    display:flex;justify-content:space-between;align-items:center;width:100%;
    background:none;border:none;color:var(--text);font:inherit;font-size:14.5px;
    padding:11px 15px;cursor:pointer;text-align:left;
  }
  .sug button:hover,.sug button.sel{background:var(--teal-dim)}
  .sug .cnt{color:var(--faint);font-size:12px}
  .sug b{color:var(--teal);font-weight:600}

  .chips{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:16px}
  .chip{
    background:var(--panel);border:1px solid var(--line2);color:var(--dim);
    border-radius:999px;padding:7px 14px;font-size:13px;cursor:pointer;
    font-family:inherit;transition:border-color .15s,color .15s,background .15s;
  }
  .chip:hover{border-color:var(--teal);color:var(--text);background:var(--panel2)}

  .stats{
    display:grid;grid-template-columns:repeat(4,1fr);gap:1px;
    background:var(--line);border:1px solid var(--line);border-radius:var(--r);
    overflow:hidden;margin:44px 0 0;
  }
  .stats div{background:var(--bg2);padding:16px 14px;text-align:center}
  .stats .n{font-size:19px;font-weight:640;letter-spacing:-.02em}
  .stats .k{font-size:11.5px;color:var(--faint);margin-top:3px}
  @media(max-width:620px){.stats{grid-template-columns:repeat(2,1fr)}}

  #out{padding:34px 0 70px}
  .card{
    background:var(--panel);border:1px solid var(--line);border-radius:16px;
    padding:22px;margin-bottom:20px;animation:rise .28s ease both;
  }
  @keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
  .card h2{
    font-size:11.5px;font-weight:640;letter-spacing:.1em;text-transform:uppercase;
    color:var(--faint);margin:0 0 18px;display:flex;align-items:center;gap:9px;
  }
  .card h2 .rule{flex:1;height:1px;background:var(--line)}

  .pgrid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
  @media(max-width:620px){.pgrid{grid-template-columns:1fr}}
  .pbox{border-radius:var(--r);padding:17px;border:1px solid}
  .pbox.ceil{background:var(--amber-dim);border-color:var(--amber-line)}
  .pbox.floor{background:var(--teal-dim);border-color:var(--teal-line)}
  .pbox .lbl{font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--dim)}
  .pbox .amt{font-size:31px;font-weight:660;letter-spacing:-.03em;margin:7px 0 1px;line-height:1}
  .pbox.ceil .amt{color:var(--amber)}
  .pbox.floor .amt{color:var(--teal)}
  .pbox .per{font-size:13px;color:var(--dim)}
  .pbox .who{font-size:12.5px;color:var(--faint);margin-top:11px;line-height:1.5}
  .pbox .none{font-size:13.5px;color:var(--faint);font-style:italic;margin-top:9px}

  .barcap{margin-top:18px}
  .barlbl{display:flex;justify-content:space-between;font-size:12px;color:var(--faint);margin-bottom:6px}
  .bar{height:26px;border-radius:7px;overflow:hidden;display:flex;border:1px solid var(--line)}
  .bar .seg-floor{background:var(--teal);transition:width .5s cubic-bezier(.4,0,.2,1)}
  .bar .seg-rest{flex:1;background:repeating-linear-gradient(45deg,#3b2d0d,#3b2d0d 7px,#463412 7px,#463412 14px)}
  .ratio{
    display:flex;align-items:baseline;gap:9px;margin-top:12px;
    background:var(--panel2);border:1px solid var(--line2);border-radius:10px;padding:12px 15px;
  }
  .ratio .x{font-size:22px;font-weight:680;color:var(--amber);letter-spacing:-.02em}
  .ratio .t{font-size:13.5px;color:var(--dim)}

  .tier{border-radius:var(--r);padding:16px 17px;border:1px solid;margin-top:14px}
  .tier.t1{background:var(--amber-dim);border-color:var(--amber-line)}
  .tier.t2{background:var(--blue-dim);border-color:var(--blue-line)}
  .tier .head{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
  .badge{
    font-size:10.5px;font-weight:660;letter-spacing:.07em;text-transform:uppercase;
    padding:3px 8px;border-radius:5px;
  }
  .t1 .badge{background:var(--amber);color:#2b1d04}
  .t2 .badge{background:var(--blue);color:#0b1e33}
  .tier .name{font-weight:560;font-size:14.5px}
  .tier .src{font-size:12.5px;color:var(--dim);margin:5px 0 0}
  .rec{border-top:1px solid rgba(255,255,255,.08);padding:14px 0 2px;margin-top:12px}
  .rec:first-of-type{border-top:none;margin-top:8px;padding-top:0}
  .rec .rname{font-weight:520;font-size:14.5px;margin-bottom:9px}
  .rec dl{margin:0;display:grid;grid-template-columns:88px 1fr;gap:4px 12px}
  .rec dt{color:var(--faint);font-size:12.5px}
  .rec dd{margin:0;font-size:13.5px;color:var(--dim);word-break:break-word}
  .rec dd.mono{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;font-size:13px;color:var(--text)}

  .prov{
    font-size:12.5px;color:var(--faint);font-style:italic;margin-top:16px;
    padding:11px 14px;border-left:2px solid var(--amber-line);background:rgba(240,166,58,.05);
    border-radius:0 8px 8px 0;
  }
  .warn{
    font-size:13px;color:var(--amber);margin-top:14px;padding:11px 14px;
    background:rgba(240,166,58,.08);border:1px solid var(--amber-line);border-radius:9px;
  }
  .note{
    font-size:12.5px;color:var(--faint);margin-top:18px;padding-top:15px;
    border-top:1px solid var(--line);line-height:1.65;
  }
  .empty{padding:44px 0;text-align:center;color:var(--faint)}
  .empty .big{font-size:34px;margin-bottom:10px;opacity:.5}

  footer{border-top:1px solid var(--line);background:var(--bg2);padding:34px 0;margin-top:20px}
  footer h3{font-size:12px;letter-spacing:.09em;text-transform:uppercase;color:var(--faint);margin:0 0 12px}
  .fgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:22px}
  @media(max-width:680px){.fgrid{grid-template-columns:1fr}}
  .fgrid p{font-size:13px;color:var(--dim);margin:0}
  .fgrid .num{
    display:inline-flex;width:20px;height:20px;border-radius:50%;
    background:var(--panel2);border:1px solid var(--line2);
    align-items:center;justify-content:center;font-size:11px;color:var(--faint);
    margin-right:7px;font-weight:600;
  }
  .footnote{font-size:12px;color:var(--faint);margin-top:26px;padding-top:18px;border-top:1px solid var(--line)}
</style>
</head>
<body>

<header>
  <div class="wrap bar">
    <div class="logo">
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#5fd0a8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0H5a2 2 0 0 1-2-2v-4m6 6h10a2 2 0 0 0 2-2v-4"/>
      </svg>
      Nuskha
    </div>
    <div class="tag">India &middot; government data only</div>
  </div>
</header>

<div class="wrap">

  <div class="hero">
    <h1>Your prescription has a <span class="hl">legal maximum price</span>.<br>Nobody shows it to you.</h1>
    <p>Type the salt on the prescription. See the ceiling, the government generic price, and
       whether the regulator has a quality record for that batch.</p>
  </div>

  <div class="searchwrap">
    <div class="searchrow">
      <div class="field">
        <input id="q" type="text" placeholder="atorvastatin" autocomplete="off" spellcheck="false" autofocus>
        <button class="clear" id="clear" title="Clear">&#215;</button>
        <div class="sug" id="sug"></div>
      </div>
      <select id="form" title="Dosage form">
        <option value="">any form</option>
        <option value="tablet">tablet</option>
        <option value="capsule">capsule</option>
        <option value="syrup">syrup / liquid</option>
        <option value="injection">injection</option>
        <option value="gel">gel / cream</option>
      </select>
    </div>
    <div class="chips" id="chips"></div>
  </div>

  <div class="stats">
    <div><div class="n" id="s1"></div><div class="k">batch records</div></div>
    <div><div class="n" id="s2"></div><div class="k">WHO alerts</div></div>
    <div><div class="n" id="s3"></div><div class="k">ceiling prices</div></div>
    <div><div class="n" id="s4"></div><div class="k">generic prices</div></div>
  </div>

</div>

<div class="wrap"><div id="out"></div></div>

<footer>
  <div class="wrap">
    <h3>How this works</h3>
    <div class="fgrid">
      <p><span class="num">1</span><strong>Type the salt.</strong> Composition first, not brand
         names &mdash; a brand cannot be resolved to a composition without a dataset that does
         not exist publicly.</p>
      <p><span class="num">2</span><strong>Two official numbers.</strong> The NPPA ceiling is the
         legally binding maximum. The Jan Aushadhi price is the government's own generic. Both
         are matched on strength and dosage form.</p>
      <p><span class="num">3</span><strong>The record.</strong> CDSCO's list of batches that failed
         testing, and WHO's alerts. Kept in separate tiers, never blended.</p>
    </div>
    <div class="footnote">
      Nuskha does not give medical advice and never instructs a substitution. Composition match
      is not proven therapeutic equivalence. Always ask your prescriber.
    </div>
  </div>
</footer>

<script>
const DATA = __DATA__;

const NOISE = /[^a-z0-9 ]/g;
function key(s) {
  return (s || "").toLowerCase().replace(NOISE, " ").replace(/\s+/g, " ").trim();
}
const KINDS = [
  ["tablet", /\btablet/], ["capsule", /\bcapsule/],
  ["ml", /\bml\b|\binjection\b|\bsyrup\b|\bsuspension\b|\bsolution\b|\bdrop/],
  ["g", /\bg\b|\bgm\b|\bgram|\bgel\b|\bcream\b|\bointment\b|\bpowder\b/],
  ["sachet", /\bsachet\b/], ["patch", /\bpatch\b/],
];
function unitKind(text, fallback) {
  const t = ((text || "") + " " + (fallback || "")).toLowerCase();
  for (const pair of KINDS) if (pair[1].test(t)) return pair[0];
  return "unit";
}
function parseUnit(raw, name) {
  const s = (raw || "").trim();
  const m = s.match(/^(\d+(?:\.\d+)?)\s*'?s?\s*(.*)$/);
  if (!m) return [1, unitKind(s, name)];
  const qty = parseFloat(m[1]) || 1;
  const tail = (m[2] || "").trim();
  let kind = tail ? unitKind(tail, name) : unitKind(name);
  if (kind === "unit") kind = unitKind(name);
  return [qty, kind];
}
const FORM_MAP = {tablet:"tablet", capsule:"capsule", capsules:"capsule", syrup:"ml",
  suspension:"ml", solution:"ml", injection:"ml", liquid:"ml", drops:"ml",
  gel:"g", cream:"g", ointment:"g", powder:"g"};
const STRENGTH = /(\d+(?:\.\d+)?)\s*(mg|mcg|g|gm|ml|iu|%|w\/w|w\/v)\b/gi;
const TO_MG = {mg:1, mcg:0.001, g:1000, gm:1000};
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
const COMB = /\s(?:&|and)\s|,/i;
const ESCAPES = {"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;"};
const esc = s => (s || "").replace(/[&<>"]/g, c => ESCAPES[c]);
const money = v => "\u20b9" + Number(v).toLocaleString("en-IN", {minimumFractionDigits:2, maximumFractionDigits:2});

/* ---------- autocomplete ---------- */
const salts = DATA.salts || [];
function suggest(q) {
  const k = key(q);
  if (k.length < 2) return [];
  const starts = [], contains = [];
  for (const s of salts) {
    const i = s.t.indexOf(k);
    if (i === 0) starts.push(s);
    else if (i > 0) contains.push(s);
  }
  return starts.concat(contains).slice(0, 7);
}
function hl(term, q) {
  const i = term.indexOf(q);
  if (i < 0) return esc(term);
  return esc(term.slice(0, i)) + "<b>" + esc(term.slice(i, i + q.length)) + "</b>" +
         esc(term.slice(i + q.length));
}

/* ---------- render ---------- */
const out = document.getElementById("out");
const qEl = document.getElementById("q");
const formEl = document.getElementById("form");
const sugEl = document.getElementById("sug");
const clearEl = document.getElementById("clear");
let selIdx = -1, curSug = [];

function render() {
  const raw = qEl.value.trim();
  clearEl.classList.toggle("on", raw.length > 0);
  if (raw.length < 3) { out.innerHTML = ""; return; }

  const nameOnly = raw.replace(/(\d+(?:\.\d+)?)\s*(?:mg|mcg|g|gm|ml|iu|%|w\/w|w\/v)\b/gi, " ");
  const k = key(nameOnly), toks = k.split(" ").filter(t => t.length > 2);
  const hit = s => { const h = key(s); return toks.length > 0 && toks.every(t => h.includes(t)); };
  const wantStr = strengthsOf(raw);
  const wantForm = FORM_MAP[formEl.value] || formEl.value || null;

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
  const rank = a => a.sort((x, y) =>
    (COMB.test(x.f || x.g) - COMB.test(y.f || y.g)) || (x.pr - y.pr));
  rank(nppa); rank(ja);

  const nsq = DATA.nsq.filter(r => hit(r.p) || hit(r.m)).slice(0, 6);
  const who = DATA.who.filter(r => hit(r.l) || hit(r.p) || hit(r.m)).slice(0, 4);

  if (!nppa.length && !ja.length && !nsq.length && !who.length) {
    out.innerHTML = '<div class="empty"><div class="big">&#8709;</div>' +
      'No record for &ldquo;' + esc(raw) + '&rdquo;.<br>' +
      '<span style="font-size:13px">Composition-first only &mdash; brand names cannot be ' +
      'resolved. Try the salt, e.g. <em>atorvastatin</em>.</span></div>';
    return;
  }

  let html = "";

  if (nppa.length || ja.length) {
    const c = nppa[0], f = ja[0];
    html += '<div class="card"><h2>What it should cost<span class="rule"></span></h2><div class="pgrid">';
    html += '<div class="pbox ceil"><div class="lbl">Legal maximum</div>' +
      (c ? '<div class="amt">' + money(c.pr) + '</div><div class="per">per ' + esc(c.u) + '</div>' +
           '<div class="who">' + esc(c.f) + (c.nr ? " &middot; " + esc(c.nr) : "") + '</div>'
         : '<div class="none">No same-strength ceiling on record</div>') + '</div>';
    html += '<div class="pbox floor"><div class="lbl">Government generic</div>' +
      (f ? '<div class="amt">' + money(f.pr) + '</div><div class="per">per ' + esc(f.u) + '</div>' +
           '<div class="who">' + esc(f.g) + '</div>'
         : '<div class="none">No same-strength generic on record</div>') + '</div>';
    html += '</div>';

    if (c && f) {
      const cu = parseUnit(c.u, c.f), fu = parseUnit(f.u, f.g);
      const cq = cu[0], ck = cu[1], fq = fu[0], fk = fu[1];
      if (COMB.test(c.f) || COMB.test(f.g)) {
        html += '<div class="ratio"><span class="t">No ratio shown &mdash; one of these matches ' +
                'is a combination product, so the two figures are not the same medicine.</span></div>';
      } else if (ck === fk && cq && fq) {
        const pc = c.pr / cq, pf = f.pr / fq;
        const pct = Math.max(3, Math.min(100, (pf / pc) * 100));
        html += '<div class="barcap"><div class="barlbl"><span>generic ' + money(pf) + ' / ' +
                esc(ck) + '</span><span>ceiling ' + money(pc) + ' / ' + esc(ck) + '</span></div>' +
                '<div class="bar"><div class="seg-floor" style="width:' + pct.toFixed(1) +
                '%"></div><div class="seg-rest"></div></div></div>';
        html += '<div class="ratio"><span class="x">' + (pc / pf).toFixed(1) + '&times;</span>' +
                '<span class="t">between the government generic and the legal ceiling</span></div>';
      } else {
        html += '<div class="ratio"><span class="t">The two sources quote different units, so ' +
                'no per-unit comparison is shown.</span></div>';
      }
    }
    if (c && COMB.test(c.f)) html += '<div class="warn">The ceiling shown is a combination product that contains this ingredient &mdash; it is not the price of the ingredient alone.</div>';
    if (f && COMB.test(f.g)) html += '<div class="warn">The generic shown is a combination product that contains this ingredient.</div>';
    html += '<div class="prov">Both figures come from third-party mirrors of the official documents, not from the issuing bodies. Verify against the primary source before relying on it. NPPA prices exclude GST.</div>';
    html += '<div class="note">Charging above the NPPA ceiling for a scheduled formulation is illegal. Not medical advice &mdash; composition match is not proven therapeutic equivalence. Ask your prescriber before changing anything.</div>';
    html += '</div>';
  }

  html += '<div class="card"><h2>Regulatory record<span class="rule"></span></h2>';

  html += '<div class="tier t1"><div class="head"><span class="badge">Tier 1</span>' +
          '<span class="name">CDSCO NSQ batch alerts</span></div>' +
          '<p class="src">Batches that failed laboratory testing. Recorded by the regulator.</p>';
  if (!nsq.length) html += '<p class="src" style="font-style:italic">No batch alert on record for this name.</p>';
  for (const r of nsq) {
    html += '<div class="rec"><div class="rname">' + esc(r.p) + '</div><dl>' +
      '<dt>batch</dt><dd class="mono">' + (esc(r.b) || "&mdash;") + '</dd>' +
      '<dt>maker</dt><dd>' + esc(r.m) + '</dd>' +
      '<dt>reason</dt><dd>' + (esc(r.r) || "&mdash;") + '</dd>' +
      '<dt>alert</dt><dd>' + (r.s === "state" ? "state" : "central") + ' lab, ' +
      r.y + '-' + String(r.mo).padStart(2, "0") + '</dd>' +
      (r.u ? '<dt>document</dt><dd><a href="' + esc(r.u) + '" target="_blank" rel="noopener">original alert PDF &nearr;</a></dd>' : '') +
      '</dl></div>';
  }
  html += '</div>';

  html += '<div class="tier t2"><div class="head"><span class="badge">Tier 2</span>' +
          '<span class="name">WHO Medical Product Alerts</span></div>' +
          '<p class="src">Recalls, suspensions and contamination events. Published by WHO.</p>';
  if (!who.length) html += '<p class="src" style="font-style:italic">No WHO alert on record for this name.</p>';
  for (const r of who) {
    html += '<div class="rec"><div class="rname">' + esc(r.l) + '</div><dl>' +
      (r.d ? '<dt>date</dt><dd>' + esc(r.d) + '</dd>' : '') +
      (r.p ? '<dt>products</dt><dd>' + esc(r.p) + '</dd>' : '') +
      (r.m ? '<dt>makers</dt><dd>' + esc(r.m) + '</dd>' : '') +
      (r.u ? '<dt>source</dt><dd><a href="' + esc(r.u) + '" target="_blank" rel="noopener">WHO alert &nearr;</a></dd>' : '') +
      '</dl></div>';
  }
  html += '</div>';

  html += '<div class="note">An NSQ finding is <strong>batch-specific</strong>: one batch failed testing on one date for the stated reason. It is not a statement about the company. Absence of a record is <strong>not</strong> evidence of quality &mdash; only sampled batches are tested. The two tiers are never merged: Tier 1 is a regulator record, Tier 2 is a WHO publication. Not medical advice &mdash; never change a prescribed medicine without asking the prescriber.</div>';
  html += '</div>';

  out.innerHTML = html;
}

/* ---------- suggestions ---------- */
function renderSug() {
  curSug = suggest(qEl.value);
  selIdx = -1;
  if (!curSug.length) { sugEl.classList.remove("on"); sugEl.innerHTML = ""; return; }
  const k = key(qEl.value);
  sugEl.innerHTML = curSug.map((s, i) =>
    '<button type="button" data-i="' + i + '">' + hl(s.t, k) +
    '<span class="cnt">' + s.n + '</span></button>').join("");
  sugEl.classList.add("on");
  sugEl.querySelectorAll("button").forEach(b => b.addEventListener("mousedown", e => {
    e.preventDefault();
    pick(parseInt(b.dataset.i, 10));
  }));
}
function pick(i) {
  if (!curSug[i]) return;
  qEl.value = curSug[i].t;
  sugEl.classList.remove("on");
  selIdx = -1;
  pushState();
  render();
}
function moveSel(d) {
  if (!curSug.length) return;
  selIdx = (selIdx + d + curSug.length) % curSug.length;
  sugEl.querySelectorAll("button").forEach((b, i) => b.classList.toggle("sel", i === selIdx));
}

/* ---------- state ---------- */
function pushState() {
  const p = new URLSearchParams();
  if (qEl.value.trim()) p.set("q", qEl.value.trim());
  if (formEl.value) p.set("f", formEl.value);
  const qs = p.toString();
  history.replaceState(null, "", qs ? "?" + qs : location.pathname);
}
function readState() {
  const p = new URLSearchParams(location.search);
  if (p.get("q")) qEl.value = p.get("q");
  if (p.get("f")) formEl.value = p.get("f");
}

/* ---------- wire up ---------- */
let timer = null;
qEl.addEventListener("input", () => {
  renderSug();
  clearTimeout(timer);
  timer = setTimeout(() => { pushState(); render(); }, 120);
});
qEl.addEventListener("focus", renderSug);
qEl.addEventListener("blur", () => setTimeout(() => sugEl.classList.remove("on"), 120));
qEl.addEventListener("keydown", e => {
  if (e.key === "ArrowDown") { e.preventDefault(); moveSel(1); }
  else if (e.key === "ArrowUp") { e.preventDefault(); moveSel(-1); }
  else if (e.key === "Enter") { if (selIdx >= 0) { e.preventDefault(); pick(selIdx); } }
  else if (e.key === "Escape") { sugEl.classList.remove("on"); }
});
formEl.addEventListener("change", () => { pushState(); render(); });
clearEl.addEventListener("click", () => {
  qEl.value = ""; qEl.focus(); clearEl.classList.remove("on");
  sugEl.classList.remove("on"); pushState(); render();
});

/* ---------- boot ---------- */
document.getElementById("s1").textContent = DATA.nsq.length.toLocaleString("en-IN");
document.getElementById("s2").textContent = DATA.who.length;
document.getElementById("s3").textContent = DATA.nppa.length.toLocaleString("en-IN");
document.getElementById("s4").textContent = DATA.ja.length.toLocaleString("en-IN");

const EXAMPLES = ["atorvastatin 10mg", "metformin 500mg", "paracetamol 500mg", "coldrif"];
document.getElementById("chips").innerHTML = EXAMPLES.map(e =>
  '<button class="chip" type="button" data-q="' + esc(e) + '">' + esc(e) + '</button>').join("");
document.querySelectorAll(".chip").forEach(b => b.addEventListener("click", () => {
  qEl.value = b.dataset.q; pushState(); render(); qEl.focus();
}));

readState();
if (!qEl.value) qEl.value = "atorvastatin 10mg";
pushState();
render();
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
    # Python turns an unescaped \b in a plain string into a backspace character and
    # does NOT warn about it (unlike \d). That silently produced a regex which could
    # never match. Refuse to write output containing control characters.
    bad = {c for c in html if ord(c) < 32 and c not in "\n\t"}
    if bad:
        codes = ", ".join(f"0x{ord(c):02x}" for c in sorted(bad))
        raise SystemExit(
            f"refusing to write: generated HTML contains control characters ({codes}). "
            "An unescaped \\b or \\f in a Python string literal becomes a control "
            "character and silently breaks the JS regexes."
        )
    OUT.write_text(html, encoding="utf-8")
    # Second copy for GitHub Pages (served from /docs on main).
    pages = ROOT / "docs" / "index.html"
    pages.write_text(html, encoding="utf-8")
    print(f"nsq {len(payload['nsq']):,} | who {len(payload['who'])} | "
          f"nppa {len(payload['nppa'])} | janaushadhi {len(payload['ja']):,} | "
          f"salt index {len(payload['salts'])}")
    print(f"-> {OUT.relative_to(ROOT)}  ({OUT.stat().st_size / 1024:.0f} KB, self-contained)")
    print(f"-> {pages.relative_to(ROOT)}  (GitHub Pages copy)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
