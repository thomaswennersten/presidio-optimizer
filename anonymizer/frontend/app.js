/*
 * Presidio Anonymizer
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

const API_BASE_URL = './api';

let selectedFiles = [];

const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const browseBtn = document.getElementById('browseBtn');
const filesList = document.getElementById('filesList');
const analyzeBtn = document.getElementById('analyzeBtn');
const anonymizeBtn = document.getElementById('anonymizeBtn');
const resultsSection = document.getElementById('resultsSection');
const resultsContent = document.getElementById('resultsContent');
const loading = document.getElementById('loading');

uploadArea.addEventListener('click', () => fileInput.click());
browseBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
});

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    handleFiles(e.dataTransfer.files);
});

fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
});

function handleFiles(files) {
    const validFiles = Array.from(files).filter(file => {
        const ext = file.name.split('.').pop().toLowerCase();
        return ['docx', 'xlsx', 'pdf', 'txt'].includes(ext);
    });

    if (validFiles.length === 0) {
        showMessage('Vänligen välj giltiga filer (DOCX, XLSX, PDF, TXT)', 'error');
        return;
    }

    selectedFiles = validFiles;
    displayFiles();
    updateButtons();
}

function displayFiles() {
    filesList.innerHTML = '';
    
    selectedFiles.forEach((file, index) => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        
        const ext = file.name.split('.').pop().toUpperCase();
        const size = formatFileSize(file.size);
        
        fileItem.innerHTML = `
            <div class="file-info">
                <div class="file-icon">${ext}</div>
                <div class="file-details">
                    <h4>${file.name}</h4>
                    <p>${size}</p>
                </div>
            </div>
            <button class="remove-btn" onclick="removeFile(${index})">×</button>
        `;
        
        filesList.appendChild(fileItem);
    });
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    displayFiles();
    updateButtons();
    if (selectedFiles.length === 0) {
        resultsSection.style.display = 'none';
    }
}

function updateButtons() {
    const hasFiles = selectedFiles.length > 0;
    analyzeBtn.disabled = !hasFiles;
    anonymizeBtn.disabled = !hasFiles;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

analyzeBtn.addEventListener('click', async () => {
    if (selectedFiles.length === 0) return;
    
    loading.style.display = 'block';
    resultsSection.style.display = 'none';
    
    try {
        const results = [];
        
        for (const file of selectedFiles) {
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch(`${API_BASE_URL}/analyze`, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`Fel vid analys av ${file.name}`);
            }
            
            const result = await response.json();
            results.push(result);
        }
        
        displayAnalysisResults(results);
    } catch (error) {
        showMessage(`Fel: ${error.message}`, 'error');
    } finally {
        loading.style.display = 'none';
    }
});

anonymizeBtn.addEventListener('click', async () => {
    if (selectedFiles.length === 0) return;
    
    loading.style.display = 'block';
    resultsSection.style.display = 'none';
    
    try {
        for (const file of selectedFiles) {
            console.log(`Starting anonymization for: ${file.name}`);
            const formData = new FormData();
            formData.append('file', file);
            
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 minutes timeout
            
            const response = await fetch(`${API_BASE_URL}/anonymize`, {
                method: 'POST',
                body: formData,
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            console.log(`Response status: ${response.status}`);
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error(`Error response: ${errorText}`);
                throw new Error(`Fel vid anonymisering av ${file.name}: ${errorText}`);
            }
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `anonymized_${file.name}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        }
        
        showMessage('Dokument har anonymiserats och laddats ner!', 'success');
    } catch (error) {
        if (error.name === 'AbortError') {
            showMessage(`Timeout: ${error.message}`, 'error');
        } else {
            showMessage(`Fel: ${error.message}`, 'error');
        }
        console.error('Anonymization error:', error);
    } finally {
        loading.style.display = 'none';
    }
});

function displayAnalysisResults(results) {
    resultsSection.style.display = 'block';
    resultsContent.innerHTML = '';
    
    results.forEach(result => {
        const resultDiv = document.createElement('div');
        resultDiv.className = 'entity-group';
        
        let html = `<h3>${result.filename}</h3>`;
        html += `<p>Totalt antal entiteter funna: ${result.total_entities}</p>`;
        
        for (const [entityType, entities] of Object.entries(result.entities_found)) {
            html += `<div class="entity-type">${entityType}</div>`;
            html += '<div>';
            entities.forEach(entity => {
                html += `<span class="entity-item">${entity.text} (${Math.round(entity.score * 100)}%)</span>`;
            });
            html += '</div>';
        }
        
        resultDiv.innerHTML = html;
        resultsContent.appendChild(resultDiv);
    });
}

function showMessage(message, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = type === 'error' ? 'error-message' : 'success-message';
    messageDiv.textContent = message;
    
    resultsSection.style.display = 'block';
    resultsContent.innerHTML = '';
    resultsContent.appendChild(messageDiv);
    
    setTimeout(() => {
        messageDiv.remove();
        if (resultsContent.children.length === 0) {
            resultsSection.style.display = 'none';
        }
    }, 5000);
}