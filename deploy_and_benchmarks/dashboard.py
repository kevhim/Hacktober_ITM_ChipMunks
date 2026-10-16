#!/usr/bin/env python3
"""Chaos-Harness Live Web Dashboard & REST Server.

A zero-dependency interactive visual dashboard for adversarial red-teaming,
safety evaluation, and prompt auto-hardening powered by Google Gemma 4.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure repository root is on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from deploy_and_benchmarks.provider_router import ProviderRouter, ProviderType
from deploy_and_benchmarks.benchmark_loader import (
    BenchmarkSuite,
    BenchmarkTarget,
    load_benchmark_suite,
)

# Global router instance for the server
ROUTER: Optional[ProviderRouter] = None
SUITE: Optional[BenchmarkSuite] = None


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Chaos-Harness | Red-Teaming & Self-Healing Studio</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-dark: #0a0d14;
      --bg-card: rgba(18, 24, 38, 0.75);
      --bg-card-hover: rgba(26, 35, 54, 0.85);
      --border-color: rgba(255, 255, 255, 0.08);
      --border-focus: rgba(66, 133, 244, 0.5);
      --text-main: #f1f5f9;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --primary-blue: #4285f4;
      --accent-cyan: #06b6d4;
      --danger-red: #ef4444;
      --danger-bg: rgba(239, 68, 68, 0.12);
      --success-green: #10b981;
      --success-bg: rgba(16, 185, 129, 0.12);
      --warning-amber: #f59e0b;
      --radius: 12px;
      --radius-sm: 8px;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background-color: var(--bg-dark);
      background-image: 
        radial-gradient(circle at 15% 15%, rgba(66, 133, 244, 0.08) 0%, transparent 40%),
        radial-gradient(circle at 85% 85%, rgba(239, 68, 68, 0.06) 0%, transparent 40%);
      color: var(--text-main);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      overflow-x: hidden;
    }

    header {
      background: rgba(10, 13, 20, 0.8);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--border-color);
      position: sticky;
      top: 0;
      z-index: 100;
      padding: 1rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }

    .brand-icon {
      font-size: 1.5rem;
      background: linear-gradient(135deg, #ef4444, #f59e0b);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      filter: drop-shadow(0 0 10px rgba(239, 68, 68, 0.4));
    }

    .brand-title {
      font-size: 1.25rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }

    .brand-tag {
      font-size: 0.75rem;
      background: rgba(66, 133, 244, 0.15);
      color: #93c5fd;
      border: 1px solid rgba(66, 133, 244, 0.3);
      padding: 0.2rem 0.5rem;
      border-radius: 9999px;
      font-weight: 600;
    }

    .header-status {
      display: flex;
      align-items: center;
      gap: 1.25rem;
    }

    .status-pill {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--border-color);
      padding: 0.4rem 0.8rem;
      border-radius: 9999px;
      font-size: 0.8rem;
      color: var(--text-muted);
    }

    .status-dot {
      width: 8px;
      height: 8px;
      background-color: var(--success-green);
      border-radius: 50%;
      box-shadow: 0 0 8px var(--success-green);
      animation: pulse-dot 2s infinite;
    }

    @keyframes pulse-dot {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.5; transform: scale(0.85); }
    }

    main {
      flex: 1;
      max-width: 1400px;
      width: 100%;
      margin: 0 auto;
      padding: 2rem;
      display: flex;
      flex-direction: column;
      gap: 2rem;
    }

    .hero-banner {
      background: var(--bg-card);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-color);
      border-radius: var(--radius);
      padding: 1.75rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }

    .hero-info h1 {
      font-size: 1.6rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      margin-bottom: 0.35rem;
      background: linear-gradient(90deg, #ffffff, #94a3b8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .hero-info p {
      font-size: 0.9rem;
      color: var(--text-muted);
    }

    .selector-container {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      min-width: 340px;
    }

    .selector-label {
      font-size: 0.8rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-dim);
    }

    select.target-dropdown {
      background: #0f1523;
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 0.75rem 1rem;
      border-radius: var(--radius-sm);
      font-size: 0.95rem;
      font-family: inherit;
      outline: none;
      cursor: pointer;
      transition: all 0.2s ease;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }

    select.target-dropdown:focus {
      border-color: var(--primary-blue);
      box-shadow: 0 0 0 3px rgba(66, 133, 244, 0.25);
    }

    .grid-layout {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.75rem;
    }

    @media (max-width: 1024px) {
      .grid-layout {
        grid-template-columns: 1fr;
      }
      .hero-banner {
        flex-direction: column;
        align-items: flex-start;
        gap: 1.25rem;
      }
      .selector-container {
        width: 100%;
      }
    }

    .card {
      background: var(--bg-card);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-color);
      border-radius: var(--radius);
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
      transition: border-color 0.2s ease;
    }

    .card:hover {
      border-color: rgba(255, 255, 255, 0.15);
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--border-color);
      padding-bottom: 0.85rem;
    }

    .card-title {
      font-size: 1.05rem;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }

    .badge {
      font-size: 0.75rem;
      font-weight: 600;
      padding: 0.25rem 0.6rem;
      border-radius: 9999px;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }

    .badge-danger {
      background: var(--danger-bg);
      color: #f87171;
      border: 1px solid rgba(239, 68, 68, 0.3);
    }

    .badge-domain {
      background: rgba(255, 255, 255, 0.05);
      color: var(--text-muted);
      border: 1px solid var(--border-color);
    }

    .badge-success {
      background: var(--success-bg);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.3);
    }

    .target-meta-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 0.75rem;
    }

    .meta-item {
      background: rgba(0, 0, 0, 0.2);
      border: 1px solid var(--border-color);
      padding: 0.75rem;
      border-radius: var(--radius-sm);
    }

    .meta-title {
      font-size: 0.7rem;
      color: var(--text-dim);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.25rem;
    }

    .meta-value {
      font-size: 0.9rem;
      font-weight: 500;
      color: var(--text-main);
    }

    .prompt-editor-container {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }

    .editor-label {
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--text-muted);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    textarea.prompt-textarea {
      width: 100%;
      height: 180px;
      background: #090d16;
      border: 1px solid var(--border-color);
      border-radius: var(--radius-sm);
      padding: 0.85rem;
      color: #e2e8f0;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      line-height: 1.5;
      resize: vertical;
      outline: none;
      transition: all 0.2s ease;
    }

    textarea.prompt-textarea:focus {
      border-color: var(--border-focus);
      box-shadow: 0 0 0 2px rgba(66, 133, 244, 0.2);
    }

    /* Attack Studio Controls (Feature 2) */
    .category-pills {
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
    }

    .pill-btn {
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--border-color);
      color: var(--text-muted);
      padding: 0.35rem 0.75rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s ease;
    }

    .pill-btn:hover {
      background: rgba(255, 255, 255, 0.08);
      color: var(--text-main);
    }

    .pill-btn.active {
      background: rgba(239, 68, 68, 0.2);
      border-color: rgba(239, 68, 68, 0.5);
      color: #fca5a5;
      box-shadow: 0 0 10px rgba(239, 68, 68, 0.2);
    }

    .btn-attack {
      background: linear-gradient(135deg, #ef4444, #dc2626);
      color: #ffffff;
      border: none;
      padding: 0.85rem 1.25rem;
      border-radius: var(--radius-sm);
      font-weight: 600;
      font-size: 0.95rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.6rem;
      transition: all 0.2s ease;
      box-shadow: 0 4px 16px rgba(239, 68, 68, 0.35);
      width: 100%;
    }

    .btn-attack:hover {
      transform: translateY(-1px);
      box-shadow: 0 6px 20px rgba(239, 68, 68, 0.5);
      filter: brightness(1.08);
    }

    .btn-attack:disabled {
      opacity: 0.6;
      cursor: not-allowed;
      transform: none;
    }

    .btn-judge {
      background: linear-gradient(135deg, #4285f4, #2563eb);
      color: #ffffff;
      border: none;
      padding: 0.85rem 1.25rem;
      border-radius: var(--radius-sm);
      font-weight: 600;
      font-size: 0.95rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.6rem;
      transition: all 0.2s ease;
      box-shadow: 0 4px 16px rgba(66, 133, 244, 0.35);
      width: 100%;
    }

    .btn-judge:hover {
      transform: translateY(-1px);
      box-shadow: 0 6px 20px rgba(66, 133, 244, 0.5);
      filter: brightness(1.08);
    }

    .btn-judge:disabled {
      opacity: 0.6;
      cursor: not-allowed;
      transform: none;
    }

    .attack-box {
      background: rgba(239, 68, 68, 0.04);
      border: 1px solid rgba(239, 68, 68, 0.25);
      border-radius: var(--radius-sm);
      padding: 0.85rem;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }

    .response-box {
      background: rgba(0, 0, 0, 0.25);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: var(--radius-sm);
      padding: 0.85rem;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }

    .response-box.compromised {
      border-color: rgba(239, 68, 68, 0.4);
      background: rgba(239, 68, 68, 0.06);
    }

    .box-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--text-dim);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .code-display {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      line-height: 1.45;
      color: #fca5a5;
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 120px;
      overflow-y: auto;
    }

    .response-display {
      font-family: inherit;
      font-size: 0.85rem;
      line-height: 1.45;
      color: #e2e8f0;
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 120px;
      overflow-y: auto;
    }

    /* Feature 3: Safety Radar & Risk Gauges */
    .radar-container {
      display: grid;
      grid-template-columns: 200px 1fr;
      gap: 1.75rem;
      align-items: center;
      background: rgba(0, 0, 0, 0.2);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-sm);
      padding: 1.25rem;
    }

    @media (max-width: 768px) {
      .radar-container {
        grid-template-columns: 1fr;
        justify-items: center;
      }
    }

    .gauge-wrapper {
      position: relative;
      width: 140px;
      height: 140px;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto;
    }

    .gauge-svg {
      transform: rotate(-90deg);
      width: 140px;
      height: 140px;
    }

    .gauge-bg {
      fill: none;
      stroke: rgba(255, 255, 255, 0.08);
      stroke-width: 10;
    }

    .gauge-progress {
      fill: none;
      stroke: var(--danger-red);
      stroke-width: 10;
      stroke-linecap: round;
      stroke-dasharray: 339.292;
      stroke-dashoffset: 339.292;
      transition: stroke-dashoffset 1.2s cubic-bezier(0.4, 0, 0.2, 1), stroke 0.5s ease;
    }

    .gauge-content {
      position: absolute;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }

    .gauge-number {
      font-size: 2.25rem;
      font-weight: 800;
      line-height: 1;
      letter-spacing: -0.03em;
      color: var(--danger-red);
      transition: color 0.5s ease;
    }

    .gauge-label {
      font-size: 0.65rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-dim);
      margin-top: 0.2rem;
    }

    .breakdown-bars {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      width: 100%;
    }

    .bar-row {
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }

    .bar-label-group {
      display: flex;
      justify-content: space-between;
      font-size: 0.75rem;
      color: var(--text-muted);
    }

    .bar-track {
      width: 100%;
      height: 6px;
      background: rgba(255, 255, 255, 0.08);
      border-radius: 9999px;
      overflow: hidden;
    }

    .bar-fill {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #ef4444, #f87171);
      border-radius: 9999px;
      transition: width 1s ease-in-out;
    }

    .diagnostic-panel {
      background: rgba(239, 68, 68, 0.08);
      border-left: 3px solid var(--danger-red);
      padding: 0.85rem 1rem;
      border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
    }

    .diagnostic-panel.pass {
      background: rgba(16, 185, 129, 0.08);
      border-left-color: var(--success-green);
    }

    .diag-title {
      font-size: 0.8rem;
      font-weight: 700;
      color: var(--text-main);
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }

    .diag-desc {
      font-size: 0.8rem;
      color: var(--text-muted);
      line-height: 1.4;
    }

    footer {
      border-top: 1px solid var(--border-color);
      padding: 1.25rem 2rem;
      background: rgba(10, 13, 20, 0.5);
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.8rem;
      color: var(--text-dim);
    }

    .footer-links a {
      color: var(--text-muted);
      text-decoration: none;
      transition: color 0.2s;
    }

    .footer-links a:hover {
      color: var(--primary-blue);
    }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <span class="brand-icon">💥</span>
      <span class="brand-title">Chaos-Harness</span>
      <span class="brand-tag">Gemma 4 Studio</span>
    </div>
    <div class="header-status">
      <div class="status-pill">
        <span class="status-dot"></span>
        <span id="providerStatus">Engine: Gemma 4 (gemma-4-26b-a4b-it)</span>
      </div>
      <div class="status-pill">
        <span>Standard: agentskills.io</span>
      </div>
    </div>
  </header>

  <main>
    <!-- Hero / Target Selection -->
    <section class="hero-banner">
      <div class="hero-info">
        <h1>Adversarial Red-Teaming & Self-Healing Studio</h1>
        <p>Stress-test vulnerable system prompts and autonomously synthesize defense-in-depth instructions using Google Gemma 4.</p>
      </div>
      <div class="selector-container">
        <label for="targetSelect" class="selector-label">Select Evaluation Target</label>
        <select id="targetSelect" class="target-dropdown">
          <option value="" disabled selected>Loading benchmark targets...</option>
        </select>
      </div>
    </section>

    <!-- Main 2-Column Grid -->
    <div class="grid-layout">
      
      <!-- Left Column: Target Profile & Prompt Editor -->
      <section class="card" id="targetProfileCard">
        <div class="card-header">
          <div class="card-title">
            <span>🎯</span>
            <span id="displayTargetName">Target Profile</span>
          </div>
          <span class="badge badge-danger" id="displayRiskCategory">Vulnerability</span>
        </div>

        <div class="target-meta-grid">
          <div class="meta-item">
            <div class="meta-title">Domain</div>
            <div class="meta-value" id="displayDomain">-</div>
          </div>
          <div class="meta-item">
            <div class="meta-title">Target ID</div>
            <div class="meta-value" id="displayTargetId">-</div>
          </div>
        </div>

        <div class="meta-item">
          <div class="meta-title">Vulnerability Diagnosis</div>
          <div class="meta-value" id="displayVulnerability" style="font-weight: 400; line-height: 1.4;">-</div>
        </div>

        <div class="prompt-editor-container">
          <div class="editor-label">
            <span>Active System Prompt (Editable)</span>
            <span style="font-size: 0.75rem; color: var(--text-dim);" id="charCount">0 chars</span>
          </div>
          <textarea id="promptTextarea" class="prompt-textarea" placeholder="System prompt under evaluation..."></textarea>
        </div>
      </section>

      <!-- Right Column: Adversarial Attack Studio (Feature 2) -->
      <section class="card" id="attackStudioCard">
        <div class="card-header">
          <div class="card-title">
            <span>⚔️</span>
            <span>Adversarial Attack Studio</span>
          </div>
          <span class="badge badge-danger" id="attackStatusBadge">Ready to Attack</span>
        </div>

        <!-- Category Selector Pills -->
        <div class="prompt-editor-container">
          <div class="editor-label">Select Attack Vector Domain</div>
          <div class="category-pills" id="categoryPills">
            <button class="pill-btn active" data-category="AUTO">⚡ Auto-Detected</button>
            <button class="pill-btn" data-category="PROMPT_INJECTION">💉 Prompt Injection</button>
            <button class="pill-btn" data-category="PII_LEAKAGE">🔓 PII Phishing</button>
            <button class="pill-btn" data-category="SCHEMA_VIOLATION">💥 Schema Breaker</button>
            <button class="pill-btn" data-category="HALLUCINATION">🌀 Hallucination Trap</button>
          </div>
        </div>

        <!-- Attack Trigger Button -->
        <button id="btnLaunchAttack" class="btn-attack" onclick="launchAttack()">
          <span>⚔️</span>
          <span>Launch Gemma 4 Adversarial Attack</span>
        </button>

        <!-- Adversarial Payload Box -->
        <div class="attack-box" id="attackBox">
          <div class="box-header">
            <span>⚔️ Gemma 4 Adversarial Payload</span>
            <span id="payloadLatency" style="font-weight: normal; color: var(--text-muted);">-</span>
          </div>
          <div class="code-display" id="attackPayloadDisplay">Select a target and click 'Launch Gemma 4 Adversarial Attack' to generate a safety evaluation probe.</div>
        </div>

        <!-- Target Compromised Response Box -->
        <div class="response-box compromised" id="responseBox">
          <div class="box-header">
            <span>🚨 Vulnerable Bot Response (Under Attack)</span>
            <span class="badge badge-danger" id="compromiseBadge">Pre-Hardening</span>
          </div>
          <div class="response-display" id="targetResponseDisplay">Target assistant has not been attacked yet.</div>
        </div>
      </section>

    </div>

    <!-- Feature 3: Safety Radar & Risk Score Adjudication -->
    <section class="card" id="safetyRadarCard">
      <div class="card-header">
        <div class="card-title">
          <span>📊</span>
          <span>Gemma 4 Safety Radar & Adjudication</span>
        </div>
        <span class="badge badge-danger" id="radarStatusBadge">Adjudication Pending</span>
      </div>

      <!-- Judge Button -->
      <button id="btnJudgeSafety" class="btn-judge" onclick="judgeSafety()">
        <span>⚖️</span>
        <span>Adjudicate Safety with Gemma 4 Judge</span>
      </button>

      <button id="btnHeal" class="btn-judge" onclick="hardenAndRetest()">
        Harden candidate and replay attack
      </button>
      <pre id="healingOutput" style="white-space:pre-wrap;padding:1rem" aria-live="polite"></pre>

      <!-- Gauge & Breakdown Grid -->
      <div class="radar-container">
        <!-- Circular Animated Gauge -->
        <div class="gauge-wrapper">
          <svg class="gauge-svg" viewBox="0 0 120 120">
            <circle class="gauge-bg" cx="60" cy="60" r="54"></circle>
            <circle class="gauge-progress" id="gaugeCircle" cx="60" cy="60" r="54"></circle>
          </svg>
          <div class="gauge-content">
            <span class="gauge-number" id="gaugeNumber">--</span>
            <span class="gauge-label" id="gaugeLabel">Risk Score</span>
          </div>
        </div>

        <!-- Breakdown Progress Bars -->
        <div class="breakdown-bars">
          <div class="bar-row">
            <div class="bar-label-group">
              <span>Prompt Injection Vulnerability</span>
              <span id="valInjection">--%</span>
            </div>
            <div class="bar-track">
              <div class="bar-fill" id="barInjection"></div>
            </div>
          </div>

          <div class="bar-row">
            <div class="bar-label-group">
              <span>Schema & Formatting Breach</span>
              <span id="valSchema">--%</span>
            </div>
            <div class="bar-track">
              <div class="bar-fill" id="barSchema"></div>
            </div>
          </div>

          <div class="bar-row">
            <div class="bar-label-group">
              <span>PII & Secrets Exfiltration</span>
              <span id="valPii">--%</span>
            </div>
            <div class="bar-track">
              <div class="bar-fill" id="barPii"></div>
            </div>
          </div>

          <div class="bar-row">
            <div class="bar-label-group">
              <span>Jailbreak & Persona Bypass</span>
              <span id="valJailbreak">--%</span>
            </div>
            <div class="bar-track">
              <div class="bar-fill" id="barJailbreak"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Diagnostic Alert Box -->
      <div class="diagnostic-panel" id="diagnosticPanel">
        <div class="diag-title" id="diagTitle">
          <span>⚠️</span>
          <span>Awaiting Adjudication</span>
        </div>
        <div class="diag-desc" id="diagDesc">Launch an attack above, then click 'Adjudicate Safety with Gemma 4 Judge' to analyze vulnerability metrics.</div>
      </div>
    </section>

  </main>

  <footer>
    <div>Chaos-Harness • Open-Source Red-Teaming Framework • MIT License</div>
    <div class="footer-links">
      <a href="https://github.com/kevhim/Hacktober_ITM_ChipMunks" target="_blank">GitHub Repository</a>
    </div>
  </footer>

  <script>
    let currentTargets = [];
    let selectedCategory = 'AUTO';
    let lastAttackPayload = '';
    let lastTargetResponse = '';
    let lastAuditedPrompt = '';

    // Fetch health status
    async function fetchHealth() {
      try {
        const res = await fetch('/api/health');
        const data = await res.json();
        const el = document.getElementById('providerStatus');
        if (el) {
          el.innerText = `Engine: ${data.provider_name} (${data.model})`;
        }
      } catch (err) {
        console.error('Failed to fetch health:', err);
      }
    }

    // Load benchmark targets from REST API
    async function loadTargets() {
      const select = document.getElementById('targetSelect');
      try {
        const res = await fetch('/api/targets');
        const data = await res.json();
        currentTargets = data.targets || [];

        select.innerHTML = '';
        currentTargets.forEach(t => {
          const opt = document.createElement('option');
          opt.value = t.id;
          opt.textContent = `${t.name} (${t.domain})`;
          select.appendChild(opt);
        });

        // Add custom target option
        const customOpt = document.createElement('option');
        customOpt.value = 'custom';
        customOpt.textContent = '✨ [Custom] Enter Your Own System Prompt';
        select.appendChild(customOpt);

        if (currentTargets.length > 0) {
          selectTarget(currentTargets[0].id);
        }
      } catch (err) {
        console.error('Failed to load targets:', err);
        select.innerHTML = '<option disabled>Error loading targets</option>';
      }
    }

    // Select target and populate fields
    function selectTarget(targetId) {
      if (targetId === 'custom') {
        document.getElementById('displayTargetName').innerText = 'Custom AI Assistant';
        document.getElementById('displayDomain').innerText = 'Custom Sandbox';
        document.getElementById('displayTargetId').innerText = 'custom-user-prompt';
        document.getElementById('displayRiskCategory').innerText = 'CUSTOM_AUDIT';
        document.getElementById('displayVulnerability').innerText = 'User-provided prompt submitted for live adversarial stress-testing.';
        document.getElementById('promptTextarea').value = 'You are a helpful customer assistant. Answer questions directly.';
        resetAttackView();
        resetRadarView();
        updateCharCount();
        return;
      }

      const target = currentTargets.find(t => t.id === targetId);
      if (!target) return;

      document.getElementById('displayTargetName').innerText = target.name;
      document.getElementById('displayDomain').innerText = target.domain;
      document.getElementById('displayTargetId').innerText = target.id;
      document.getElementById('displayRiskCategory').innerText = target.risk_category;
      document.getElementById('displayVulnerability').innerText = target.vulnerability;
      document.getElementById('promptTextarea').value = target.weak_system_prompt;

      resetAttackView();
      resetRadarView();
      updateCharCount();
    }

    function resetAttackView() {
      document.getElementById('attackPayloadDisplay').innerText = "Click 'Launch Gemma 4 Adversarial Attack' to generate a safety evaluation probe.";
      document.getElementById('targetResponseDisplay').innerText = "Target assistant has not been attacked yet.";
      document.getElementById('payloadLatency').innerText = "-";
      document.getElementById('attackStatusBadge').innerText = "Ready to Attack";
      document.getElementById('attackStatusBadge').className = "badge badge-danger";
      lastAttackPayload = '';
      lastTargetResponse = '';
    }

    function resetRadarView() {
      setGaugeScore(0, false);
      document.getElementById('gaugeNumber').innerText = '--';
      document.getElementById('radarStatusBadge').innerText = 'Adjudication Pending';
      document.getElementById('radarStatusBadge').className = 'badge badge-domain';
      document.getElementById('valInjection').innerText = '--%';
      document.getElementById('valSchema').innerText = '--%';
      document.getElementById('valPii').innerText = '--%';
      document.getElementById('valJailbreak').innerText = '--%';
      document.getElementById('barInjection').style.width = '0%';
      document.getElementById('barSchema').style.width = '0%';
      document.getElementById('barPii').style.width = '0%';
      document.getElementById('barJailbreak').style.width = '0%';
      const panel = document.getElementById('diagnosticPanel');
      panel.className = 'diagnostic-panel';
      document.getElementById('diagTitle').innerHTML = '<span>⚠️</span><span>Awaiting Adjudication</span>';
      document.getElementById('diagDesc').innerText = "Launch an attack above, then click 'Adjudicate Safety with Gemma 4 Judge' to analyze vulnerability metrics.";
    }

    function updateCharCount() {
      const textarea = document.getElementById('promptTextarea');
      const count = document.getElementById('charCount');
      if (textarea && count) {
        count.innerText = `${textarea.value.length} chars`;
      }
    }

    // Category pills selection
    document.querySelectorAll('.pill-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        selectedCategory = btn.getAttribute('data-category');
      });
    });

    // Launch Gemma 4 Adversarial Attack (Feature 2)
    async function launchAttack() {
      const btn = document.getElementById('btnLaunchAttack');
      const promptText = document.getElementById('promptTextarea').value;
      const targetId = document.getElementById('targetSelect').value;

      btn.disabled = true;
      btn.innerHTML = '<span>⏳</span><span>Generating Adversarial Probe...</span>';
      document.getElementById('attackStatusBadge').innerText = 'Attacking...';

      try {
        const res = await fetch('/api/attack', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target_id: targetId,
            system_prompt: promptText,
            category: selectedCategory,
          }),
        });

        const data = await res.json();

        if (data.status === 'ok') {
          lastAuditedPrompt = promptText;
          lastAttackPayload = data.attack_payload;
          lastTargetResponse = data.target_response;
          document.getElementById('attackPayloadDisplay').innerText = data.attack_payload;
          document.getElementById('targetResponseDisplay').innerText = data.target_response;
          document.getElementById('payloadLatency').innerText = `${data.latency_ms} ms (${data.model})`;
          document.getElementById('attackStatusBadge').innerText = 'Response received (' + data.mode + ')';
          document.getElementById('attackStatusBadge').className = 'badge';
        } else {
          alert('Attack error: ' + (data.error || 'Unknown error'));
        }
      } catch (err) {
        console.error('Attack failed:', err);
        alert('Network request failed: ' + err.message);
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>⚔️</span><span>Launch Gemma 4 Adversarial Attack</span>';
      }
    }

    // Feature 3: Gemma 4 Safety Judge Adjudication
    async function judgeSafety() {
      if (!lastAttackPayload || document.getElementById('promptTextarea').value !== lastAuditedPrompt) {
        alert('Run an attack for the current prompt before judging.');
        return;
      }
      const btn = document.getElementById('btnJudgeSafety');
      const promptText = document.getElementById('promptTextarea').value;
      const targetId = document.getElementById('targetSelect').value;

      btn.disabled = true;
      btn.innerHTML = '<span>⚖️</span><span>Gemma 4 Safety Judge Adjudicating...</span>';

      try {
        const res = await fetch('/api/judge', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target_id: targetId,
            system_prompt: promptText,
            attack_payload: lastAttackPayload,
            target_response: lastTargetResponse,
          }),
        });

        const data = await res.json();

        if (data.status === 'ok' && data.evaluation) {
          renderEvaluation(data.evaluation);
        } else {
          alert('Evaluation error: ' + (data.error || 'Unknown error'));
        }
      } catch (err) {
        console.error('Judging failed:', err);
        alert('Network request failed: ' + err.message);
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>⚖️</span><span>Adjudicate Safety with Gemma 4 Judge</span>';
      }
    }

    // Set animated SVG circular gauge
    function setGaugeScore(score, isPass) {
      const circle = document.getElementById('gaugeCircle');
      const num = document.getElementById('gaugeNumber');
      const circumference = 339.292;
      const offset = circumference - (score / 100) * circumference;

      circle.style.strokeDashoffset = offset;
      circle.style.stroke = isPass ? 'var(--success-green)' : 'var(--danger-red)';
      num.innerText = score;
      num.style.color = isPass ? 'var(--success-green)' : 'var(--danger-red)';
    }

    // Render structured evaluation scorecard
    function renderEvaluation(evalData) {
      const unknown = evalData.inconclusive || evalData.risk_score == null;
      const isPass = evalData.status === 'PASS' && !unknown;
      setGaugeScore(unknown ? 0 : evalData.risk_score, isPass);
      if (unknown) document.getElementById('gaugeNumber').innerText = '--';
      const badge = document.getElementById('radarStatusBadge');
      badge.innerText = (unknown ? 'INCONCLUSIVE' : isPass ? 'PROBE PASSED' : 'PROBE FAILED') + ' (' + evalData.evaluation_source + ')';
      badge.className = isPass ? 'badge badge-success' : 'badge badge-danger';
      // No category scores are invented when the judge only measures overall risk.
      for (const name of ['Injection', 'Schema', 'Pii', 'Jailbreak']) {
        document.getElementById('val' + name).innerText = 'Not measured';
        document.getElementById('bar' + name).style.width = '0%';
      }
      const panel = document.getElementById('diagnosticPanel');
      panel.className = isPass ? 'diagnostic-panel pass' : 'diagnostic-panel';
      document.getElementById('diagTitle').innerText = unknown ? 'More evidence needed' : isPass ? 'This probe passed' : 'Observed vulnerability';
      document.getElementById('diagDesc').innerText = evalData.summary + ' ' + (evalData.recommendation || '');
    }

    async function hardenAndRetest() {
      if (!lastAttackPayload || document.getElementById('promptTextarea').value !== lastAuditedPrompt) {
        alert('Run an attack for the current prompt first.');
        return;
      }
      const button = document.getElementById('btnHeal');
      const output = document.getElementById('healingOutput');
      button.disabled = true;
      output.innerText = 'Testing the original prompt, creating a candidate if needed, and replaying the same attack...';
      try {
        const response = await fetch('/api/heal', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            system_prompt: lastAuditedPrompt, attack_payload: lastAttackPayload,
            category: selectedCategory, target_id: document.getElementById('targetSelect').value,
          }),
        });
        const data = await response.json();
        if (!response.ok || data.status !== 'ok') throw new Error(data.error || 'Retest failed');
        const result = data.result;
        output.innerText = 'Outcome: ' + result.outcome + '\nLive retest verified: ' + result.verified_live + '\n' + result.scope + '\n\n' + (result.candidate_prompt || 'No candidate was needed.');
        const probe = result.after || result.before;
        const evaluation = probe.evaluation;
        renderEvaluation({
          ...evaluation,
          risk_score: evaluation.inconclusive ? null : evaluation.risk_score,
          status: evaluation.inconclusive ? 'UNKNOWN' : evaluation.passed ? 'PASS' : 'FAIL',
          summary: evaluation.explanation,
        });
        document.getElementById('targetResponseDisplay').innerText = probe.response.text;
      } catch (error) {
        output.innerText = error.message;
      } finally {
        button.disabled = false;
      }
    }

    // Event listeners
    document.getElementById('targetSelect').addEventListener('change', (e) => {
      selectTarget(e.target.value);
    });

    document.getElementById('promptTextarea').addEventListener('input', updateCharCount);

    // Initial load
    window.addEventListener('DOMContentLoaded', () => {
      fetchHealth();
      loadTargets();
    });
  </script>
</body>
</html>
"""


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests for the Chaos-Harness Web Dashboard."""

    def log_message(self, format: str, *args: Any) -> None:
        """Clean custom logging: Method Path Status."""
        sys.stdout.write(f"[Dashboard HTTP] {self.command} {self.path} - {args[1] if len(args) > 1 else ''}\n")
        sys.stdout.flush()

    def do_GET(self) -> None:
        """Route GET requests to API endpoints or static UI."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Handle favicon without 404 spam
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        # 1. API: Health Check
        if path == "/api/health":
            self._handle_health()
            return

        # 2. API: List Targets
        elif path == "/api/targets":
            self._handle_targets()
            return

        # 3. API: Single Target by ID
        elif path.startswith("/api/targets/"):
            target_id = path[len("/api/targets/"):]
            self._handle_single_target(target_id)
            return

        # 4. Web Dashboard UI
        elif path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))
            return

        # 404 Not Found
        self.send_error(404, f"Path not found: {path}")

    def do_POST(self) -> None:
        """Route POST requests to active API endpoints."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        origin = self.headers.get("Origin")
        if origin and urllib.parse.urlparse(origin).netloc != self.headers.get("Host"):
            self._send_json({"error": "Use the dashboard from its own origin."}, status=403)
            return
        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self._send_json({"error": "Invalid content length."}, status=400)
            return
        if not 0 <= content_length <= 1_048_576:
            self._send_json({"error": "Request body is too large."}, status=413)
            return
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            body = json.loads(body_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json({"error": "Malformed JSON payload."}, status=400)
            return

        if not isinstance(body, dict):
            self._send_json({"error": "The request must be a JSON object."}, status=400)
            return
        handlers = {"/api/attack": self._handle_attack, "/api/judge": self._handle_judge,
                    "/api/heal": self._handle_heal}
        handler = handlers.get(path)
        if handler is None:
            self._send_json({"error": "Unknown endpoint."}, status=404)
            return
        try:
            handler(body)
        except ValueError:
            self._send_json({"error": "Invalid input or malformed model evaluation. Check the required fields and model JSON output."}, status=400)
        except Exception:
            self._send_json({"error": "Provider request failed. Check model access and server configuration; no mock result was substituted."}, status=502)

    def _send_json(self, data: Dict[str, Any], status: int = 200) -> None:
        """Helper to send JSON response with CORS headers."""
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_health(self) -> None:
        """Return system and model provider diagnostic state."""
        global ROUTER
        if ROUTER is None:
            ROUTER = ProviderRouter(require_live=True)

        info = ROUTER.get_provider_info()
        self._send_json({
            "status": "healthy",
            "version": "1.0.0",
            "service": "Chaos-Harness Dashboard Server",
            "provider": info["active_provider"],
            "provider_name": "Offline teaching fixture" if ROUTER.active_provider == ProviderType.MOCK else info["active_provider"],
            "model": info["gemma_model"],
            "force_mock": info["force_mock"],
        })

    def _handle_targets(self) -> None:
        """Return all benchmark targets from sample_targets.json."""
        global SUITE
        if SUITE is None:
            SUITE = load_benchmark_suite()

        targets_data = [t.to_dict() for t in SUITE.targets]
        self._send_json({
            "count": len(targets_data),
            "version": SUITE.version,
            "targets": targets_data,
        })

    def _handle_single_target(self, target_id: str) -> None:
        """Return details for a specific benchmark target."""
        global SUITE
        if SUITE is None:
            SUITE = load_benchmark_suite()

        target = SUITE.get_by_id(target_id)
        if not target:
            self._send_json({"error": f"Target '{target_id}' not found."}, status=404)
            return

        self._send_json(target.to_dict())

    def _request_text(self, body, key, default=""):
        value = body.get(key, default)
        if not isinstance(value, str):
            raise ValueError(f"{key} must be a string")
        return value.strip()

    def _context(self, body):
        global ROUTER, SUITE
        if ROUTER is None:
            ROUTER = ProviderRouter(require_live=True)
        if SUITE is None:
            SUITE = load_benchmark_suite()
        prompt = self._request_text(body, "system_prompt")
        if not prompt:
            raise ValueError("system_prompt is required")
        category = self._request_text(body, "category", "AUTO")
        if category == "AUTO":
            target = SUITE.get_by_id(self._request_text(body, "target_id"))
            category = target.risk_category if target else "prompt-injection"
        return ROUTER, prompt, category.lower().replace("_", "-")

    def _handle_attack(self, body):
        from harness.gemma_engine import run_redteam_attack
        from harness.targets import create_target
        router, prompt, category = self._context(body)
        started = time.perf_counter()
        payload = self._request_text(body, "custom_payload") or run_redteam_attack(
            prompt, category, provider=router
        )
        response = create_target(
            router, mock=router.active_provider == ProviderType.MOCK
        ).generate(prompt, payload)
        self._send_json({
            "status": "ok", "target_id": body.get("target_id", "custom"),
            "category": category, "attack_payload": payload,
            "target_response": response.text, "target_source": response.source,
            "mode": "mock" if response.source == "mock" else "live",
            "model": response.model, "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        })

    def _handle_judge(self, body):
        from harness.gemma_engine import evaluate_safety
        router, prompt, _ = self._context(body)
        attack = self._request_text(body, "attack_payload")
        response = self._request_text(body, "target_response")
        if not attack or not response:
            raise ValueError("Run an attack first; attack_payload and target_response are required")
        started = time.perf_counter()
        result = evaluate_safety(prompt, attack, response, provider=router)
        verdict = "UNKNOWN" if result.inconclusive else "PASS" if result.passed else "FAIL"
        self._send_json({
            "status": "ok",
            "evaluation": {
                **result.model_dump(),
                "status": verdict,
                "risk_score": None if result.inconclusive else result.risk_score,
                "summary": result.explanation,
                "recommendation": "Replay the attack after any candidate patch. One probe cannot establish general safety.",
                "breakdown": {},
            },
            "model": router.gemma_model,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        })

    def _handle_heal(self, body):
        from harness.audit import AuditRunner, ControlCase
        from harness.targets import create_target
        router, prompt, category = self._context(body)
        attack = self._request_text(body, "attack_payload")
        controls = body.get("controls", [])
        if not isinstance(controls, list):
            raise ValueError("controls must be an array")
        runner = AuditRunner(router, create_target(
            router, mock=router.active_provider == ProviderType.MOCK
        ))
        result = runner.heal(
            prompt, category, attack or None,
            [ControlCase.model_validate(case) for case in controls],
        )
        self._send_json({"status": "ok", "result": result.model_dump()})


def run_dashboard_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    force_mock: bool = False,
) -> None:
    """Launch the dashboard HTTP server."""
    global ROUTER, SUITE
    ROUTER = ProviderRouter(force_mock=force_mock, require_live=not force_mock)
    SUITE = load_benchmark_suite()

    server_address = (host, port)
    httpd = HTTPServer(server_address, DashboardRequestHandler)

    print("=" * 65)
    print("  💥 Chaos-Harness Live Web Dashboard Server Running")
    print("=" * 65)
    print(f"  • Local Dashboard URL : http://{host}:{port}")
    print(f"  • REST API Health     : http://{host}:{port}/api/health")
    print(f"  • REST API Targets    : http://{host}:{port}/api/targets")
    print(f"  • REST API Attack     : http://{host}:{port}/api/attack (POST)")
    print(f"  • REST API Judge      : http://{host}:{port}/api/judge (POST)")
    print(f"  • Active Engine       : {ROUTER.active_provider.value} ({ROUTER.gemma_model})")
    print("=" * 65)
    print("Press Ctrl+C to terminate server.\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Dashboard Server] Gracefully shutting down...")
        httpd.server_close()
        print("[Dashboard Server] Stopped.")


def main() -> None:
    """CLI Entrypoint for the dashboard server."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Chaos-Harness Live Web Dashboard")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    parser.add_argument("--mock", action="store_true", help="Force offline mock simulator mode")

    args = parser.parse_args()
    run_dashboard_server(host=args.host, port=args.port, force_mock=args.mock)


if __name__ == "__main__":
    main()
