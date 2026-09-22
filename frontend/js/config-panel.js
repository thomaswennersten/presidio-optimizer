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
 * Konfigurationsvisning + export.
 */
const ConfigPanel = (() => {
    let sessionId = null;

    function init(sid) {
        sessionId = sid;
        document.getElementById('config-toggle').addEventListener('click', togglePanel);
        document.getElementById('export-json-btn').addEventListener('click', () => exportConfig('json'));
        document.getElementById('export-yaml-btn').addEventListener('click', () => exportConfig('yaml'));
    }

    function togglePanel() {
        const content = document.getElementById('config-content');
        const icon = document.querySelector('.toggle-icon');
        content.classList.toggle('hidden');
        icon.classList.toggle('open');
    }

    async function loadConfig() {
        if (!sessionId) return;
        try {
            const config = await API.getConfig(sessionId);
            const viewer = document.getElementById('config-viewer');
            viewer.textContent = JSON.stringify(config, null, 2);
            document.getElementById('config-section').classList.remove('hidden');
        } catch (e) {
            console.error('Failed to load config:', e);
        }
    }

    async function exportConfig(format) {
        if (!sessionId) return;
        try {
            const result = await API.exportConfig(sessionId, format);
            const blob = new Blob([result.content], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `presidio-config.${format}`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (e) {
            console.error('Export failed:', e);
            alert('Exportfel: ' + e.message);
        }
    }

    return { init, loadConfig };
})();
