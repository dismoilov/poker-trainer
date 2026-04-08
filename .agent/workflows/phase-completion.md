---
description: How to properly complete a phase — always deliver walkthrough automatically
---

# Phase Completion Workflow

When finishing ANY phase of work, ALWAYS do the following steps in order:

## 1. Execute all implementation work
Complete all code changes, tests, API verification, browser checks.

## 2. Create/update the walkthrough artifact AUTOMATICALLY
- Do NOT wait for the user to ask for a walkthrough
- Do NOT just say "phase is complete" without the walkthrough
- The walkthrough is a MANDATORY deliverable at the end of every phase
- Write it to the walkthrough.md artifact with `RequestFeedback: true`

## 3. Deliver the walkthrough as the final message
- Your final turn message should reference the walkthrough artifact
- Include a brief summary of what was done
- The user should never have to ask "дай walkthrough" — it must already be there

## CRITICAL RULE
**Never end a phase with just a status summary.** The walkthrough artifact IS the phase completion deliverable. If you haven't written the walkthrough, the phase is NOT complete.
