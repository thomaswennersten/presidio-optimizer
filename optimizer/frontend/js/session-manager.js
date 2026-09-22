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
 * SessionManager - Hanterar namngivna persistenta sessioner.
 */
const SessionManager = (() => {
    let onSessionSelected = null;
    let sessionsData = [];

    function init(callback) {
        onSessionSelected = callback;

        document.getElementById('create-session-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const input = document.getElementById('session-name-input');
            const name = input.value.trim();
            if (!name) return;

            try {
                const btn = document.getElementById('create-session-btn');
                btn.disabled = true;
                btn.textContent = 'Skapar...';

                const result = await API.createSession(name);
                input.value = '';
                if (onSessionSelected) {
                    onSessionSelected(result.session_id, result.name);
                }
            } catch (e) {
                if (e.message === 'AUTH_REQUIRED') throw e;
                alert('Kunde inte skapa session: ' + e.message);
            } finally {
                const btn = document.getElementById('create-session-btn');
                btn.disabled = false;
                btn.textContent = 'Skapa session';
            }
        });
    }

    async function loadSessions() {
        const list = document.getElementById('session-list');
        const empty = document.getElementById('session-list-empty');

        try {
            const data = await API.listSessions();
            sessionsData = data.sessions || [];
        } catch (e) {
            if (e.message === 'AUTH_REQUIRED') throw e;
            sessionsData = [];
        }

        list.innerHTML = '';
        if (sessionsData.length === 0) {
            empty.classList.remove('hidden');
            return;
        }
        empty.classList.add('hidden');

        for (const s of sessionsData) {
            const item = document.createElement('div');
            item.className = 'session-item';

            const date = new Date(s.created_at + 'Z').toLocaleDateString('sv-SE', {
                year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
            });

            item.innerHTML = `
                <div class="session-item-header">
                    <div class="session-item-info">
                        <span class="session-item-name">${escapeHtml(s.name)}</span>
                        <span class="session-item-date">${date}</span>
                    </div>
                    <div class="session-item-meta">
                        ${s.filename ? `<span class="session-meta-tag">${escapeHtml(s.filename)}</span>` : ''}
                        ${s.iterations > 0 ? `<span class="session-meta-tag">${s.iterations} iterationer</span>` : ''}
                    </div>
                    <div class="session-item-actions">
                        <button class="btn btn-small btn-secondary session-files-toggle" data-id="${s.id}">Filer</button>
                        <button class="btn btn-small btn-primary session-open-btn" data-id="${s.id}" data-name="${escapeAttr(s.name)}">Fortsatt</button>
                        <button class="btn btn-small btn-fara session-delete-btn" data-id="${s.id}" data-name="${escapeAttr(s.name)}">Ta bort</button>
                    </div>
                </div>
                <div class="session-files-panel hidden" id="files-${s.id}">
                    <div class="session-files-loading">Laddar filer...</div>
                </div>
            `;

            list.appendChild(item);
        }

        // Delegerad hantering, kopplad EN gång. Tidigare lades en ny lyssnare
        // på vid varje omritning av listan — innerHTML rensar bara barnen, inte
        // lyssnare på behållaren. Efter tre omladdningar utlöstes varje klick
        // tre gånger, vilket blir synligt först när en knapp gör något
        // oåterkalleligt.
        if (!list.dataset.kopplad) {
            list.addEventListener('click', handleListClick);
            list.dataset.kopplad = '1';
        }
    }

    async function taBortSession(knapp) {
        const id = knapp.dataset.id;
        const namn = knapp.dataset.name;
        if (!confirm(`Ta bort sessionen "${namn}"?\n\n`
                   + 'Text, markeringar, iterationer och uppladdade filer försvinner '
                   + 'och går inte att få tillbaka.\n\n'
                   + 'Regelverk som publicerats till maskera ligger kvar och '
                   + 'påverkas inte — de tas bort separat under "Publicerade regelverk".')) {
            return;
        }
        knapp.disabled = true;
        knapp.textContent = 'Tar bort…';
        try {
            const svar = await API.deleteSession(id);
            const kvar = svar.publicerade_kvar || [];
            if (kvar.length) {
                // Sägs rakt ut. Annars tror den som städat att allt är borta,
                // medan ett regelverk fortfarande är i drift i maskera.
                alert(`Sessionen är borttagen.\n\n${kvar.length} publicerat `
                    + `regelverk ligger kvar i maskera: `
                    + kvar.map(k => k.config_id).join(', '));
            }
            await loadSessions();
        } catch (e) {
            if (e.message === 'AUTH_REQUIRED') throw e;
            alert(`Kunde inte ta bort sessionen: ${e.message}`);
            knapp.disabled = false;
            knapp.textContent = 'Ta bort';
        }
    }

    async function handleListClick(e) {
        const deleteBtn = e.target.closest('.session-delete-btn');
        if (deleteBtn) {
            await taBortSession(deleteBtn);
            return;
        }

        const openBtn = e.target.closest('.session-open-btn');
        if (openBtn) {
            const id = openBtn.dataset.id;
            const name = openBtn.dataset.name;
            if (onSessionSelected) onSessionSelected(id, name);
            return;
        }

        const filesToggle = e.target.closest('.session-files-toggle');
        if (filesToggle) {
            const id = filesToggle.dataset.id;
            const panel = document.getElementById(`files-${id}`);
            if (panel.classList.contains('hidden')) {
                panel.classList.remove('hidden');
                await loadFiles(id, panel);
            } else {
                panel.classList.add('hidden');
            }
            return;
        }

        const dlBtn = e.target.closest('.session-dl-btn');
        if (dlBtn) {
            const sid = dlBtn.dataset.sid;
            const filename = dlBtn.dataset.filename;
            const dlname = dlBtn.dataset.dlname;
            try {
                await API.downloadFile(sid, filename, dlname);
            } catch (err) {
                alert('Nedladdning misslyckades: ' + err.message);
            }
            return;
        }

        const reportBtn = e.target.closest('.session-report-btn');
        if (reportBtn) {
            const sid = reportBtn.dataset.sid;
            try {
                const data = await API.getReport(sid);
                // Generera rapport och ladda ner som .md
                const blob = new Blob([data.report], { type: 'text/markdown' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                // Hämta sessionsnamn
                const session = sessionsData.find(s => s.id === sid);
                const safeName = (session ? session.name : sid).replace(/[^a-zA-Z0-9_-\s]/g, '_').replace(/\s+/g, '_');
                a.download = `${safeName}_rapport.md`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(url);
            } catch (err) {
                alert('Rapport misslyckades: ' + err.message);
            }
        }
    }

    async function loadFiles(sessionId, panel) {
        try {
            const data = await API.getSessionFiles(sessionId);
            const files = data.files || [];

            if (files.length === 0) {
                panel.innerHTML = '<div class="session-files-empty">Inga filer att ladda ner</div>';
                return;
            }

            let html = '<div class="session-file-list">';
            for (const f of files) {
                html += `
                    <div class="session-file-item">
                        <span class="session-file-label">${escapeHtml(f.label)}</span>
                        <button class="btn btn-small btn-secondary session-dl-btn"
                            data-sid="${sessionId}"
                            data-filename="${escapeAttr(f.filename)}"
                            data-dlname="${escapeAttr(f.download_name)}">Ladda ner</button>
                    </div>
                `;
            }
            html += `
                <div class="session-file-item">
                    <span class="session-file-label">Generera rapport</span>
                    <button class="btn btn-small btn-secondary session-report-btn"
                        data-sid="${sessionId}">Rapport (MD)</button>
                </div>
            `;
            html += '</div>';
            panel.innerHTML = html;
        } catch (err) {
            panel.innerHTML = `<div class="session-files-empty">Fel: ${escapeHtml(err.message)}</div>`;
        }
    }

    function show() {
        document.getElementById('session-manager-section').classList.remove('hidden');
        loadSessions();
    }

    function hide() {
        document.getElementById('session-manager-section').classList.add('hidden');
    }

    function escapeHtml(str) {
        const d = document.createElement('div');
        d.textContent = str || '';
        return d.innerHTML;
    }

    function escapeAttr(str) {
        return (str || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    return { init, show, hide, loadSessions };
})();
