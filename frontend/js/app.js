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
 * Huvudkontroller - Presidio Optimizer.
 */
(function () {
    let sessionId = null;
    let sessionName = null;

    // Display current date
    const dateEl = document.getElementById('date-display');
    dateEl.textContent = new Date().toLocaleDateString('sv-SE', {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
    });

    // --- Authentication ---
    const loginOverlay = document.getElementById('login-overlay');
    const loginForm = document.getElementById('login-form');
    const loginError = document.getElementById('login-error');
    const mainContent = document.getElementById('main-content');
    const sessionManagerSection = document.getElementById('session-manager-section');
    const sessionIndicator = document.getElementById('session-indicator');

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const password = document.getElementById('login-password').value;
        loginError.classList.add('hidden');

        try {
            const result = await API.login(password);
            API.setToken(result.token);
            showApp();
        } catch (err) {
            loginError.classList.remove('hidden');
            document.getElementById('login-password').value = '';
            document.getElementById('login-password').focus();
        }
    });

    // Check if already authenticated
    if (API.getToken()) {
        API.checkAuth().then(() => showApp()).catch(() => showLogin());
    } else {
        showLogin();
    }

    function showLogin() {
        loginOverlay.classList.remove('hidden');
        mainContent.classList.add('hidden');
        sessionManagerSection.classList.add('hidden');
        sessionIndicator.classList.add('hidden');
        document.getElementById('login-password').focus();
    }

    function showApp() {
        loginOverlay.classList.add('hidden');
        mainContent.classList.add('hidden');
        sessionIndicator.classList.add('hidden');
        SessionManager.show();
    }

    // --- Session Manager integration ---
    SessionManager.init(onSessionReady);

    async function onSessionReady(sid, name) {
        sessionId = sid;
        document.body.dataset.sessionId = sid;
        sessionName = name;
        SessionManager.hide();
        mainContent.classList.remove('hidden');

        // Visa sessionsindikator
        document.getElementById('session-indicator-name').textContent = name;
        sessionIndicator.classList.remove('hidden');

        ['results-section', 'optimization-section', 'comparison-section', 'config-section', 'history-section'].forEach(
            id => document.getElementById(id).classList.add('hidden')
        );

        ConfigPanel.init(sessionId);
        IterationHistory.init(sessionId);

        // Återuppta: hämta tillbaka text, träffar och feedback. Tidigare
        // nollställdes vyn alltid, så en tidigare session såg tom ut och man
        // fick ladda upp dokumentet igen trots att allt låg kvar på servern.
        try {
            const state = await API.getSessionState(sid);
            if (state && state.har_analys) {
                aterstallSession(state);
            }
        } catch (e) {
            if (e.message !== 'AUTH_REQUIRED') {
                console.warn('Kunde inte återuppta sessionen:', e.message);
            }
        }
    }

    function aterstallSession(state) {
        const section = document.getElementById('results-section');
        section.classList.remove('hidden');

        const typeCounts = {};
        state.results.forEach(r => {
            typeCounts[r.entity_type] = (typeCounts[r.entity_type] || 0) + 1;
        });
        document.getElementById('results-stats').innerHTML =
            `<span class="stat">Totalt: ${state.results.length}</span>` +
            Object.entries(typeCounts).map(([t, c]) =>
                `<span class="stat">${TextAnnotator.getEntityLabels()[t] || t}: ${c}</span>`
            ).join('') +
            '<span class="stat">Återupptagen session</span>';

        TextAnnotator.renderLegend(document.getElementById('entity-legend'), state.results);
        TextAnnotator.setFeedback(state.false_positives, state.false_negatives);
        TextAnnotator.render(
            document.getElementById('annotated-text'),
            state.text,
            state.results,
            false
        );
    }

    document.getElementById('back-to-sessions-btn').addEventListener('click', () => {
        sessionId = null;
        sessionName = null;
        mainContent.classList.add('hidden');
        sessionIndicator.classList.add('hidden');
        // Reset file upload
        FileUpload.reset && FileUpload.reset();
        document.getElementById('file-info').classList.add('hidden');
        document.getElementById('analyze-btn').classList.add('hidden');
        SessionManager.show();
    });

    // --- Loading overlay ---
    function showLoading(msg) {
        document.getElementById('loading-message').textContent = msg || 'Bearbetar...';
        document.getElementById('loading-overlay').classList.remove('hidden');
    }
    function hideLoading() {
        document.getElementById('loading-overlay').classList.add('hidden');
    }

    // --- Init ---
    FileUpload.init(onFileSelected);
    TextAnnotator.init(onFeedbackChange);

    document.getElementById('analyze-btn').addEventListener('click', doAnalyze);
    document.getElementById('submit-feedback-btn').addEventListener('click', doOptimize);
    document.getElementById('clear-feedback-btn').addEventListener('click', doClearFeedback);
    document.getElementById('reanalyze-btn').addEventListener('click', doReanalyze);
    document.getElementById('iterate-btn').addEventListener('click', doIterate);
    document.getElementById('accept-btn').addEventListener('click', doAccept);

    // --- Handlers ---

    function handleAuthError(e) {
        if (e.message === 'AUTH_REQUIRED') {
            showLogin();
            return true;
        }
        return false;
    }

    function onFileSelected() {
        ['results-section', 'optimization-section', 'comparison-section'].forEach(
            id => document.getElementById(id).classList.add('hidden')
        );
    }

    function onFeedbackChange(fps, fns) {
        const btn = document.getElementById('submit-feedback-btn');
        const summary = document.getElementById('feedback-summary');
        const counts = document.getElementById('feedback-counts');

        if (fps.length + fns.length > 0) {
            btn.disabled = false;
            summary.classList.remove('hidden');
            counts.innerHTML = `
                <span class="fp-label">False positives: ${fps.length}</span>
                <span class="fn-label">False negatives: ${fns.length}</span>
            `;
        } else {
            btn.disabled = true;
            summary.classList.add('hidden');
        }
    }

    async function doAnalyze() {
        const file = FileUpload.getFile();
        if (!file) return;
        if (!sessionId) return;

        try {
            showLoading('Laddar upp dokument...');
            await API.uploadDocument(sessionId, file);

            showLoading('Analyserar med Presidio...');
            const data = await API.analyze(sessionId);

            renderResults(data);
            await ConfigPanel.loadConfig();
            await IterationHistory.loadHistory();
        } catch (e) {
            if (!handleAuthError(e)) alert('Fel: ' + e.message);
        } finally {
            hideLoading();
        }
    }

    function renderResults(data) {
        const section = document.getElementById('results-section');
        section.classList.remove('hidden');

        const stats = document.getElementById('results-stats');
        const typeCounts = {};
        (data.results || []).forEach(r => {
            typeCounts[r.entity_type] = (typeCounts[r.entity_type] || 0) + 1;
        });
        stats.innerHTML = `<span class="stat">Totalt: ${data.total}</span>` +
            Object.entries(typeCounts).map(([t, c]) =>
                `<span class="stat">${TextAnnotator.getEntityLabels()[t] || t}: ${c}</span>`
            ).join('');

        TextAnnotator.renderLegend(document.getElementById('entity-legend'), data.results);

        TextAnnotator.clearFeedback();
        TextAnnotator.render(
            document.getElementById('annotated-text'),
            data.text,
            data.results,
            false
        );

        document.getElementById('submit-feedback-btn').disabled = true;
        document.getElementById('feedback-summary').classList.add('hidden');

        section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    /* Bara etiketterna för de typer som faktiskt använts i omgången. Att skicka
       alla egna typer användaren någonsin skapat hade lagt in poster i
       regelverket för typer utan igenkännare — de hade då dykt upp i maskeras
       lista över "typer ingen igenkännare hittar", vilket är sant men brus. */
    function etiketterFor(falseNegatives) {
        const alla = TextAnnotator.getEntityLabels();
        const ut = {};
        for (const fn of falseNegatives || []) {
            const t = fn.entity_type;
            if (t && alla[t] && alla[t] !== t) ut[t] = alla[t];
        }
        return ut;
    }

    async function doOptimize() {
        if (!sessionId) return;
        const { falsePositives, falseNegatives } = TextAnnotator.getFeedback();

        try {
            showLoading('Skickar feedback...');
            await API.submitFeedback(sessionId, falsePositives, falseNegatives,
                                     etiketterFor(falseNegatives));

            showLoading('LLM optimerar konfiguration...');
            const result = await API.optimize(sessionId);

            renderOptimization(result);
            await ConfigPanel.loadConfig();
            await IterationHistory.loadHistory();
        } catch (e) {
            if (!handleAuthError(e)) alert('Optimeringsfel: ' + e.message);
        } finally {
            hideLoading();
        }
    }

    function renderOptimization(result) {
        const section = document.getElementById('optimization-section');
        section.classList.remove('hidden');

        // Ett misslyckande får inte se ut som ett normalt resultat. Utan detta
        // visades "kunde inte tolka svaret" med samma grå text som "inga
        // ändringar behövdes" — användaren trodde att konfigurationen var bra.
        const ruta = document.getElementById('optimization-reasoning');
        ruta.textContent = result.reasoning || 'Ingen förklaring tillgänglig.';
        ruta.classList.toggle('optimering-fel', !!result.fel);

        const changesList = document.getElementById('optimization-changes');
        changesList.innerHTML = '';
        (result.changes || []).forEach(c => {
            const item = document.createElement('div');
            item.className = 'change-item';
            item.innerHTML = `
                <span class="change-action">${c.action}</span>
                <div class="change-detail">
                    <strong>${c.target || ''}</strong>
                    <div>${JSON.stringify(c.details || {}, null, 1)}</div>
                </div>
            `;
            changesList.appendChild(item);
        });

        if (!result.changes || result.changes.length === 0) {
            changesList.innerHTML = result.fel
                ? '<p class="optimering-fel">Optimeringen misslyckades — konfigurationen är '
                  + 'oförändrad. Ingen slutsats kan dras om regelverkets kvalitet.</p>'
                : '<p style="color:#78909c">Inga ändringar föreslagna.</p>';
        }

        section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    async function doReanalyze() {
        if (!sessionId) return;
        try {
            showLoading('Analyserar om med ny konfiguration...');
            const data = await API.reanalyze(sessionId);
            renderComparison(data);
        } catch (e) {
            if (!handleAuthError(e)) alert('Omanalysfel: ' + e.message);
        } finally {
            hideLoading();
        }
    }

    function renderComparison(data) {
        const section = document.getElementById('comparison-section');
        section.classList.remove('hidden');

        const comp = data.comparison;
        const statsEl = document.getElementById('comparison-stats');
        statsEl.innerHTML = `
            <div class="stat-card">
                <div class="stat-value">${comp.old_count}</div>
                <div class="stat-label">Fore</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${comp.new_count}</div>
                <div class="stat-label">Efter</div>
            </div>
            <div class="stat-card positive">
                <div class="stat-value">+${comp.added}</div>
                <div class="stat-label">Nya detektioner</div>
            </div>
            <div class="stat-card negative">
                <div class="stat-value">-${comp.removed}</div>
                <div class="stat-label">Borttagna</div>
            </div>
        `;

        const oldVersion = data.config_version - 1 || 1;
        document.getElementById('old-version').textContent = oldVersion;
        document.getElementById('new-version').textContent = data.config_version;

        TextAnnotator.render(document.getElementById('old-results'), data.text, data.old_results, true);
        TextAnnotator.render(document.getElementById('new-results'), data.text, data.new_results, true);

        section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function doIterate() {
        document.getElementById('optimization-section').classList.add('hidden');
        document.getElementById('comparison-section').classList.add('hidden');

        const resultsSection = document.getElementById('results-section');
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

        doReloadAnalysis();
    }

    async function doReloadAnalysis() {
        if (!sessionId) return;
        try {
            showLoading('Laddar senaste analys...');
            const data = await API.analyze(sessionId);
            renderResults(data);
        } catch (e) {
            if (!handleAuthError(e)) alert('Fel: ' + e.message);
        } finally {
            hideLoading();
        }
    }

    function doAccept() {
        alert('Konfigurationen ar accepterad! Exportera den via konfigurationspanelen nedan.');
        document.getElementById('config-section').classList.remove('hidden');
        const content = document.getElementById('config-content');
        content.classList.remove('hidden');
        document.querySelector('.toggle-icon').classList.add('open');
        document.getElementById('config-section').scrollIntoView({ behavior: 'smooth' });
    }

    function doClearFeedback() {
        TextAnnotator.clearFeedback();
        const container = document.getElementById('annotated-text');
        if (container._lastText && container._lastResults) {
            TextAnnotator.render(container, container._lastText, container._lastResults, false);
        }
    }
})();

document.addEventListener('DOMContentLoaded', () => {
    // Textstorlek — 0.9rem var för litet för att träffa rätt ord med markören.
    const storlek = document.getElementById('textstorlek');
    if (storlek) {
        const sparad = localStorage.getItem('optimizer_textstorlek');
        if (sparad) storlek.value = sparad;
        // Skriv en egen stilregel istället för att bara sätta variabeln. Regeln
        // överlever omritningar av texten och kan inte förlora mot en mer
        // specifik selektor någon annanstans i stilmallen.
        let regel = document.getElementById('textstorlek-regel');
        if (!regel) {
            regel = document.createElement('style');
            regel.id = 'textstorlek-regel';
            document.head.appendChild(regel);
        }
        const satt = () => {
            const v = Number(storlek.value);
            document.documentElement.style.setProperty('--textstorlek', v + 'rem');
            regel.textContent = `.annotated-text { font-size: ${v}rem !important; }`;
            document.getElementById('textstorlek-varde').textContent = v.toFixed(2) + '×';
            localStorage.setItem('optimizer_textstorlek', storlek.value);
        };
        storlek.addEventListener('input', satt);
        satt();
    }
});

document.addEventListener('DOMContentLoaded', () => {
    // Publicering: optimizern sparar regelverk under db/sessions/<id>/configs/,
    // men maskera-applikationen läser db/configs/. Utan detta steg når ett nytt
    // regelverk aldrig maskeringen.
    const btn = document.getElementById('publish-btn');
    const status = document.getElementById('publish-status');
    if (!btn) return;
    btn.addEventListener('click', async () => {
        const sid = document.body.dataset.sessionId;
        if (!sid) { alert('Ingen session vald.'); return; }
        btn.disabled = true;
        const gammal = btn.textContent;
        btn.textContent = 'Publicerar…';
        status.textContent = '';
        status.className = 'publish-status';
        try {
            const r = await API.publishConfig(sid);
            status.textContent = `Publicerad som "${r.config_id}" (v${r.senaste_version}) `
                               + '— valbar i maskera direkt, ingen omstart behövs.';
            status.classList.add('publish-ok');
        } catch (e) {
            status.textContent = 'Publiceringen misslyckades: ' + e.message;
            status.classList.add('publish-fel');
        } finally {
            btn.disabled = false;
            btn.textContent = gammal;
        }
    });
});

/* ===== Publicerade regelverk =====
   Radering ligger HÄR och inte i maskera-applikationen: maskera saknar helt
   autentisering och monterar inte ens regelverkskatalogen (mcp:n har den
   skrivskyddad). Optimizer har både lösenord och skrivrättighet. */
document.addEventListener('DOMContentLoaded', () => {
    const lista = document.getElementById('published-list');
    const tom = document.getElementById('published-empty');
    if (!lista) return;

    function datum(iso) {
        const d = new Date(iso);
        return isNaN(d) ? '' : d.toLocaleString('sv-SE',
            { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    }
    const esc = v => String(v ?? '').replace(/[&<>"']/g,
        c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    async function rita() {
        let poster = [];
        try {
            poster = (await API.listPublished()).publicerade || [];
        } catch (e) {
            if (e.message === 'AUTH_REQUIRED') return;
            lista.innerHTML = `<p class="publ-fel">Kunde inte hämta: ${esc(e.message)}</p>`;
            return;
        }
        tom.classList.toggle('hidden', poster.length > 0);
        lista.innerHTML = poster.map(p => `
            <div class="publ-rad">
                <div class="publ-text">
                    <strong>${esc(p.namn)}</strong>
                    <span>v${p.senaste_version} · ${esc(datum(p.skapad)) || 'okänt datum'}${p.har_meta ? '' : ' · äldre'}</span>
                </div>
                <button class="publ-bort" data-id="${esc(p.config_id)}"
                        data-namn="${esc(p.namn)}" title="Ta bort ${esc(p.namn)}">Ta bort</button>
            </div>`).join('');

        lista.querySelectorAll('.publ-bort').forEach(b => b.addEventListener('click', async () => {
            const namn = b.dataset.namn;
            if (!confirm(`Ta bort regelverket "${namn}" från maskera-applikationen?\n\n`
                       + 'Sessionen här i Optimizer påverkas inte — regelverket kan publiceras igen.\n'
                       + 'Dokument som redan maskerats ändras inte.')) return;
            b.disabled = true; b.textContent = 'Tar bort…';
            try {
                await API.deletePublished(b.dataset.id);
                await rita();
            } catch (e) {
                alert('Kunde inte ta bort: ' + e.message);
                b.disabled = false; b.textContent = 'Ta bort';
            }
        }));
    }

    // Rita om när sessionsvyn visas, så listan speglar nyss gjorda publiceringar.
    rita();
    const btn = document.getElementById('publish-btn');
    if (btn) btn.addEventListener('click', () => setTimeout(rita, 900));
    const tillbaka = document.getElementById('back-to-sessions-btn');
    if (tillbaka) tillbaka.addEventListener('click', () => setTimeout(rita, 200));
});
