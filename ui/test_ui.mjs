import fs from 'fs';

const html = fs.readFileSync('ui/index.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

const store = {};
const els = {
  q: { value: '', addEventListener() {}, classList: { toggle() {} }, focus() {} },
  form: { value: '', addEventListener() {} },
  out: { innerHTML: '' },
  sug: { innerHTML: '', classList: { add() {}, remove() {}, toggle() {} }, querySelectorAll: () => [] },
  clear: { classList: { toggle() {}, remove() {} }, addEventListener() {} },
  s1: { textContent: '' }, s2: { textContent: '' },
  s3: { textContent: '' }, s4: { textContent: '' },
  chips: { innerHTML: '' },
};
global.document = {
  getElementById: (id) => els[id],
  querySelectorAll: () => [],
};
global.history = { replaceState: (a, b, url) => { store.url = url; } };
global.location = { search: '', pathname: '/index.html' };

eval(script.replace(/^const DATA = /m, 'globalThis.DATA = ') +
  '\nglobalThis.key=key; globalThis.parseUnit=parseUnit; globalThis.strengthsOf=strengthsOf;' +
  '\nglobalThis.render=render; globalThis.suggest=suggest; globalThis.pushState=pushState;');

const P = (label, ok, extra) =>
  console.log((ok ? '  PASS  ' : '  FAIL  ') + label + (extra ? '  -> ' + extra : ''));

console.log('--- unit helpers ---');
P('key normalises punctuation + case',
  key('M/s. Pulse Pharma Pvt. Ltd.') === 'm s pulse pharma pvt ltd',
  JSON.stringify(key('M/s. Pulse Pharma Pvt. Ltd.')));
P('key matches regardless of noise (same normaliser both sides)',
  key('M/s. Pulse Pharma Pvt. Ltd.').includes(key('Pulse Pharma')));
P('parseUnit on "10\'s"', JSON.stringify(parseUnit("10's", 'Atorvastatin Tablets')) === '[10,"tablet"]');
P('parseUnit on "1 Capsule"', JSON.stringify(parseUnit('1 Capsule', 'Aspirin Capsules')) === '[1,"capsule"]');
P('mg and g compare equal',
  JSON.stringify([...strengthsOf('1000 mg')]) === JSON.stringify([...strengthsOf('1 g')]));

console.log();
console.log('--- autocomplete ---');
const s1 = suggest('atorva');
P('suggest("atorva") returns atorvastatin first',
  s1.length > 0 && s1[0].t === 'atorvastatin', JSON.stringify(s1.slice(0, 3)));
const s2 = suggest('metfor');
P('suggest("metfor") returns metformin first',
  s2.length > 0 && s2[0].t === 'metformin', JSON.stringify(s2.slice(0, 3)));
P('suggest("zz") returns nothing', suggest('zz').length === 0);
P('no salt-form noise in the index',
  !DATA.salts.some(s => ['hydrochloride', 'sodium', 'suture', 'needle'].includes(s.t)));

console.log();
console.log('--- stats wired ---');
P('stats populated',
  String(els.s1.textContent) === '3,591' && String(els.s2.textContent) === '15',
  els.s1.textContent + ' / ' + els.s2.textContent);

function run(q, f) {
  els.q.value = q;
  els.form.value = f || '';
  render();
  const t = els.out.innerHTML;
  const grab = (re) => { const m = t.match(re); return m ? m[1].replace(/<[^>]+>/g, '').trim() : null; };
  return {
    ceiling: grab(/Legal maximum<\/div><div class="amt">([^<]+)</),
    floor: grab(/Government generic<\/div><div class="amt">([^<]+)</),
    ratio: grab(/<span class="x">([^<]+)</),
    bar: /seg-floor" style="width:([\d.]+)%/.test(t),
    warn: /combination product/.test(t),
    prov: /third-party mirrors/.test(t),
    disc: /Not medical advice/.test(t),
    tiers: /Tier 1/.test(t) && /Tier 2/.test(t),
    records: (t.match(/<div class="rec">/g) || []).length,
    empty: /No record for/.test(t),
    doc: /original alert PDF/.test(t),
  };
}

console.log();
console.log('--- queries ---');
const cases = [
  ['atorvastatin 10mg', '', 'Rs 4.94 / Rs 8.80 / 5.6x, bar shown, no warning'],
  ['atorvastatin 10mg', 'tablet', 'same as above with the form filter'],
  ['atorvastatin 10mg', 'syrup', 'no price match (no syrup exists)'],
  ['metformin 500mg', 'tablet', 'combination ceiling -> warning, no ratio'],
  ['coldrif', '', 'both tiers, no price, document link'],
  ['zzzznope', '', 'empty state'],
];
for (const [q, f, expect] of cases) {
  const r = run(q, f);
  console.log('  ' + q + ' [' + (f || 'any') + ']');
  console.log('     ' + JSON.stringify(r));
  console.log('     expect: ' + expect);
}

console.log();
console.log('--- URL state ---');
els.q.value = 'metformin';
els.form.value = 'tablet';
pushState();
render();
console.log('  state url ->', store.url);
P('url carries the query', /q=metformin/.test(store.url || ''));
P('url carries the form', /f=tablet/.test(store.url || ''));
