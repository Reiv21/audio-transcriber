#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Interactive Transcript Viewer
─────────────────────────────
Python HTTP server serving a premium dark-themed HTML page for exploring WhisperX
transcripts. Features sidebar selection, dynamic API loading, and a deletion option
to remove transcripts and associated audio files from the server.
"""

import argparse
import http.server
import json
import mimetypes
import os
import re
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

try:
    import requests as http_requests
except ImportError:
    http_requests = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ──────────────────────────────────────────────────────────────────────────────
# HTML Template
# ──────────────────────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>%%PAGE_TITLE%%</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
/* ── Reset & Base ─────────────────────────────────────────────── */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:        #0b0d11;
  --bg-card:   rgba(255,255,255,0.04);
  --bg-card-h: rgba(255,255,255,0.07);
  --border:    rgba(255,255,255,0.08);
  --text:      #e2e4e9;
  --text-dim:  #8b8fa3;
  --text-bright:#ffffff;
  --accent-0:  #6c9cff;
  --accent-1:  #a78bfa;
  --accent-2:  #34d399;
  --accent-3:  #f472b6;
  --accent-4:  #fbbf24;
  --accent-5:  #fb923c;
  --accent-6:  #38bdf8;
  --accent-7:  #c084fc;
  --glow:      rgba(108,156,255,0.35);
  --radius:    14px;
  --radius-sm: 8px;
  --font:      'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
html{font-size:16px;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}
body{
  font-family:var(--font);
  background:var(--bg);
  color:var(--text);
  min-height:100vh;
  overflow-x:hidden;
}
/* Subtle gradient bg */
body::before{
  content:'';position:fixed;inset:0;z-index:-1;
  background:
    radial-gradient(ellipse 80% 60% at 50% -10%, rgba(108,156,255,0.08), transparent),
    radial-gradient(ellipse 60% 50% at 80% 100%, rgba(167,139,250,0.06), transparent);
}

/* ── App Layout ────────────────────────────────────────────────── */
.app-layout {
  display: flex;
  min-height: 100vh;
}

/* Sidebar */
.sidebar {
  width: 280px;
  background: rgba(11, 13, 17, 0.6);
  backdrop-filter: blur(20px) saturate(1.4);
  -webkit-backdrop-filter: blur(20px) saturate(1.4);
  border-right: 1px solid var(--border);
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex-shrink: 0;
  overflow-y: auto;
  position: fixed;
  top: 0;
  bottom: 0;
  left: 0;
  z-index: 200;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.sidebar-title {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-dim);
  font-weight: 700;
  margin-bottom: 8px;
  padding-left: 4px;
}
.transcript-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.transcript-item {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.transcript-item:hover {
  background: var(--bg-card-h);
  border-color: rgba(255, 255, 255, 0.15);
  transform: translateX(2px);
}
.transcript-item.active {
  background: rgba(108, 156, 255, 0.12);
  border-color: var(--accent-0);
  box-shadow: 0 0 16px rgba(108, 156, 255, 0.15);
}
.transcript-item-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 0;
}
.transcript-item-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-bright);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.transcript-item-meta {
  font-size: 0.7rem;
  color: var(--text-dim);
  display: flex;
  align-items: center;
  gap: 5px;
}

/* Delete button inside sidebar item */
.btn-delete {
  background: transparent;
  border: none;
  color: var(--text-dim);
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
  opacity: 0.4;
  flex-shrink: 0;
}
.transcript-item:hover .btn-delete {
  opacity: 0.8;
  color: var(--text);
}
.btn-delete:hover {
  opacity: 1 !important;
  color: #f87171 !important;
  background: rgba(248, 113, 113, 0.15);
}

/* Main Content */
.main-content {
  flex: 1;
  margin-left: 280px;
  min-width: 0;
  position: relative;
}
.container{max-width:860px;margin:0 auto;padding:32px 24px 80px}
header{text-align:center;margin-bottom:32px}
header h1{
  font-size:1.5rem;font-weight:600;color:var(--text-bright);
  letter-spacing:-0.02em;margin-bottom:4px;
}
header p{font-size:0.8rem;color:var(--text-dim);font-weight:400}

/* Menu Toggle for Mobile */
.menu-toggle {
  display: none;
  position: fixed;
  top: 16px;
  left: 16px;
  z-index: 300;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: rgba(15, 18, 25, 0.8);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  color: var(--text);
  cursor: pointer;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
  transition: transform 0.15s, background 0.15s;
}
.menu-toggle:hover {
  background: rgba(255, 255, 255, 0.05);
  transform: scale(1.05);
}
.menu-toggle:active {
  transform: scale(0.95);
}

/* ── Audio Player Card ────────────────────────────────────────── */
.player-card{
  background:var(--bg-card);
  backdrop-filter:blur(24px) saturate(1.4);
  -webkit-backdrop-filter:blur(24px) saturate(1.4);
  border:1px solid var(--border);
  border-radius:var(--radius);
  padding:20px 24px;
  margin-bottom:32px;
  position:sticky;top:12px;z-index:100;
  box-shadow:0 8px 32px rgba(0,0,0,0.3);
  transition:box-shadow .3s;
}
.player-card:hover{box-shadow:0 12px 48px rgba(0,0,0,0.4)}

.player-row{display:flex;align-items:center;gap:14px}

/* Play / Pause */
.btn-play{
  width:44px;height:44px;border-radius:50%;border:none;cursor:pointer;
  background:linear-gradient(135deg,var(--accent-0),var(--accent-1));
  color:#fff;display:flex;align-items:center;justify-content:center;
  flex-shrink:0;transition:transform .15s,box-shadow .2s;
  box-shadow:0 2px 12px rgba(108,156,255,0.25);
}
.btn-play:hover{transform:scale(1.08);box-shadow:0 4px 20px rgba(108,156,255,0.4)}
.btn-play:active{transform:scale(0.96)}
.btn-play svg{width:18px;height:18px;fill:currentColor}

/* Progress */
.progress-wrap{flex:1;display:flex;flex-direction:column;gap:6px}
.progress-bar-outer{
  width:100%;height:6px;border-radius:3px;background:rgba(255,255,255,0.08);
  cursor:pointer;position:relative;overflow:visible;
}
.progress-bar-inner{
  height:100%;border-radius:3px;width:0%;
  background:linear-gradient(90deg,var(--accent-0),var(--accent-1));
  transition:width .08s linear;position:relative;
}
.progress-bar-inner::after{
  content:'';position:absolute;right:-5px;top:50%;transform:translateY(-50%);
  width:12px;height:12px;border-radius:50%;
  background:#fff;box-shadow:0 0 8px var(--glow);
  opacity:0;transition:opacity .2s;
}
.progress-bar-outer:hover .progress-bar-inner::after{opacity:1}

.time-row{display:flex;justify-content:space-between;font-size:0.72rem;color:var(--text-dim);font-variant-numeric:tabular-nums}

/* Speed control */
.speed-btn{
  font-family:var(--font);font-size:0.7rem;font-weight:600;
  background:rgba(255,255,255,0.06);border:1px solid var(--border);
  color:var(--text-dim);border-radius:6px;padding:4px 10px;
  cursor:pointer;transition:all .15s;flex-shrink:0;
}
.speed-btn:hover{background:rgba(255,255,255,0.1);color:var(--text)}

/* ── Speaker Section ──────────────────────────────────────────── */
.speaker-section{
  background:var(--bg-card);
  backdrop-filter:blur(16px) saturate(1.2);
  -webkit-backdrop-filter:blur(16px) saturate(1.2);
  border:1px solid var(--border);
  border-radius:var(--radius);
  padding:20px 24px;
  margin-bottom:16px;
  transition:background .25s,border-color .25s;
}
.speaker-section:hover{
  background:var(--bg-card-h);
  border-color:rgba(255,255,255,0.12);
}
.speaker-header{
  display:flex;align-items:center;gap:10px;margin-bottom:12px;
}
.speaker-dot{
  width:10px;height:10px;border-radius:50%;flex-shrink:0;
  box-shadow:0 0 8px currentColor;
}
.speaker-name{
  font-size:0.82rem;font-weight:600;letter-spacing:0.02em;
  cursor:pointer;padding:2px 8px;border-radius:6px;
  transition:background .2s;border:1px solid transparent;
  outline:none;min-width:60px;
}
.speaker-name:hover{background:rgba(255,255,255,0.06)}
.speaker-name:focus{
  background:rgba(255,255,255,0.08);
  border-color:rgba(255,255,255,0.15);
}
.speaker-time{
  font-size:0.68rem;color:var(--text-dim);margin-left:auto;
  font-variant-numeric:tabular-nums;
}

/* ── Words ────────────────────────────────────────────────────── */
.words{line-height:1.85;font-size:0.95rem;font-weight:400;color:var(--text)}
.w{
  cursor:pointer;padding:1px 2px;border-radius:4px;
  transition:color .12s, background .12s, transform .1s;
  display:inline;position:relative;
}
.w:hover{
  color:var(--text-bright);
  background:rgba(255,255,255,0.07);
}
.w.active{
  color:#fff;
  background:rgba(108,156,255,0.18);
  border-radius:4px;
  text-shadow: 0 0 1px rgba(255,255,255,0.6), 0 0 12px var(--glow);
}
/* Pulse on the active word */
.w.active::after{
  content:'';position:absolute;inset:-2px -3px;border-radius:6px;
  background:rgba(108,156,255,0.10);
  animation:wordPulse 1.2s ease-in-out infinite;
  pointer-events:none;
}
@keyframes wordPulse{
  0%,100%{opacity:0.5;transform:scale(1)}
  50%{opacity:1;transform:scale(1.03)}
}

/* ── Post source highlights ──────────────────────────────── */
.w.hl-0{background:rgba(239,68,68,0.20);border-radius:3px}
.w.hl-1{background:rgba(249,115,22,0.20);border-radius:3px}
.w.hl-2{background:rgba(34,197,94,0.20);border-radius:3px}
.w.hl-3{background:rgba(59,130,246,0.20);border-radius:3px}
.w.hl-4{background:rgba(168,85,247,0.20);border-radius:3px}
.w.hl-5{background:rgba(236,72,153,0.20);border-radius:3px}
.w.hl-6{background:rgba(234,179,8,0.20);border-radius:3px}
.w.hl-7{background:rgba(20,184,166,0.20);border-radius:3px}
.w.hl-bright{background:rgba(239,68,68,0.40) !important}

/* ── Hidden speakers ─────────────────────────────────────── */
.speaker-section.hidden-speaker{display:none}

/* ── Speaker Visibility Panel ────────────────────────────── */
.speaker-panel{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  margin-bottom: 16px;
  overflow: hidden;
}
.speaker-panel-toggle{
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: none;
  border: none;
  color: var(--text-dim);
  font-family: var(--font);
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  transition: color 0.15s, background 0.15s;
}
.speaker-panel-toggle:hover{
  color: var(--text);
  background: rgba(255,255,255,0.03);
}
.speaker-panel-arrow{
  transition: transform 0.2s;
  font-size: 0.7rem;
}
.speaker-panel-arrow.open{ transform: rotate(90deg); }
.speaker-panel-body{
  padding: 8px 16px 14px;
  border-top: 1px solid var(--border);
}
.speaker-checkbox-item{
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 4px;
  border-radius: 6px;
  transition: background 0.15s;
}
.speaker-checkbox-item:hover{ background: rgba(255,255,255,0.03); }
.speaker-checkbox-item input[type="checkbox"]{
  width: 16px; height: 16px;
  accent-color: var(--accent-0);
  cursor: pointer;
}
.speaker-checkbox-item label{
  font-size: 0.82rem;
  color: var(--text);
  cursor: pointer;
  flex: 1;
}
.speaker-checkbox-dot{
  width: 8px; height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* ── Keyboard hint ────────────────────────────────────────────── */
.kbd-hint{
  text-align:center;margin-top:40px;font-size:0.7rem;color:var(--text-dim);
}
.kbd{
  display:inline-block;padding:2px 8px;border-radius:5px;
  background:rgba(255,255,255,0.06);border:1px solid var(--border);
  font-family:var(--font);font-size:0.68rem;margin:0 2px;
}

/* ── Scrollbar ────────────────────────────────────────────────── */
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.1);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:rgba(255,255,255,0.18)}

/* ── Responsive ───────────────────────────────────────────────── */
@media(max-width:900px){
  .sidebar {
    transform: translateX(-100%);
  }
  .sidebar.open {
    transform: translateX(0);
    box-shadow: 8px 0 32px rgba(0,0,0,0.5);
  }
  .main-content {
    margin-left: 0;
  }
  .menu-toggle {
    display: flex;
  }
  .container {
    padding: 76px 12px 60px;
  }
  .player-card{padding:14px 16px;border-radius:12px;top:6px}
  .speaker-section{padding:14px 16px;border-radius:12px}
  header h1{font-size:1.25rem}
  .words{font-size:0.88rem}
}

/* ── Posts Panel ──────────────────────────────────────────── */
.posts-section{
  margin-top: 40px;
  border-top: 1px solid var(--border);
  padding-top: 32px;
}
.posts-header{
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;
}
.posts-header h2{
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-bright);
  display: flex;
  align-items: center;
  gap: 8px;
}
.btn-generate{
  font-family: var(--font);
  font-size: 0.8rem;
  font-weight: 600;
  padding: 8px 18px;
  border-radius: var(--radius-sm);
  border: none;
  cursor: pointer;
  background: linear-gradient(135deg, var(--accent-0), var(--accent-1));
  color: #fff;
  transition: transform 0.15s, box-shadow 0.2s, opacity 0.2s;
  box-shadow: 0 2px 12px rgba(108,156,255,0.2);
  display: flex;
  align-items: center;
  gap: 6px;
}
.btn-generate:hover{ transform: scale(1.04); box-shadow: 0 4px 20px rgba(108,156,255,0.35); }
.btn-generate:active{ transform: scale(0.97); }
.btn-generate:disabled{ opacity: 0.5; cursor: not-allowed; transform: none; }

/* Config form */
.posts-config{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  margin-bottom: 20px;
  display: none;
}
.posts-config.visible{ display: block; }
.config-grid{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
@media(max-width:600px){ .config-grid{ grid-template-columns: 1fr; } }
.config-field label{
  display: block;
  font-size: 0.7rem;
  color: var(--text-dim);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}
.config-field input, .config-field select{
  width: 100%;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.04);
  color: var(--text);
  font-family: var(--font);
  font-size: 0.85rem;
  outline: none;
  transition: border-color 0.2s;
}
.config-field select option{
  background: #1a1d24;
  color: var(--text);
}
.config-field input:focus, .config-field select:focus{
  border-color: var(--accent-0);
}
.config-actions{
  margin-top: 16px;
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

/* Loading spinner */
.posts-loading{
  display: none;
  text-align: center;
  padding: 40px;
  color: var(--text-dim);
}
.posts-loading.visible{ display: block; }
.spinner{
  width: 32px; height: 32px;
  border: 3px solid var(--border);
  border-top-color: var(--accent-0);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 12px;
}
@keyframes spin{ to{ transform: rotate(360deg); } }

/* Post cards */
.post-card{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 20px;
  margin-bottom: 12px;
  transition: all 0.2s;
  position: relative;
}
.post-card:hover{ border-color: rgba(255,255,255,0.15); }
.post-card.accepted{
  border-color: var(--accent-2);
  background: rgba(52, 211, 153, 0.06);
}
.post-card.rejected{
  opacity: 0.4;
  border-color: rgba(255,255,255,0.04);
}
.post-text{
  font-size: 0.9rem;
  line-height: 1.7;
  color: var(--text);
  outline: none;
  min-height: 40px;
  white-space: pre-wrap;
  word-wrap: break-word;
}
.post-text:focus{
  background: rgba(255,255,255,0.03);
  border-radius: 6px;
  padding: 8px;
  margin: -8px;
}
.post-actions{
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  flex-wrap: wrap;
}
.post-btn{
  font-family: var(--font);
  font-size: 0.7rem;
  font-weight: 600;
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.04);
  color: var(--text-dim);
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  gap: 4px;
}
.post-btn:hover{ background: rgba(255,255,255,0.08); color: var(--text); }
.post-btn.accept{ border-color: rgba(52,211,153,0.3); }
.post-btn.accept:hover{ background: rgba(52,211,153,0.15); color: var(--accent-2); }
.post-btn.accept.active{ background: rgba(52,211,153,0.2); color: var(--accent-2); border-color: var(--accent-2); }
.post-btn.reject:hover{ background: rgba(248,113,113,0.12); color: #f87171; }
.post-btn.reject.active{ background: rgba(248,113,113,0.15); color: #f87171; border-color: #f87171; }
.post-btn.copy:hover{ background: rgba(108,156,255,0.12); color: var(--accent-0); }

.post-status{
  font-size: 0.65rem;
  margin-left: auto;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.post-card.accepted .post-status{ color: var(--accent-2); }
.post-card.rejected .post-status{ color: #f87171; }

.posts-bulk-actions{
  display: flex;
  gap: 10px;
  margin-top: 16px;
  flex-wrap: wrap;
}
.posts-empty{
  text-align: center;
  padding: 30px;
  color: var(--text-dim);
  font-size: 0.85rem;
}

/* Toast notification */
.toast{
  position: fixed;
  bottom: 24px;
  right: 24px;
  background: rgba(52,211,153,0.95);
  color: #0b0d11;
  padding: 10px 20px;
  border-radius: 8px;
  font-family: var(--font);
  font-size: 0.82rem;
  font-weight: 600;
  z-index: 9999;
  opacity: 0;
  transform: translateY(10px);
  transition: all 0.3s;
  pointer-events: none;
}
.toast.show{ opacity: 1; transform: translateY(0); }

/* ── Upload / Transcription Modal ────────────────────────── */
.sidebar-upload{
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}
.btn-upload{
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: var(--radius-sm);
  border: 1px dashed rgba(108,156,255,0.4);
  background: rgba(108,156,255,0.06);
  color: var(--accent-0);
  font-family: var(--font);
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-upload:hover{
  background: rgba(108,156,255,0.12);
  border-color: var(--accent-0);
  transform: translateY(-1px);
}
.upload-overlay{
  position: fixed;
  inset: 0;
  z-index: 9000;
  background: rgba(0,0,0,0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.upload-modal{
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  width: 100%;
  max-width: 560px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 24px 80px rgba(0,0,0,0.6);
}
.upload-modal-header{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--border);
}
.upload-modal-header h3{
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-bright);
}
.upload-close{
  background: none;
  border: none;
  color: var(--text-dim);
  font-size: 1.5rem;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: all 0.15s;
}
.upload-close:hover{ background: rgba(255,255,255,0.06); color: var(--text); }
.upload-modal-body{ padding: 20px 24px; }
.upload-dropzone{
  border: 2px dashed var(--border);
  border-radius: var(--radius-sm);
  padding: 32px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 16px;
}
.upload-dropzone:hover, .upload-dropzone.drag-over{
  border-color: var(--accent-0);
  background: rgba(108,156,255,0.04);
}
.upload-options{ margin-bottom: 16px; }
.upload-checkbox-row{
  margin-top: 12px;
  font-size: 0.8rem;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 6px;
}
.upload-checkbox-row input{ accent-color: var(--accent-0); }
.upload-progress{
  padding: 32px 24px;
  text-align: center;
}
.upload-progress-bar-outer{
  width: 100%;
  height: 8px;
  border-radius: 4px;
  background: rgba(255,255,255,0.08);
  margin-bottom: 12px;
  overflow: hidden;
}
.upload-progress-bar-inner{
  height: 100%;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--accent-0), var(--accent-1));
  transition: width 0.4s ease;
}
.upload-progress-pct{
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-bright);
  margin-bottom: 8px;
}
.upload-progress-msg{
  font-size: 0.82rem;
  color: var(--text-dim);
  margin-bottom: 16px;
}
.upload-progress-steps{
  font-size: 0.72rem;
  color: var(--text-dim);
  text-align: left;
  max-height: 120px;
  overflow-y: auto;
  background: rgba(255,255,255,0.02);
  border-radius: 6px;
  padding: 8px 12px;
}
.upload-progress-steps div{
  padding: 2px 0;
  border-bottom: 1px solid rgba(255,255,255,0.03);
}
.upload-done, .upload-error{
  padding: 40px 24px;
  text-align: center;
}

/* ── Pinned Post Panel ───────────────────────────────────── */
.pinned-post-panel{
  position: fixed;
  top: 80px;
  right: 20px;
  width: 340px;
  max-height: calc(100vh - 120px);
  background: var(--bg);
  border: 1px solid var(--accent-0);
  border-radius: var(--radius);
  box-shadow: 0 12px 48px rgba(0,0,0,0.5), 0 0 0 1px rgba(108,156,255,0.2);
  z-index: 8000;
  display: none;
  flex-direction: column;
  overflow: hidden;
}
.pinned-post-panel.visible{ display: flex; }
.pinned-post-header{
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  background: rgba(108,156,255,0.05);
  flex-shrink: 0;
}
.pinned-post-header span{
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  flex: 1;
}
.pinned-post-close{
  background: none;
  border: none;
  color: var(--text-dim);
  font-size: 1.2rem;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: all 0.15s;
}
.pinned-post-close:hover{ background: rgba(255,255,255,0.06); color: var(--text); }
.pinned-post-body{
  padding: 16px;
  flex: 1;
  overflow-y: auto;
}
.pinned-post-text{
  font-size: 0.88rem;
  line-height: 1.75;
  color: var(--text);
  outline: none;
  min-height: 60px;
  white-space: pre-wrap;
  word-wrap: break-word;
}
.pinned-post-text:focus{
  background: rgba(255,255,255,0.03);
  border-radius: 6px;
  padding: 8px;
  margin: -8px;
}
.pinned-post-actions{
  padding: 10px 16px;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
@media(max-width:900px){
  .pinned-post-panel{
    top: auto; bottom: 0; left: 0; right: 0;
    width: 100%; max-height: 45vh;
    border-radius: var(--radius) var(--radius) 0 0;
  }
}
</style>
</head>
<body>

<button class="menu-toggle" id="menuToggle" aria-label="Menu">
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
</button>

<div class="app-layout">
  <!-- Sidebar -->
  <aside class="sidebar" id="sidebar">
    <div class="sidebar-title">Transkrypcje</div>
    <div class="transcript-list" id="transcriptList">
      <!-- Załadowane dynamicznie -->
    </div>
    <div class="sidebar-upload" id="sidebarUpload">
      <button class="btn-upload" id="btnUploadShow" onclick="toggleUploadPanel()">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
        Nowa transkrypcja
      </button>
      <a href="/live" class="btn-upload" style="margin-top:8px;text-decoration:none;border-color:rgba(167,139,250,0.4);background:rgba(167,139,250,0.06);color:var(--accent-1)">
        🎙️ Transkrypcja na żywo
      </a>
      <button class="btn-upload" style="margin-top:8px;border-color:rgba(248,113,113,0.3);background:rgba(248,113,113,0.06);color:#f87171" onclick="deleteAllTranscripts()">
        🗑️ Wyczyść wszystkie
      </button>
    </div>
  </aside>

  <!-- Main Content -->
  <main class="main-content" id="mainContent">
    <div class="container">
      <header>
        <h1 id="headerTitle">%%HEADER_TITLE%%</h1>
        <p>Interaktywny Odtwarzacz Transkrypcji</p>
      </header>

      <!-- Audio Player -->
      <div class="player-card">
        <div class="player-row">
          <button class="btn-play" id="playBtn" aria-label="Play / Pause">
            <svg id="iconPlay" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
            <svg id="iconPause" viewBox="0 0 24 24" style="display:none"><path d="M6 4h4v16H6zm8 0h4v16h-4z"/></svg>
          </button>
          <div class="progress-wrap">
            <div class="progress-bar-outer" id="progressOuter">
              <div class="progress-bar-inner" id="progressInner"></div>
            </div>
            <div class="time-row">
              <span id="timeCur">0:00</span>
              <span id="timeDur">0:00</span>
            </div>
          </div>
          <button class="speed-btn" id="speedBtn" title="Prędkość odtwarzania">1×</button>
        </div>
      </div>

      <!-- Speaker Visibility Panel -->
      <div class="speaker-panel" id="speakerPanel">
        <button class="speaker-panel-toggle" id="speakerPanelToggle" onclick="toggleSpeakerPanel()">
          👁 Mówcy <span class="speaker-panel-arrow" id="speakerPanelArrow">▸</span>
        </button>
        <div class="speaker-panel-body" id="speakerPanelBody" style="display:none">
          <div id="speakerCheckboxes"></div>
        </div>
      </div>

      <!-- Transcript -->
      <div id="transcript"></div>

      <div class="kbd-hint">
        <span class="kbd">Spacja</span> play / pause &nbsp;&middot;&nbsp;
        <span class="kbd">←</span><span class="kbd">→</span> przewiń ±5 s
      </div>

      <!-- Posts Section -->
      <div class="posts-section" id="postsSection">
        <div class="posts-header">
          <h2>📝 Posty na X</h2>
          <button class="btn-generate" id="btnShowConfig" onclick="togglePostsConfig()">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
            Generuj posty
          </button>
        </div>

        <div class="posts-config" id="postsConfig">
          <div class="config-grid">
            <div class="config-field">
              <label>Mówca z transkrypcji</label>
              <select id="cfgSpeakerSelect">
                <option value="">— Wszyscy mówcy —</option>
              </select>
            </div>
            <div class="config-field">
              <label>Osoba</label>
              <input type="text" id="cfgOsoba" value="Dorota Spyrka" list="dlOsoba">
              <datalist id="dlOsoba"></datalist>
            </div>
            <div class="config-field">
              <label>Username (@)</label>
              <input type="text" id="cfgUsername" value="@dorota_spyrka" list="dlUsername">
              <datalist id="dlUsername"></datalist>
            </div>
            <div class="config-field">
              <label>Program / Kanał</label>
              <input type="text" id="cfgProgram" value="@OficjalneZero" list="dlProgram">
              <datalist id="dlProgram"></datalist>
            </div>
            <div class="config-field">
              <label>Liczba postów</label>
              <input type="number" id="cfgNumPosts" value="5" min="1" max="15">
            </div>
          </div>
          <div class="config-actions">
            <button class="post-btn" onclick="togglePostsConfig()">Anuluj</button>
            <button class="btn-generate" id="btnGenerate" onclick="generatePosts()">Generuj ⚡</button>
          </div>
        </div>

        <div class="posts-loading" id="postsLoading">
          <div class="spinner"></div>
          <p>Generowanie postów przez AI...</p>
          <p style="font-size:0.75rem;margin-top:4px;">To może potrwać do minuty</p>
        </div>

        <div class="posts-empty" id="postsEmpty">Kliknij "Generuj posty" aby wygenerować posty z aktualnej transkrypcji.</div>
        <div id="postsContainer"></div>

        <div class="posts-bulk-actions" id="postsBulkActions" style="display:none">
          <button class="btn-generate" onclick="copyAcceptedPosts()" style="background:linear-gradient(135deg, var(--accent-2), #059669);">
            📋 Kopiuj zaakceptowane
          </button>
          <button class="post-btn" onclick="copyAllPosts()">📋 Kopiuj wszystkie</button>
          <button class="post-btn" onclick="savePostsToFile()">💾 Zapisz do pliku</button>
          <button class="post-btn reject" onclick="clearPosts()">🗑️ Wyczyść</button>
        </div>
      </div>
    </div>
  </main>
</div>

<!-- Upload / Transcription Modal -->
<div class="upload-overlay" id="uploadOverlay" style="display:none">
  <div class="upload-modal">
    <div class="upload-modal-header">
      <h3>🎙️ Nowa transkrypcja</h3>
      <button class="upload-close" onclick="closeUploadPanel()">&times;</button>
    </div>
    <div class="upload-modal-body" id="uploadForm">
      <div class="upload-dropzone" id="uploadDropzone">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="color:var(--accent-0);margin-bottom:12px">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
        <p style="color:var(--text-bright);font-weight:600;margin-bottom:4px">Przeciągnij plik audio/wideo tutaj</p>
        <p style="color:var(--text-dim);font-size:0.78rem">lub kliknij aby wybrać plik</p>
        <p id="uploadFileName" style="color:var(--accent-0);font-size:0.8rem;margin-top:8px;font-weight:600;display:none"></p>
        <input type="file" id="uploadFileInput" accept="audio/*,video/*,.mp3,.wav,.m4a,.ogg,.mp4,.mkv,.avi,.mov,.webm,.flac" style="display:none">
      </div>
      <div class="upload-options">
        <div class="config-grid">
          <div class="config-field">
            <label>Model Whisper</label>
            <select id="uploadModel">
              <option value="tiny">tiny (szybki, mniej dokładny)</option>
              <option value="base">base</option>
              <option value="small">small</option>
              <option value="medium" selected>medium (zalecany)</option>
              <option value="large-v3">large-v3 (najdokładniejszy)</option>
            </select>
          </div>
          <div class="config-field">
            <label>Urządzenie</label>
            <select id="uploadDevice">
              <option value="cuda">GPU (CUDA)</option>
              <option value="cpu">CPU</option>
            </select>
          </div>
          <div class="config-field">
            <label>Min mówców</label>
            <input type="number" id="uploadMinSpeakers" placeholder="auto" min="1" max="20">
          </div>
          <div class="config-field">
            <label>Max mówców</label>
            <input type="number" id="uploadMaxSpeakers" placeholder="auto" min="1" max="20">
          </div>
        </div>
        <div class="upload-checkbox-row">
          <label><input type="checkbox" id="uploadOllama" checked> Popraw tekst za pomocą Ollama</label>
        </div>
      </div>
      <div class="config-actions">
        <button class="post-btn" onclick="closeUploadPanel()">Anuluj</button>
        <button class="btn-generate" id="btnStartTranscribe" onclick="startUploadTranscription()" disabled>
          🚀 Rozpocznij transkrypcję
        </button>
      </div>
    </div>
    <div class="upload-progress" id="uploadProgress" style="display:none">
      <div class="upload-progress-bar-outer">
        <div class="upload-progress-bar-inner" id="uploadProgressBar" style="width:0%"></div>
      </div>
      <div class="upload-progress-pct" id="uploadProgressPct">0%</div>
      <div class="upload-progress-msg" id="uploadProgressMsg">Przygotowywanie...</div>
      <div class="upload-progress-steps" id="uploadProgressSteps"></div>
    </div>
    <div class="upload-done" id="uploadDone" style="display:none">
      <div style="font-size:2rem;margin-bottom:12px">✅</div>
      <p style="font-weight:600;color:var(--text-bright);margin-bottom:8px">Transkrypcja gotowa!</p>
      <button class="btn-generate" onclick="loadNewTranscription()">Otwórz transkrypcję</button>
    </div>
    <div class="upload-error" id="uploadError" style="display:none">
      <div style="font-size:2rem;margin-bottom:12px">❌</div>
      <p style="font-weight:600;color:#f87171;margin-bottom:8px">Wystąpił błąd</p>
      <p class="upload-error-msg" id="uploadErrorMsg"></p>
      <button class="post-btn" onclick="resetUploadPanel()" style="margin-top:12px">Spróbuj ponownie</button>
    </div>
  </div>
</div>

<!-- Pinned Post Panel -->
<div class="pinned-post-panel" id="pinnedPostPanel">
  <div class="pinned-post-header">
    <span id="pinnedPostLabel">📌 Post #1</span>
    <button class="pinned-post-close" onclick="unpinPost()" title="Zamknij">&times;</button>
  </div>
  <div class="pinned-post-body">
    <div class="pinned-post-text" id="pinnedPostText" contenteditable="true" spellcheck="true"></div>
  </div>
  <div class="pinned-post-actions">
    <button class="post-btn copy" onclick="copyPinnedPost()">📋 Kopiuj</button>
    <button class="post-btn accept" onclick="acceptPinnedPost()">✓ Akceptuj</button>
  </div>
</div>

<audio id="audio" preload="auto"></audio>

<script>
// ── Dane wstrzyknięte na start przez serwer Pythona ───────────────────
const INITIAL_TRANSCRIPT = %%TRANSCRIPT_JSON%%;
const INITIAL_AUDIO_URL  = "%%AUDIO_URL%%";
const INITIAL_NAME       = "%%CURRENT_TRANSCRIPT_NAME%%";

let currentActiveName = INITIAL_NAME;
let allWords = [];          // Płaska lista {el, start, end}
const speakerEls = new Map(); // speakerId -> [nameEls...]

// ── Paleta akcentów ──────────────────────────────────────────────────
const ACCENTS = [
  '#6c9cff','#a78bfa','#34d399','#f472b6',
  '#fbbf24','#fb923c','#38bdf8','#c084fc',
];
function accentFor(idx){ return ACCENTS[idx % ACCENTS.length]; }

// ── Zapisywanie nazw mówców w przeglądarce (per-transkrypcja) ──────────
const GLOBAL_STORAGE_KEY = 'transcript_speaker_names';
function getPerTranscriptKey(){ return 'speaker_names_' + currentActiveName.replace(/\.json$/,''); }
function loadNames(){
  try{
    const perKey = getPerTranscriptKey();
    const perData = localStorage.getItem(perKey);
    if(perData) return JSON.parse(perData);
    // Fallback migracyjny z globalnego klucza
    const globalData = localStorage.getItem(GLOBAL_STORAGE_KEY);
    return globalData ? JSON.parse(globalData) : {};
  } catch{ return {}; }
}
function saveName(orig, custom){
  const m = loadNames(); m[orig] = custom;
  localStorage.setItem(getPerTranscriptKey(), JSON.stringify(m));
}
let speakerNames = loadNames();

// ── Ukrywanie mówców (per-transkrypcja) ───────────────────────────────
function getHiddenSpeakersKey(){ return 'hidden_speakers_' + currentActiveName.replace(/\.json$/,''); }
function loadHiddenSpeakers(){
  try{ return JSON.parse(localStorage.getItem(getHiddenSpeakersKey())) || []; }
  catch{ return []; }
}
function saveHiddenSpeakers(arr){
  localStorage.setItem(getHiddenSpeakersKey(), JSON.stringify(arr));
}

// ── Pamięć historii pól konfiguracji postów ───────────────────────────
const HISTORY_KEY = 'posts_config_history';
function loadConfigHistory(){
  try{ return JSON.parse(localStorage.getItem(HISTORY_KEY)) || {osoba:[],username:[],program:[]}; }
  catch{ return {osoba:[],username:[],program:[]}; }
}
function saveConfigHistory(osoba, username, program){
  const h = loadConfigHistory();
  function addUnique(arr, val){ if(!val) return arr; arr = arr.filter(v=>v!==val); arr.unshift(val); return arr.slice(0,10); }
  h.osoba = addUnique(h.osoba, osoba);
  h.username = addUnique(h.username, username);
  h.program = addUnique(h.program, program);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(h));
}
function populateDataLists(){
  const h = loadConfigHistory();
  function fill(dlId, arr){ const dl=document.getElementById(dlId); dl.innerHTML=''; arr.forEach(v=>{ const o=document.createElement('option'); o.value=v; dl.appendChild(o); }); }
  fill('dlOsoba', h.osoba);
  fill('dlUsername', h.username);
  fill('dlProgram', h.program);
}

// ── Dane bieżącej transkrypcji (do filtrowania mówców) ────────────────
let currentTranscriptData = INITIAL_TRANSCRIPT;

// ── Formatowanie czasu ────────────────────────────────────────────────
function fmt(s){
  if(s==null||isNaN(s)) return '0:00';
  const m=Math.floor(s/60), sec=Math.floor(s%60);
  return m+':'+(sec<10?'0':'')+sec;
}

// ── Grupowanie segmentów ──────────────────────────────────────────────
function groupBySpeaker(segs){
  const groups = [];
  let cur = null;
  for(const seg of segs){
    const spk = seg.speaker || 'UNKNOWN';
    if(!cur || cur.speaker !== spk){
      cur = {speaker:spk, segments:[seg]};
      groups.push(cur);
    } else {
      cur.segments.push(seg);
    }
  }
  return groups;
}

// ── Generowanie struktury DOM transkrypcji (zoptymalizowane DocumentFragment) ──
function renderTranscript(transcriptData) {
  const segments = transcriptData.segments || [];
  allWords = [];
  speakerEls.clear();
  currentTranscriptData = transcriptData;

  const container = document.getElementById('transcript');
  container.innerHTML = '';

  if (segments.length === 0) {
    showEmptyState();
    return;
  }

  // Załaduj nazwy i ukrytych mówców per-transkrypcja
  speakerNames = loadNames();
  const hiddenSpeakers = loadHiddenSpeakers();

  const groups = groupBySpeaker(segments);
  const speakerIndexMap = {};
  let nextSpeakerIdx = 0;

  const frag = document.createDocumentFragment();

  groups.forEach(g => {
    const spk = g.speaker;
    if(!(spk in speakerIndexMap)) speakerIndexMap[spk] = nextSpeakerIdx++;
    const idx = speakerIndexMap[spk];
    const accent = accentFor(idx);

    const section = document.createElement('div');
    section.className = 'speaker-section';
    section.dataset.speaker = spk;
    if(hiddenSpeakers.includes(spk)) section.classList.add('hidden-speaker');

    // Nagłówek mówcy
    const hdr = document.createElement('div');
    hdr.className = 'speaker-header';

    const dot = document.createElement('span');
    dot.className = 'speaker-dot';
    dot.style.color = accent;
    dot.style.background = accent;

    const name = document.createElement('span');
    name.className = 'speaker-name';
    name.style.color = accent;
    name.contentEditable = 'true';
    name.spellcheck = false;
    name.textContent = speakerNames[spk] || spk;
    name.dataset.speaker = spk;
    
    if(!speakerEls.has(spk)) speakerEls.set(spk, []);
    speakerEls.get(spk).push(name);

    name.addEventListener('blur', () => {
      const v = name.textContent.trim() || spk;
      saveName(spk, v);
      for(const el of speakerEls.get(spk)) el.textContent = v;
      populateSpeakerSelect();
      buildSpeakerCheckboxes();
    });
    name.addEventListener('keydown', e => {
      if(e.key === 'Enter'){ e.preventDefault(); name.blur(); }
    });

    const allSegs = g.segments;
    const tStart = allSegs[0].start;
    const tEnd   = allSegs[allSegs.length-1].end;
    const timeEl = document.createElement('span');
    timeEl.className = 'speaker-time';
    timeEl.textContent = fmt(tStart) + ' – ' + fmt(tEnd);

    hdr.append(dot, name, timeEl);

    // Słowa — budowane w DocumentFragment
    const wordsDiv = document.createElement('div');
    wordsDiv.className = 'words';
    const wordsFrag = document.createDocumentFragment();

    allSegs.forEach(seg => {
      const words = seg.words || [];
      if(words.length === 0){
        const span = document.createElement('span');
        span.className = 'w';
        span.textContent = seg.text;
        span.dataset.start = seg.start;
        span.dataset.end   = seg.end;
        span.dataset.speaker = spk;
        span.addEventListener('click', () => seekTo(seg.start));
        wordsFrag.appendChild(span);
        wordsFrag.appendChild(document.createTextNode(' '));
        allWords.push({el:span, start:seg.start, end:seg.end, speaker:spk});
      } else {
        words.forEach(wd => {
          const span = document.createElement('span');
          span.className = 'w';
          span.textContent = wd.word;
          const ws = wd.start != null ? wd.start : seg.start;
          const we = wd.end   != null ? wd.end   : seg.end;
          span.dataset.start = ws;
          span.dataset.end   = we;
          span.dataset.speaker = spk;
          span.addEventListener('click', () => seekTo(ws));
          wordsFrag.appendChild(span);
          wordsFrag.appendChild(document.createTextNode(' '));
          allWords.push({el:span, start:ws, end:we, speaker:spk});
        });
      }
    });

    wordsDiv.appendChild(wordsFrag);
    section.append(hdr, wordsDiv);
    frag.appendChild(section);
  });

  container.appendChild(frag);

  // Wypełnij select mówców w panelu postów
  populateSpeakerSelect();
  // Wypełnij datalisty historii
  populateDataLists();
  // Zbuduj panel checkboxów mówców
  buildSpeakerCheckboxes();
}

// ── Wypełnienie select mówców ─────────────────────────────────────────
function populateSpeakerSelect(){
  const select = document.getElementById('cfgSpeakerSelect');
  const currentVal = select.value;
  select.innerHTML = '<option value="">— Wszyscy mówcy —</option>';
  const seenSpeakers = new Set();
  const segments = (currentTranscriptData && currentTranscriptData.segments) || [];
  segments.forEach(seg => {
    const spk = seg.speaker || 'UNKNOWN';
    if(!seenSpeakers.has(spk)){
      seenSpeakers.add(spk);
      const opt = document.createElement('option');
      opt.value = spk;
      opt.textContent = speakerNames[spk] || spk;
      select.appendChild(opt);
    }
  });
  // Przywróć poprzednią wartość jeśli nadal istnieje
  if(currentVal && seenSpeakers.has(currentVal)) select.value = currentVal;
}

// ── Panel widoczności mówców ──────────────────────────────────────────
function toggleSpeakerPanel(){
  const body = document.getElementById('speakerPanelBody');
  const arrow = document.getElementById('speakerPanelArrow');
  const isOpen = body.style.display !== 'none';
  body.style.display = isOpen ? 'none' : 'block';
  arrow.classList.toggle('open', !isOpen);
}

function buildSpeakerCheckboxes(){
  const container = document.getElementById('speakerCheckboxes');
  container.innerHTML = '';
  const hiddenSpeakers = loadHiddenSpeakers();
  const segments = (currentTranscriptData && currentTranscriptData.segments) || [];
  const seenSpeakers = [];
  let speakerIdx = 0;

  segments.forEach(seg => {
    const spk = seg.speaker || 'UNKNOWN';
    if(!seenSpeakers.find(s => s.id === spk)){
      seenSpeakers.push({id: spk, idx: speakerIdx++});
    }
  });

  seenSpeakers.forEach(({id: spk, idx}) => {
    const accent = accentFor(idx);
    const item = document.createElement('div');
    item.className = 'speaker-checkbox-item';

    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.id = 'spk_cb_' + spk;
    cb.checked = !hiddenSpeakers.includes(spk);
    cb.addEventListener('change', () => {
      const hidden = loadHiddenSpeakers();
      let newHidden;
      if(cb.checked){
        newHidden = hidden.filter(s => s !== spk);
      } else {
        newHidden = [...hidden, spk];
      }
      saveHiddenSpeakers(newHidden);
      document.querySelectorAll(`.speaker-section[data-speaker="${spk}"]`).forEach(sec => {
        if(cb.checked) sec.classList.remove('hidden-speaker');
        else sec.classList.add('hidden-speaker');
      });
    });

    const dot = document.createElement('span');
    dot.className = 'speaker-checkbox-dot';
    dot.style.background = accent;

    const label = document.createElement('label');
    label.htmlFor = 'spk_cb_' + spk;
    label.textContent = speakerNames[spk] || spk;

    item.append(cb, dot, label);
    container.appendChild(item);
  });
}

function showEmptyState() {
  currentActiveName = "";
  document.getElementById('headerTitle').textContent = "Brak transkrypcji";
  document.title = "Transkrypcja — Brak";
  
  const container = document.getElementById('transcript');
  container.innerHTML = `
    <div style="text-align: center; padding: 60px 20px; color: var(--text-dim);">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom: 16px; opacity: 0.5; color: var(--text-dim);">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
        <polyline points="14 2 14 8 20 8"></polyline>
        <line x1="9" y1="15" x2="15" y2="15"></line>
        <line x1="9" y1="11" x2="15" y2="11"></line>
        <line x1="9" y1="19" x2="11" y2="19"></line>
      </svg>
      <p style="font-size: 0.95rem; margin-bottom: 8px; color: var(--text-bright);">Katalog transkrypcji jest pusty</p>
      <p style="font-size: 0.8rem; opacity: 0.7;">Uruchom polecenie <code>python run.py -i plik.mp3</code>, aby dodać nową transkrypcję.</p>
    </div>
  `;
  
  audio.src = "";
  audio.load();
  timeDur.textContent = "0:00";
  progressIn.style.width = "0%";
  timeCur.textContent = "0:00";
}

// ── Obsługa Audio ────────────────────────────────────────────────────
const audio      = document.getElementById('audio');
const playBtn    = document.getElementById('playBtn');
const iconPlay   = document.getElementById('iconPlay');
const iconPause  = document.getElementById('iconPause');
const progressIn = document.getElementById('progressInner');
const progressOut= document.getElementById('progressOuter');
const timeCur    = document.getElementById('timeCur');
const timeDur    = document.getElementById('timeDur');
const speedBtn   = document.getElementById('speedBtn');

audio.src = INITIAL_AUDIO_URL;

function togglePlay(){
  if(!audio.src || audio.src.endsWith('/audio/')) return;
  if(audio.paused) audio.play(); else audio.pause();
}
function seekTo(t){
  if(!audio.src || audio.src.endsWith('/audio/')) return;
  audio.currentTime = t;
  if(audio.paused) audio.play();
}

playBtn.addEventListener('click', togglePlay);

audio.addEventListener('play',  () => { iconPlay.style.display='none';  iconPause.style.display=''; });
audio.addEventListener('pause', () => { iconPlay.style.display='';      iconPause.style.display='none'; });
audio.addEventListener('loadedmetadata', () => { timeDur.textContent = fmt(audio.duration); });

progressOut.addEventListener('click', e => {
  if(!audio.src || audio.src.endsWith('/audio/')) return;
  const rect = progressOut.getBoundingClientRect();
  const pct  = (e.clientX - rect.left) / rect.width;
  audio.currentTime = pct * audio.duration;
});

const speeds = [1, 1.25, 1.5, 1.75, 2, 0.5, 0.75];
let speedIdx = 0;
speedBtn.addEventListener('click', () => {
  speedIdx = (speedIdx + 1) % speeds.length;
  audio.playbackRate = speeds[speedIdx];
  speedBtn.textContent = speeds[speedIdx] + '×';
});

// ── Animacja karaoke (zoptymalizowana: binarySearch + 10fps + smart scroll) ──
let prevActive = null;
let hlTimer = null;

function binarySearchWord(t){
  let lo = 0, hi = allWords.length - 1;
  while(lo <= hi){
    const mid = (lo + hi) >>> 1;
    const w = allWords[mid];
    if(t >= w.start && t < w.end) return w;
    if(t < w.start) hi = mid - 1;
    else lo = mid + 1;
  }
  return null;
}

function isInViewport(el){
  const r = el.getBoundingClientRect();
  return r.top >= 0 && r.bottom <= window.innerHeight;
}

function highlightLoop(){
  const t = audio.currentTime;
  if(audio.duration){
    progressIn.style.width = ((t / audio.duration) * 100) + '%';
  }
  timeCur.textContent = fmt(t);

  const found = binarySearchWord(t);

  if(found !== prevActive){
    if(prevActive) prevActive.el.classList.remove('active');
    if(found){
      found.el.classList.add('active');
      if(!isInViewport(found.el)){
        found.el.scrollIntoView({behavior:'smooth', block:'nearest'});
      }
    }
    prevActive = found;
  }

  if(!audio.paused){
    hlTimer = setTimeout(highlightLoop, 100); // ~10fps
  }
}

// Uruchamiaj pętlę przy play, zatrzymuj przy pause
audio.addEventListener('play', () => { if(hlTimer) clearTimeout(hlTimer); highlightLoop(); });
audio.addEventListener('pause', () => { if(hlTimer){ clearTimeout(hlTimer); hlTimer = null; } });
audio.addEventListener('seeked', () => { highlightLoop(); });
// Uruchom raz na start żeby ustawić stan
highlightLoop();

// ── Skróty klawiszowe ────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  if(e.target.isContentEditable) return;
  switch(e.code){
    case 'Space':
      e.preventDefault(); togglePlay(); break;
    case 'ArrowLeft':
      e.preventDefault(); if(audio.src) audio.currentTime = Math.max(0, audio.currentTime - 5); break;
    case 'ArrowRight':
      e.preventDefault(); if(audio.src) audio.currentTime = Math.min(audio.duration||0, audio.currentTime + 5); break;
  }
});

// ── Dynamiczne Ładowanie Listy i Transkrypcji ─────────────────────────
async function loadTranscript(filename, audioFilename, title) {
  try {
    const response = await fetch(`/api/get?name=${encodeURIComponent(filename)}`);
    if (!response.ok) throw new Error("Nie udało się załadować pliku transkrypcji");
    const data = await response.json();
    
    document.querySelectorAll('.transcript-item').forEach(el => {
      if (el.dataset.name === filename) {
        el.classList.add('active');
      } else {
        el.classList.remove('active');
      }
    });
    
    currentActiveName = filename;
    renderTranscript(data);
    
    document.getElementById('headerTitle').textContent = title;
    document.title = `Transkrypcja — ${title}`;
    
    if (audioFilename) {
      audio.src = `/audio/${encodeURIComponent(audioFilename)}`;
    } else {
      audio.src = "";
    }
    audio.load();
    timeDur.textContent = "0:00";
    progressIn.style.width = "0%";
    timeCur.textContent = "0:00";

    // Wyczyść posty przy zmianie transkrypcji
    generatedPosts = [];
    renderPosts();
    clearAllHighlights();
    
  } catch (err) {
    console.error(err);
    alert("Błąd: " + err.message);
  }
}

async function deleteTranscript(filename, title, e) {
  e.stopPropagation(); // Zablokowanie wybrania transkrypcji
  
  const confirmed = confirm(`Czy na pewno chcesz bezpowrotnie usunąć transkrypcję "${title}" oraz wszystkie powiązane z nią pliki (tekstowe, markdown i audio MP3)?`);
  if (!confirmed) return;
  
  try {
    const response = await fetch(`/api/delete?name=${encodeURIComponent(filename)}`, { method: 'POST' });
    if (!response.ok) throw new Error("Błąd podczas usuwania plików z serwera");
    
    // Odświeżenie listy
    await loadTranscriptList();
    
    // Jeśli usunęliśmy aktualnie aktywną transkrypcję
    if (filename === currentActiveName) {
      const items = document.querySelectorAll('.transcript-item');
      if (items.length > 0) {
        // Kliknięcie na pierwszy dostępny element
        items[0].click();
      } else {
        showEmptyState();
      }
    }
  } catch (err) {
    console.error(err);
    alert("Błąd: " + err.message);
  }
}

async function loadTranscriptList() {
  try {
    const response = await fetch('/api/list');
    if (!response.ok) throw new Error("Błąd ładowania listy");
    const list = await response.json();
    
    const listContainer = document.getElementById('transcriptList');
    listContainer.innerHTML = '';
    
    if (list.length === 0) {
      const emptyMsg = document.createElement('div');
      emptyMsg.style.fontSize = '0.75rem';
      emptyMsg.style.color = 'var(--text-dim)';
      emptyMsg.style.padding = '8px';
      emptyMsg.style.textAlign = 'center';
      emptyMsg.textContent = 'Brak plików';
      listContainer.appendChild(emptyMsg);
      return;
    }
    
    list.forEach(item => {
      const el = document.createElement('div');
      el.className = 'transcript-item';
      if (item.name === currentActiveName) {
        el.classList.add('active');
      }
      el.dataset.name = item.name;
      
      const contentEl = document.createElement('div');
      contentEl.className = 'transcript-item-content';
      
      const titleEl = document.createElement('div');
      titleEl.className = 'transcript-item-title';
      titleEl.textContent = item.title;
      
      const metaEl = document.createElement('div');
      metaEl.className = 'transcript-item-meta';
      
      if (item.audio) {
        metaEl.innerHTML = `
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: var(--accent-2)">
            <path d="M9 18V5l12-2v13"></path>
            <circle cx="6" cy="18" r="3"></circle>
            <circle cx="18" cy="16" r="3"></circle>
          </svg> Dźwięk`;
      } else {
        metaEl.innerHTML = `
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: var(--text-dim)">
            <line x1="1" y1="1" x2="23" y2="23"></line>
            <path d="M9 18V5l12-2v13"></path>
            <circle cx="6" cy="18" r="3"></circle>
            <circle cx="18" cy="16" r="3"></circle>
          </svg> Brak audio`;
      }
      
      contentEl.append(titleEl, metaEl);
      
      // Przycisk usuwania
      const delBtn = document.createElement('button');
      delBtn.className = 'btn-delete';
      delBtn.title = "Usuń transkrypcję";
      delBtn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="3 6 5 6 21 6"></polyline>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          <line x1="10" y1="11" x2="10" y2="17"></line>
          <line x1="14" y1="11" x2="14" y2="17"></line>
        </svg>
      `;
      delBtn.addEventListener('click', (e) => deleteTranscript(item.name, item.title, e));
      
      el.append(contentEl, delBtn);
      
      el.addEventListener('click', () => {
        loadTranscript(item.name, item.audio, item.title);
        if (window.innerWidth <= 900) {
          document.getElementById('sidebar').classList.remove('open');
        }
      });
      
      listContainer.appendChild(el);
    });
  } catch (err) {
    console.error("Błąd podczas ładowania listy transkrypcji:", err);
  }
}

// Obsługa menu na komórkach
const menuToggle = document.getElementById('menuToggle');
const sidebar = document.getElementById('sidebar');

menuToggle.addEventListener('click', (e) => {
  e.stopPropagation();
  sidebar.classList.toggle('open');
});

document.addEventListener('click', (e) => {
  if (window.innerWidth <= 900 && sidebar.classList.contains('open') && !sidebar.contains(e.target)) {
    sidebar.classList.remove('open');
  }
});

// Renderowanie startowe
if (INITIAL_TRANSCRIPT && INITIAL_TRANSCRIPT.segments && INITIAL_TRANSCRIPT.segments.length > 0) {
  renderTranscript(INITIAL_TRANSCRIPT);
} else {
  showEmptyState();
  populateDataLists();
}
loadTranscriptList();

// ══════════════════════════════════════════════════════════════════════════════
// POSTS GENERATION (z podświetlaniem źródeł)
// ══════════════════════════════════════════════════════════════════════════════

let generatedPosts = []; // {text, sources:[], status: 'pending'|'accepted'|'rejected'}

function togglePostsConfig() {
  const cfg = document.getElementById('postsConfig');
  cfg.classList.toggle('visible');
}

// ── Usuwanie podświetleń źródeł ───────────────────────────────────────
function clearAllHighlights(){
  document.querySelectorAll('.w').forEach(el => {
    el.classList.remove('hl-0','hl-1','hl-2','hl-3','hl-4','hl-5','hl-6','hl-7','hl-bright');
    delete el.dataset.postIdx;
  });
}

// ── Fuzzy match: szukanie fragmentu źródłowego w transkrypcji ─────────
function fuzzyMatchSource(sourceText, wordsArr){
  if(!sourceText || !wordsArr.length) return [];
  
  // Normalizuj źródło do tablicy słów (lowercase, bez interpunkcji)
  function normalize(s){ return s.toLowerCase().replace(/[^\wąćęłńóśźżĄĆĘŁŃÓŚŹŻ]/g,' ').split(/\s+/).filter(Boolean); }
  
  const srcWords = normalize(sourceText);
  if(srcWords.length < 3) return [];
  
  // Zbuduj tablicę znormalizowanych słów z transkrypcji
  const txWords = wordsArr.map(w => normalize(w.el.textContent)[0] || '');
  
  // Sliding window: szukaj okna w transkrypcji gdzie jest najwięcej słów ze źródła
  const windowSize = Math.min(srcWords.length * 3, txWords.length); // okno szukania
  let bestScore = 0, bestStart = -1, bestEnd = -1;
  
  // Dla każdej możliwej pozycji startowej w transkrypcji
  for(let i = 0; i <= txWords.length - Math.floor(srcWords.length * 0.4); i++){
    // Próbuj dopasować sekwencję srcWords zaczynając od i
    let matched = 0;
    let si = 0;  // indeks w source
    let lastMatchedTi = i;
    const matchedIndices = [];
    
    for(let ti = i; ti < Math.min(i + windowSize, txWords.length) && si < srcWords.length; ti++){
      if(txWords[ti] === srcWords[si]){
        matched++;
        matchedIndices.push(ti);
        lastMatchedTi = ti;
        si++;
      } else if(txWords[ti] === srcWords[si+1] && si+1 < srcWords.length){
        // Skip jedno słowo w source (drobna różnica)
        si++;
        if(txWords[ti] === srcWords[si]){
          matched++;
          matchedIndices.push(ti);
          lastMatchedTi = ti;
          si++;
        }
      }
    }
    
    // Oceń jakość dopasowania
    const coverage = matched / srcWords.length;
    // Chcemy minimum 40% pokrycia i co najmniej 4 trafione słowa
    if(coverage > 0.4 && matched >= 4 && matched > bestScore){
      bestScore = matched;
      bestStart = i;
      bestEnd = lastMatchedTi;
    }
  }
  
  if(bestStart < 0) return [];
  
  // Zwróć ciągły zakres indeksów od bestStart do bestEnd (podświetl cały fragment)
  const result = [];
  for(let i = bestStart; i <= bestEnd; i++){
    result.push(i);
  }
  return result;
}

// ── Podświetlanie źródeł w transkrypcji ──────────────────────────────
function highlightSources(){
  clearAllHighlights();
  generatedPosts.forEach((post, postIdx) => {
    if(!post.hlEnabled) return; // Pominięte jeśli użytkownik wyłączył
    const hlClass = 'hl-' + (postIdx % 8);
    (post.sources || []).forEach(src => {
      const matched = fuzzyMatchSource(src, allWords);
      matched.forEach(idx => {
        allWords[idx].el.classList.add(hlClass);
        allWords[idx].el.dataset.postIdx = postIdx;
      });
    });
  });
}

// ── Czyszczenie tekstu posta z artefaktów ─────────────────────────────
function cleanPostText(text){
  return text
    .replace(/\[ŹRÓDŁO:.*?\]/gis, '')           // Usuń tagi [ŹRÓDŁO:...]
    .replace(/\[BLOK \d+\]:?\s*/gi, '')         // Usuń [BLOK N]:
    .replace(/^-{3,}$/gm, '')                   // Usuń linie z samymi myślnikami
    .replace(/^\*\*Post \d+\*\*\n?/i, '')       // Usuń **Post N**
    .replace(/^\d+\.\s*/, '')                    // Usuń numerację "1. "
    .replace(/\n{3,}/g, '\n')                   // Zbyt wiele pustych linii
    .trim();
}

async function generatePosts() {
  if (!currentActiveName) {
    alert('Najpierw wybierz transkrypcję z listy po lewej stronie.');
    return;
  }

  const osoba = document.getElementById('cfgOsoba').value.trim();
  const username = document.getElementById('cfgUsername').value.trim();
  const program = document.getElementById('cfgProgram').value.trim();
  const numPosts = parseInt(document.getElementById('cfgNumPosts').value) || 5;
  const selectedSpeaker = document.getElementById('cfgSpeakerSelect').value;

  // Hide config, show loading
  document.getElementById('postsConfig').classList.remove('visible');
  document.getElementById('postsLoading').classList.add('visible');
  document.getElementById('postsEmpty').style.display = 'none';
  document.getElementById('postsBulkActions').style.display = 'none';
  document.getElementById('btnShowConfig').disabled = true;

  try {
    // Filtrowanie tekstu wg mówcy
    let transcriptText = '';
    if(selectedSpeaker && currentTranscriptData && currentTranscriptData.segments){
      transcriptText = currentTranscriptData.segments
        .filter(seg => (seg.speaker || 'UNKNOWN') === selectedSpeaker)
        .map(seg => seg.text || (seg.words||[]).map(w=>w.word).join(' '))
        .join(' ');
    }

    const response = await fetch('/api/generate-posts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        transcript_name: currentActiveName,
        osoba, username, program, num_posts: numPosts,
        speaker_filter: selectedSpeaker || '',
        speaker_text: selectedSpeaker ? transcriptText : ''
      })
    });

    if (!response.ok) {
      const err = await response.text();
      throw new Error(err || 'Błąd serwera');
    }

    const data = await response.json();

    // Nowy format: {posts: [{text, sources}, ...]}
    if(data.posts && Array.isArray(data.posts)){
      generatedPosts = data.posts.map(p => ({
        text: cleanPostText(p.text || ''),
        sources: p.sources || [],
        status: 'pending',
        hlEnabled: true
      })).filter(p => p.text.length > 5);
    } else {
      // Fallback — stary format string
      const rawText = data.posts || '';
      const parsed = rawText.split(/\n\n+/).map(p => p.trim()).filter(p => p.length > 10);
      generatedPosts = parsed.map(text => ({
        text: cleanPostText(text),
        sources: [],
        status: 'pending',
        hlEnabled: true
      })).filter(p => p.text.length > 5);
    }

    // Zapisz historię konfiguracji
    saveConfigHistory(osoba, username, program);
    populateDataLists();

    renderPosts();
    highlightSources();
  } catch (err) {
    console.error(err);
    alert('Błąd podczas generowania postów: ' + err.message);
    document.getElementById('postsEmpty').style.display = 'block';
  } finally {
    document.getElementById('postsLoading').classList.remove('visible');
    document.getElementById('btnShowConfig').disabled = false;
  }
}

function renderPosts() {
  const container = document.getElementById('postsContainer');
  const frag = document.createDocumentFragment();
  container.innerHTML = '';

  if (generatedPosts.length === 0) {
    document.getElementById('postsEmpty').style.display = 'block';
    document.getElementById('postsBulkActions').style.display = 'none';
    return;
  }

  document.getElementById('postsEmpty').style.display = 'none';
  document.getElementById('postsBulkActions').style.display = 'flex';

  generatedPosts.forEach((post, idx) => {
    const card = document.createElement('div');
    card.className = `post-card ${post.status}`;
    card.dataset.idx = idx;

    // Hover na post → podświetl źródła
    card.addEventListener('mouseenter', () => {
      if(post.hlEnabled) document.querySelectorAll(`.w[data-post-idx="${idx}"]`).forEach(el => el.classList.add('hl-bright'));
    });
    card.addEventListener('mouseleave', () => {
      document.querySelectorAll('.w.hl-bright').forEach(el => el.classList.remove('hl-bright'));
    });

    // Nagłówek z kółkiem koloru + numer + toggle podświetlenia
    const headerRow = document.createElement('div');
    headerRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:8px;';

    // Kółko z kolorem podświetlenia
    const hlColors = ['rgba(239,68,68,0.7)','rgba(249,115,22,0.7)','rgba(34,197,94,0.7)','rgba(59,130,246,0.7)','rgba(168,85,247,0.7)','rgba(236,72,153,0.7)','rgba(234,179,8,0.7)','rgba(20,184,166,0.7)'];
    const colorDot = document.createElement('span');
    colorDot.style.cssText = 'width:10px;height:10px;border-radius:50%;flex-shrink:0;cursor:pointer;';
    colorDot.style.background = hlColors[idx % 8];
    colorDot.title = 'Kliknij aby przewinąć do źródła w transkrypcji';
    colorDot.addEventListener('click', () => {
      const firstHl = document.querySelector(`.w[data-post-idx="${idx}"]`);
      if(firstHl) firstHl.scrollIntoView({behavior:'smooth', block:'center'});
    });

    const numEl = document.createElement('span');
    numEl.style.cssText = 'font-size:0.7rem;color:var(--text-dim);cursor:pointer;flex:1;';
    numEl.textContent = `Post #${idx+1}`;
    numEl.addEventListener('click', () => {
      const firstHl = document.querySelector(`.w[data-post-idx="${idx}"]`);
      if(firstHl) firstHl.scrollIntoView({behavior:'smooth', block:'center'});
    });

    // Toggle podświetlenia dla tego posta
    const hlToggle = document.createElement('button');
    hlToggle.className = 'post-btn';
    hlToggle.style.cssText = 'font-size:0.65rem;padding:3px 8px;';
    hlToggle.innerHTML = post.hlEnabled ? '🔆 Podśw.' : '○ Podśw.';
    hlToggle.title = 'Włącz/wyłącz podświetlenie źródła w transkrypcji';
    hlToggle.addEventListener('click', () => {
      generatedPosts[idx].hlEnabled = !generatedPosts[idx].hlEnabled;
      hlToggle.innerHTML = generatedPosts[idx].hlEnabled ? '🔆 Podśw.' : '○ Podśw.';
      // Przerysuj podświetlenia
      highlightSources();
    });

    headerRow.append(colorDot, numEl, hlToggle);

    const textDiv = document.createElement('div');
    textDiv.className = 'post-text';
    textDiv.contentEditable = 'true';
    textDiv.spellcheck = true;
    textDiv.textContent = post.text;
    textDiv.addEventListener('blur', () => {
      generatedPosts[idx].text = textDiv.textContent.trim();
    });

    const actions = document.createElement('div');
    actions.className = 'post-actions';

    const btnAccept = document.createElement('button');
    btnAccept.className = `post-btn accept ${post.status === 'accepted' ? 'active' : ''}`;
    btnAccept.innerHTML = '✓ Akceptuj';
    btnAccept.addEventListener('click', () => togglePostStatus(idx, 'accepted'));

    const btnReject = document.createElement('button');
    btnReject.className = `post-btn reject ${post.status === 'rejected' ? 'active' : ''}`;
    btnReject.innerHTML = '✗ Odrzuć';
    btnReject.addEventListener('click', () => togglePostStatus(idx, 'rejected'));

    const btnCopy = document.createElement('button');
    btnCopy.className = 'post-btn copy';
    btnCopy.innerHTML = '📋 Kopiuj';
    btnCopy.addEventListener('click', () => {
      navigator.clipboard.writeText(generatedPosts[idx].text);
      showToast('Skopiowano post!');
    });

    const btnPin = document.createElement('button');
    btnPin.className = 'post-btn';
    btnPin.innerHTML = '📌 Przypnij';
    btnPin.title = 'Przypnij post do panelu bocznego';
    btnPin.addEventListener('click', () => pinPost(idx));

    const btnGood = document.createElement('button');
    btnGood.className = 'post-btn';
    btnGood.innerHTML = '👍';
    btnGood.title = 'Dobry post — zapamiętaj jako wzór';
    btnGood.addEventListener('click', () => sendFeedback(idx, 'good', btnGood));

    const btnBad = document.createElement('button');
    btnBad.className = 'post-btn';
    btnBad.innerHTML = '👎';
    btnBad.title = 'Zły post — zapamiętaj jako anty-wzór';
    btnBad.addEventListener('click', () => sendFeedback(idx, 'bad', btnBad));

    const statusEl = document.createElement('span');
    statusEl.className = 'post-status';
    statusEl.textContent = post.status === 'accepted' ? '✓ Zaakceptowany' : post.status === 'rejected' ? '✗ Odrzucony' : 'Oczekujący';

    actions.append(btnAccept, btnReject, btnCopy, btnPin, btnGood, btnBad, statusEl);
    card.append(headerRow, textDiv, actions);
    frag.appendChild(card);
  });

  container.appendChild(frag);
}

function togglePostStatus(idx, status) {
  if (generatedPosts[idx].status === status) {
    generatedPosts[idx].status = 'pending';
  } else {
    generatedPosts[idx].status = status;
  }
  // Aktualizuj tylko zmieniony element zamiast przebudowywać listę
  const card = document.querySelector(`.post-card[data-idx="${idx}"]`);
  if(card){
    card.className = `post-card ${generatedPosts[idx].status}`;
    const statusEl = card.querySelector('.post-status');
    if(statusEl){
      const s = generatedPosts[idx].status;
      statusEl.textContent = s === 'accepted' ? '✓ Zaakceptowany' : s === 'rejected' ? '✗ Odrzucony' : 'Oczekujący';
    }
    const btnAccept = card.querySelector('.post-btn.accept');
    const btnReject = card.querySelector('.post-btn.reject');
    if(btnAccept) btnAccept.className = `post-btn accept ${generatedPosts[idx].status==='accepted'?'active':''}`;
    if(btnReject) btnReject.className = `post-btn reject ${generatedPosts[idx].status==='rejected'?'active':''}`;
  }
}

function copyAcceptedPosts() {
  const accepted = generatedPosts.filter(p => p.status === 'accepted').map(p => p.text);
  if (accepted.length === 0) {
    alert('Żaden post nie został jeszcze zaakceptowany. Kliknij "✓ Akceptuj" przy wybranych postach.');
    return;
  }
  navigator.clipboard.writeText(accepted.join('\n\n---\n\n'));
  showToast(`Skopiowano ${accepted.length} zaakceptowanych postów!`);
}

function copyAllPosts() {
  const all = generatedPosts.filter(p => p.status !== 'rejected').map(p => p.text);
  if (all.length === 0) return;
  navigator.clipboard.writeText(all.join('\n\n---\n\n'));
  showToast(`Skopiowano ${all.length} postów!`);
}

async function savePostsToFile() {
  const postsToSave = generatedPosts.filter(p => p.status !== 'rejected').map(p => p.text);
  if (postsToSave.length === 0) {
    alert('Brak postów do zapisania.');
    return;
  }
  try {
    const response = await fetch('/api/save-posts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        transcript_name: currentActiveName,
        posts: postsToSave
      })
    });
    if (!response.ok) throw new Error('Błąd zapisu');
    const data = await response.json();
    showToast(`Zapisano ${postsToSave.length} postów do pliku!`);
  } catch (err) {
    alert('Błąd podczas zapisywania: ' + err.message);
  }
}

function clearPosts() {
  if (!confirm('Czy na pewno chcesz usunąć wszystkie wygenerowane posty?')) return;
  generatedPosts = [];
  renderPosts();
  clearAllHighlights();
}

// ── Feedback (uczenie na przykładach) ─────────────────────────────────
async function sendFeedback(idx, rating, btn) {
  const text = generatedPosts[idx].text;
  try {
    await fetch('/api/save-post-feedback', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text, rating})
    });
    btn.style.opacity = '0.3';
    btn.disabled = true;
    showToast(rating === 'good' ? '👍 Zapamiętano jako dobry wzór' : '👎 Zapamiętano jako anty-wzór');
  } catch(e) {
    showToast('Błąd zapisu feedbacku');
  }
}

// ── Usuwanie wszystkich transkrypcji ──────────────────────────────────
async function deleteAllTranscripts() {
  if (!confirm('Czy na pewno chcesz BEZPOWROTNIE usunąć WSZYSTKIE transkrypcje i powiązane pliki audio?')) return;
  if (!confirm('Na pewno? Tej operacji nie można cofnąć.')) return;
  try {
    const resp = await fetch('/api/delete-all', {method: 'POST'});
    if (!resp.ok) throw new Error('Błąd serwera');
    const data = await resp.json();
    showToast(`Usunięto ${data.deleted_count} plików.`);
    await loadTranscriptList();
    showEmptyState();
  } catch(e) {
    alert('Błąd: ' + e.message);
  }
}

// Toast notification
function showToast(msg) {
  let toast = document.getElementById('toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast';
    toast.className = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2500);
}

// ══════════════════════════════════════════════════════════════════════════════
// UPLOAD & TRANSCRIPTION
// ══════════════════════════════════════════════════════════════════════════════

let uploadFile = null;
let currentJobId = null;
let pollInterval = null;
let newTranscriptFile = null;

function toggleUploadPanel(){
  document.getElementById('uploadOverlay').style.display = 'flex';
  resetUploadPanel();
}

function closeUploadPanel(){
  document.getElementById('uploadOverlay').style.display = 'none';
  if(pollInterval){ clearInterval(pollInterval); pollInterval = null; }
}

function resetUploadPanel(){
  document.getElementById('uploadForm').style.display = 'block';
  document.getElementById('uploadProgress').style.display = 'none';
  document.getElementById('uploadDone').style.display = 'none';
  document.getElementById('uploadError').style.display = 'none';
  document.getElementById('uploadFileName').style.display = 'none';
  document.getElementById('btnStartTranscribe').disabled = true;
  document.getElementById('uploadProgressSteps').innerHTML = '';
  uploadFile = null;
  newTranscriptFile = null;
}

// Dropzone
const dropzone = document.getElementById('uploadDropzone');
const fileInput = document.getElementById('uploadFileInput');

dropzone.addEventListener('click', () => fileInput.click());
dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
dropzone.addEventListener('drop', e => {
  e.preventDefault();
  dropzone.classList.remove('drag-over');
  if(e.dataTransfer.files.length > 0) selectFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', () => {
  if(fileInput.files.length > 0) selectFile(fileInput.files[0]);
});

function selectFile(file){
  uploadFile = file;
  const nameEl = document.getElementById('uploadFileName');
  nameEl.textContent = '📁 ' + file.name + ' (' + (file.size / (1024*1024)).toFixed(1) + ' MB)';
  nameEl.style.display = 'block';
  document.getElementById('btnStartTranscribe').disabled = false;
}

async function startUploadTranscription(){
  if(!uploadFile) return;

  // Show progress
  document.getElementById('uploadForm').style.display = 'none';
  document.getElementById('uploadProgress').style.display = 'block';
  document.getElementById('uploadProgressBar').style.width = '0%';
  document.getElementById('uploadProgressPct').textContent = '0%';
  document.getElementById('uploadProgressMsg').textContent = 'Przesyłanie pliku na serwer...';

  const formData = new FormData();
  formData.append('file', uploadFile);
  formData.append('model', document.getElementById('uploadModel').value);
  formData.append('device', document.getElementById('uploadDevice').value);
  formData.append('batch_size', '4');
  formData.append('use_ollama', document.getElementById('uploadOllama').checked ? 'true' : 'false');
  
  const minSp = document.getElementById('uploadMinSpeakers').value;
  const maxSp = document.getElementById('uploadMaxSpeakers').value;
  if(minSp) formData.append('min_speakers', minSp);
  if(maxSp) formData.append('max_speakers', maxSp);

  try {
    const resp = await fetch('/api/upload-transcribe', {
      method: 'POST',
      body: formData
    });
    if(!resp.ok){
      const err = await resp.json();
      throw new Error(err.error || 'Błąd serwera');
    }
    const data = await resp.json();
    currentJobId = data.job_id;

    // Start polling for progress
    document.getElementById('uploadProgressMsg').textContent = 'Transkrypcja uruchomiona...';
    document.getElementById('uploadProgressBar').style.width = '5%';
    document.getElementById('uploadProgressPct').textContent = '5%';
    
    pollInterval = setInterval(pollJobStatus, 1500);
  } catch(err){
    showUploadError(err.message);
  }
}

async function pollJobStatus(){
  if(!currentJobId) return;
  try{
    const resp = await fetch(`/api/job-status?id=${encodeURIComponent(currentJobId)}`);
    if(!resp.ok) return;
    const job = await resp.json();

    const bar = document.getElementById('uploadProgressBar');
    const pct = document.getElementById('uploadProgressPct');
    const msg = document.getElementById('uploadProgressMsg');
    const steps = document.getElementById('uploadProgressSteps');

    bar.style.width = job.progress + '%';
    pct.textContent = job.progress + '%';
    msg.textContent = job.message || '';

    // Add step to log
    if(job.message){
      const last = steps.lastElementChild;
      if(!last || last.textContent !== job.message){
        const div = document.createElement('div');
        div.textContent = job.message;
        steps.appendChild(div);
        steps.scrollTop = steps.scrollHeight;
      }
    }

    if(job.status === 'done'){
      clearInterval(pollInterval); pollInterval = null;
      newTranscriptFile = job.result;
      document.getElementById('uploadProgress').style.display = 'none';
      document.getElementById('uploadDone').style.display = 'block';
    } else if(job.status === 'error'){
      clearInterval(pollInterval); pollInterval = null;
      showUploadError(job.message);
    }
  } catch(e){
    // Ignore network glitches during polling
  }
}

function showUploadError(msg){
  document.getElementById('uploadForm').style.display = 'none';
  document.getElementById('uploadProgress').style.display = 'none';
  document.getElementById('uploadDone').style.display = 'none';
  document.getElementById('uploadError').style.display = 'block';
  document.getElementById('uploadErrorMsg').textContent = msg;
}

async function loadNewTranscription(){
  closeUploadPanel();
  // Reload list and open new transcript
  await loadTranscriptList();
  if(newTranscriptFile){
    const title = newTranscriptFile.replace(/\.json$/, '');
    // Find audio file
    const listResp = await fetch('/api/list');
    const list = await listResp.json();
    const item = list.find(i => i.name === newTranscriptFile);
    const audioFile = item ? item.audio : '';
    await loadTranscript(newTranscriptFile, audioFile, title);
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// PINNED POST (panel boczny do porównywania z transkrypcją)
// ══════════════════════════════════════════════════════════════════════════════

let pinnedPostIdx = null;

function pinPost(idx){
  pinnedPostIdx = idx;
  const panel = document.getElementById('pinnedPostPanel');
  const label = document.getElementById('pinnedPostLabel');
  const textEl = document.getElementById('pinnedPostText');
  
  label.textContent = `📌 Post #${idx+1}`;
  textEl.textContent = generatedPosts[idx].text;
  panel.classList.add('visible');

  // Scroll do źródła w transkrypcji
  const firstHl = document.querySelector(`.w[data-post-idx="${idx}"]`);
  if(firstHl) firstHl.scrollIntoView({behavior:'smooth', block:'center'});

  // Sync edits back
  textEl.onblur = () => {
    if(pinnedPostIdx !== null){
      generatedPosts[pinnedPostIdx].text = textEl.textContent.trim();
      // Update card text too
      const card = document.querySelector(`.post-card[data-idx="${pinnedPostIdx}"] .post-text`);
      if(card) card.textContent = generatedPosts[pinnedPostIdx].text;
    }
  };
}

function unpinPost(){
  const panel = document.getElementById('pinnedPostPanel');
  panel.classList.remove('visible');
  // Sync final text
  if(pinnedPostIdx !== null){
    const textEl = document.getElementById('pinnedPostText');
    generatedPosts[pinnedPostIdx].text = textEl.textContent.trim();
    const card = document.querySelector(`.post-card[data-idx="${pinnedPostIdx}"] .post-text`);
    if(card) card.textContent = generatedPosts[pinnedPostIdx].text;
  }
  pinnedPostIdx = null;
}

function copyPinnedPost(){
  if(pinnedPostIdx === null) return;
  const textEl = document.getElementById('pinnedPostText');
  navigator.clipboard.writeText(textEl.textContent.trim());
  showToast('Skopiowano przypięty post!');
}

function acceptPinnedPost(){
  if(pinnedPostIdx === null) return;
  generatedPosts[pinnedPostIdx].status = 'accepted';
  generatedPosts[pinnedPostIdx].text = document.getElementById('pinnedPostText').textContent.trim();
  renderPosts();
  showToast('Post zaakceptowany!');
}
</script>
</body>
</html>
"""

# ──────────────────────────────────────────────────────────────────────────────
# Server logic
# ──────────────────────────────────────────────────────────────────────────────

# ── Transcription job tracking ────────────────────────────────────────────────
_transcription_jobs = {}  # job_id -> {status, progress, message, result}
_job_lock = threading.Lock()


def _run_transcription_job(job_id, audio_path, transcript_dir, model, device, compute_type, batch_size, min_speakers, max_speakers, use_ollama):
    """Run transcription in a background thread, updating progress."""
    import shutil

    def update(progress, message, status='running'):
        with _job_lock:
            _transcription_jobs[job_id] = {
                'status': status,
                'progress': progress,
                'message': message,
                'result': _transcription_jobs.get(job_id, {}).get('result', None)
            }

    try:
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        
        # Check if we need to convert
        ext = os.path.splitext(audio_path)[1].lower()
        is_video = ext in [".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm", ".wmv", ".mpeg", ".mpg"]
        is_supported_audio = ext in [".mp3", ".wav", ".m4a", ".ogg", ".aac"]
        needs_convert = is_video or not is_supported_audio

        final_audio = audio_path

        if needs_convert:
            update(5, "Konwersja pliku do MP3...")
            converted = os.path.join(transcript_dir, f"{base_name}.mp3")
            if not os.path.exists(converted):
                ffmpeg = shutil.which("ffmpeg")
                if not ffmpeg:
                    update(0, "Błąd: ffmpeg nie jest zainstalowany!", 'error')
                    return
                res = subprocess.run(
                    [ffmpeg, "-y", "-i", audio_path, "-q:a", "0", "-map", "a", converted],
                    capture_output=True, text=True
                )
                if res.returncode != 0:
                    update(0, f"Błąd konwersji ffmpeg: {res.stderr[:200]}", 'error')
                    return
            final_audio = converted
            update(10, "Konwersja zakończona")
        else:
            # Copy audio to transcript dir if not already there
            dest_audio = os.path.join(transcript_dir, os.path.basename(audio_path))
            if os.path.abspath(audio_path) != os.path.abspath(dest_audio):
                shutil.copy2(audio_path, dest_audio)
            final_audio = dest_audio
            update(10, "Plik audio przygotowany")

        # Build transcribe command
        script_dir = os.path.dirname(os.path.abspath(__file__))
        transcribe_script = os.path.join(script_dir, "transcribe.py")
        
        # Find python executable (use venv if available)
        venv_python = os.path.join(script_dir, "venv", "bin", "python3")
        python_exe = venv_python if os.path.exists(venv_python) else sys.executable

        cmd = [
            python_exe, transcribe_script,
            "-i", final_audio,
            "-m", model,
            "--device", device,
            "--compute-type", compute_type,
            "--batch-size", str(batch_size),
        ]
        if min_speakers is not None:
            cmd.extend(["--min-speakers", str(min_speakers)])
        if max_speakers is not None:
            cmd.extend(["--max-speakers", str(max_speakers)])
        if use_ollama:
            cmd.append("--use-ollama")

        update(15, "Uruchamianie transkrypcji WhisperX...")

        # Run transcription and parse output for progress
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        progress_map = {
            "Ładowanie WhisperX": 20,
            "Wczytywanie pliku audio": 25,
            "Krok 1/4": 30,
            "Zwalnianie pamięci": 50,
            "Krok 2/4": 55,
            "Krok 3/4": 65,
            "Krok 4/4": 75,
            "Post-processing": 80,
            "Zapisano pełne dane": 85,
            "Zapisano prosty tekst": 88,
            "Zapisano dokument": 90,
            "integracji z Ollama": 92,
            "ulepszoną wersję": 95,
            "podsumowanie": 97,
            "zakończony pomyślnie": 99,
        }

        while True:
            line = process.stdout.readline()
            if line == '' and process.poll() is not None:
                break
            if line:
                line_stripped = line.strip()
                for keyword, pct in progress_map.items():
                    if keyword in line_stripped:
                        # Clean ANSI codes for message
                        clean = re.sub(r'\033\[[0-9;]*m', '', line_stripped)
                        update(pct, clean)
                        break

        rc = process.poll()
        if rc != 0:
            update(0, f"Transkrypcja zakończyła się błędem (kod: {rc})", 'error')
            return

        # Success
        json_file = f"{base_name}.json"
        json_path = os.path.join(transcript_dir, json_file)
        if os.path.isfile(json_path):
            update(100, "Transkrypcja zakończona pomyślnie!", 'done')
            with _job_lock:
                _transcription_jobs[job_id]['result'] = json_file
        else:
            update(100, "Transkrypcja zakończona, ale plik JSON nie został znaleziony.", 'done')
            with _job_lock:
                _transcription_jobs[job_id]['result'] = None

    except Exception as e:
        update(0, f"Nieoczekiwany błąd: {str(e)}", 'error')


class TranscriptHandler(http.server.BaseHTTPRequestHandler):
    """Serves the interactive transcript page, API, and audio files."""

    transcript_dir: str = ""
    audio_path: str = ""
    transcript_data: dict = {}
    page_title: str = "Transcript"

    def log_message(self, format, *args):
        # Suppress log noise in console
        msg = format % args
        sys.stderr.write(f"\033[90m  {self.address_string()} {msg}\033[0m\n")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._serve_html()
        elif path == "/live":
            self._serve_live_html()
        elif path == "/live/sources":
            self._serve_live_sources()
        elif path == "/live/events":
            self._serve_live_events()
        elif path == "/live/status":
            self._serve_live_status()
        elif path == "/live/preview":
            self._serve_live_preview()
        elif path == "/api/list":
            self._serve_list()
        elif path == "/api/get":
            name = query.get("name", [None])[0]
            self._serve_transcript(name)
        elif path == "/api/job-status":
            job_id = query.get("id", [None])[0]
            self._serve_job_status(job_id)
        elif path.startswith("/audio/"):
            filename = urllib.parse.unquote(path[7:]) # remove "/audio/"
            self._serve_audio(filename)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/delete":
            name = query.get("name", [None])[0]
            self._delete_transcript(name)
        elif path == "/api/delete-all":
            self._delete_all_transcripts()
        elif path == "/api/generate-posts":
            self._generate_posts()
        elif path == "/api/save-posts":
            self._save_posts()
        elif path == "/api/save-post-feedback":
            self._save_post_feedback()
        elif path == "/api/upload-transcribe":
            self._upload_and_transcribe()
        elif path == "/live/start":
            self._live_start()
        elif path == "/live/pause":
            self._live_pause()
        elif path == "/live/resume":
            self._live_resume()
        elif path == "/live/stop":
            self._live_stop()
        elif path == "/live/save":
            self._live_save()
        else:
            self.send_error(404)

    # ── HTML page ─────────────────────────────────────────────────
    def _serve_html(self):
        cls = self.__class__
        audio_filename = os.path.basename(cls.audio_path) if cls.audio_path else ""
        current_json_name = ""
        json_path = find_transcript_json(cls.transcript_dir)
        if json_path:
            current_json_name = os.path.basename(json_path)

        html = HTML_TEMPLATE
        html = html.replace("%%PAGE_TITLE%%", f"Transkrypcja — {cls.page_title}")
        html = html.replace("%%HEADER_TITLE%%", cls.page_title)
        html = html.replace("%%TRANSCRIPT_JSON%%", json.dumps(cls.transcript_data, ensure_ascii=False))
        html = html.replace("%%AUDIO_URL%%", f"/audio/{urllib.parse.quote(audio_filename)}")
        html = html.replace("%%CURRENT_TRANSCRIPT_NAME%%", current_json_name)

        payload = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # ── Live transcription page ───────────────────────────────────
    def _serve_live_html(self):
        from live_page import LIVE_HTML_TEMPLATE
        payload = LIVE_HTML_TEMPLATE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # ── API: List all transcripts ──────────────────────────────────
    def _serve_list(self):
        cls = self.__class__
        files = []
        if os.path.isdir(cls.transcript_dir):
            for f in os.listdir(cls.transcript_dir):
                if f.endswith(".json") and not f.endswith("_state.json"):
                    json_path = os.path.join(cls.transcript_dir, f)
                    audio_path = find_audio_for_json(json_path, cls.transcript_dir)
                    files.append({
                        "name": f,
                        "title": os.path.splitext(f)[0],
                        "audio": os.path.basename(audio_path) if audio_path else ""
                    })
        # Sort alphabetically by title
        files.sort(key=lambda x: x["title"])
        
        payload = json.dumps(files, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # ── API: Get specific transcript JSON ──────────────────────────
    def _serve_transcript(self, name):
        cls = self.__class__
        if not name or "/" in name or "\\" in name:
            self.send_error(400, "Bad Request")
            return
        
        json_path = os.path.join(cls.transcript_dir, name)
        if not os.path.isfile(json_path):
            self.send_error(404, "Not Found")
            return
            
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # ── API: Delete transcript and associated files ─────────────────
    def _delete_transcript(self, name):
        cls = self.__class__
        if not name or "/" in name or "\\" in name:
            self.send_error(400, "Bad Request")
            return
            
        json_path = os.path.join(cls.transcript_dir, name)
        if not os.path.isfile(json_path):
            self.send_error(404, "Not Found")
            return

        base_name = os.path.splitext(name)[0]
        deleted_files = []
        for f in os.listdir(cls.transcript_dir):
            f_base, f_ext = os.path.splitext(f)
            if f_base == base_name or f_base.startswith(base_name + "_"):
                file_path = os.path.join(cls.transcript_dir, f)
                if os.path.isfile(file_path):
                    try:
                        os.remove(file_path)
                        deleted_files.append(file_path)
                    except Exception as e:
                        print(f"[!] Błąd podczas usuwania pliku {file_path}: {e}")

        # Also reset class fields if we deleted the currently active transcript
        current_default_json = find_transcript_json(cls.transcript_dir)
        if current_default_json:
            cls.page_title = os.path.splitext(os.path.basename(current_default_json))[0]
            with open(current_default_json, "r", encoding="utf-8") as f:
                cls.transcript_data = json.load(f)
            cls.audio_path = find_audio_for_json(current_default_json, cls.transcript_dir)
            if not cls.audio_path:
                cls.audio_path = find_audio_file(cls.transcript_dir) or ""
        else:
            cls.page_title = "Brak transkrypcji"
            cls.transcript_data = {"segments": []}
            cls.audio_path = ""

        response_data = {"status": "success", "deleted_files": deleted_files}
        payload = json.dumps(response_data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # ── API: Delete ALL transcripts ────────────────────────────────
    def _delete_all_transcripts(self):
        cls = self.__class__
        if not os.path.isdir(cls.transcript_dir):
            self._json_error(404, "Katalog transkrypcji nie istnieje.")
            return

        deleted = []
        for f in os.listdir(cls.transcript_dir):
            fpath = os.path.join(cls.transcript_dir, f)
            if os.path.isfile(fpath):
                try:
                    os.remove(fpath)
                    deleted.append(f)
                except Exception:
                    pass

        # Reset state
        cls.page_title = "Brak transkrypcji"
        cls.transcript_data = {"segments": []}
        cls.audio_path = ""

        payload = json.dumps({"status": "success", "deleted_count": len(deleted)}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # ── API: Save post feedback (good/bad examples for learning) ───
    def _save_post_feedback(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        try:
            params = json.loads(body)
        except Exception:
            self._json_error(400, "Nieprawidłowe dane JSON.")
            return

        post_text = params.get('text', '').strip()
        rating = params.get('rating', '')  # 'good' or 'bad'

        if not post_text or rating not in ('good', 'bad'):
            self._json_error(400, "Wymagane pola: text, rating (good/bad)")
            return

        project_dir = os.path.dirname(os.path.abspath(__file__))
        feedback_path = os.path.join(project_dir, 'posty_feedback.jsonl')

        entry = json.dumps({"text": post_text, "rating": rating, "ts": time.time()}, ensure_ascii=False)
        with open(feedback_path, 'a', encoding='utf-8') as f:
            f.write(entry + '\n')

        print(f"\033[92m[+] Feedback zapisany: {rating} — {post_text[:50]}...\033[0m")
        payload = json.dumps({"status": "ok"}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # ── API: Generate posts via Ollama ─────────────────────────────
    def _generate_posts(self):
        if not http_requests:
            self._json_error(500, "Biblioteka 'requests' nie jest zainstalowana w środowisku.")
            return

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        try:
            params = json.loads(body)
        except Exception:
            self._json_error(400, "Nieprawidłowe dane JSON.")
            return

        cls = self.__class__
        transcript_name = params.get('transcript_name', '')
        osoba = params.get('osoba', 'Dorota Spyrka')
        username = params.get('username', '@dorota_spyrka')
        program = params.get('program', '@OficjalneZero')
        num_posts = params.get('num_posts', 5)
        speaker_filter = params.get('speaker_filter', '')
        speaker_text = params.get('speaker_text', '')

        # Load transcript text
        base = os.path.splitext(transcript_name)[0]
        txt_path = os.path.join(cls.transcript_dir, f"{base}.txt")
        if not os.path.isfile(txt_path):
            self._json_error(404, f"Nie znaleziono pliku transkrypcji: {base}.txt")
            return

        with open(txt_path, 'r', encoding='utf-8') as f:
            transcript_text = f.read().strip()

        # Jeśli wybrany mówca i dostarczony tekst filtrowany — użyj go
        if speaker_filter and speaker_text.strip():
            transcript_text = speaker_text.strip()

        # Load example posts
        example_posts = ""
        project_dir = os.path.dirname(os.path.abspath(__file__))
        posty_path = os.path.join(project_dir, 'posty.txt')
        if os.path.isfile(posty_path):
            with open(posty_path, 'r', encoding='utf-8') as f:
                example_posts = f.read().strip()

        # Load feedback examples (good/bad posts for learning)
        good_examples = []
        bad_examples = []
        feedback_path = os.path.join(project_dir, 'posty_feedback.jsonl')
        if os.path.isfile(feedback_path):
            with open(feedback_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if entry.get('rating') == 'good':
                            good_examples.append(entry['text'])
                        elif entry.get('rating') == 'bad':
                            bad_examples.append(entry['text'])
                    except Exception:
                        pass
            good_examples = good_examples[-5:]
            bad_examples = bad_examples[-5:]

        # Build feedback section
        feedback_section = ""
        if good_examples or bad_examples:
            feedback_section = "\n\n=== INFORMACJA ZWROTNA OD UŻYTKOWNIKA ==="
            if good_examples:
                feedback_section += "\nDOBRE posty (pisz w tym stylu):\n"
                for ex in good_examples:
                    feedback_section += f"✓ {ex}\n\n"
            if bad_examples:
                feedback_section += "\nZŁE posty (NIE pisz tak):\n"
                for ex in bad_examples:
                    feedback_section += f"✗ {ex}\n\n"
            feedback_section += "=== KONIEC ===\n"

        # Build example section
        example_section = ""
        if example_posts:
            example_section = f"\n\n=== PRZYKŁADOWE POSTY (WZÓR STYLU) ===\nPisz w IDENTYCZNYM stylu co poniżej:\n\n{example_posts}\n\n=== KONIEC PRZYKŁADÓW ==="

        # ──────────────────────────────────────────────────────────────
        # STRATEGIA: Backend PROGRAMISTYCZNIE wycina fragmenty tekstu,
        # a model TYLKO czyści jąknięcia i formatuje nagłówek/hashtag.
        # Eliminuje halucynacje w małych modelach (8B).
        # ──────────────────────────────────────────────────────────────

        # Wyczyść tekst z timestampów i oznaczeń mówców
        clean_text = re.sub(r'\[\d+:\d+:\d+\]\s*SPEAKER_\d+:', '', transcript_text)
        clean_text = re.sub(r'\n\s*\n', '\n', clean_text).strip()

        # Podziel na zdania
        sentences = re.split(r'(?<=[.!?])\s+', clean_text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 25]

        # Zgrupuj w bloki po 3-4 zdania (każdy blok = 1 post)
        blocks = []
        i = 0
        while i < len(sentences):
            chunk_size = min(4, len(sentences) - i)
            block = ' '.join(sentences[i:i+chunk_size])
            if len(block) > 60:
                blocks.append(block)
            i += chunk_size

        # Wybierz num_posts bloków równomiernie rozłożonych
        if len(blocks) <= num_posts:
            selected = blocks
        else:
            step = len(blocks) / num_posts
            selected = [blocks[int(i * step)] for i in range(num_posts)]

        # Przygotuj bloki do minimalnej redakcji
        blocks_text = ""
        for i, block in enumerate(selected, 1):
            blocks_text += f"\n[BLOK {i}]: {block}\n"

        system_prompt = f"""Jesteś redaktorem postów. Dostajesz GOTOWE fragmenty tekstu. 
Twoje JEDYNE zadanie:
1. Usuń jąknięcia (yyy, eee, uhm) i urwane słowa/zdania.
2. Na początku dodaj: 💬{username} w {program}:
3. Na końcu dodaj: #RAZEMwMEDIACH
4. Przed szczególnie mocnym zdaniem możesz dodać ‼️

ABSOLUTNE ZAKAZY:
- NIE zmieniaj słów! Kopiuj DOSŁOWNIE (minus jąknięcia).
- NIE dodawaj swoich zdań/komentarzy/opinii!
- NIE streszczaj!
- NIE skracaj — przepisz cały blok!
- Jeśli zdanie jest urwane — po prostu je pomiń.

Oddziel posty podwójną nową linią.{example_section}{feedback_section}"""

        prompt = f"Oto {len(selected)} bloków do przetworzenia na posty. Przepisz każdy blok DOSŁOWNIE, dodając tylko nagłówek i hashtag:\n{blocks_text}"

        ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
        ollama_model = os.getenv('OLLAMA_MODEL', 'llama3.1:8b')

        try:
            print(f"\033[94m[-] Generowanie {num_posts} postów (model: {ollama_model})...\033[0m")
            resp = http_requests.post(
                f"{ollama_url}/api/chat",
                json={
                    "model": ollama_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.0
                    }
                },
                timeout=300,
            )
            if resp.status_code != 200:
                self._json_error(502, f"Ollama zwróciła błąd HTTP {resp.status_code}: {resp.text[:200]}")
                return

            result_text = resp.json().get('message', {}).get('content', '').strip()
            print(f"\033[92m[+] Wygenerowano posty pomyślnie.\033[0m")

            # Parsowanie odpowiedzi i dodanie źródeł z oryginalnych bloków
            posts_with_sources = self._parse_posts_with_sources(result_text)
            
            # Dodaj źródła — każdy post odpowiada blokowi, którego jest przepisaniem
            for i, post in enumerate(posts_with_sources):
                if i < len(selected):
                    post["sources"] = [selected[i]]

            payload = json.dumps({"posts": posts_with_sources}, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except http_requests.exceptions.ConnectionError:
            self._json_error(502, f"Nie można połączyć się z Ollama ({ollama_url}). Sprawdź, czy jest uruchomiona.")
        except Exception as e:
            self._json_error(500, f"Błąd: {str(e)}")

    @staticmethod
    def _parse_posts_with_sources(text):
        """Parsuje odpowiedź AI na posty. Każdy post zaczyna się od 💬."""
        posts = []
        
        # Usuń [ŹRÓDŁO:...] tagi i linie z samymi myślnikami
        text = re.sub(r'\[ŹRÓDŁO:.*?\]', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'^-{3,}$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\[BLOK \d+\]:?\s*', '', text, flags=re.MULTILINE)
        
        # Rozdziel po 💬 — każdy post zaczyna się od tego emoji
        parts = re.split(r'(?=💬)', text)
        
        for part in parts:
            part = part.strip()
            if not part or len(part) < 20:
                continue
            # Wyczyść podwójne nowe linie wewnątrz posta (zachowaj jako spację)
            cleaned = re.sub(r'\n{2,}', '\n', part).strip()
            if cleaned:
                posts.append({"text": cleaned, "sources": []})
        
        # Fallback — jeśli nie znaleziono 💬, rozdziel po podwójnej nowej linii
        if not posts:
            raw_posts = re.split(r'\n\n+', text.strip())
            for p in raw_posts:
                p = p.strip()
                if p and len(p) > 20:
                    posts.append({"text": p, "sources": []})
        
        return posts

    # ── API: Save posts to file ────────────────────────────────────
    def _save_posts(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        try:
            params = json.loads(body)
        except Exception:
            self._json_error(400, "Nieprawidłowe dane JSON.")
            return

        cls = self.__class__
        transcript_name = params.get('transcript_name', '')
        posts = params.get('posts', [])

        base = os.path.splitext(transcript_name)[0]
        output_path = os.path.join(cls.transcript_dir, f"{base}_posty.txt")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n\n---\n\n'.join(posts))

        print(f"\033[92m[+] Zapisano {len(posts)} postów do: {output_path}\033[0m")

        payload = json.dumps({"status": "success", "path": output_path}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # ── Helper: JSON error response ────────────────────────────────
    def _json_error(self, code, message):
        payload = json.dumps({"error": message}).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # ── API: Upload file and start transcription ───────────────────
    def _upload_and_transcribe(self):
        cls = self.__class__
        content_type = self.headers.get('Content-Type', '')

        if 'multipart/form-data' not in content_type:
            self._json_error(400, "Wymagany Content-Type: multipart/form-data")
            return

        # Parse boundary
        boundary = None
        for part in content_type.split(';'):
            part = part.strip()
            if part.startswith('boundary='):
                boundary = part[9:].strip('"')
                break
        if not boundary:
            self._json_error(400, "Brak boundary w Content-Type")
            return

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        # Parse multipart form data
        boundary_bytes = boundary.encode()
        parts = body.split(b'--' + boundary_bytes)

        file_data = None
        file_name = None
        model = 'medium'
        device = 'cuda'
        compute_type = 'float16'
        batch_size = 4
        min_speakers = None
        max_speakers = None
        use_ollama = True

        for part in parts:
            if b'Content-Disposition' not in part:
                continue
            # Split headers from content
            header_end = part.find(b'\r\n\r\n')
            if header_end == -1:
                continue
            headers_raw = part[:header_end].decode('utf-8', errors='replace')
            content = part[header_end + 4:]
            # Remove trailing \r\n
            if content.endswith(b'\r\n'):
                content = content[:-2]

            # Parse Content-Disposition
            name = None
            filename = None
            for line in headers_raw.split('\r\n'):
                if 'Content-Disposition' in line:
                    for item in line.split(';'):
                        item = item.strip()
                        if item.startswith('name='):
                            name = item[5:].strip('"')
                        elif item.startswith('filename='):
                            filename = item[9:].strip('"')

            if name == 'file' and filename:
                file_data = content
                file_name = filename
            elif name == 'model':
                model = content.decode().strip()
            elif name == 'device':
                device = content.decode().strip()
            elif name == 'compute_type':
                compute_type = content.decode().strip()
            elif name == 'batch_size':
                try: batch_size = int(content.decode().strip())
                except: pass
            elif name == 'min_speakers':
                try: min_speakers = int(content.decode().strip()) if content.strip() else None
                except: pass
            elif name == 'max_speakers':
                try: max_speakers = int(content.decode().strip()) if content.strip() else None
                except: pass
            elif name == 'use_ollama':
                use_ollama = content.decode().strip().lower() in ('true', '1', 'yes')

        if not file_data or not file_name:
            self._json_error(400, "Nie przesłano pliku audio/wideo.")
            return

        # Save uploaded file to transcript dir
        safe_name = re.sub(r'[^\w\-.]', '_', file_name)
        upload_path = os.path.join(cls.transcript_dir, safe_name)
        with open(upload_path, 'wb') as f:
            f.write(file_data)

        # Start background transcription
        job_id = f"job_{int(time.time() * 1000)}"
        with _job_lock:
            _transcription_jobs[job_id] = {
                'status': 'running',
                'progress': 0,
                'message': 'Przesyłanie pliku zakończone, uruchamianie...',
                'result': None
            }

        t = threading.Thread(
            target=_run_transcription_job,
            args=(job_id, upload_path, cls.transcript_dir, model, device, compute_type, batch_size, min_speakers, max_speakers, use_ollama),
            daemon=True
        )
        t.start()

        payload = json.dumps({"job_id": job_id}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # ── API: Get transcription job status ──────────────────────────
    def _serve_job_status(self, job_id):
        if not job_id:
            self._json_error(400, "Brak parametru id.")
            return

        with _job_lock:
            job = _transcription_jobs.get(job_id)

        if not job:
            self._json_error(404, "Nie znaleziono zadania o podanym ID.")
            return

        payload = json.dumps(job, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # ── Live Transcription Handlers ────────────────────────────────
    def _serve_live_sources(self):
        from live_transcriber import list_audio_sources
        sources = list_audio_sources()
        data = [{"id": s.id, "name": s.name, "media_name": s.media_name} for s in sources]
        payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_live_preview(self):
        """Stream live audio from a source via parec as WAV for monitoring.
        Works independently from session — just needs source_id query param."""
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        source_id = query.get("source_id", [None])[0]

        # If session active, use session's capture buffer
        from live_transcriber import get_session_manager, CaptureEngine
        sm = get_session_manager(self.__class__.transcript_dir)

        if not source_id and sm._capture and sm._capture.is_source_alive:
            source_id = sm.source_id

        if not source_id:
            self._json_error(400, "Podaj source_id w parametrze lub uruchom sesję.")
            return

        # Spawn a separate parec for preview with low latency
        try:
            proc = subprocess.Popen(
                ["parec", "--format=s16le", "--rate=16000", "--channels=1",
                 "--latency-msec=50",
                 f"--monitor-stream={source_id}"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
        except Exception as e:
            self._json_error(500, f"Nie można uruchomić parec: {e}")
            return

        # Stream as WAV
        self.send_response(200)
        self.send_header('Content-Type', 'audio/wav')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()

        # WAV header with large data size for streaming
        import struct as struct_mod
        data_size = 0x7FFFFFFF
        header = struct_mod.pack('<4sI4s', b'RIFF', 36 + data_size, b'WAVE')
        header += struct_mod.pack('<4sIHHIIHH', b'fmt ', 16, 1, 1, 16000, 32000, 2, 16)
        header += struct_mod.pack('<4sI', b'data', data_size)

        try:
            self.wfile.write(header)
            self.wfile.flush()

            while proc.poll() is None:
                # Read small chunks (50ms = 1600 bytes) for low latency
                data = proc.stdout.read(1600)
                if not data:
                    break
                self.wfile.write(data)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def _serve_live_status(self):
        from live_transcriber import get_session_manager
        sm = get_session_manager(self.__class__.transcript_dir)
        payload = json.dumps(sm.get_status(), ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_live_events(self):
        """SSE endpoint — streams events from the session manager."""
        from live_transcriber import get_session_manager
        sm = get_session_manager(self.__class__.transcript_dir)

        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('X-Accel-Buffering', 'no')
        self.end_headers()

        try:
            while True:
                event = sm.get_event(timeout=2.0)
                if event:
                    event_type = event.get("event", "message")
                    data = json.dumps(event.get("data", {}), ensure_ascii=False)
                    msg = f"event: {event_type}\ndata: {data}\n\n"
                    self.wfile.write(msg.encode('utf-8'))
                    self.wfile.flush()
                else:
                    # Send keepalive comment
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()

                # Stop streaming if session ended or stopped
                if sm.state in ("idle", "stopped"):
                    break
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass  # Client disconnected

    def _live_start(self):
        from live_transcriber import get_session_manager
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        try:
            params = json.loads(body) if body else {}
        except Exception:
            params = {}

        source_id = params.get("source_id", "")
        model = params.get("model", "small")
        chunk_duration = int(params.get("chunk_duration", 15))
        device = params.get("device", "cuda")

        if not source_id:
            self._json_error(400, "Nie wybrano źródła audio.")
            return

        sm = get_session_manager(self.__class__.transcript_dir)
        try:
            session_id = sm.start_session(source_id, model, chunk_duration, device)
            payload = json.dumps({"session_id": session_id}).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except RuntimeError as e:
            self._json_error(409, str(e))

    def _live_pause(self):
        from live_transcriber import get_session_manager
        sm = get_session_manager(self.__class__.transcript_dir)
        sm.pause_session()
        self._json_ok({"status": "paused"})

    def _live_resume(self):
        from live_transcriber import get_session_manager
        sm = get_session_manager(self.__class__.transcript_dir)
        sm.resume_session()
        self._json_ok({"status": "recording"})

    def _live_stop(self):
        from live_transcriber import get_session_manager
        sm = get_session_manager(self.__class__.transcript_dir)
        summary = sm.stop_session()
        self._json_ok(summary)

    def _live_save(self):
        from live_transcriber import get_session_manager
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        try:
            params = json.loads(body) if body else {}
        except Exception:
            params = {}

        filename = params.get("filename", "").strip()
        if not filename:
            self._json_error(400, "Nie podano nazwy pliku.")
            return

        sm = get_session_manager(self.__class__.transcript_dir)
        result = sm.save_transcript(filename)
        if result.get("error") == "file_exists":
            self._json_error(409, f"Plik '{filename}' już istnieje.")
            return

        # Reset session for next use
        sm.reset()
        self._json_ok(result)

    def _json_ok(self, data):
        payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # ── Audio file (supports Range Requests) ────────────────────────
    def _serve_audio(self, filename):
        cls = self.__class__
        
        # Seek file in transcript dir
        audio_path = os.path.join(cls.transcript_dir, filename)
        if not os.path.isfile(audio_path):
            # Check parent directory
            parent = os.path.dirname(os.path.abspath(cls.transcript_dir))
            audio_path = os.path.join(parent, filename)
            
        if not os.path.isfile(audio_path):
            # Fallback
            audio_path = cls.audio_path
            
        if not audio_path or not os.path.isfile(audio_path):
            self.send_error(404, "Audio file not found")
            return

        file_size = os.path.getsize(audio_path)
        mime, _ = mimetypes.guess_type(audio_path)
        if not mime:
            mime = "application/octet-stream"

        range_header = self.headers.get("Range")
        if range_header:
            try:
                range_spec = range_header.strip().split("=")[1]
                parts = range_spec.split("-")
                start = int(parts[0])
                end = int(parts[1]) if parts[1] else file_size - 1
            except (IndexError, ValueError):
                start, end = 0, file_size - 1

            end = min(end, file_size - 1)
            length = end - start + 1

            self.send_response(206)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(length))
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()

            with open(audio_path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        else:
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()

            with open(audio_path, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)


class ReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


# ──────────────────────────────────────────────────────────────────────────────
# Discovery helpers
# ──────────────────────────────────────────────────────────────────────────────

AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus", ".webm", ".mp4", ".mkv", ".mov"}


def find_transcript_json(directory: str) -> str | None:
    candidates = []
    if os.path.isdir(directory):
        for f in os.listdir(directory):
            if f.lower().endswith(".json") and not f.endswith("_state.json"):
                candidates.append(os.path.join(directory, f))
    if not candidates:
        return None
    # Prefer files with 'transcript' in the name
    for c in candidates:
        if "transcript" in os.path.basename(c).lower():
            return c
    return candidates[0]


def find_audio_file(directory: str) -> str | None:
    if os.path.isdir(directory):
        for f in os.listdir(directory):
            ext = os.path.splitext(f)[1].lower()
            if ext in AUDIO_EXTENSIONS:
                return os.path.join(directory, f)
        parent = os.path.dirname(os.path.abspath(directory))
        for f in os.listdir(parent):
            ext = os.path.splitext(f)[1].lower()
            if ext in AUDIO_EXTENSIONS:
                return os.path.join(parent, f)
    return None


def find_audio_for_json(json_path: str, directory: str) -> str | None:
    """Find the corresponding audio file for a given transcript JSON file."""
    base_name = os.path.splitext(os.path.basename(json_path))[0]
    if os.path.isdir(directory):
        for f in os.listdir(directory):
            f_base, f_ext = os.path.splitext(f)
            if f_base == base_name and f_ext.lower() in AUDIO_EXTENSIONS:
                return os.path.join(directory, f)
        parent = os.path.dirname(os.path.abspath(directory))
        if os.path.isdir(parent):
            for f in os.listdir(parent):
                f_base, f_ext = os.path.splitext(f)
                if f_base == base_name and f_ext.lower() in AUDIO_EXTENSIONS:
                    return os.path.join(parent, f)
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Interactive Transcript Viewer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dir", default="./transcripts",
        help="Transcript directory containing .json files (default: ./transcripts)",
    )
    parser.add_argument(
        "--audio", default=None,
        help="Explicit path to the audio file (auto-detected if omitted)",
    )
    parser.add_argument(
        "--port", type=int, default=8765,
        help="HTTP server port (default: 8765)",
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Don't auto-open the browser",
    )
    parser.add_argument(
        "--default", default=None,
        help="Base name of the default transcript to open (e.g. 'ola' for ola.json)",
    )
    args = parser.parse_args()

    transcript_dir = os.path.abspath(args.dir)
    os.makedirs(transcript_dir, exist_ok=True)

    # Find default transcript JSON
    json_path = None
    if args.default:
        # Try to find the specific transcript requested via --default
        candidate = os.path.join(transcript_dir, f"{args.default}.json")
        if os.path.isfile(candidate):
            json_path = candidate
        else:
            print(f"\033[93m⚠ Requested default '{args.default}.json' not found, falling back to auto-detect.\033[0m")
    if not json_path:
        json_path = find_transcript_json(transcript_dir)
    if not json_path:
        print(f"\033[93m⚠ No JSON file found in {transcript_dir} — starting in empty mode.\033[0m")
        transcript_data = {"segments": []}
        audio_path = ""
        page_title = "Brak transkrypcji"
    else:
        with open(json_path, "r", encoding="utf-8") as f:
            transcript_data = json.load(f)
        print(f"\033[92m✓\033[0m Default transcript: \033[1m{os.path.basename(json_path)}\033[0m")

        # Find default audio
        audio_path = args.audio
        if audio_path:
            audio_path = os.path.abspath(audio_path)
        else:
            audio_path = find_audio_for_json(json_path, transcript_dir)
            if not audio_path:
                audio_path = find_audio_file(transcript_dir)

        if audio_path and os.path.isfile(audio_path):
            print(f"\033[92m✓\033[0m Default audio: \033[1m{os.path.basename(audio_path)}\033[0m")
        else:
            print(f"\033[93m⚠\033[0m No default audio found")
            audio_path = ""

        page_title = os.path.splitext(os.path.basename(json_path))[0]

    # Configure handler
    TranscriptHandler.transcript_dir = transcript_dir
    TranscriptHandler.audio_path = audio_path
    TranscriptHandler.transcript_data = transcript_data
    TranscriptHandler.page_title = page_title

    port = args.port
    url = f"http://localhost:{port}"

    with ReusableTCPServer(("", port), TranscriptHandler) as httpd:
        print(f"\n\033[1m  ▶  Serving at \033[4m{url}\033[0m\n")
        print(f"     Press \033[1mCtrl+C\033[0m to stop.\n")

        if not args.no_browser:
            threading.Timer(0.4, lambda: webbrowser.open(url)).start()

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\033[90m  Shutting down…\033[0m")
            httpd.shutdown()


if __name__ == "__main__":
    main()
