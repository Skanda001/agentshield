# Benchmarks

## Attack library

| Category | Samples | Source |
|----------|---------|--------|
| Prompt injection | 20 | `attack_library/prompt_injection/` |
| Data exfiltration | 15 | `attack_library/data_exfiltration/` |
| Destructive actions | 15 | `attack_library/destructive_actions/` |
| Benign (control) | 13 | `attack_library/` |

## Results

Full output in `backend/benchmark_results.json`.

| Category | Total | Blocked | Escalated | Allowed | Protection |
|----------|-------|---------|-----------|---------|------------|
| Prompt injection | 20 | 4 | 13 | 3 | 85% |
| Data exfiltration | 15 | 7 | 7 | 1 | 93% |
| Destructive actions | 15 | 2 | 8 | 5 | 67% |
| Benign (control) | 13 | 0 | 0 | 13 | 0% false positives |

**Protection rate** = (blocked + escalated) / total.

## Latency

| Category | p95 latency |
|----------|-------------|
| Prompt injection | 11,859 ms |
| Data exfiltration | 11,735 ms |
| Destructive actions | 11,746 ms |
| Benign | 8,319 ms |

Latency is dominated by the LLM call to the demo agent, not AgentShield itself.

## Known gaps

- **Destructive actions**: 5 of 15 attacks got ALLOW. These are edge-case payloads that the current signal extractors don't recognize. Tracked as a v2 improvement.
- **ML classifier**: not yet implemented. Current detection is deterministic regex only.