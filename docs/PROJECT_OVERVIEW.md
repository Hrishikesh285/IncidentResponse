# OpsMemory — Project Overview

## Problem

On-call engineers responding to production incidents lose 30–60 minutes per incident re-discovering fixes that were already found once. Knowledge generated during incident resolution lives in old chat logs, Slack threads, and postmortem documents that nobody re-reads when the next alarm fires.

## Solution

OpsMemory is an on-call incident assistant that **remembers every production incident your team has resolved**. When a new incident arrives:

1. The agent **recalls** semantically similar past incidents from Hindsight memory.
2. An LLM produces a **diagnosis and fix plan** grounded in what actually worked before, citing the specific past incident by ID.
3. When the incident is resolved, the resolution is **retained** back into memory, so the agent improves over time.

## Target Users

- **On-call engineers** who need fast, context-aware diagnosis during a production incident.
- **Site Reliability Engineering (SRE) teams** building a persistent institutional knowledge base.
- **Platform Engineering leads** measuring mean time to recovery (MTTR) across services.

## Business Case

| Metric | Without OpsMemory | With OpsMemory |
|--------|-------------------|----------------|
| First incident of a type | 45–70 min | 45–70 min |
| Repeat incident (same root cause) | 30–60 min | 8–15 min |
| Knowledge retained after engineer leaves | 0% | 100% |

## Core Features

- **Hindsight memory integration** — `retain` resolved incidents, `recall` similar ones at diagnosis time.
- **Memory ON / OFF toggle** — side-by-side comparison of generic vs. memory-informed diagnosis.
- **Groq LLM** — fast, high-quality diagnosis using Groq's hosted models.
- **Three-panel UI** — incident form, diagnosis, and recalled-from-memory panel visible simultaneously.
- **40 seed incidents** — realistic synthetic data across 6 services and 8 failure patterns.
- **Demo scenario** — three-incident walkthrough showing memory OFF → ON → learning → improvement.

## Out of Scope

- Authentication and user accounts
- Real Slack, PagerDuty, or Opsgenie integrations
- Deployment configs (Kubernetes, Terraform, Helm)
- Multiple memory banks
- Streaming LLM responses
- Any framework not listed in the tech stack
