document.addEventListener('DOMContentLoaded', () => {
    const appContainer = document.getElementById('app-container');
    const fileInput = document.getElementById('file-input');
    const selectedFileName = document.getElementById('selected-file-name');
    const generateBtn = document.getElementById('generate-btn');
    // const statusCard = document.getElementById('status-card'); // Removed
    const terminal = document.getElementById('terminal');
    const statusBadge = document.getElementById('status-badge');
    const modelSelect = document.getElementById('model-select');
    const btnLoader = document.getElementById('btn-loader');
    const dropZone = document.getElementById('drop-zone');
    const progressBar = document.getElementById('progress-bar');
    const modelListBody = document.getElementById('model-list-body');

    const downloadArea = document.getElementById('download-area');
    const downloadLink = document.getElementById('download-link');
    const captionPreviewContainer = document.getElementById('caption-preview-container');
    const captionPreview = document.getElementById('caption-preview');

    // Progress Modal Elements
    const progressModal = document.getElementById('progress-modal-overlay');
    const progressTitle = document.getElementById('progress-title');
    const progressStatus = document.getElementById('progress-status');
    const progressPercent = document.getElementById('progress-percent');
    const progressCloseBtn = document.getElementById('progress-close-btn');
    const cancelBtn = document.getElementById('cancel-btn');

    let selectedFile = null;
    let selectedModelKey = 'large-v3-turbo';
    let modelsMetadataCache = {};

    setProcessing(false);
    loadModels();

    // --- Modal Logic ---
    const startProgress = (title) => {
        progressTitle.textContent = title;
        progressCloseBtn.hidden = true;
        downloadArea.hidden = true;
        cancelBtn.hidden = false; // TODO: Implement cancel logic
        progressModal.hidden = false;
        terminal.innerHTML = ''; // Clear logs
        captionPreviewContainer.hidden = true;
    };

    const closeProgress = () => {
        progressModal.hidden = true;
    };

    progressCloseBtn.addEventListener('click', closeProgress);

    // --- Core Functions ---

    async function loadModels() {
        try {
            const response = await fetch('/models');
            const models = await response.json();
            modelsMetadataCache = models.reduce((acc, m) => { acc[m.key] = m; return acc; }, {});
            renderModelTable(models);
            
            // Set initial selection
            const defaultModel = models.find(m => m.key === selectedModelKey) || models[0];
            if (defaultModel) modelSelect.value = defaultModel.id;
        } catch (error) {
            console.error('Failed to load models:', error);
            modelListBody.innerHTML = '<tr><td colspan="6" class="table-loading">Error loading models.</td></tr>';
        }
    }

    function renderModelTable(models) {
        modelListBody.innerHTML = models.map(m => `
            <tr class="model-row ${m.key === selectedModelKey ? 'selected' : ''}" data-key="${m.key}" data-id="${m.id}">
                <td>
                    <div class="model-name-cell">
                        <strong>${m.name}</strong>
                        <span class="model-id-sub">${m.id}</span>
                    </div>
                </td>
                <td>${m.min_ram}</td>
                <td><span class="badge ${getSpeedBadge(m.speed)}">${m.speed}</span></td>
                <td><span class="badge ${getAccuracyBadge(m.accuracy)}">${m.accuracy}</span></td>
                <td id="status-${m.key}">
                    ${m.downloaded ? '<span class="badge badge-success">Downloaded</span>' : '<span class="badge badge-warning">Missing</span>'}
                </td>
                <td>
                    ${m.downloaded
                        ? `
                            <div style="display: flex; gap: 8px;">
                                <button class="btn btn-secondary btn-small" disabled>Ready</button>
                                <button class="btn btn-danger btn-small delete-btn" data-key="${m.key}">Delete</button>
                            </div>
                        `
                        : `<button class="btn btn-primary btn-small download-btn" data-key="${m.key}">Download</button>`}
                </td>
            </tr>
        `).join('');

        // Attach listeners
        document.querySelectorAll('.model-row').forEach(row => {
            row.addEventListener('click', (e) => {
                if (e.target.classList.contains('download-btn') || e.target.classList.contains('delete-btn')) return;
                selectModel(row);
            });
        });

        document.querySelectorAll('.download-btn').forEach(btn => {
            btn.addEventListener('click', () => downloadModel(btn.dataset.key));
        });

        document.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                confirmDelete(btn.dataset.key);
            });
        });
    }

    function selectModel(row) {
        document.querySelectorAll('.model-row').forEach(r => r.classList.remove('selected'));
        row.classList.add('selected');
        selectedModelKey = row.dataset.key;
        modelSelect.value = row.dataset.id;
    }

    // --- Deletion Logic ---

    function confirmDelete(key) {
        const meta = modelsMetadataCache[key];
        showModal(
            'Confirm Deletion',
            `<p>Are you sure you want to delete the local files for <strong>${meta.name}</strong>?</p>
             <p>This will free up disk space, but you will need to download it again to use it.</p>`,
            'Cancel'
        );
        
        modalBtn.textContent = 'Yes, Delete';
        modalBtn.classList.remove('btn-primary');
        modalBtn.classList.add('btn-danger');
        
        const originalAction = modalBtn.onclick;
        modalBtn.onclick = async () => {
            modalBtn.onclick = originalAction; // Reset
            modalBtn.classList.remove('btn-danger');
            modalBtn.classList.add('btn-primary');
            modalOverlay.hidden = true;
            await deleteModel(key);
        };
    }

    async function deleteModel(key) {
        setProcessing(true, 'Deleting...');
        // We can use the progress modal for deletion logs too, or just blocking UI
        // For now, let's just block UI and alert on error/success to keep it simple or use simple terminal overlay
        // Actually, let's use the new progress modal so they see what's happening
        startProgress('Deleting Model...');
        addTerminalLine(`Deleting model "${key}"...`);
        
        try {
            const response = await fetch(`/models/delete/${key}`, { method: 'POST' });
            const data = await response.json();
            if (data.status === 'success') {
                addTerminalLine(`SUCCESS: Model "${key}" deleted.`);
                await loadModels();
                setTimeout(closeProgress, 1000);
            } else {
                throw new Error(data.message);
            }
        } catch (error) {
            addTerminalLine(`ERROR: Failed to delete model: ${error.message}`);
            showModal('Deletion Failed', error.message);
            closeProgress(); // Close the progress modal so they can see the error modal
        } finally {
            setProcessing(false);
        }
    }

    // --- Download & Transcription Logic ---

    function downloadModel(key, chainTranscription = false) {
        return new Promise((resolve, reject) => {
            const btn = document.querySelector(`.download-btn[data-key="${key}"]`);
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Starting...';
            }

            fetch(`/models/download/${key}`, { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    startProgress('Downloading Model...');
                    addTerminalLine(`Action: Downloading ${key}...`);
                    updateProgressStatus('Downloading...', 10);
                    
                    startStatusStream(data.task_id, null, async () => {
                        await loadModels();
                        if (chainTranscription) {
                            addTerminalLine('Download complete. Starting transcription...');
                            startTranscription();
                        } else {
                            // Just close checks if not chaining
                            addTerminalLine('Download complete.');
                            setTimeout(closeProgress, 1500);
                        }
                        resolve();
                    });
                })
                .catch(err => {
                    showModal('Download Error', `Failed to start download: ${err.message}`);
                    if (btn) {
                        btn.disabled = false;
                        btn.textContent = 'Download';
                    }
                    closeProgress();
                    reject(err);
                });
        });
    }

    async function startTranscription() {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('model', modelSelect.value);

        setProcessing(true, 'Uploading File...');
        startProgress('Transcribing...');
        updateProgressStatus('Uploading...', 0);
        
        terminal.innerHTML = '<div class="terminal-line">> Initializing...</div>';
        progressBar.style.width = '0%';
        progressBar.style.background = 'var(--primary)';

        try {
            const response = await fetch('/transcribe', { method: 'POST', body: formData });
            if (!response.ok) throw new Error('Upload failed');
            const data = await response.json();
            
            updateProgressStatus('Waiting for AI...', 5);
            startStatusStream(data.task_id, selectedFile.name.replace(/\.[^/.]+$/, "") + ".srt", () => {
                fetchAndShowCaptions(data.task_id);
            });
        } catch (error) {
            addTerminalLine(`ERROR: ${error.message}`);
            finishProcessing('Failed', '#ef4444');
            showModal('Error', `Transcription failed: ${error.message}`);
            // Don't close progress immediately on error so they can read logs
        }
    }

    // --- Helpers ---

    function startStatusStream(taskId, srtFilename, onComplete) {
        const eventSource = new EventSource(`/status/${taskId}`);
        eventSource.addEventListener('log', (event) => {
            const log = event.data;
            addTerminalLine(log);
            const lowerLog = log.toLowerCase();
            
            if (lowerLog.includes('loading model')) updateProgressStatus('Loading AI...', -1);
            if (lowerLog.includes('starting inference')) updateProgressStatus('Transcribing...', -1);
            if (lowerLog.includes('done!') || lowerLog.includes('success:')) {
                finishProcessing('Completed', '#10b981');
                updateProgressStatus('Finished', 100);
                if (srtFilename) showDownloadLink(srtFilename);
                if (onComplete) onComplete();
                eventSource.close();
            }
            if (lowerLog.includes('error:')) {
                finishProcessing('Error', '#ef4444');
                updateProgressStatus('Process Failed', -1);
                showModal('Processing Error', log);
                eventSource.close();
            }
        });

        eventSource.addEventListener('progress', (event) => {
            const progress = parseFloat(event.data);
            if (progress >= 0) {
                progressBar.style.width = `${progress}%`;
                progressPercent.textContent = `${Math.round(progress)}%`;
                if (progress > 0 && progress < 100 && !taskId.startsWith('download')) {
                    setProcessing(true, `Processing (${progress.toFixed(0)}%)`);
                }
            } else if (progress === -1) {
                progressBar.style.width = '100%';
                progressBar.style.background = '#ef4444';
                finishProcessing('Error', '#ef4444');
            }
        });
        
        eventSource.onerror = () => { eventSource.close(); };
    }

    function showDownloadLink(filename) {
        downloadArea.hidden = false;
        progressCloseBtn.hidden = false;
        cancelBtn.hidden = true;
        
        downloadLink.href = `/uploads/${filename}`;
        downloadLink.download = filename;
        
        progressTitle.textContent = 'Conversion Complete!';
    }

    // --- Event Listeners & UI Helpers ---

    fileInput.addEventListener('change', (e) => handleFileSelect(e.target.files[0]));

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        if (appContainer.classList.contains('processing')) return;
        dropZone.style.borderColor = 'var(--primary)';
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--border)';
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        if (appContainer.classList.contains('processing')) return;
        dropZone.style.borderColor = 'var(--border)';
        handleFileSelect(e.dataTransfer.files[0]);
    });

    generateBtn.addEventListener('click', async () => {
        if (!selectedFile) {
            showModal('File Missing', 'Please select a video or audio file first!');
            return;
        }
        
        const autoDownload = document.getElementById('auto-download-check')?.checked;
        const meta = modelsMetadataCache[selectedModelKey];
        
        if (!meta) {
            showModal('Selection Error', 'Please select a model from the list again.');
            return;
        }

        if (!meta.downloaded) {
            if (autoDownload) {
                addTerminalLine(`Model "${meta.name}" is missing. Auto-downloading...`);
                await downloadModel(selectedModelKey, true);
            } else {
                showModal('Model Not Downloaded', `
                    <p>The selected model (<strong>${meta.name}</strong>) is not available locally.</p>
                    <p>Please click the <strong>Download</strong> button in the table or enable <strong>Auto-download missing models</strong>.</p>
                `);
            }
        } else {
            startTranscription();
        }
    });

    // --- Utilities ---

    function handleFileSelect(file) {
        if (file) {
            selectedFile = file;
            selectedFileName.textContent = file.name;
        }
    }

    function getSpeedBadge(val) {
        if (val.includes('Ultra')) return 'badge-info';
        if (val.includes('Very')) return 'badge-success';
        return 'badge-info';
    }

    function getAccuracyBadge(val) {
        if (val === 'High') return 'badge-success';
        if (val === 'Good') return 'badge-info';
        return 'badge-warning';
    }

    function formatSeconds(s) {
        const h = Math.floor(s/3600); const m = Math.floor((s%3600)/60); const sec = Math.floor(s%60);
        return `${h.toString().padStart(2,'0')}:${m.toString().padStart(2,'0')}:${sec.toString().padStart(2,'0')}`;
    }

    function addTerminalLine(text) {
        const line = document.createElement('div');
        line.className = 'terminal-line';
        const ts = new Date().toLocaleTimeString([], { hour12: false });
        line.textContent = `[${ts}] > ${text}`;
        terminal.appendChild(line);
        if (terminal.childNodes.length > 50) terminal.removeChild(terminal.firstChild);
        terminal.scrollTop = terminal.scrollHeight;
    }

    function updateProgressStatus(text, percent = -1) {
        progressStatus.textContent = text;
        if (percent >= 0) {
            progressPercent.textContent = `${Math.round(percent)}%`;
            progressBar.style.width = `${percent}%`;
        }
    }

    function setProcessing(isProcessing, text = 'Processing...') {
        if (isProcessing) {
            appContainer.classList.add('processing');
            generateBtn.disabled = true;
            btnLoader.hidden = false;
            generateBtn.querySelector('span').textContent = text;
        } else {
            appContainer.classList.remove('processing');
            generateBtn.disabled = false;
            btnLoader.hidden = true;
            generateBtn.querySelector('span').textContent = 'Generate Captions';
        }
    }

    function finishProcessing(label, color) {
        setProcessing(false);
        // Note: statusBadge was removed from index.html, so we can ignore it or just log
    }

    async function fetchAndShowCaptions(taskId) {
        try {
            const response = await fetch(`/results/${taskId}`);
            if (!response.ok) throw new Error('Could not fetch captions');
            const segments = await response.json();
            captionPreviewContainer.hidden = false;
            captionPreview.innerHTML = segments.map(seg => `
                <div class="caption-segment">
                    <span class="caption-time">${formatSeconds(seg.start)}</span>
                    <span class="caption-text">${seg.text}</span>
                </div>
            `).join('');
        } catch (e) { console.error(e); }
    }

    // --- General Modal ---
    const modalOverlay = document.getElementById('modal-overlay');
    const modalTitle = document.getElementById('modal-title');
    const modalMessage = document.getElementById('modal-message');
    const modalBtn = document.getElementById('modal-btn');
    const modalClose = document.getElementById('modal-close');

    function showModal(title, message, btnText = 'Okay') {
        modalTitle.textContent = title;
        modalMessage.innerHTML = message;
        modalBtn.textContent = btnText;
        modalOverlay.hidden = false;
    }

    modalBtn.onclick = () => modalOverlay.hidden = true;
    modalClose.onclick = () => modalOverlay.hidden = true;
});
