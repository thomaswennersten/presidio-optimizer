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

    function onSessionReady(sid, name) {
        sessionId = sid;
        sessionName = name;
        SessionManager.hide();
        mainContent.classList.remove('hidden');

        // Visa sessionsindikator
        document.getElementById('session-indicator-name').textContent = name;
        sessionIndicator.classList.remove('hidden');

        // Reset vy
        ['results-section', 'optimization-section', 'comparison-section', 'config-section', 'history-section'].forEach(
            id => document.getElementById(id).classList.add('hidden')
        );

        ConfigPanel.init(sessionId);
        IterationHistory.init(sessionId);
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

    async function doOptimize() {
        if (!sessionId) return;
        const { falsePositives, falseNegatives } = TextAnnotator.getFeedback();

        try {
            showLoading('Skickar feedback...');
            await API.submitFeedback(sessionId, falsePositives, falseNegatives);

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

        document.getElementById('optimization-reasoning').textContent =
            result.reasoning || 'Ingen förklaring tillgänglig.';

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
            changesList.innerHTML = '<p style="color:#78909c">Inga andringar foreslagna.</p>';
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
