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
 * Optimeringshistorik - tidslinje.
 */
const IterationHistory = (() => {
    let sessionId = null;

    function init(sid) {
        sessionId = sid;
    }

    async function loadHistory() {
        if (!sessionId) return;
        try {
            const data = await API.getConfigHistory(sessionId);
            renderTimeline(data.versions || []);
            if (data.versions && data.versions.length > 0) {
                document.getElementById('history-section').classList.remove('hidden');
            }
        } catch (e) {
            console.error('Failed to load history:', e);
        }
    }

    function renderTimeline(versions) {
        const container = document.getElementById('history-timeline');
        container.innerHTML = '';

        for (const v of versions) {
            const item = document.createElement('div');
            item.className = 'timeline-item';

            const time = v.created_at ? new Date(v.created_at).toLocaleString('sv-SE') : '';
            const customRec = v.num_custom_recognizers ? ` · ${v.num_custom_recognizers} custom recognizers` : '';

            item.innerHTML = `
                <div class="version-label">Version ${v.version}</div>
                <div class="version-desc">${v.description || 'Ingen beskrivning'}${customRec}</div>
                <div class="version-time">${time} · Tröskel: ${v.score_threshold}</div>
            `;
            container.appendChild(item);
        }
    }

    return { init, loadHistory };
})();
