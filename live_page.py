#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live transcription HTML page template."""

LIVE_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Transkrypcja na żywo</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0b0d11;--bg-card:rgba(255,255,255,0.04);--bg-card-h:rgba(255,255,255,0.07);
  --border:rgba(255,255,255,0.08);--text:#e2e4e9;--text-dim:#8b8fa3;--text-bright:#fff;
  --accent-0:#6c9cff;--accent-1:#a78bfa;--accent-2:#34d399;--accent-3:#f472b6;
  --radius:14px;--radius-sm:8px;
  --font:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
}
html{font-size:16px;-webkit-font-smoothing:antialiased}
body{font-family:var(--font);background:var(--bg);color:var(--text);min-height:100vh;padding:24px}
body::before{content:'';position:fixed;inset:0;z-index:-1;background:radial-gradient(ellipse 80% 60% at 50% -10%,rgba(108,156,255,0.08),transparent)}
.container{max-width:900px;margin:0 auto}
h1{font-size:1.4rem;font-weight:600;color:var(--text-bright);margin-bottom:4px}
.subtitle{font-size:0.8rem;color:var(--text-dim);margin-bottom:24px}
a{color:var(--accent-0);text-decoration:none}
a:hover{text-decoration:underline}

.card{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:20px;margin-bottom:16px}
.card h2{font-size:0.85rem;font-weight:600;color:var(--text-bright);margin-bottom:12px;text-transform:uppercase;letter-spacing:0.04em}

/* Config */
.config-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
@media(max-width:700px){.config-grid{grid-template-columns:1fr}}
.config-field label{display:block;font-size:0.7rem;color:var(--text-dim);margin-bottom:4px;font-weight:600;text-transform:uppercase;letter-spacing:0.04em}
.config-field select,.config-field input{width:100%;padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:rgba(255,255,255,0.04);color:var(--text);font-family:var(--font);font-size:0.85rem;outline:none}
.config-field select option{background:#1a1d24;color:var(--text)}
.config-field select:focus,.config-field input:focus{border-color:var(--accent-0)}

/* Sources */
.source-list{display:flex;flex-direction:column;gap:8px}
.source-item{display:flex;align-items:center;gap:10px;padding:10px 14px;border-radius:var(--radius-sm);border:1px solid var(--border);cursor:pointer;transition:all 0.15s}
.source-item:hover{background:var(--bg-card-h);border-color:rgba(255,255,255,0.15)}
.source-item.selected{background:rgba(108,156,255,0.12);border-color:var(--accent-0)}
.source-item input[type="radio"]{accent-color:var(--accent-0)}
.source-item .name{font-size:0.85rem;font-weight:600;color:var(--text-bright)}
.source-item .meta{font-size:0.7rem;color:var(--text-dim)}
.source-empty{text-align:center;padding:20px;color:var(--text-dim);font-size:0.82rem}
.btn-refresh{background:none;border:1px solid var(--border);color:var(--text-dim);padding:6px 12px;border-radius:6px;font-size:0.75rem;cursor:pointer;font-family:var(--font);transition:all 0.15s}
.btn-refresh:hover{background:rgba(255,255,255,0.05);color:var(--text)}

/* Controls */
.controls{display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap;align-items:center}
.btn{font-family:var(--font);font-size:0.82rem;font-weight:600;padding:10px 20px;border-radius:var(--radius-sm);border:none;cursor:pointer;transition:all 0.15s;display:flex;align-items:center;gap:6px}
.btn-start{background:linear-gradient(135deg,var(--accent-2),#059669);color:#fff;box-shadow:0 2px 12px rgba(52,211,153,0.25)}
.btn-start:hover{transform:scale(1.04);box-shadow:0 4px 20px rgba(52,211,153,0.35)}
.btn-pause{background:rgba(251,191,36,0.15);border:1px solid rgba(251,191,36,0.4);color:#fbbf24}
.btn-pause:hover{background:rgba(251,191,36,0.25)}
.btn-stop{background:rgba(248,113,113,0.12);border:1px solid rgba(248,113,113,0.3);color:#f87171}
.btn-stop:hover{background:rgba(248,113,113,0.2)}
.btn-resume{background:rgba(52,211,153,0.12);border:1px solid rgba(52,211,153,0.3);color:var(--accent-2)}
.btn:disabled{opacity:0.4;cursor:not-allowed;transform:none}

/* Status */
.status-bar{display:flex;align-items:center;gap:16px;padding:12px 16px;border-radius:var(--radius-sm);background:rgba(255,255,255,0.02);border:1px solid var(--border);margin-bottom:16px;flex-wrap:wrap}
.status-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.status-dot.idle{background:#8b8fa3}
.status-dot.recording{background:#34d399;animation:pulse 1.5s infinite}
.status-dot.paused{background:#fbbf24}
.status-dot.stopped{background:#f87171}
@keyframes pulse{0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(52,211,153,0.4)}50%{opacity:0.8;box-shadow:0 0 0 6px rgba(52,211,153,0)}}
.status-label{font-size:0.8rem;font-weight:600;color:var(--text-bright)}
.status-meta{font-size:0.72rem;color:var(--text-dim);font-variant-numeric:tabular-nums}

/* Transcript area */
.transcript-live{min-height:300px;max-height:60vh;overflow-y:auto;padding:16px;font-size:0.9rem;line-height:1.8;color:var(--text);white-space:pre-wrap;word-wrap:break-word}
.chunk-text{margin-bottom:8px}
.chunk-time{font-size:0.7rem;color:var(--accent-0);font-weight:600;margin-right:8px;font-variant-numeric:tabular-nums}
.chunk-processing{color:var(--text-dim);font-style:italic;animation:fadePulse 1.5s infinite}
@keyframes fadePulse{0%,100%{opacity:0.5}50%{opacity:1}}

/* Save */
.save-section{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.save-section input{flex:1;min-width:200px;padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:rgba(255,255,255,0.04);color:var(--text);font-family:var(--font);font-size:0.85rem;outline:none}
.save-section input:focus{border-color:var(--accent-0)}
.btn-save{background:linear-gradient(135deg,var(--accent-0),var(--accent-1));color:#fff;box-shadow:0 2px 12px rgba(108,156,255,0.2)}
.btn-save:hover{transform:scale(1.04)}

/* Toast */
.toast{position:fixed;bottom:24px;right:24px;background:rgba(52,211,153,0.95);color:#0b0d11;padding:10px 20px;border-radius:8px;font-size:0.82rem;font-weight:600;z-index:9999;opacity:0;transform:translateY(10px);transition:all 0.3s;pointer-events:none}
.toast.show{opacity:1;transform:translateY(0)}
</style>
</head>
<body>
<div class="container">
  <a href="/">← Wróć do transkrypcji</a>
  <h1 style="margin-top:16px">🎙️ Transkrypcja na żywo</h1>
  <p class="subtitle">Przechwytywanie audio z aplikacji i transkrypcja w czasie rzeczywistym</p>

  <!-- Config -->
  <div class="card" id="configCard">
    <h2>⚙️ Konfiguracja</h2>
    <div class="config-grid">
      <div class="config-field">
        <label>Model Whisper</label>
        <select id="cfgModel">
          <option value="tiny">tiny (~3s opóźnienia)</option>
          <option value="base">base (~5s)</option>
          <option value="small" selected>small (~12s)</option>
          <option value="medium">medium (~20s)</option>
        </select>
      </div>
      <div class="config-field">
        <label>Rozmiar porcji</label>
        <select id="cfgChunk">
          <option value="10">10 sekund</option>
          <option value="15" selected>15 sekund</option>
          <option value="20">20 sekund</option>
          <option value="30">30 sekund</option>
        </select>
      </div>
      <div class="config-field">
        <label>Urządzenie</label>
        <select id="cfgDevice">
          <option value="cuda">GPU (CUDA)</option>
          <option value="cpu">CPU</option>
        </select>
      </div>
    </div>
  </div>

  <!-- Sources -->
  <div class="card">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
      <h2 style="margin-bottom:0">🔊 Źródło audio</h2>
      <div style="display:flex;gap:8px">
        <button class="btn-refresh" id="btnPreview" onclick="togglePreview()" disabled>🔈 Odsłuchaj źródło</button>
        <button class="btn-refresh" onclick="refreshSources()">↻ Odśwież</button>
      </div>
    </div>
    <div class="source-list" id="sourceList">
      <div class="source-empty">Ładowanie źródeł...</div>
    </div>
  </div>

  <!-- Controls -->
  <div class="controls">
    <button class="btn btn-start" id="btnStart" onclick="startSession()" disabled>▶ Start</button>
    <button class="btn btn-pause" id="btnPause" onclick="pauseSession()" disabled>⏸ Pauza</button>
    <button class="btn btn-resume" id="btnResume" onclick="resumeSession()" style="display:none">▶ Wznów</button>
    <button class="btn btn-stop" id="btnStop" onclick="stopSession()" disabled>⏹ Stop</button>
  </div>

  <!-- Status -->
  <div class="status-bar" id="statusBar">
    <span class="status-dot idle" id="statusDot"></span>
    <span class="status-label" id="statusLabel">Bezczynny</span>
    <span class="status-meta" id="statusMeta"></span>
  </div>

  <!-- Live transcript -->
  <div class="card">
    <h2>📜 Transkrypcja</h2>
    <div class="transcript-live" id="transcriptLive">
      <div style="text-align:center;color:var(--text-dim);padding:40px">
        Wybierz źródło audio i kliknij Start aby rozpocząć transkrypcję na żywo.
      </div>
    </div>
  </div>

  <!-- Save -->
  <div class="card" id="saveCard" style="display:none">
    <h2>💾 Zapisz transkrypt</h2>
    <div class="save-section">
      <input type="text" id="saveName" placeholder="Nazwa pliku (bez rozszerzenia)">
      <button class="btn btn-save" onclick="saveTranscript()">💾 Zapisz</button>
    </div>
  </div>
</div>

<div id="previewAudioContainer" style="position:absolute;left:-9999px"></div>

<script>
let selectedSource = null;
let eventSource = null;
let sessionActive = false;
let autoScroll = true;

// ── Source list ───────────────────────────────────────────────
async function refreshSources(){
  const list = document.getElementById('sourceList');
  list.innerHTML = '<div class="source-empty">Ładowanie...</div>';
  try{
    const resp = await fetch('/live/sources');
    const sources = await resp.json();
    if(sources.length === 0){
      list.innerHTML = '<div class="source-empty">Brak aktywnych źródeł audio. Uruchom jakąś aplikację odtwarzającą dźwięk.</div>';
      return;
    }
    list.innerHTML = '';
    sources.forEach(src => {
      const item = document.createElement('div');
      item.className = 'source-item';
      item.innerHTML = `
        <input type="radio" name="source" value="${src.id}">
        <div>
          <div class="name">${src.name || 'Nieznane źródło'}</div>
          <div class="meta">ID: ${src.id} ${src.media_name ? '• ' + src.media_name : ''}</div>
        </div>
      `;
      item.addEventListener('click', () => {
        document.querySelectorAll('.source-item').forEach(el => el.classList.remove('selected'));
        item.classList.add('selected');
        item.querySelector('input').checked = true;
        selectedSource = src.id;
        document.getElementById('btnStart').disabled = false;
        document.getElementById('btnPreview').disabled = false;
      });
      list.appendChild(item);
    });
  } catch(e){
    list.innerHTML = '<div class="source-empty">Błąd ładowania źródeł: ' + e.message + '</div>';
  }
}

// ── Session controls ──────────────────────────────────────────
async function startSession(){
  if(!selectedSource) return;
  const model = document.getElementById('cfgModel').value;
  const chunk = document.getElementById('cfgChunk').value;
  const device = document.getElementById('cfgDevice').value;

  document.getElementById('btnStart').disabled = true;
  document.getElementById('configCard').style.opacity = '0.5';
  document.getElementById('configCard').style.pointerEvents = 'none';

  try{
    const resp = await fetch('/live/start', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({source_id: selectedSource, model, chunk_duration: parseInt(chunk), device})
    });
    if(!resp.ok){
      const err = await resp.json();
      alert('Błąd: ' + (err.error || 'Nieznany'));
      resetUI();
      return;
    }
    sessionActive = true;
    document.getElementById('btnPause').disabled = false;
    document.getElementById('btnStop').disabled = false;
    document.getElementById('btnPreview').disabled = false;
    document.getElementById('transcriptLive').innerHTML = '<div class="chunk-processing">● Nagrywanie rozpoczęte, ładowanie modelu...</div>';
    document.getElementById('saveCard').style.display = 'none';
    connectSSE();
    startStatusPolling();
  } catch(e){
    alert('Błąd połączenia: ' + e.message);
    resetUI();
  }
}

async function pauseSession(){
  await fetch('/live/pause', {method:'POST'});
  document.getElementById('btnPause').style.display = 'none';
  document.getElementById('btnResume').style.display = '';
}

async function resumeSession(){
  await fetch('/live/resume', {method:'POST'});
  document.getElementById('btnResume').style.display = 'none';
  document.getElementById('btnPause').style.display = '';
}

async function stopSession(){
  try{
    const resp = await fetch('/live/stop', {method:'POST'});
    if(!resp.ok){
      console.error('Stop failed:', resp.status);
    }
  } catch(e){
    console.error('Stop error:', e);
  }
  sessionActive = false;
  if(eventSource){ eventSource.close(); eventSource = null; }
  if(statusInterval){ clearInterval(statusInterval); statusInterval = null; }
  // Stop live preview if playing
  if(previewPlaying){
    document.getElementById('previewAudioContainer').innerHTML = '';
    previewPlaying = false;
  }
  document.getElementById('btnPause').disabled = true;
  document.getElementById('btnStop').disabled = true;
  document.getElementById('btnStart').disabled = false;
  document.getElementById('btnResume').style.display = 'none';
  document.getElementById('btnPause').style.display = '';
  document.getElementById('btnPreview').disabled = !selectedSource;
  document.getElementById('btnPreview').innerHTML = '🔈 Odsłuchaj źródło';
  document.getElementById('btnPreview').style.borderColor = '';
  document.getElementById('saveCard').style.display = 'block';
  document.getElementById('configCard').style.opacity = '1';
  document.getElementById('configCard').style.pointerEvents = '';
}

function resetUI(){
  document.getElementById('btnStart').disabled = !selectedSource;
  document.getElementById('btnPause').disabled = true;
  document.getElementById('btnStop').disabled = true;
  document.getElementById('configCard').style.opacity = '1';
  document.getElementById('configCard').style.pointerEvents = '';
}

// ── SSE ───────────────────────────────────────────────────────
function connectSSE(){
  if(eventSource) eventSource.close();
  eventSource = new EventSource('/live/events');

  eventSource.addEventListener('chunk', e => {
    const data = JSON.parse(e.data);
    appendChunk(data);
  });

  eventSource.addEventListener('status', e => {
    const data = JSON.parse(e.data);
    updateStatus(data);
  });

  eventSource.addEventListener('error_event', e => {
    const data = JSON.parse(e.data);
    showToast('⚠️ ' + data.message);
  });

  eventSource.addEventListener('session_ended', e => {
    const data = JSON.parse(e.data);
    updateStatus({state:'stopped', duration: data.duration, chunks_completed: data.chunks, total_words: data.words});
    document.getElementById('saveCard').style.display = 'block';
  });

  eventSource.onerror = () => {
    // Will auto-reconnect or we ignore
  };
}

// ── Transcript rendering ──────────────────────────────────────
function appendChunk(data){
  const container = document.getElementById('transcriptLive');
  // Remove processing indicator
  const proc = container.querySelector('.chunk-processing');
  if(proc) proc.remove();

  data.segments.forEach(seg => {
    const div = document.createElement('div');
    div.className = 'chunk-text';
    const timeStr = formatTime(seg.start);
    div.innerHTML = `<span class="chunk-time">[${timeStr}]</span>${escHtml(seg.text)}`;
    container.appendChild(div);
  });

  // Add processing indicator
  const indicator = document.createElement('div');
  indicator.className = 'chunk-processing';
  indicator.textContent = '● nagrywanie...';
  container.appendChild(indicator);

  if(autoScroll) container.scrollTop = container.scrollHeight;
}

// ── Status polling (fallback + timer) ─────────────────────────
let statusInterval = null;
function startStatusPolling(){
  if(statusInterval) clearInterval(statusInterval);
  statusInterval = setInterval(async () => {
    if(!sessionActive){ clearInterval(statusInterval); return; }
    try{
      const resp = await fetch('/live/status');
      const data = await resp.json();
      updateStatus(data);
    } catch(e){}
  }, 2000);
}

function updateStatus(data){
  const dot = document.getElementById('statusDot');
  const label = document.getElementById('statusLabel');
  const meta = document.getElementById('statusMeta');

  dot.className = 'status-dot ' + (data.state || 'idle');

  const stateNames = {idle:'Bezczynny', recording:'● Nagrywanie', paused:'⏸ Pauza', stopped:'⏹ Zakończony', processing:'Przetwarzanie'};
  label.textContent = stateNames[data.state] || data.state;

  const parts = [];
  if(data.duration != null) parts.push(formatTime(data.duration));
  if(data.chunks_completed != null) parts.push(`Porcji: ${data.chunks_completed}`);
  if(data.total_words != null) parts.push(`Słów: ${data.total_words}`);
  if(data.chunks_processing > 0) parts.push(`(przetwarzanie porcji...)`);
  meta.textContent = parts.join(' • ');
}

// ── Save ──────────────────────────────────────────────────────
async function saveTranscript(){
  const name = document.getElementById('saveName').value.trim();
  if(!name){ alert('Podaj nazwę pliku.'); return; }
  try{
    const resp = await fetch('/live/save', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({filename: name})
    });
    const data = await resp.json();
    if(data.error){
      alert('Błąd: ' + data.error);
    } else {
      showToast('Transkrypt zapisany! Możesz go otworzyć w głównym viewerze.');
      document.getElementById('saveCard').style.display = 'none';
    }
  } catch(e){
    alert('Błąd zapisu: ' + e.message);
  }
}

// ── Helpers ───────────────────────────────────────────────────
function formatTime(s){
  if(s == null) return '0:00';
  const m = Math.floor(s/60), sec = Math.floor(s%60);
  return m + ':' + (sec<10?'0':'') + sec;
}
function escHtml(t){ return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function showToast(msg){
  let t = document.getElementById('toast');
  if(!t){ t = document.createElement('div'); t.id='toast'; t.className='toast'; document.body.appendChild(t); }
  t.textContent = msg; t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'), 3000);
}

// Auto-scroll detection
document.getElementById('transcriptLive').addEventListener('scroll', function(){
  const el = this;
  autoScroll = (el.scrollHeight - el.scrollTop - el.clientHeight) < 50;
});

// ── Audio preview ─────────────────────────────────────────────
let previewPlaying = false;

function togglePreview(){
  const btn = document.getElementById('btnPreview');
  const container = document.getElementById('previewAudioContainer');

  if(previewPlaying){
    // Stop — destroy the audio element completely
    container.innerHTML = '';
    previewPlaying = false;
    btn.textContent = '🔈 Odsłuchaj źródło';
    btn.style.borderColor = '';
    return;
  }

  if(!selectedSource){
    showToast('⚠️ Najpierw wybierz źródło audio.');
    return;
  }

  // Create fresh audio element each time
  container.innerHTML = '';
  const audio = document.createElement('audio');
  audio.autoplay = true;
  audio.src = '/live/preview?source_id=' + encodeURIComponent(selectedSource) + '&t=' + Date.now();
  container.appendChild(audio);

  previewPlaying = true;
  btn.textContent = '🔇 Zatrzymaj odsłuch';
  btn.style.borderColor = 'var(--accent-2)';
  showToast('🔊 Odsłuchiwanie źródła...');

  audio.onerror = () => {
    if(previewPlaying){
      showToast('⚠️ Odsłuch przerwany');
      previewPlaying = false;
      btn.textContent = '🔈 Odsłuchaj źródło';
      btn.style.borderColor = '';
    }
  };
}

// Init
refreshSources();
</script>
</body>
</html>"""
