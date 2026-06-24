// Codessey frontend — single-flow review UI: input → analyzing → results.

const els = {};

document.addEventListener('DOMContentLoaded', () => {
  cacheEls();
  initTabs();
  initPaste();
  initUpload();
  initUrl();
  initReviewAnother();
});

function cacheEls() {
  els.tabs = document.querySelectorAll('.tab');
  els.panels = {
    paste: document.getElementById('tab-paste'),
    upload: document.getElementById('tab-upload'),
    url: document.getElementById('tab-url'),
  };
  els.codeInput = document.getElementById('code-input');
  els.fileInput = document.getElementById('file-input');
  els.dropzone = document.getElementById('dropzone');
  els.dzText = document.getElementById('dz-text');
  els.urlInput = document.getElementById('url-input');
  els.uploadBtn = document.getElementById('review-upload-btn');

  els.views = {
    input: document.getElementById('view-input'),
    loading: document.getElementById('view-loading'),
    results: document.getElementById('view-results'),
  };

  els.mcCount = document.getElementById('mc-count');
  els.mcElapsed = document.getElementById('mc-elapsed');
  els.agents = {};
  document.querySelectorAll('.agent').forEach((card) => {
    els.agents[card.dataset.agent] = {
      card,
      status: card.querySelector('.agent-status'),
    };
  });

  els.error = document.getElementById('error');
  els.summary = document.getElementById('summary');
  els.report = document.getElementById('report');
  els.gradeBadge = document.getElementById('grade-badge');
  els.healthValue = document.getElementById('health-value');
  els.scoreBarFill = document.getElementById('score-bar-fill');
  els.findingsCount = document.getElementById('findings-count');
  els.unavailableStat = document.getElementById('unavailable-stat');
  els.unavailableCount = document.getElementById('unavailable-count');
}

/* ---------- View switching ---------- */
function showView(name) {
  Object.entries(els.views).forEach(([key, el]) => {
    el.classList.toggle('active', key === name);
  });
}

/* ---------- Tabs ---------- */
function initTabs() {
  els.tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      els.tabs.forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      Object.values(els.panels).forEach((p) => p.classList.add('hidden'));
      els.panels[tab.dataset.tab].classList.remove('hidden');
    });
  });
}

/* ---------- Paste ---------- */
function initPaste() {
  document.getElementById('review-paste-btn').addEventListener('click', () => {
    const content = els.codeInput.value;
    if (!content.trim()) return;
    runReview('/api/review/paste', { content });
  });
  document.getElementById('clear-paste-btn').addEventListener('click', () => {
    els.codeInput.value = '';
    els.codeInput.focus();
  });
}

/* ---------- Upload ---------- */
function initUpload() {
  const { fileInput, dropzone, dzText, uploadBtn } = els;

  const setFile = () => {
    if (fileInput.files.length) {
      dzText.innerHTML = `<span class="dz-file">${escapeHtml(fileInput.files[0].name)}</span>`;
      uploadBtn.disabled = false;
    } else {
      uploadBtn.disabled = true;
    }
  };

  fileInput.addEventListener('change', setFile);

  ['dragenter', 'dragover'].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    })
  );
  ['dragleave', 'drop'].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    })
  );
  dropzone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files.length) {
      fileInput.files = e.dataTransfer.files;
      setFile();
    }
  });

  uploadBtn.addEventListener('click', () => {
    if (!fileInput.files.length) return;
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    runReview('/api/review/upload', formData, true);
  });
}

/* ---------- URL ---------- */
function initUrl() {
  document.getElementById('review-url-btn').addEventListener('click', () => {
    const url = els.urlInput.value;
    if (!url.trim()) return;
    runReview('/api/review/url', { url });
  });
}

/* ---------- Review another ---------- */
function initReviewAnother() {
  document.getElementById('review-another-btn').addEventListener('click', () => {
    els.error.classList.remove('active');
    showView('input');
    els.codeInput.focus();
  });
}

/* ---------- Mission control animation ---------- */
const AGENT_MESSAGES = {
  security: [
    'scanning injection vectors…',
    'checking auth & secrets…',
    'auditing unsafe calls…',
    'validating input handling…',
  ],
  logic: [
    'scanning control flow…',
    'tracing edge cases…',
    'checking off-by-one…',
    'verifying branch logic…',
  ],
  readability: [
    'measuring cyclomatic complexity…',
    'reviewing naming clarity…',
    'inspecting structure…',
    'scanning for dead code…',
  ],
  performance: [
    'profiling algorithmic complexity…',
    'inspecting hot loops…',
    'looking for N+1 patterns…',
    'measuring allocations…',
  ],
};

const mission = { timers: [], start: 0, raf: 0 };

function startMission() {
  stopMission();
  mission.start = performance.now();

  Object.values(els.agents).forEach((a) => {
    a.card.classList.remove('done');
    a.msgIndex = 0;
    a.status.textContent = AGENT_MESSAGES[a.card.dataset.agent][0];
  });
  els.mcCount.textContent = '0';

  const tick = () => {
    const elapsed = (performance.now() - mission.start) / 1000;
    els.mcElapsed.textContent = elapsed.toFixed(1);
    mission.raf = requestAnimationFrame(tick);
  };
  mission.raf = requestAnimationFrame(tick);

  Object.values(els.agents).forEach((a) => {
    const name = a.card.dataset.agent;
    const pool = AGENT_MESSAGES[name];
    const timer = setInterval(() => {
      if (a.card.classList.contains('done')) return;
      a.msgIndex = (a.msgIndex + 1) % pool.length;
      a.status.textContent = pool[a.msgIndex];
    }, 1500 + Math.random() * 900);
    mission.timers.push(timer);
  });

  // Mark up to 3 agents "complete" while we wait for the backend.
  const order = ['logic', 'performance', 'security'];
  let done = 0;
  order.forEach((name, i) => {
    const t = setTimeout(() => {
      const a = els.agents[name];
      if (!a) return;
      a.card.classList.add('done');
      a.status.textContent = 'complete';
      done += 1;
      els.mcCount.textContent = String(done);
    }, 1400 + i * 1300 + Math.random() * 600);
    mission.timers.push(t);
  });
}

function stopMission() {
  cancelAnimationFrame(mission.raf);
  mission.timers.forEach((t) => {
    clearInterval(t);
    clearTimeout(t);
  });
  mission.timers = [];
}

/* ---------- Review request ---------- */
async function runReview(endpoint, body, isFormData = false) {
  showView('loading');
  startMission();

  try {
    const options = isFormData
      ? { method: 'POST', body }
      : {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        };

    const response = await fetch(endpoint, options);

    if (!response.ok) {
      const data = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(data.detail || `HTTP ${response.status}`);
    }

    renderResults(await response.json());
  } catch (e) {
    showError(e.message);
  } finally {
    stopMission();
  }
}

/* ---------- Rendering ---------- */
function renderResults(data) {
  els.error.classList.remove('active');
  els.summary.classList.remove('hidden');

  els.gradeBadge.textContent = data.grade || '–';
  els.gradeBadge.className = `grade-badge grade-${data.grade || 'F'}`;

  els.healthValue.textContent = data.overall_health ?? 0;
  els.scoreBarFill.style.width = `${data.overall_health ?? 0}%`;
  els.scoreBarFill.style.background = scoreColor(data.overall_health ?? 0);

  els.findingsCount.textContent = data.findings_count ?? 0;

  const unavailable = data.agents_unavailable || [];
  if (unavailable.length) {
    els.unavailableCount.textContent = unavailable.length;
    els.unavailableStat.classList.remove('hidden');
  } else {
    els.unavailableStat.classList.add('hidden');
  }

  els.report.innerHTML = markdownToHtml(data.markdown_report || '');
  showView('results');
}

function scoreColor(score) {
  if (score >= 75) return '#6ee7a8';
  if (score >= 60) return '#e0b341';
  return '#f87171';
}

function showError(message) {
  els.error.textContent = message;
  els.error.classList.add('active');
  els.summary.classList.add('hidden');
  els.report.innerHTML = '';
  showView('results');
}

/* ---------- Minimal markdown → HTML ---------- */
function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function markdownToHtml(md) {
  return escapeHtml(md)
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/^---$/gm, '<hr>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/^/, '<p>')
    .replace(/$/, '</p>');
}
