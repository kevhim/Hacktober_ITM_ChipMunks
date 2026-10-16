## Description
<!-- Provide a clear, detailed summary of the changes introduced in this Pull Request. -->

## PR Type
What kind of change does this PR introduce?
- [ ] `feat`: New feature or harness capability
- [ ] `skill`: New adversarial attack skill under Agent Skill Open Standard
- [ ] `fix`: Bug fix
- [ ] `docs`: Documentation update or enhancement
- [ ] `test`: Unit tests, integration tests, or CI workflow improvements
- [ ] `refactor`: Code refactoring without behavioral alterations

---

## Responsible AI & Red-Teaming Checklist
- [ ] **Dual-Use Safeguards**: Adversarial prompts and skills adhere to ethical red-teaming principles and do not generate uncontrolled toxic or malicious outputs.
- [ ] **Non-Destructive Testing**: All attack scenarios are designed for defensive evaluation, robustness verification, and prompt hardening only.
- [ ] **Evaluation Integrity**: Safety evaluations provide clear explanations, accurate vulnerability classifications, and bounded risk scores (0–100).
- [ ] **Data Privacy & Redaction**: No real-world PII, proprietary credentials, API keys, or sensitive training data are included in test prompts or commit logs.

---

## Open-Source & Code Quality Checklist
- [ ] **License Compliance**: All work is original or permissively licensed under the MIT License.
- [ ] **Branch Naming Standard**: Branch adheres to repository convention (`feat/*`, `fix/*`, `skill/*`, `docs/*`, `test/*`).
- [ ] **Offline Mock Fallback**: Core modules include offline mock fallbacks so CI passes even when `GEMINI_API_KEY` is not set.
- [ ] **Tests Passing**: Verified with `pytest` locally (`pytest -v`).
- [ ] **Code Styling & Types**: Code adheres to PEP 8 standards with type hints and Pydantic schema validation.
- [ ] **Self-Contained Scope**: PR does not modify teammate-owned directories (`skills/` core infrastructure or `deploy_and_benchmarks/` without coordination).

---

## How Has This Been Tested?
<!-- Describe the tests run to verify your changes. Include terminal commands and sample outputs. -->
```bash
pytest -v
```

## Additional Context / Screenshots
<!-- Add any relevant screenshots (e.g. Rich CLI terminal output), logs, or design considerations. -->
