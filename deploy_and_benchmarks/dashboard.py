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
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

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

    /* Attack Studio Controls */
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

    /* Auto-Hardener Button & Diff Styles */
    .btn-harden {
      background: linear-gradient(135deg, #10b981, #059669);
      color: #ffffff;
      border: none;
      padding: 0.9rem 1.5rem;
      border-radius: var(--radius-sm);
      font-weight: 600;
      font-size: 1rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.6rem;
      transition: all 0.2s ease;
      box-shadow: 0 4px 18px rgba(16, 185, 129, 0.35);
      width: 100%;
    }

    .btn-harden:hover {
      transform: translateY(-1px);
      box-shadow: 0 6px 24px rgba(16, 185, 129, 0.5);
      filter: brightness(1.08);
    }

    .btn-harden:disabled {
      opacity: 0.6;
      cursor: not-allowed;
      transform: none;
    }

    /* Feature 5: Verification & Victory Styles */
    .btn-verify {
      background: linear-gradient(135deg, #3b82f6, #1d4ed8);
      color: #ffffff;
      border: none;
      padding: 0.95rem 1.5rem;
      border-radius: var(--radius-sm);
      font-weight: 600;
      font-size: 1rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.6rem;
      transition: all 0.2s ease;
      box-shadow: 0 4px 18px rgba(59, 130, 246, 0.35);
      width: 100%;
    }

    .btn-verify:hover {
      transform: translateY(-1px);
      box-shadow: 0 6px 24px rgba(59, 130, 246, 0.5);
      filter: brightness(1.08);
    }

    .btn-verify:disabled {
      opacity: 0.6;
      cursor: not-allowed;
      transform: none;
    }

    .comparison-container {
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }

    .comparison-table {
      width: 100%;
      border-collapse: collapse;
      border-radius: var(--radius-sm);
      overflow: hidden;
      font-size: 0.85rem;
      border: 1px solid var(--border-color);
    }

    .comparison-table th {
      background: rgba(0, 0, 0, 0.35);
      padding: 0.75rem 1rem;
      text-align: left;
      font-size: 0.75rem;
      color: var(--text-dim);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .comparison-table td {
      padding: 0.85rem 1rem;
      border-top: 1px solid var(--border-color);
    }

    .export-actions {
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
    }

    .btn-export {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 0.65rem 1.25rem;
      border-radius: var(--radius-sm);
      font-size: 0.85rem;
      font-weight: 500;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      transition: all 0.2s ease;
    }

    .btn-export:hover {
      background: rgba(255, 255, 255, 0.1);
      border-color: var(--primary-blue);
      color: #93c5fd;
    }

    .btn-apply {
      background: rgba(16, 185, 129, 0.15);
      color: #6ee7b7;
      border: 1px solid rgba(16, 185, 129, 0.4);
      padding: 0.6rem 1.25rem;
      border-radius: var(--radius-sm);
      font-weight: 600;
      font-size: 0.85rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      transition: all 0.2s ease;
      margin-top: 0.5rem;
    }

    .btn-apply:hover {
      background: rgba(16, 185, 129, 0.25);
      border-color: var(--success-green);
    }

    .diff-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.25rem;
    }

    @media (max-width: 900px) {
      .diff-grid {
        grid-template-columns: 1fr;
      }
    }

    .diff-column {
      background: rgba(0, 0, 0, 0.25);
      border-radius: var(--radius-sm);
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.6rem;
    }

    .diff-column.vulnerable {
      border: 1px solid rgba(239, 68, 68, 0.35);
      background: rgba(239, 68, 68, 0.04);
    }

    .diff-column.hardened {
      border: 1px solid rgba(16, 185, 129, 0.45);
      background: rgba(16, 185, 129, 0.04);
      box-shadow: 0 0 20px rgba(16, 185, 129, 0.08);
    }

    .diff-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    .diff-content {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      line-height: 1.5;
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 220px;
      overflow-y: auto;
      padding: 0.75rem;
      background: rgba(0, 0, 0, 0.3);
      border-radius: var(--radius-sm);
    }

    .diff-column.vulnerable .diff-content {
      color: #fca5a5;
    }

    .diff-column.hardened .diff-content {
      color: #6ee7b7;
    }

    .rules-container {
      background: rgba(0, 0, 0, 0.2);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-sm);
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.6rem;
    }

    .rules-title {
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--text-main);
    }

    .rules-list {
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
    }

    .rule-item {
      font-size: 0.8rem;
      color: #94a3b8;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }

    .rule-item::before {
      content: "✓";
      color: var(--success-green);
      font-weight: bold;
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

    /* Safety Radar & Risk Gauges */
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
        <span id="providerStatus">Engine: Gemma 4 (gemma-4-27b-it)</span>
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

    <!-- Feature 4: Autonomous Prompt Auto-Hardener & Side-by-Side Diff -->
    <section class="card" id="autoHardenerCard">
      <div class="card-header">
        <div class="card-title">
          <span>🛡️</span>
          <span>Autonomous Prompt Auto-Hardener & Diff Inspector</span>
        </div>
        <span class="badge badge-success" id="hardenerStatusBadge">Self-Healing Ready</span>
      </div>

      <!-- Action Button -->
      <button id="btnAutoHarden" class="btn-harden" onclick="autoHardenPrompt()">
        <span>🛡️</span>
        <span>Auto-Harden System Prompt with Gemma 4</span>
      </button>

      <!-- Side-by-Side Diff Grid -->
      <div class="diff-grid" id="diffGrid">
        <!-- Left: Vulnerable Prompt -->
        <div class="diff-column vulnerable">
          <div class="diff-header">
            <span>⚠️ Original system prompt</span>
            <span class="badge">Baseline</span>
          </div>
          <div class="diff-content" id="diffOriginalPrompt">Click 'Auto-Harden System Prompt with Gemma 4' to synthesize defense-in-depth rules.</div>
        </div>

        <!-- Right: Hardened Directives -->
        <div class="diff-column hardened">
          <div class="diff-header">
            <span>🛡️ Gemma 4 Hardened Directives (Defensive)</span>
            <span class="badge badge-success" id="hardenedBadge">Requires retest</span>
          </div>
          <div class="diff-content" id="diffHardenedPrompt">Hardened directives will be synthesized and displayed here.</div>
        </div>
      </div>

      <!-- Defensive Rules Added Checklist -->
      <div class="rules-container" id="rulesContainer" style="display: none;">
        <div class="rules-title">🛡️ Candidate review checklist:</div>
        <div class="rules-list" id="rulesList"></div>
        <button id="btnApplyHardened" class="btn-apply" onclick="applyHardenedPrompt()">
          <span>📥 Apply Hardened Directives to Active Prompt</span>
        </button>
      </div>
    </section>

    <!-- Feature 5: Dual-Loop Verification & Victory Showcase -->
    <section class="card" id="verificationCard">
      <div class="card-header">
        <div class="card-title">
          <span>🏆</span>
          <span>Attack replay & retest comparison</span>
        </div>
        <span class="badge badge-domain" id="verifyStatusBadge">Verification Pending</span>
      </div>

      <!-- Action Button -->
      <button id="btnVerifyHardened" class="btn-verify" onclick="verifyHardenedPrompt()">
        <span>🏆</span>
        <span>Re-Test Attack on Hardened Assistant (Dual-Loop Close)</span>
      </button>

      <!-- Deflection Response Box -->
      <div class="response-box" id="hardenedResponseBox" style="display: none; border-color: rgba(16, 185, 129, 0.4); background: rgba(16, 185, 129, 0.05);">
        <div class="box-header">
          <span style="color: #6ee7b7;">🛡️ Candidate target response</span>
          <span class="badge" id="deflectionBadge">Pending</span>
        </div>
        <div class="response-display" id="hardenedResponseDisplay" style="color: #6ee7b7;"></div>
      </div>

      <!-- Verification Comparison Table -->
      <div class="comparison-container" id="comparisonContainer" style="display: none;">
        <table class="comparison-table">
          <thead>
            <tr>
              <th>Evaluation Phase</th>
              <th>System Status</th>
              <th>Risk Score</th>
              <th>Safety Verdict</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>1. Pre-Hardening</td>
              <td><span class="badge badge-danger">Baseline prompt</span></td>
              <td style="color: var(--danger-red); font-weight: bold;" id="tablePreScore">--</td>
              <td><span class="badge" id="tablePreVerdict">Pending</span></td>
            </tr>
            <tr style="background: rgba(16, 185, 129, 0.08);">
              <td>2. Post-Hardening</td>
              <td><span class="badge badge-success">Candidate prompt</span></td>
              <td style="color: var(--success-green); font-weight: bold;" id="tablePostScore">--</td>
              <td><span class="badge" id="tablePostVerdict">Pending</span></td>
            </tr>
          </tbody>
        </table>

        <!-- 1-Click Export Actions -->
        <div class="export-actions">
          <button class="btn-export" id="btnCopyReport" onclick="copyMarkdownReport()">
            <span>📋 Copy Markdown Audit Report</span>
          </button>
          <button class="btn-export" onclick="downloadJsonReport()">
            <span>💾 Download JSON Audit Report</span>
          </button>
        </div>
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
    let lastHardenedPrompt = '';
    let lastHardenedResponse = '';
    let preScore = null;
    let postScore = null;
    let preVerdict = 'Pending';
    let lastAuditId = '';
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
        resetHardenerView();
        resetVerificationView();
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
      resetHardenerView();
      resetVerificationView();
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
      lastAuditId = '';
      preScore = null;
      preVerdict = 'Pending';
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

    function resetHardenerView() {
      document.getElementById('diffOriginalPrompt').innerText = "Click 'Auto-Harden System Prompt with Gemma 4' to synthesize defense-in-depth rules.";
      document.getElementById('diffHardenedPrompt').innerText = "Hardened directives will be synthesized and displayed here.";
      document.getElementById('rulesContainer').style.display = 'none';
      document.getElementById('rulesList').innerHTML = '';
      lastHardenedPrompt = '';
    }

    function resetVerificationView() {
      document.getElementById('verifyStatusBadge').innerText = "Verification Pending";
      document.getElementById('verifyStatusBadge').className = "badge badge-domain";
      document.getElementById('hardenedResponseBox').style.display = "none";
      document.getElementById('comparisonContainer').style.display = "none";
      lastHardenedResponse = '';
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
      resetAttackView();
      resetHardenerView();
      resetVerificationView();
      resetRadarView();
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
            audit_id: lastAuditId,
            target_id: targetId,
            system_prompt: promptText,
            category: selectedCategory,
          }),
        });

        const data = await res.json();

        if (data.status === 'ok') {
          lastAuditId = data.audit_id;
          lastAuditedPrompt = promptText;
          lastAttackPayload = data.attack_payload;
          lastTargetResponse = data.target_response;
          document.getElementById('attackPayloadDisplay').innerText = data.attack_payload;
          document.getElementById('targetResponseDisplay').innerText = data.target_response;
          document.getElementById('payloadLatency').innerText = `${data.latency_ms} ms (${data.model})`;
          document.getElementById('attackStatusBadge').innerText = 'Response received (' + data.mode + ')';
          document.getElementById('attackStatusBadge').className = 'badge badge-danger';
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
      if (!lastAuditId || document.getElementById('promptTextarea').value !== lastAuditedPrompt) {
        alert('Run an attack for the current prompt first.');
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
            audit_id: lastAuditId,
            target_id: targetId,
            system_prompt: promptText,
            attack_payload: lastAttackPayload,
            target_response: lastTargetResponse,
          }),
        });

        const data = await res.json();

        if (data.status === 'ok' && data.evaluation) {
          preScore = data.evaluation.risk_score ?? null;
          preVerdict = data.evaluation.status;
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

    // Feature 4: Gemma 4 Autonomous Auto-Hardener
    async function autoHardenPrompt() {
      if (!lastAuditId || document.getElementById('promptTextarea').value !== lastAuditedPrompt) {
        alert('Run an attack for the current prompt first.');
        return;
      }
      const btn = document.getElementById('btnAutoHarden');
      const promptText = document.getElementById('promptTextarea').value;
      const targetId = document.getElementById('targetSelect').value;

      btn.disabled = true;
      btn.innerHTML = '<span>🛡️</span><span>Gemma 4 Synthesizing Defensive Directives...</span>';

      try {
        const res = await fetch('/api/harden', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            audit_id: lastAuditId,
            target_id: targetId,
            system_prompt: promptText,
            vulnerability: selectedCategory,
            attack_payload: lastAttackPayload,
          }),
        });

        const data = await res.json();

        if (data.status === 'ok') {
          lastHardenedPrompt = data.hardened_prompt;
          document.getElementById('diffOriginalPrompt').innerText = data.original_prompt;
          document.getElementById('diffHardenedPrompt').innerText = data.hardened_prompt;

          // Render defensive rules checklist
          const rulesList = document.getElementById('rulesList');
          rulesList.innerHTML = '';
          (data.defensive_rules || []).forEach(r => {
            const div = document.createElement('div');
            div.className = 'rule-item';
            div.innerText = r;
            rulesList.appendChild(div);
          });
          document.getElementById('rulesContainer').style.display = 'flex';
        } else {
          alert('Auto-hardening error: ' + (data.error || 'Unknown error'));
        }
      } catch (err) {
        console.error('Auto-hardening failed:', err);
        alert('Network request failed: ' + err.message);
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>🛡️</span><span>Auto-Harden System Prompt with Gemma 4</span>';
      }
    }

    // Apply hardened directives into the main system prompt textarea
    function applyHardenedPrompt() {
      if (lastHardenedPrompt) {
        document.getElementById('promptTextarea').value = lastHardenedPrompt;
        updateCharCount();
        const alertBtn = document.getElementById('btnApplyHardened');
        alertBtn.innerHTML = '<span>✅ Hardened Directives Applied to Active Prompt!</span>';
        setTimeout(() => {
          alertBtn.innerHTML = '<span>📥 Apply Hardened Directives to Active Prompt</span>';
        }, 2000);
      }
    }

    // Feature 5: Dual-Loop Verification
    async function verifyHardenedPrompt() {
      if (!lastAuditId || !lastHardenedPrompt) {
        alert('Run an attack and generate a candidate prompt first.');
        return;
      }
      const button = document.getElementById('btnVerifyHardened');
      button.disabled = true;
      try {
        const response = await fetch('/api/verify', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            audit_id: lastAuditId,
            hardened_prompt: lastHardenedPrompt,
            attack_payload: lastAttackPayload,
          }),
        });
        const data = await response.json();
        if (!response.ok || data.status !== 'ok') throw new Error(data.error || 'Retest failed');
        lastHardenedResponse = data.hardened_response;
        postScore = data.evaluation.risk_score;
        document.getElementById('hardenedResponseDisplay').innerText = lastHardenedResponse;
        document.getElementById('hardenedResponseBox').style.display = 'flex';
        renderEvaluation(data.evaluation);
        document.getElementById('tablePreScore').innerText = preScore == null ? 'N/A' : preScore + ' / 100';
        document.getElementById('tablePostScore').innerText = postScore == null ? 'N/A' : postScore + ' / 100';
        document.getElementById('tablePreVerdict').innerText = preVerdict;
        document.getElementById('tablePostVerdict').innerText = data.evaluation.status;
        document.getElementById('tablePostScore').style.color = data.deflected ? 'var(--success-green)' : 'var(--danger-red)';
        document.getElementById('tablePostVerdict').className = data.deflected ? 'badge badge-success' : 'badge badge-danger';
        document.getElementById('comparisonContainer').style.display = 'flex';
        const badge = document.getElementById('verifyStatusBadge');
        badge.innerText = data.outcome + ' (' + data.evaluation.evaluation_source + ')';
        badge.className = data.deflected ? 'badge badge-success' : 'badge badge-danger';
        document.getElementById('deflectionBadge').innerText = data.evaluation.status;
      } catch (error) {
        alert(error.message);
      } finally {
        button.disabled = false;
      }
    }

    // Copy Markdown Report to Clipboard
    async function copyMarkdownReport() {
      const targetName = document.getElementById('displayTargetName').innerText;
      const domain = document.getElementById('displayDomain').innerText;
      const promptText = document.getElementById('promptTextarea').value;

      try {
        const res = await fetch('/api/export', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            audit_id: lastAuditId,
            target_name: targetName,
            domain: domain,
            pre_score: preScore,
            post_score: postScore,
            attack_payload: lastAttackPayload,
            vulnerable_response: lastTargetResponse,
            hardened_response: lastHardenedResponse,
            hardened_prompt: lastHardenedPrompt || promptText,
          }),
        });
        const data = await res.json();
        if (data.status === 'ok') {
          await navigator.clipboard.writeText(data.markdown_report);
          const btn = document.getElementById('btnCopyReport');
          btn.innerHTML = '<span>✅ Copied Markdown Audit Report!</span>';
          setTimeout(() => {
            btn.innerHTML = '<span>📋 Copy Markdown Audit Report</span>';
          }, 2000);
        }
      } catch (err) {
        console.error('Export failed:', err);
      }
    }

    // Download JSON Report Certificate
    async function downloadJsonReport() {
      const targetName = document.getElementById('displayTargetName').innerText;
      const domain = document.getElementById('displayDomain').innerText;
      const promptText = document.getElementById('promptTextarea').value;

      try {
        const res = await fetch('/api/export', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            audit_id: lastAuditId,
            target_name: targetName,
            domain: domain,
            pre_score: preScore,
            post_score: postScore,
            attack_payload: lastAttackPayload,
            vulnerable_response: lastTargetResponse,
            hardened_response: lastHardenedResponse,
            hardened_prompt: lastHardenedPrompt || promptText,
          }),
        });
        const data = await res.json();
        if (data.status === 'ok') {
          const blob = new Blob([data.json_report], { type: 'application/json' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `chaos_harness_audit_${Date.now()}.json`;
          a.click();
          URL.revokeObjectURL(url);
        }
      } catch (err) {
        console.error('Download failed:', err);
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
      const passed = evalData.status === 'PASS' && !unknown;
      setGaugeScore(unknown ? 0 : evalData.risk_score, passed);
      if (unknown) document.getElementById('gaugeNumber').innerText = '--';
      const badge = document.getElementById('radarStatusBadge');
      badge.innerText = (unknown ? 'INCONCLUSIVE' : passed ? 'PROBE PASSED' : 'PROBE FAILED') + ' (' + evalData.evaluation_source + ')';
      badge.className = passed ? 'badge badge-success' : 'badge badge-danger';
      for (const name of ['Injection', 'Schema', 'Pii', 'Jailbreak']) {
        document.getElementById('val' + name).innerText = 'Not measured';
        document.getElementById('bar' + name).style.width = '0%';
      }
      document.getElementById('diagnosticPanel').className = passed ? 'diagnostic-panel pass' : 'diagnostic-panel';
      document.getElementById('diagTitle').innerText = unknown ? 'More evidence needed' : passed ? 'This probe passed' : 'Observed vulnerability';
      document.getElementById('diagDesc').innerText = evalData.summary + ' ' + (evalData.recommendation || '');
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
                    "/api/heal": self._handle_heal, "/api/harden": self._handle_harden,
                    "/api/verify": self._handle_verify, "/api/export": self._handle_export}
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
            "model": info["model"],
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

    def _audits(self):
        if not hasattr(self.server, "audits"):
            self.server.audits = {}
        return self.server.audits

    def _save_audit(self, record):
        records = self._audits()
        if len(records) >= 64:
            records.pop(next(iter(records)))
        audit_id = uuid.uuid4().hex
        records[audit_id] = record
        return audit_id

    def _record(self, body):
        audit_id = self._request_text(body, "audit_id")
        record = self._audits().get(audit_id)
        if record is None:
            raise ValueError("Run an attack in this dashboard session first")
        return audit_id, record

    @staticmethod
    def _evaluation_payload(result):
        return {
            **result.model_dump(),
            "status": "UNKNOWN" if result.inconclusive else "PASS" if result.passed else "FAIL",
            "risk_score": None if result.inconclusive else result.risk_score,
            "summary": result.explanation,
            "recommendation": "One observed probe does not establish general safety.",
            "breakdown": {},
        }

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
        audit_id = self._save_audit({
            "system_prompt": prompt, "category": category, "attack": payload,
            "response": response.model_dump(),
        })
        self._send_json({
            "status": "ok", "audit_id": audit_id, "target_id": body.get("target_id", "custom"),
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
        record = None
        if body.get("audit_id"):
            _, record = self._record(body)
            if (prompt, attack, response) != (record["system_prompt"], record["attack"], record["response"]["text"]):
                raise ValueError("The prompt or response changed; run a new attack")
        if not attack or not response:
            raise ValueError("Run an attack first; attack_payload and target_response are required")
        started = time.perf_counter()
        result = evaluate_safety(prompt, attack, response, provider=router)
        if record is not None:
            record["evaluation"] = result.model_dump()
        self._send_json({
            "status": "ok",
            "evaluation": self._evaluation_payload(result),
            "model": router.model_name,
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
        audit_id = self._save_audit({"result": result.model_dump()})
        self._send_json({"status": "ok", "audit_id": audit_id, "result": result.model_dump()})

    def _handle_harden(self, body):
        from harness.gemma_engine import evaluate_safety
        from harness.hardener import harden_prompt
        router, prompt, category = self._context(body)
        attack = self._request_text(body, "attack_payload")
        record = None
        if body.get("audit_id"):
            _, record = self._record(body)
            if prompt != record["system_prompt"] or attack != record["attack"]:
                raise ValueError("The original prompt or attack changed")
            evaluation = evaluate_safety(prompt, attack, record["response"]["text"], provider=router)
            record["evaluation"] = evaluation.model_dump()
            if evaluation.inconclusive or evaluation.passed:
                raise ValueError("A candidate patch requires a conclusive observed failure")
            explanation = evaluation.explanation
        else:
            explanation = self._request_text(body, "vulnerability", category)
        candidate = harden_prompt(
            prompt, explanation, category, provider=router, attack_prompt=attack,
            target_response=record["response"]["text"] if record else "",
        )
        if record is not None:
            record["candidate_prompt"] = candidate
        target = SUITE.get_by_id(body.get("target_id", ""))
        self._send_json({
            "status": "ok", "original_prompt": prompt, "hardened_prompt": candidate,
            "defensive_rules": target.expected_hardened_rules if target else [],
            "candidate_requires_retest": True, "model": router.model_name,
            "evaluation_source": "mock" if router.active_provider == ProviderType.MOCK else "live",
        })

    def _handle_verify(self, body):
        from harness.audit import AuditRunner, ControlCase, ProbeResult
        from harness.gemma_engine import SafetyEvaluation, evaluate_safety
        from harness.targets import create_target
        audit_id, record = self._record(body)
        router, prompt, _ = self._context({**body, "system_prompt": record["system_prompt"]})
        candidate = self._request_text(body, "hardened_prompt")
        if not candidate or self._request_text(body, "attack_payload") != record["attack"]:
            raise ValueError("A candidate and the original attack payload are required")
        evaluation = SafetyEvaluation.model_validate(record["evaluation"]) if record.get("evaluation") else evaluate_safety(
            prompt, record["attack"], record["response"]["text"], provider=router
        )
        before = ProbeResult(category=record["category"], attack=record["attack"],
                             response=record["response"], evaluation=evaluation)
        controls = body.get("controls", [])
        if not isinstance(controls, list):
            raise ValueError("controls must be an array")
        runner = AuditRunner(router, create_target(router, mock=router.active_provider == ProviderType.MOCK))
        result = runner.retest(prompt, candidate, before, [ControlCase.model_validate(c) for c in controls])
        record["result"] = result.model_dump()
        self._send_json({
            "status": "ok", "audit_id": audit_id,
            "deflected": result.outcome == "retest_passed",
            "verified_live": result.verified_live,
            "hardened_response": result.after.response.text,
            "evaluation": self._evaluation_payload(result.after.evaluation),
            "model": result.after.response.model, "outcome": result.outcome,
        })

    def _handle_export(self, body):
        audit_id, record = self._record(body)
        if "result" not in record:
            raise ValueError("Run a retest before exporting an audit report")
        report = {"audit_id": audit_id, "framework": "Chaos-Harness",
                  "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  **record["result"]}
        serialized = json.dumps(report, indent=2)
        markdown = "# Chaos-Harness observed audit report\n\n" + report["scope"] + "\n\n```json\n" + serialized + "\n```\n"
        self._send_json({"status": "ok", "markdown_report": markdown, "json_report": serialized})


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
