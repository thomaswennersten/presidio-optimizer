/**
 * API-kommunikationslager för Presidio Optimizer.
 */
const API = (() => {
    const BASE = 'api';
    let authToken = sessionStorage.getItem('authToken') || '';

    function setToken(token) {
        authToken = token;
        sessionStorage.setItem('authToken', token);
    }

    function getToken() {
        return authToken;
    }

    function clearToken() {
        authToken = '';
        sessionStorage.removeItem('authToken');
    }

    async function request(method, path, body, isFormData) {
        const opts = { method, headers: {} };

        if (authToken) {
            opts.headers['X-Auth-Token'] = authToken;
        }

        if (body) {
            if (isFormData) {
                opts.body = body;
            } else {
                opts.headers['Content-Type'] = 'application/json';
                opts.body = JSON.stringify(body);
            }
        }
        const res = await fetch(`${BASE}${path}`, opts);
        if (res.status === 401) {
            clearToken();
            throw new Error('AUTH_REQUIRED');
        }
        if (!res.ok) {
            let msg = `HTTP ${res.status}`;
            try { const j = await res.json(); msg = j.detail || msg; } catch {}
            throw new Error(msg);
        }
        return res.json();
    }

    async function downloadBlob(path, fallbackName) {
        const opts = { method: 'GET', headers: {} };
        if (authToken) {
            opts.headers['X-Auth-Token'] = authToken;
        }
        const res = await fetch(`${BASE}${path}`, opts);
        if (res.status === 401) {
            clearToken();
            throw new Error('AUTH_REQUIRED');
        }
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }
        const disposition = res.headers.get('content-disposition') || '';
        let filename = fallbackName;
        const match = disposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';\n]+)/i);
        if (match) filename = decodeURIComponent(match[1]);

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    }

    return {
        setToken,
        getToken,
        clearToken,

        login(password) {
            return request('POST', '/login', { password });
        },

        checkAuth() {
            return request('GET', '/auth/check');
        },

        createSession(name) {
            return request('POST', '/session', { name });
        },

        listSessions() {
            return request('GET', '/sessions');
        },

        uploadDocument(sessionId, file) {
            const fd = new FormData();
            fd.append('file', file);
            return request('POST', `/session/${sessionId}/upload`, fd, true);
        },

        analyze(sessionId) {
            return request('POST', `/session/${sessionId}/analyze`);
        },

        submitFeedback(sessionId, falsePositives, falseNegatives) {
            return request('POST', `/session/${sessionId}/feedback`, {
                false_positives: falsePositives,
                false_negatives: falseNegatives,
            });
        },

        optimize(sessionId) {
            return request('POST', `/session/${sessionId}/optimize`);
        },

        reanalyze(sessionId) {
            return request('POST', `/session/${sessionId}/reanalyze`);
        },

        getConfig(sessionId) {
            return request('GET', `/session/${sessionId}/config`);
        },

        getConfigHistory(sessionId) {
            return request('GET', `/session/${sessionId}/config/history`);
        },

        exportConfig(sessionId, format) {
            return request('GET', `/session/${sessionId}/config/export?format=${format}`);
        },

        getSessionFiles(sessionId) {
            return request('GET', `/session/${sessionId}/files`);
        },

        downloadFile(sessionId, filename, downloadName) {
            return downloadBlob(`/session/${sessionId}/download/${filename}`, downloadName);
        },

        getReport(sessionId) {
            return request('GET', `/session/${sessionId}/report`);
        },
    };
})();
