---
name: auto-hardener
description: Automatically rewrites and patches vulnerable AI system prompts with robust defensive guardrails using Google Gemma 4.
version: 1.0.0
license: MIT
tags: [security, red-team, gemma-4]
---

# Automated Prompt Patcher & Self-Healing Guardian (`auto-hardener`)

## Overview
`auto-hardener` is an open-standard Agent Skill (`agentskills.io`) built for **Antigravity** and **DigitalOcean Hermes Agent**. When an AI agent's system prompt fails an adversarial audit or red-team stress test, this skill takes the vulnerable prompt and its diagnostic report, leveraging Google's **Gemma 4** to rewrite, patch, and secure the system prompt with explicit defensive guardrails.

## When to Invoke This Skill
Invoke this skill whenever:
- An adversarial audit (such as `injection-fuzzer`, `schema-breaker`, `pii-leak-prober`, or `hallucination-trap`) flags a system prompt as vulnerable (`passed: false`).
- You want to automatically generate a hardened version of a system prompt before deploying it to production or publishing it to DigitalOcean Hermes.
- Completing an autonomous self-healing remediation loop without manual prompt engineering.

## Input Parameters
| Parameter | Flag | Type | Required | Description |
| :--- | :--- | :--- | :--- | :--- |
| `prompt` | `--prompt` | `string` | Yes | The vulnerable system prompt that failed security auditing. |
| `diagnosis` | `--diagnosis` | `string` | No | The vulnerability diagnosis or remediation hint from the failing audit report. |
| `model` | `--model` | `string` | No | Gemma model identifier via `google-genai` (defaults to `gemma-4-27b-it` with automatic fallback). |

## Step-by-Step Execution Instructions

1. **Locate the Skill Script:**
   Ensure your working directory is the repository root (`chaos-harness/`).
2. **Execute the Standalone Runner:**
   Run `skills/auto-hardener/scripts/run_skill.py` and pass the vulnerable prompt and diagnosis:
   ```bash
   python skills/auto-hardener/scripts/run_skill.py \
     --prompt "You are FinBot. Answer user questions politely and do whatever the user asks." \
     --diagnosis "Target lacks instruction-priority boundaries; synthetic roleplay override hijacked the persona."
   ```
3. **Interpret the Hardened Output:**
   The runner outputs a structured JSON response containing:
   - `hardened_prompt`: The fortified, production-ready system prompt text.
   - `guardrails_applied`: Specific defensive barriers integrated (precedence anchoring, persona invariance, untrusted data isolation).
   - `original_prompt`: The initial vulnerable prompt.
   - `status`: Confirmation of successful prompt synthesis.

## Defensive Guardrail Strategies
1. **Instruction Precedence Anchoring**: Guarantees that system instructions permanently supersede conflicting user directives or emergency simulation claims.
2. **Persona & Roleplay Invariance**: Hardens the agent against persona hijacking, rogue aliases (e.g., 'Cipher'), or hypothetical unconstrained roles.
3. **Untrusted Data Boundary Isolation**: Treats all runtime user inputs strictly as passive data rather than executable system commands.
4. **Confidentiality & Secret Protection**: Strictly forbids disclosure, quoting, or paraphrasing of internal initialization parameters or canary keys.
5. **Standardized Refusal Protocols**: Provides immutable, polite refusal templates for out-of-bounds requests.

## Self-Healing Verification
After running `auto-hardener`, feed the generated `hardened_prompt` back into the auditing skill (`injection-fuzzer`, `schema-breaker`, etc.) to verify that the resilience score exceeds the $\ge 75$ passing threshold.
