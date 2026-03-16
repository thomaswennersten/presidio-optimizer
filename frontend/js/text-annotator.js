/**
 * Interaktiv textmarkering - kärnkomponent.
 *
 * - Visar text med färgkodade PII-markeringar
 * - Klicka på entitet → false positive
 * - Markera text → popup för att välja entitetstyp → false negative
 * - Hovra → tooltip med entitetstyp + score
 */
const TextAnnotator = (() => {
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

    let falsePositives = [];
    let falseNegatives = [];
    let currentText = '';
    let currentResults = [];
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
        container.innerHTML = '';

        if (!text) return;

        // Sort results by start position
        const sorted = [...results].sort((a, b) => a.start - b.start);

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
            span.className = `entity-annotation entity-${r.entity_type}`;
            span.textContent = text.slice(r.start, r.end);
            span.dataset.start = r.start;
            span.dataset.end = r.end;
            span.dataset.entityType = r.entity_type;
            span.dataset.score = r.score || 0;
            span.dataset.recognizer = r.recognizer_name || '';

            if (!readOnly) {
                span.addEventListener('click', handleEntityClick);
            }
            span.addEventListener('mouseenter', showTooltip);
            span.addEventListener('mouseleave', hideTooltip);

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

        // Apply false negative marks
        container.appendChild(frag);
        applyFalseNegativeMarks(container);
    }

    function renderLegend(container, results) {
        const types = new Set(results.map(r => r.entity_type));
        container.innerHTML = '';
        for (const t of ENTITY_TYPES) {
            if (!types.has(t)) continue;
            const item = document.createElement('span');
            item.className = 'legend-item';
            item.innerHTML = `<span class="legend-dot entity-${t}" style="background:var(--c)"></span>${ENTITY_LABELS[t] || t}`;
            // Extract background color from CSS class
            const tmp = document.createElement('span');
            tmp.className = `entity-annotation entity-${t}`;
            document.body.appendChild(tmp);
            const bg = getComputedStyle(tmp).borderBottomColor;
            document.body.removeChild(tmp);
            item.querySelector('.legend-dot').style.background = bg;
            container.appendChild(item);
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
            if (node === range.startContainer) {
                startPos = offset + range.startOffset;
            }
            if (node === range.endContainer) {
                endPos = offset + range.endOffset;
            }
            if (node.nodeType === Node.TEXT_NODE) {
                offset += node.textContent.length;
            } else if (node.nodeType === Node.ELEMENT_NODE) {
                if (node.classList && node.classList.contains('entity-annotation')) {
                    const s = parseInt(node.dataset.start);
                    const e = parseInt(node.dataset.end);
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
                falseNegatives.push({
                    start, end, entity_type: t, text,
                });
                popup.classList.add('hidden');
                window.getSelection().removeAllRanges();
                notifyChange();
                // Re-render to show the false negative mark
                const container = document.getElementById('annotated-text');
                applyFalseNegativeMarks(container);
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
        popup.classList.remove('hidden');
    }

    function applyFalseNegativeMarks(container) {
        // Remove existing marks
        container.querySelectorAll('.false-negative-mark').forEach(m => {
            const parent = m.parentNode;
            while (m.firstChild) parent.insertBefore(m.firstChild, m);
            parent.removeChild(m);
        });

        // This is simplified - for a production version we'd need TreeWalker
        // For now, show false negatives as a separate indicator
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

    function clearFeedback() {
        falsePositives = [];
        falseNegatives = [];
        notifyChange();
    }

    function getEntityTypes() { return ENTITY_TYPES; }
    function getEntityLabels() { return ENTITY_LABELS; }

    return { init, render, renderLegend, getFeedback, clearFeedback, getEntityTypes, getEntityLabels };
})();
