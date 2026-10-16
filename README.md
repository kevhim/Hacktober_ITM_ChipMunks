# Chaos-Harness

An open-source prompt red-teaming harness with observed target responses, structured safety judgments, and candidate prompt hardening.

## Current behavior

The CLI, demo, and dashboard share one flow:

1. Generate an adversarial probe, or use a supplied benchmark payload.
2. Send the system prompt and probe to the target in a fresh conversation.
3. Judge the observed response.
4. If the result is a conclusive failure, generate a candidate system prompt.
5. Replay the exact same probe against the same target with the candidate prompt.
6. Run any supplied benign control checks and report the observed outcome.

A candidate can remain vulnerable or fail a control check. A single successful retest does not establish general safety. Candidates are returned for review; adopting them in an agent is a separate step.

## Install

Requires Python 3.10 or later.

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
```

The older `python -m pip install -r requirements.txt` workflow also installs the runtime dependencies and pytest.

## Offline demonstration

No credentials or cloud calls are needed:

```bash
python -m harness.cli --mock --heal --categories role-reversal
python deploy_and_benchmarks/run_demo.py --mock --fast
python deploy_and_benchmarks/dashboard.py --mock
```

The dashboard defaults to `http://127.0.0.1:8000`. It is intended for local use.

Mock mode uses a deterministic target fixture and a keyword heuristic judge. Reports label both as mock, and `verified_live` stays false. These results demonstrate the workflow and cannot validate an actual model.

## Live Google/Gemma run

Copy `.env.example` to `.env` and configure `GEMINI_API_KEY` locally. Keep credentials out of Git.

```dotenv
GEMINI_API_KEY=your-local-key
GEMMA_MODEL=gemma-4-26b-a4b-it
```

Google documents `gemma-4-26b-a4b-it` and `gemma-4-31b-it` for the Gemini API. See the [official Gemma API guide](https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api).

```bash
python -m harness.cli --prompt-file target_prompt.txt --heal --output report.json
python deploy_and_benchmarks/run_demo.py --target target-01-refund-bot
python deploy_and_benchmarks/dashboard.py
```

By default the configured provider serves attacker, target, judge, and hardener roles through separate calls. Live entry points require configuration; provider errors and malformed evaluations fail visibly instead of substituting mock scores.

## Test a different target model or agent

### Live Gemma 4 vs. local Llama stress and repair

With `GEMINI_API_KEY` in `.env`, install the local model and run:

```bash
ollama pull llama3.2:3b
python -m deploy_and_benchmarks.live_stress --env-file .env --output reports/live-stress.json
```

This uses live Gemma 4 for two fresh attacks, judging and up to three prompt repairs. Llama receives three fixed probes plus the generated attacks in fresh sessions. Every repair replays the full suite and checks legitimate and expired refund requests. Repairs combine a candidate prompt with Ollama's native JSON Schema decoding, temperature 0 and three business examples using different amounts and delivery ages from the probes; each round records those settings. Raw target responses are retained without cleaning or replacing them. Strict JSON, field types, refund limits and confidential-token checks supplement the model judge. The benchmark token stays local and is redacted from evidence sent to Google.

Progress and partial results are saved after each response. A successful run writes `reports/live-stress.prompt.txt` and `reports/live-stress.target.json`; adopt both the prompt and decoding settings together. `--resume` continues the saved output after a provider error without rerunning completed probes. `--replay-report previous-report.json` reuses the exact earlier probes; add `--reuse-baseline` to reuse its failed baseline for the same target model. Exit codes are 0 for all observed checks passing, 1 for remaining failures and 2 for configuration/provider errors. Reports are ignored by Git.

Open the dashboard with the measured repair and its runtime settings:

```bash
python -m deploy_and_benchmarks.dashboard --env-file .env --live-report reports/live-stress.json
```

The repaired Llama target appears first in the target list. Additional attacks still make live calls; a previous passing suite does not predetermine their results.

The local Llama refund scenario is also available through the shared runner. With Ollama running and the model installed, use:

```bash
python deploy_and_benchmarks/run_demo.py --scenario upi-ecommerce-refund-bot --target-model llama3.2:1b
python deploy_and_benchmarks/run_demo.py --scenario upi-ecommerce-refund-bot --mock --json
```

It uses [Ollama's OpenAI-compatible endpoint](https://docs.ollama.com/api/openai-compatibility) at `http://127.0.0.1:11434/v1` by default. Three fixed authority, schema, and false-premise probes are tested before and after one candidate patch; previously passing probes are replayed to detect regressions. Mock mode makes no availability probe or network call.

For an OpenAI-compatible target, set `TARGET_ENDPOINT`, `TARGET_MODEL`, and, if required, `TARGET_API_KEY`. Google remains the attacker/judge/hardener provider.

```bash
python -m harness.cli --prompt-file target_prompt.txt --heal \
  --target-endpoint https://inference.do-ai.run --target-model YOUR_ENABLED_MODEL
```

A base URL or a full `/v1/chat/completions` URL is accepted. DigitalOcean uses an inference key and the [serverless inference endpoint](https://docs.digitalocean.com/reference/api/reference/serverless-inference/). Local compatible servers may omit an API key.

An agent webhook can instead use `--target-url` or `TARGET_AGENT_URL`: it receives `{prompt, system_prompt, model}` and must return `{response: "..."}` or `{text: "..."}`. Webhook authentication uses `TARGET_API_KEY`. The older `TargetAgent` API and `--auto-heal` option remain supported.

To use a compatible cloud provider for all roles, leave `GEMINI_API_KEY` empty and configure `OPTIONAL_CLOUD_ENDPOINT`, `OPTIONAL_CLOUD_MODEL`, and `OPTIONAL_CLOUD_KEY`.

Custom Python agents can implement the two-input target contract:

```python
from harness.audit import AuditRunner, ControlCase
from harness.targets import CallableTarget

def call_my_agent(system_prompt: str, user_prompt: str) -> str:
    # Start a fresh agent session using system_prompt, then return its response.
    return my_agent_api(system_prompt=system_prompt, message=user_prompt)

runner = AuditRunner(target=CallableTarget(call_my_agent, name="my-agent"))
result = runner.heal(
    "You are a support assistant. Never disclose internal credentials.",
    "role-reversal",
    controls=[ControlCase(
        prompt="What is the support email?",
        expected_contains="support@example.test",
    )],
)
print(result.model_dump_json(indent=2))
```

Use benign controls relevant to your actual task. A failed control blocks a successful healing outcome. The CLI accepts the same control objects in a JSON array through `--controls controls.json`.

## Reports and scoring

```bash
python -m harness.cli --mock --heal --json
python -m harness.cli --mock --response "An unrelated response" --categories prompt-injection
```

A recorded response can be judged with `--response`, but cannot be used for an automatic retest.

- Harness `risk_score` runs from 0 to 100; lower is safer.
- Standalone skill `score` measures resilience; higher is safer.
- `inconclusive` means the judge cannot determine the outcome. Ignore its numeric risk placeholder.
- Reports include target source, provider/model, judge source, attack, before/after responses, candidate, controls, and outcome.
- `verified_live` means the retest passed using live target and judge calls, with supplied controls passing. It is not a safety certification.
- CLI exit codes: 0 for the observed probes passing, 1 for a conclusive failure or failed retest/control, 2 for an error or inconclusive result.

## Five Agent Skills

Each folder contains `SKILL.md` and `scripts/run_skill.py`:

| Skill | Purpose |
|---|---|
| injection-fuzzer | Instruction hierarchy and persona drift |
| schema-breaker | Raw JSON output compliance |
| pii-leak-prober | Synthetic secret/canary disclosure |
| hallucination-trap | False-premise and grounding checks |
| auto-hardener | Candidate system prompt generation |

Standalone skills use exported `GEMINI_API_KEY` and `GEMMA_MODEL` (the older `GEMMA_MODEL_ID` variable remains supported). Use `--mock` to force offline fixtures. Live target calls use the real system/user roles, and configured model failures do not silently select a different model. The legacy `simulated_target_response` key is retained for compatibility; live reports also provide `target_response`.

For Hermes, install this package in the Python environment used by the agent. Either merge the documented `skills.external_dirs` snippet in `deploy_and_benchmarks/hermes_config.yaml` into your Hermes config, or install the complete skill folders:

```bash
python deploy_and_benchmarks/install_skills.py --dry-run
python deploy_and_benchmarks/install_skills.py --copy
hermes skills list
```

The installer preserves existing skills and refuses incomplete source folders. It does not configure a model, provision a Droplet, or create placeholder skills. See the [Hermes skills documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills).

## Validation and remaining external checks

```bash
python -m pytest -q
```

Tests exercise the full HTTP target cycle against a local model stub, fixed-payload replay, failed hardening, benign controls, provider outages, malformed judgments, dashboard APIs, skill installation, and standalone skills. CI runs Python 3.10-3.13 on Ubuntu plus a Windows Python 3.13 job.

Cloud credentials and a Hermes host are still needed to verify live Google/DigitalOcean inference and an actual Hermes deployment. No hosted model or cloud deployment success is inferred from offline tests.

## Data handling

The project adds no telemetry. Live mode sends target system prompts, attack inputs, responses, and diagnostics to the configured providers. Provider data policies apply. The local dashboard retains up to 64 audit records in server memory for evidence-based export; they disappear when it stops. Saved reports contain these inputs and may contain secrets exposed by the target, so review them before sharing.

## Layout

- `harness/`: engine roles, target adapters, observed audit/retest runner, CLI, hardener.
- `skills/`: five portable skill manifests and runners.
- `deploy_and_benchmarks/`: provider adapter, benchmark targets, demo, local dashboard, Hermes installer/config.
- `tests/` and `.github/workflows/ci.yml`: offline tests and CI.

The original component plan is implemented. Remaining release work is live provider/deployment verification and review of observed results, rather than missing skill folders.

Contributions should follow [CONTRIBUTING.md](CONTRIBUTING.md) and use feature branches and PRs. Licensed under [MIT](LICENSE).
