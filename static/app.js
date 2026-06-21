// Codessey frontend — minimal JS for the review UI

document.addEventListener('DOMContentLoaded', () => {
    const tabs = document.querySelectorAll('.tab');
    const pasteTab = document.getElementById('tab-paste');
    const uploadTab = document.getElementById('tab-upload');
    const urlTab = document.getElementById('tab-url');
    const tabPanels = { paste: pasteTab, upload: uploadTab, url: urlTab };

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            Object.values(tabPanels).forEach(p => p.classList.add('hidden'));
            tabPanels[tab.dataset.tab].classList.remove('hidden');
        });
    });

    document.getElementById('review-paste-btn').addEventListener('click', async () => {
        const content = document.getElementById('code-input').value;
        if (!content.trim()) return;
        await runReview('/api/review/paste', { content });
    });

    document.getElementById('review-upload-btn').addEventListener('click', async () => {
        const fileInput = document.getElementById('file-input');
        if (!fileInput.files.length) return;
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        await runReview('/api/review/upload', formData, true);
    });

    document.getElementById('review-url-btn').addEventListener('click', async () => {
        const url = document.getElementById('url-input').value;
        if (!url.trim()) return;
        await runReview('/api/review/url', { url });
    });
});

async function runReview(endpoint, body, isFormData = false) {
    const loading = document.getElementById('loading');
    const report = document.getElementById('report');
    const error = document.getElementById('error');

    loading.classList.add('active');
    report.innerHTML = '';
    error.classList.add('hidden');

    try {
        const options = isFormData
            ? { method: 'POST', body }
            : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };

        const response = await fetch(endpoint, options);

        if (!response.ok) {
            const data = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(data.detail || `HTTP ${response.status}`);
        }

        const data = await response.json();
        report.innerHTML = markdownToHtml(data.markdown_report);
    } catch (e) {
        error.textContent = e.message;
        error.classList.remove('hidden');
    } finally {
        loading.classList.remove('active');
    }
}

function markdownToHtml(md) {
    // ponytail: minimal markdown→HTML, no dependency needed for a demo
    return md
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
        .replace(/^---$/gm, '<hr>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>')
        .replace(/^/, '<p>').replace(/$/, '</p>');
}
