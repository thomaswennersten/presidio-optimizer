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
 * Drag & drop filuppladdning.
 */
const FileUpload = (() => {
    let selectedFile = null;
    let onFileSelected = null;

    function init(callback) {
        onFileSelected = callback;
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');

        dropZone.addEventListener('click', e => {
            // Don't double-trigger if the click came from the label or input
            // (the label's for="file-input" already opens the dialog natively)
            if (e.target === fileInput || e.target.closest('label[for="file-input"]')) return;
            fileInput.click();
        });
        dropZone.addEventListener('dragover', e => {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('drag-over');
        });
        dropZone.addEventListener('drop', e => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            if (e.dataTransfer.files.length) {
                handleFile(e.dataTransfer.files[0]);
            }
        });
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length) {
                handleFile(fileInput.files[0]);
            }
        });
    }

    function handleFile(file) {
        const ext = file.name.split('.').pop().toLowerCase();
        const allowed = ['docx', 'xlsx', 'pdf', 'txt'];
        if (!allowed.includes(ext)) {
            alert(`Filtyp "${ext}" stöds inte. Tillåtna: ${allowed.join(', ')}`);
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            alert('Filen är för stor (max 10 MB).');
            return;
        }
        selectedFile = file;
        showFileInfo(file);
        if (onFileSelected) onFileSelected(file);
    }

    function showFileInfo(file) {
        const info = document.getElementById('file-info');
        const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
        info.innerHTML = `<span class="filename">${file.name}</span><span class="filesize">${sizeMB} MB</span>`;
        info.classList.remove('hidden');
        document.getElementById('analyze-btn').classList.remove('hidden');
    }

    function getFile() {
        return selectedFile;
    }

    function reset() {
        selectedFile = null;
        document.getElementById('file-info').classList.add('hidden');
        document.getElementById('analyze-btn').classList.add('hidden');
        document.getElementById('file-input').value = '';
    }

    return { init, getFile, reset };
})();
