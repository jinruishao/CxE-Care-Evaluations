/* ═══════════════════════════════════════════════════════════════════════
   CxE Care Evaluation Agent — Frontend Application Logic
   ═══════════════════════════════════════════════════════════════════════ */

// ── Configuration ─────────────────────────────────────────────────────

const API_BASE = 'http://localhost:8020/api';

let currentDataset = null;  // Currently viewed/generated dataset

// ── Navigation ────────────────────────────────────────────────────────

function navigateTo(page) {
    // Update nav links
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.toggle('active', link.dataset.page === page);
    });

    // Show target page
    document.querySelectorAll('.page').forEach(p => {
        p.classList.toggle('active', p.id === `page-${page}`);
    });

    // Page-specific loading
    if (page === 'datasets') {
        loadLocalDatasets();
        loadGitHubDatasets();
    } else if (page === 'home') {
        refreshStats();
    }
}

// Setup navigation click handlers
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        navigateTo(link.dataset.page);
    });
});

// Setup tab handlers
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        const tabGroup = tab.closest('.tabs') || tab.parentElement;
        const container = tabGroup.parentElement;

        tabGroup.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        container.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        const target = container.querySelector(`#tab-${tab.dataset.tab}`);
        if (target) target.classList.add('active');
    });
});

// ── API Helpers ───────────────────────────────────────────────────────

async function apiCall(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) options.body = JSON.stringify(body);

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, options);
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || data.error || 'API request failed');
        }
        return data;
    } catch (err) {
        if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
            showToast('API server is not running. Start the backend with: uvicorn backend.app:app --reload', 'error');
        }
        throw err;
    }
}

// ── Health Check ──────────────────────────────────────────────────────

async function checkAPIHealth() {
    const statusEl = document.getElementById('apiStatus');
    try {
        await apiCall('/health');
        statusEl.innerHTML = '<span class="status-dot online"></span><span class="status-text">API Online</span>';
        return true;
    } catch {
        statusEl.innerHTML = '<span class="status-dot offline"></span><span class="status-text">API Offline</span>';
        return false;
    }
}

// ── Dataset Generation ────────────────────────────────────────────────

document.getElementById('generateForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    await generateDataset();
});

async function generateDataset() {
    const generateBtn = document.getElementById('generateBtn');
    const progressCard = document.getElementById('generationProgress');
    const resultCard = document.getElementById('generationResult');

    const kustoTablesRaw = document.getElementById('kustoTables').value;
    const kustoTables = kustoTablesRaw ? kustoTablesRaw.split(',').map(t => t.trim()).filter(Boolean) : null;

    const scenario = {
        title: document.getElementById('scenarioTitle').value,
        description: document.getElementById('scenarioDescription').value,
        category: document.getElementById('scenarioCategory').value,
        num_samples: parseInt(document.getElementById('numSamples').value) || 20,
        kusto_database: document.getElementById('kustoDatabase').value || null,
        kusto_tables: kustoTables,
    };

    // Show progress
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating…';
    progressCard.classList.remove('hidden');
    resultCard.classList.add('hidden');

    // Animate progress
    const progressFill = document.getElementById('progressFill');
    const progressMessage = document.getElementById('progressMessage');
    let progress = 0;

    const progressInterval = setInterval(() => {
        if (progress < 90) {
            progress += Math.random() * 8;
            progressFill.style.width = `${Math.min(progress, 90)}%`;

            const messages = [
                'Extracting keywords from scenario…',
                'Discovering relevant Kusto tables…',
                'Analyzing table schemas…',
                'Generating evaluation samples…',
                'Refining sample quality…',
                'Finalizing expected outputs…',
                'Validating dataset quality…',
                'Compiling final dataset…',
            ];
            const msgIndex = Math.min(Math.floor(progress / 12), messages.length - 1);
            progressMessage.textContent = messages[msgIndex];
        }
    }, 800);

    try {
        const response = await apiCall('/datasets/generate', 'POST', scenario);

        clearInterval(progressInterval);
        progressFill.style.width = '100%';
        progressMessage.textContent = 'Complete!';

        if (response.success) {
            currentDataset = response.data;
            showGenerationResult(response.data);
            showToast(`Dataset generated with ${response.data.total_samples} samples`, 'success');
        } else {
            throw new Error(response.error || 'Generation failed');
        }
    } catch (err) {
        clearInterval(progressInterval);
        showToast(`Generation failed: ${err.message}`, 'error');
        progressCard.classList.add('hidden');
    } finally {
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<i class="fas fa-wand-magic-sparkles"></i> Generate Dataset';
    }
}

function showGenerationResult(data) {
    const resultCard = document.getElementById('generationResult');
    const progressCard = document.getElementById('generationProgress');

    progressCard.classList.add('hidden');
    resultCard.classList.remove('hidden');

    // Show statistics
    const statsEl = document.getElementById('resultStats');

    statsEl.innerHTML = `
        <div class="result-stat"><strong>${data.total_samples}</strong> Total Samples</div>
        <div class="result-stat">ID: <strong>${data.id}</strong></div>
    `;

    // Show preview of first 3 samples
    const previewEl = document.getElementById('samplePreview');
    const previewData = data.samples ? data.samples.slice(0, 3) : [];
    previewEl.textContent = JSON.stringify(previewData, null, 2);
}

// ── Publish to GitHub ─────────────────────────────────────────────────

async function publishDataset() {
    if (!currentDataset) {
        showToast('No dataset to publish', 'error');
        return;
    }

    const publishBtn = document.getElementById('publishBtn');
    publishBtn.disabled = true;
    publishBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Publishing…';

    try {
        const response = await apiCall(`/datasets/${currentDataset.id}/publish`, 'POST', {
            dataset_id: currentDataset.id,
            commit_message: `Golden dataset: ${currentDataset.scenario?.title || currentDataset.id}`,
        });

        if (response.success) {
            showToast('Dataset published to GitHub!', 'success');
            if (response.data?.url) {
                window.open(response.data.url, '_blank');
            }
        }
    } catch (err) {
        showToast(`Publish failed: ${err.message}`, 'error');
    } finally {
        publishBtn.disabled = false;
        publishBtn.innerHTML = '<i class="fab fa-github"></i> Publish to GitHub';
    }
}

// ── Download Dataset ──────────────────────────────────────────────────

function downloadDataset() {
    if (!currentDataset) {
        showToast('No dataset to download', 'error');
        return;
    }

    const blob = new Blob([JSON.stringify(currentDataset, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `golden-dataset-${currentDataset.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('Dataset downloaded', 'success');
}

// ── Datasets Listing ──────────────────────────────────────────────────

async function loadLocalDatasets() {
    const container = document.getElementById('localDatasetsList');
    try {
        const response = await apiCall('/datasets');
        const datasets = response.data || [];

        if (datasets.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <p>No datasets generated yet. <a href="#" onclick="navigateTo('generate')">Generate one now</a>.</p>
                </div>`;
            return;
        }

        container.innerHTML = datasets.map(ds => renderDatasetCard(ds, 'local')).join('');
    } catch {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <p>Could not load datasets. Is the API server running?</p>
            </div>`;
    }
}

async function loadGitHubDatasets() {
    const container = document.getElementById('githubDatasetsList');
    try {
        const response = await apiCall('/github/datasets');
        const datasets = response.data || [];

        if (datasets.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fab fa-github"></i>
                    <p>No datasets published to GitHub yet.</p>
                </div>`;
            return;
        }

        container.innerHTML = datasets.map(ds => `
            <div class="dataset-card" onclick="window.open('${ds.url}', '_blank')">
                <div class="dataset-card-header">
                    <h3><i class="fab fa-github"></i> ${ds.id}</h3>
                </div>
                <div class="meta">Published to GitHub</div>
                <div class="dataset-card-actions">
                    <a href="${ds.url}" target="_blank" class="btn btn-sm btn-secondary">
                        <i class="fas fa-external-link-alt"></i> View on GitHub
                    </a>
                </div>
            </div>
        `).join('');
    } catch {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fab fa-github"></i>
                <p>Could not load GitHub datasets.</p>
            </div>`;
    }
}

function renderDatasetCard(ds, source) {
    const scenario = ds.scenario || {};

    return `
        <div class="dataset-card" onclick="showDatasetDetail('${ds.id}', '${source}')">
            <div class="dataset-card-header">
                <div>
                    <h3>${scenario.title || ds.id}</h3>
                    <div class="meta">${scenario.category || 'custom'} • ${ds.created_at ? new Date(ds.created_at).toLocaleDateString() : ''}</div>
                </div>
                <span class="status-badge ${ds.status || 'completed'}">${ds.status || 'completed'}</span>
            </div>
            <div class="stats-row">
                <span><i class="fas fa-vials"></i> ${ds.total_samples || 0} samples</span>
            </div>
            <div class="dataset-card-actions">
                <button class="btn btn-sm btn-primary" onclick="event.stopPropagation(); publishDatasetById('${ds.id}')">
                    <i class="fab fa-github"></i> Publish
                </button>
                <button class="btn btn-sm btn-secondary" onclick="event.stopPropagation(); downloadDatasetById('${ds.id}')">
                    <i class="fas fa-download"></i> Download
                </button>
                <button class="btn btn-sm btn-danger" onclick="event.stopPropagation(); deleteDatasetById('${ds.id}')">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `;
}

async function showDatasetDetail(id, source) {
    try {
        const response = await apiCall(`/datasets/${id}`);
        const ds = response.data;
        if (!ds) return;

        document.getElementById('modalTitle').textContent = ds.scenario?.title || id;
        document.getElementById('modalBody').innerHTML = `
            <p><strong>Category:</strong> ${ds.scenario?.category || 'custom'}</p>
            <p><strong>Description:</strong> ${ds.scenario?.description || ''}</p>
            <p><strong>Total Samples:</strong> ${ds.total_samples || 0}</p>
            <p><strong>Created:</strong> ${ds.created_at || ''}</p>
            <hr style="margin: 16px 0; border-color: var(--neutral-100);">
            <h3>All Samples</h3>
            <div class="json-preview">${JSON.stringify(ds.samples, null, 2)}</div>
        `;

        document.getElementById('datasetModal').classList.remove('hidden');
    } catch (err) {
        showToast(`Could not load dataset: ${err.message}`, 'error');
    }
}

async function publishDatasetById(id) {
    try {
        const response = await apiCall(`/datasets/${id}/publish`, 'POST', {
            dataset_id: id,
        });
        if (response.success) {
            showToast('Published to GitHub!', 'success');
        }
    } catch (err) {
        showToast(`Publish failed: ${err.message}`, 'error');
    }
}

async function downloadDatasetById(id) {
    try {
        const response = await apiCall(`/datasets/${id}`);
        const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `golden-dataset-${id}.json`;
        a.click();
        URL.revokeObjectURL(url);
    } catch (err) {
        showToast(`Download failed: ${err.message}`, 'error');
    }
}

async function deleteDatasetById(id) {
    if (!confirm('Delete this dataset?')) return;
    try {
        await apiCall(`/datasets/${id}`, 'DELETE');
        showToast('Dataset deleted', 'success');
        loadLocalDatasets();
    } catch (err) {
        showToast(`Delete failed: ${err.message}`, 'error');
    }
}

// ── Kusto Explorer ────────────────────────────────────────────────────

async function loadKustoDatabases() {
    const dbList = document.getElementById('databaseList');
    dbList.innerHTML = '<li class="empty-state-sm"><i class="fas fa-spinner fa-spin"></i> Loading…</li>';

    try {
        const response = await apiCall('/kusto/databases');
        const databases = response.data || [];

        if (databases.length === 0) {
            dbList.innerHTML = '<li class="empty-state-sm">No databases found</li>';
            return;
        }

        dbList.innerHTML = databases.map(db => `
            <li class="db-item" onclick="loadKustoTables('${db}')">
                <i class="fas fa-database"></i> ${db}
            </li>
        `).join('');
    } catch (err) {
        dbList.innerHTML = `<li class="empty-state-sm">Error: ${err.message}</li>`;
    }
}

async function loadKustoTables(database) {
    const dbList = document.getElementById('databaseList');
    document.getElementById('kustoDbInput').value = database;

    try {
        const response = await apiCall(`/kusto/tables/${database}`);
        const tables = response.data || [];

        // Find the current db item and add tables below it
        const dbItems = dbList.querySelectorAll('.db-item');
        dbItems.forEach(item => {
            // Remove old table items
            let next = item.nextElementSibling;
            while (next && next.classList.contains('table-item')) {
                const toRemove = next;
                next = next.nextElementSibling;
                toRemove.remove();
            }
        });

        // Find the clicked db and insert tables
        for (const item of dbItems) {
            if (item.textContent.trim().includes(database)) {
                const fragment = document.createDocumentFragment();
                tables.forEach(table => {
                    const li = document.createElement('li');
                    li.className = 'table-item';
                    li.textContent = table;
                    li.onclick = () => exploreKustoTable(database, table);
                    fragment.appendChild(li);
                });
                item.after(fragment);
                break;
            }
        }
    } catch (err) {
        showToast(`Failed to load tables: ${err.message}`, 'error');
    }
}

async function exploreKustoTable(database, table) {
    document.getElementById('kustoDbInput').value = database;
    document.getElementById('kustoQueryInput').value = `${table} | take 10`;
    await executeKustoQuery();
}

async function executeKustoQuery() {
    const database = document.getElementById('kustoDbInput').value;
    const query = document.getElementById('kustoQueryInput').value;
    const resultsEl = document.getElementById('kustoResults');

    if (!database || !query) {
        showToast('Please enter both database and query', 'error');
        return;
    }

    resultsEl.innerHTML = '<div class="empty-state-sm"><i class="fas fa-spinner fa-spin"></i> Executing…</div>';

    try {
        const response = await apiCall('/kusto/query', 'POST', { database, query });
        const rows = response.data || [];

        if (rows.length === 0) {
            resultsEl.innerHTML = '<div class="empty-state-sm">No results</div>';
            return;
        }

        const columns = Object.keys(rows[0]);
        const tableHTML = `
            <table class="results-table">
                <thead>
                    <tr>${columns.map(c => `<th>${c}</th>`).join('')}</tr>
                </thead>
                <tbody>
                    ${rows.map(row => `
                        <tr>${columns.map(c => `<td>${row[c] ?? ''}</td>`).join('')}</tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        resultsEl.innerHTML = tableHTML;
    } catch (err) {
        resultsEl.innerHTML = `<div class="empty-state-sm" style="color: var(--error);">Error: ${err.message}</div>`;
    }
}

// ── Modal ─────────────────────────────────────────────────────────────

function closeModal() {
    document.getElementById('datasetModal').classList.add('hidden');
}

document.getElementById('datasetModal').addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) closeModal();
});

// ── Toast Notifications ───────────────────────────────────────────────

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = { success: 'check-circle', error: 'exclamation-circle', info: 'info-circle' };
    toast.innerHTML = `<i class="fas fa-${icons[type] || 'info-circle'}"></i> ${message}`;

    container.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}

// ── Stats ─────────────────────────────────────────────────────────────

async function refreshStats() {
    try {
        const response = await apiCall('/datasets');
        const datasets = response.data || [];

        document.getElementById('statDatasets').textContent = datasets.length;
        document.getElementById('statSamples').textContent = datasets.reduce(
            (sum, ds) => sum + (ds.total_samples || 0), 0
        );
        document.getElementById('statPublished').textContent = datasets.filter(
            ds => ds.status === 'published'
        ).length;
    } catch {
        // Stats unavailable when API is offline
    }
}

// ── Initialization ────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    checkAPIHealth();
    setInterval(checkAPIHealth, 30000);  // Re-check every 30s
});
