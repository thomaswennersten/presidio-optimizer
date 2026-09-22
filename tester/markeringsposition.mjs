/* Reproducerar felet: markerar man text EFTER en egen tagg hamnar markeringen
   några tecken för långt fram.

   Orsak: varje egen tagg ritas som ett <sup class="fn-typ"> med typnamnet efter
   texten. Den etiketten är riktig text i DOM:en men finns inte i originalet, så
   positionsberäkningen räknar för högt — och driften växer med varje tagg.

   Kör:  JSDOM_MODUL=/tmp/t/node_modules/jsdom/lib/api.js node tester/markeringsposition.mjs */

const { JSDOM } = await import(process.env.JSDOM_MODUL || 'jsdom');
import fs from 'fs';

const js = fs.readFileSync('/opt/app/presidio-optimizer/frontend/js/text-annotator.js', 'utf8');

const TEXT = [
  'Yrkeskategori  Timarvode  Övertid enkel  Övertid kvalificerad',
  'Snickare       685 kr     1 028 kr       1 370 kr',
  'Elektriker     745 kr     1 118 kr       1 490 kr',
].join('\n');

const dom = new JSDOM('<div id="annotated-text"></div><div id="entity-popup"></div>',
                      { runScripts: 'outside-only', url: 'http://localhost/' });
const w = dom.window;
// const på skriptnivå blir INTE en egenskap på window — modulen måste räckas
// över uttryckligen. Samma fälla som i maskeras jsdom-test.
w.eval(js + '\n;window.__TA = TextAnnotator;');
const TA = w.__TA;

const behallare = w.document.getElementById('annotated-text');

// En egen tagg (false negative) på "685 kr" — precis det arbetssätt som utlöser felet.
const start685 = TEXT.indexOf('685 kr');
TA.setFeedback([], [{ start: start685, end: start685 + 6, entity_type: 'PRIS' }]);
TA.render(behallare, TEXT, [], false);

// Bygg en markering över exakt "1 028 kr" i den renderade texten.
const mal = '1 028 kr';
function hittaIDom(rot, strang) {
    const gang = rot.ownerDocument.createTreeWalker(rot, w.NodeFilter.SHOW_TEXT);
    let nod;
    while ((nod = gang.nextNode())) {
        const i = nod.textContent.indexOf(strang);
        if (i !== -1) return { nod, i };
    }
    return null;
}
let fel = 0;
function provaMarkering(namn, mal) {
    const t = hittaIDom(behallare, mal);
    if (!t) { console.log(`FEL  ${namn}: hittade inte ${JSON.stringify(mal)} i DOM:en`); fel++; return; }
    const range = w.document.createRange();
    range.setStart(t.nod, t.i);
    range.setEnd(t.nod, t.i + mal.length);
    const pos = TA.getTextPosition(behallare, range);
    const sant = TEXT.indexOf(mal);
    const ok = pos.start === sant && pos.end === sant + mal.length;
    if (!ok) fel++;
    console.log(`${ok ? 'OK  ' : 'FEL '} ${namn}`);
    console.log(`      markerat ${JSON.stringify(mal)} -> beräknat ${JSON.stringify(TEXT.slice(pos.start, pos.end))}`
                + `  (drift ${pos.start - sant})`);
}

provaMarkering('efter EN egen tagg', '1 028 kr');

// Flera egna taggar före markeringen — driften ackumulerade tidigare.
const start745 = TEXT.indexOf('745 kr');
TA.setFeedback([], [
    { start: start685, end: start685 + 6, entity_type: 'PRIS' },
    { start: start745, end: start745 + 6, entity_type: 'PRIS2' },
]);
TA.render(behallare, TEXT, [], false);
provaMarkering('efter TVÅ egna taggar', '1 490 kr');

// Markering efter en vanlig Presidio-träff ska också stämma.
TA.setFeedback([], []);
TA.render(behallare, TEXT, [{ start: start685, end: start685 + 6,
                              entity_type: 'PERSON', score: 0.85 }], false);
provaMarkering('efter en Presidio-träff', '1 028 kr');

// Utan några markeringar alls — grundfallet.
TA.setFeedback([], []);
TA.render(behallare, TEXT, [], false);
provaMarkering('utan markeringar', '1 370 kr');


/* ===== Osäkra träffar märks ut visuellt (2026-08-24) ===== */

TA.setFeedback([], []);
TA.render(behallare, TEXT, [
    { start: TEXT.indexOf('685 kr'), end: TEXT.indexOf('685 kr') + 6,
      entity_type: 'SWEDISH_PERSONNUMMER', score: 0.4 },
    { start: TEXT.indexOf('745 kr'), end: TEXT.indexOf('745 kr') + 6,
      entity_type: 'SWEDISH_PERSONNUMMER', score: 0.75 },
    { start: TEXT.indexOf('1 118 kr'), end: TEXT.indexOf('1 118 kr') + 8,
      entity_type: 'PERSON', score: 0.85 },
], false);

function klasser(text) {
    const spans = [...behallare.querySelectorAll('.entity-annotation')];
    const s = spans.find(x => x.textContent === text);
    return s ? [...s.classList] : null;
}
function prova(namn, faktisk, vantad) {
    const ok = faktisk === vantad;
    if (!ok) fel++;
    console.log(`${ok ? 'OK  ' : 'FEL '} ${namn}${ok ? '' : `  (fick ${faktisk}, väntade ${vantad})`}`);
}

prova('0,40 märks som osäker', klasser('685 kr').includes('poang-lag'), true);
prova('0,75 märks som delvis säker', klasser('745 kr').includes('poang-medel'), true);
prova('0,85 märks inte alls', klasser('1 118 kr').some(k => k.startsWith('poang-')), false);

const legend = w.document.createElement('div');
TA.renderLegend(legend, [
    { entity_type: 'SWEDISH_PERSONNUMMER', score: 0.4 },
    { entity_type: 'SWEDISH_PERSONNUMMER', score: 0.75 },
    { entity_type: 'PERSON', score: 0.85 },
]);
prova('förklaringen räknar de osäkra', /1 osäkra/.test(legend.textContent), true);
prova('förklaringen räknar de delvis säkra', /1 delvis säkra/.test(legend.textContent), true);
prova('förklaringen har en streckad svatch',
      Boolean(legend.querySelector('.legend-swatch.poang-lag')), true);

// Utan osäkra träffar ska ingen förklaring ritas — annars blir den brus.
const legend2 = w.document.createElement('div');
TA.renderLegend(legend2, [{ entity_type: 'PERSON', score: 0.85 }]);
prova('ingen förklaring när allt är säkert',
      Boolean(legend2.querySelector('.legend-osakerhet')), false);

// Positionerna får inte påverkas av de nya klasserna.
provaMarkering('positionen stämmer med osäkra träffar', '1 370 kr');

console.log(fel ? `\n${fel} test misslyckades` : '\nAlla test gick igenom');
process.exit(fel ? 1 : 0);
