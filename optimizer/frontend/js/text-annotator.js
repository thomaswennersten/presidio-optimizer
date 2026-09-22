/*
 * Presidio Optimizer
 * Copyright (C) 2026 Sambruk
 *
 * Detta program är fri programvara; du får sprida och ändra det enligt
 * villkoren i GNU General Public License version 2, som den publicerats av
 * Free Software Foundation.
 *
 * Programmet distribueras i hopp om att det ska vara användbart, men UTAN
 * NÅGON GARANTI. Se GNU General Public License för fler detaljer.
 * Se filen LICENSE.
 */

/**
 * Interaktiv textmarkering - kärnkomponent.
 *
 * - Visar text med färgkodade PII-markeringar
 * - Klicka på entitet → false positive
 * - Markera text → popup för att välja entitetstyp → false negative
 * - Hovra → tooltip med entitetstyp + score
 */
const TextAnnotator = (() => {
    // Egna typer sparas lokalt i webbläsaren. Bakänden validerar inte
    // entity_type (den är en fri sträng), så de går hela vägen till optimeringen.
    const CUSTOM_KEY = 'optimizer_custom_entity_types';

    function loadCustomTypes() {
        try { return JSON.parse(localStorage.getItem(CUSTOM_KEY)) || {}; }
        catch { return {}; }
    }
    function saveCustomTypes(map) {
        localStorage.setItem(CUSTOM_KEY, JSON.stringify(map));
    }

    const ENTITY_TYPES = [
        'PERSON', 'SWEDISH_PERSONNUMMER', 'SWEDISH_SAMORDNINGSNUMMER',
        'SWEDISH_ORGANISATIONSNUMMER', 'SWEDISH_PHONE_NUMBER', 'PHONE_NUMBER',
        'EMAIL_ADDRESS', 'LOCATION', 'DATE_TIME', 'ORGANIZATION',
        'CREDIT_CARD', 'IBAN_CODE', 'IP_ADDRESS', 'URL', 'NRP', 'MEDICAL_LICENSE',
    ];

    const ENTITY_LABELS = {
        'PERSON': 'Person',
        'SWEDISH_PERSONNUMMER': 'Personnummer',
        'SWEDISH_SAMORDNINGSNUMMER': 'Samordningsnr',
        'SWEDISH_ORGANISATIONSNUMMER': 'Organisationsnr',
        'SWEDISH_PHONE_NUMBER': 'Sv. telefon',
        'PHONE_NUMBER': 'Telefon',
        'EMAIL_ADDRESS': 'E-post',
        'LOCATION': 'Plats',
        'DATE_TIME': 'Datum/Tid',
        'ORGANIZATION': 'Organisation',
        'CREDIT_CARD': 'Kreditkort',
        'IBAN_CODE': 'IBAN',
        'IP_ADDRESS': 'IP-adress',
        'URL': 'URL',
        'NRP': 'Nationalitet',
        'MEDICAL_LICENSE': 'Medicinsk licens',
    };

    // Slå in de sparade egna typerna direkt vid start.
    (function initCustomTypes() {
        const custom = loadCustomTypes();
        for (const [typ, etikett] of Object.entries(custom)) {
            if (!ENTITY_TYPES.includes(typ)) ENTITY_TYPES.push(typ);
            ENTITY_LABELS[typ] = etikett;
            ensureColor(typ);
        }
    })();

    // Egna typer saknar CSS-regel — skapa en deterministisk färg ur namnet så att
    // samma typ alltid får samma färg, även mellan sessioner.
    function ensureColor(typ) {
        const id = `entity-color-${typ}`;
        if (document.getElementById(id)) return;
        let h = 0;
        for (let i = 0; i < typ.length; i++) h = (h * 31 + typ.charCodeAt(i)) % 360;
        const style = document.createElement('style');
        style.id = id;
        style.textContent = `.entity-${typ} { background: hsla(${h},65%,55%,0.30);` +
                            ` border-bottom-color: hsl(${h},65%,60%); }`;
        document.head.appendChild(style);
    }

    function addCustomType(rawName) {
        const etikett = String(rawName || '').trim();
        if (!etikett) return null;
        // Presidio-konventionen är VERSALER_MED_UNDERSTRECK.
        const typ = etikett.toUpperCase()
            .replace(/[ÅÄ]/g, 'A').replace(/Ö/g, 'O')
            .replace(/[^A-Z0-9]+/g, '_').replace(/^_+|_+$/g, '');
        if (!typ) return null;
        if (!ENTITY_TYPES.includes(typ)) ENTITY_TYPES.push(typ);
        ENTITY_LABELS[typ] = etikett;
        ensureColor(typ);
        const custom = loadCustomTypes();
        custom[typ] = etikett;
        saveCustomTypes(custom);
        return typ;
    }

    let falsePositives = [];
    let falseNegatives = [];
    let currentText = '';
    let currentResults = [];
    let currentReadOnly = false;
    let onFeedbackChange = null;

    function init(callback) {
        onFeedbackChange = callback;
        document.addEventListener('mouseup', handleTextSelection);

        // Block browser context menu on the annotated text area
        // so it doesn't cover the entity type popup
        document.addEventListener('contextmenu', e => {
            const container = document.getElementById('annotated-text');
            if (container && container.contains(e.target)) {
                e.preventDefault();
                // Trigger selection handling on right-click too
                handleTextSelection();
            }
        });

        setupPopup();
    }

    function render(container, text, results, readOnly) {
        currentText = text;
        currentResults = results;
        currentReadOnly = !!readOnly;
        container.innerHTML = '';

        if (!text) return;

        // Egna taggningar (false negatives) ritas i SAMMA svep som träffarna.
        // Tidigare fanns bara en stubbe som rensade gamla markeringar utan att
        // rita nya, så en tagg sparades men syntes aldrig i texten.
        const sorted = [
            ...results.map(r => ({ ...r, _fn: false })),
            ...falseNegatives.map(f => ({ ...f, _fn: true })),
        ].sort((a, b) => a.start - b.start || (a._fn ? 1 : -1));

        let lastIdx = 0;
        const frag = document.createDocumentFragment();

        for (const r of sorted) {
            if (r.start < lastIdx) continue; // skip overlapping

            // Text before entity
            if (r.start > lastIdx) {
                frag.appendChild(document.createTextNode(text.slice(lastIdx, r.start)));
            }

            // Entity span
            const span = document.createElement('span');
            span.className = r._fn
                ? `false-negative-mark entity-${r.entity_type}`
                : `entity-annotation entity-${r.entity_type}`;
            span.textContent = text.slice(r.start, r.end);
            span.dataset.start = r.start;
            span.dataset.end = r.end;
            span.dataset.entityType = r.entity_type;
            span.dataset.score = r.score || 0;
            span.dataset.recognizer = r.recognizer_name || '';

            if (r._fn) {
                span.title = `Du har taggat detta som ${ENTITY_LABELS[r.entity_type] || r.entity_type}`
                           + ' — klicka för att ångra';
                if (!readOnly) {
                    span.addEventListener('click', () => {
                        falseNegatives = falseNegatives.filter(
                            f => !(f.start === r.start && f.end === r.end
                                   && f.entity_type === r.entity_type));
                        notifyChange();
                        render(container, currentText, currentResults, currentReadOnly);
                    });
                }
                frag.appendChild(span);
                // Liten etikett efter texten, så det syns VAD man taggade den som.
                const badge = document.createElement('sup');
                badge.className = 'fn-typ';
                // Etiketten är text i DOM:en som INTE finns i originaltexten.
                // Utan den här märkningen räknar getTextPosition med den, och
                // varje egen tagg förskjuter alla senare markeringar lika många
                // tecken som typnamnet är långt.
                badge.dataset.dekor = '1';
                badge.textContent = ENTITY_LABELS[r.entity_type] || r.entity_type;
                frag.appendChild(badge);
                lastIdx = r.end;
                continue;
            }

            if (!readOnly) {
                span.addEventListener('click', handleEntityClick);
            }
            span.addEventListener('mouseenter', showTooltip);
            span.addEventListener('mouseleave', hideTooltip);

            // Osäkerheten ska synas UTAN att man hovrar. Signalen sitter i
            // ramens FORM, inte i färgen — bottenramens färg bär redan
            // entitetstypen, och en signal som bara är färg är otillgänglig.
            //
            // Nivåerna följer vad poängen faktiskt betyder i kedjan:
            //   0,85  mönster + kontrollsiffra stämmer, eller NER-träff
            //   0,75  kontrollsiffran stämmer INTE, men ett kontextord finns nära
            //   0,40  kontrollsiffran stämmer inte och inget kontextord finns
            const poang = Number(r.score) || 0;
            if (poang < 0.5) span.classList.add('poang-lag');
            else if (poang < 0.8) span.classList.add('poang-medel');

            // Check if marked as false positive
            const isFP = falsePositives.some(
                fp => fp.start === r.start && fp.end === r.end
            );
            if (isFP) span.classList.add('false-positive');

            frag.appendChild(span);
            lastIdx = r.end;
        }

        // Remaining text
        if (lastIdx < text.length) {
            frag.appendChild(document.createTextNode(text.slice(lastIdx)));
        }

        container.appendChild(frag);
    }

    function renderLegend(container, results) {
        const types = new Set(results.map(r => r.entity_type));
        container.innerHTML = '';
        for (const t of ENTITY_TYPES) {
            if (!types.has(t)) continue;
            const item = document.createElement('span');
            item.className = 'legend-item';
            // Svatchen ritas med SAMMA klass som markeringen i texten, så att
            // färgen i förklaringen är identisk med den man ser i dokumentet.
            // Tidigare var svatchen heltäckande medan markeringen var 30 % genomskinlig.
            const antal = results.filter(r => r.entity_type === t).length;
            item.innerHTML = `<span class="legend-swatch entity-${t}"></span>` +
                             `${ENTITY_LABELS[t] || t} <span class="legend-count">${antal}</span>`;
            item.title = `${t} — ${antal} förekomster i texten`;
            container.appendChild(item);
        }

        // Förklara formerna, men bara när det finns något att förklara.
        const lag = results.filter(r => (Number(r.score) || 0) < 0.5).length;
        const medel = results.filter(r => {
            const p = Number(r.score) || 0;
            return p >= 0.5 && p < 0.8;
        }).length;
        if (lag || medel) {
            const forklaring = document.createElement('span');
            forklaring.className = 'legend-item legend-osakerhet';
            const delar = [];
            if (lag) delar.push(`<span class="legend-swatch poang-lag"></span>${lag} osäkra`);
            if (medel) delar.push(`<span class="legend-swatch poang-medel"></span>${medel} delvis säkra`);
            forklaring.innerHTML = delar.join(' ');
            forklaring.title = 'Streckad ram: mönstret stämmer men kontrollsiffran gör det '
                             + 'inte. Prickad ram: kontrollsiffran stämmer inte, men ett '
                             + 'kontextord i närheten höjde poängen. Hovra för exakt poäng.';
            container.appendChild(forklaring);
        }
    }

    function handleEntityClick(e) {
        e.stopPropagation();
        const span = e.currentTarget;
        const start = parseInt(span.dataset.start);
        const end = parseInt(span.dataset.end);
        const entityType = span.dataset.entityType;

        // Toggle false positive
        const idx = falsePositives.findIndex(fp => fp.start === start && fp.end === end);
        if (idx >= 0) {
            falsePositives.splice(idx, 1);
            span.classList.remove('false-positive');
        } else {
            falsePositives.push({
                start, end, entity_type: entityType,
                text: currentText.slice(start, end),
                score: parseFloat(span.dataset.score) || 0,
            });
            span.classList.add('false-positive');
        }
        notifyChange();
    }

    function handleTextSelection() {
        const sel = window.getSelection();
        if (!sel || sel.isCollapsed || !sel.rangeCount) return;

        const range = sel.getRangeAt(0);
        const container = document.getElementById('annotated-text');
        if (!container || !container.contains(range.commonAncestorContainer)) return;

        const selectedText = sel.toString().trim();
        if (!selectedText || selectedText.length < 2) return;

        // Calculate position in original text
        const pos = getTextPosition(container, range);
        if (pos.start < 0) return;

        // Check if selection overlaps existing entity
        const overlaps = currentResults.some(
            r => pos.start < r.end && pos.end > r.start
        );
        if (overlaps) return;

        showEntityPopup(pos.start, pos.end, selectedText);
    }

    function getTextPosition(container, range) {
        // Walk through child nodes to find text position
        let offset = 0;
        let startPos = -1;
        let endPos = -1;

        function walk(node) {
            // Rent visuella tillägg (typetiketten efter en egen tagg) finns inte
            // i originaltexten och får varken räknas eller synkas mot.
            if (node.nodeType === Node.ELEMENT_NODE && node.dataset && node.dataset.dekor) {
                return;
            }

            if (node === range.startContainer) {
                startPos = offset + range.startOffset;
            }
            if (node === range.endContainer) {
                endPos = offset + range.endOffset;
            }
            if (node.nodeType === Node.TEXT_NODE) {
                offset += node.textContent.length;
            } else if (node.nodeType === Node.ELEMENT_NODE) {
                // Både Presidios träffar och egna taggar bär sina positioner i
                // originaltexten. Synka mot dem i stället för att lita på den
                // hopräknade längden — då kan ingen drift bli bestående, oavsett
                // vad renderingen råkar lägga till i DOM:en.
                const markering = node.classList && (
                    node.classList.contains('entity-annotation') ||
                    node.classList.contains('false-negative-mark'));
                if (markering && node.dataset.start !== undefined) {
                    const s = parseInt(node.dataset.start, 10);
                    const e = parseInt(node.dataset.end, 10);
                    if (node === range.startContainer || node.contains(range.startContainer)) {
                        startPos = s + (range.startOffset || 0);
                    }
                    if (node === range.endContainer || node.contains(range.endContainer)) {
                        endPos = s + (range.endOffset || 0);
                    }
                    offset = e;
                    return;
                }
                for (const child of node.childNodes) {
                    walk(child);
                }
            }
        }
        walk(container);
        return { start: startPos, end: endPos };
    }

    function setupPopup() {
        document.addEventListener('click', e => {
            const popup = document.getElementById('entity-popup');
            if (!popup.contains(e.target)) {
                popup.classList.add('hidden');
            }
        });
    }

    // Gemensam väg för att tagga en missad uppgift. Fanns tidigare duplicerad
    // i två klick-hanterare, och ingen av dem varnade när markeringen överlappade
    // en redan detekterad entitet — då försvann taggen tyst vid utritningen.
    function taggaFalseNegative(start, end, text, typ) {
        const krock = currentResults.find(r => start < r.end && end > r.start);
        if (krock) {
            window.alert(
                `"${currentText.slice(krock.start, krock.end)}" är redan markerat som `
                + `${ENTITY_LABELS[krock.entity_type] || krock.entity_type}.\n\n`
                + 'Klicka på markeringen istället om typen är fel — då räknas den som '
                + 'en felaktig träff, vilket är den feedback optimeringen behöver.');
            return false;
        }
        const finns = falseNegatives.some(
            f => f.start === start && f.end === end && f.entity_type === typ);
        if (!finns) falseNegatives.push({ start, end, entity_type: typ, text });
        return true;
    }

    function showEntityPopup(start, end, text) {
        const popup = document.getElementById('entity-popup');
        const list = document.getElementById('entity-popup-list');
        list.innerHTML = '';

        for (const t of ENTITY_TYPES) {
            const item = document.createElement('div');
            item.className = 'entity-popup-item';
            item.innerHTML = `<span class="legend-dot entity-${t}"></span>${ENTITY_LABELS[t] || t}`;

            const tmp = document.createElement('span');
            tmp.className = `entity-annotation entity-${t}`;
            document.body.appendChild(tmp);
            const bg = getComputedStyle(tmp).borderBottomColor;
            document.body.removeChild(tmp);
            item.querySelector('.legend-dot').style.background = bg;

            item.addEventListener('click', () => {
                const ok = taggaFalseNegative(start, end, text, t);
                popup.classList.add('hidden');
                window.getSelection().removeAllRanges();
                if (!ok) return;
                notifyChange();
                applyFalseNegativeMarks(document.getElementById('annotated-text'));
            });
            list.appendChild(item);
        }

        // Position popup near selection
        const sel = window.getSelection();
        if (sel.rangeCount) {
            const rect = sel.getRangeAt(0).getBoundingClientRect();
            popup.style.top = `${rect.bottom + window.scrollY + 5}px`;
            popup.style.left = `${rect.left + window.scrollX}px`;
        }
        // Egen typ sist i listan — för uppgifter som inte finns bland de fördefinierade.
        const egen = document.createElement('div');
        egen.className = 'entity-popup-item entity-popup-custom';
        egen.innerHTML = '<span class="legend-dot" style="background:#90a4ae"></span>+ Egen typ…';
        egen.addEventListener('click', () => {
            const namn = window.prompt(
                'Vad ska den här sortens uppgift heta?\n' +
                'Skriv namnet som du vill se det, t.ex. "Diarienummer" eller "Fastighetsbeteckning".');
            const typ = addCustomType(namn);
            if (!typ) return;
            const ok = taggaFalseNegative(start, end, text, typ);
            popup.classList.add('hidden');
            window.getSelection().removeAllRanges();
            if (!ok) return;
            notifyChange();
            applyFalseNegativeMarks(document.getElementById('annotated-text'));
        });
        list.appendChild(egen);

        popup.classList.remove('hidden');
    }

    function applyFalseNegativeMarks(container) {
        // Ritar om hela texten. render() tar med falseNegatives, så markeringarna
        // hamnar rätt utan DOM-kirurgi (som den gamla stubben aldrig gjorde).
        if (!container || !currentText) return;
        render(container, currentText, currentResults, currentReadOnly);
    }

    function showTooltip(e) {
        const span = e.currentTarget;
        const tooltip = document.createElement('div');
        tooltip.className = 'entity-tooltip';
        const type = ENTITY_LABELS[span.dataset.entityType] || span.dataset.entityType;
        const score = parseFloat(span.dataset.score).toFixed(2);
        const rec = span.dataset.recognizer;
        let html = `<strong>${type}</strong> · Score: ${score}`;
        if (rec) html += ` · ${rec}`;
        tooltip.innerHTML = html;
        span.appendChild(tooltip);
    }

    function hideTooltip(e) {
        const tooltip = e.currentTarget.querySelector('.entity-tooltip');
        if (tooltip) tooltip.remove();
    }

    function notifyChange() {
        if (onFeedbackChange) {
            onFeedbackChange(falsePositives, falseNegatives);
        }
    }

    function getFeedback() {
        return { falsePositives: [...falsePositives], falseNegatives: [...falseNegatives] };
    }

    // Används vid återupptagning av en session — utan detta gick tidigare
    // markeringar förlorade även om de låg kvar på servern.
    function setFeedback(fp, fn) {
        falsePositives = Array.isArray(fp) ? [...fp] : [];
        falseNegatives = Array.isArray(fn) ? [...fn] : [];
        for (const f of falseNegatives) ensureColor(f.entity_type);
    }

    function clearFeedback() {
        falsePositives = [];
        falseNegatives = [];
        notifyChange();
    }

    function getEntityTypes() { return ENTITY_TYPES; }
    function getEntityLabels() { return ENTITY_LABELS; }

    return { init, render, renderLegend, getFeedback, setFeedback, clearFeedback,
             getEntityTypes, getEntityLabels, addCustomType,
             // Exponerad för test. Positionsberäkningen är den del som tyst kan
             // ge fel svar — allt annat syns direkt i gränssnittet.
             getTextPosition };
})();
