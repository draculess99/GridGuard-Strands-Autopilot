# Demo Script — GridGuard Strands Operations Autopilot
## 5-Minute Video Script Outline

**Target**: AWS "Agents for Humans" Hackathon demo video  
**Duration**: ~5 minutes  
**Format**: Screen recording + voiceover  
**Tool**: OBS Studio / Loom (your preference)

---

## Setup Before Recording

- [ ] Terminal open at project root
- [ ] `streamlit run dashboard/app.py` running (tab 1)
- [ ] Second terminal ready for CLI commands (tab 2)
- [ ] Browser at http://localhost:8501
- [ ] `data/audit_log.jsonl` cleared (`del data\audit_log.jsonl`)

---

## Script

### [0:00 – 0:30] Hook & Problem Statement

**Voiceover:**
> "Grid operations teams face a relentless stream of risk signals — severe weather, demand spikes, equipment failures. The first 30 minutes of every incident involves the same structured work: check the runbook, score the risk, draft the mitigation, prepare the work order.
>
> This is GridGuard Strands Operations Autopilot. It automates that structured triage — while keeping humans firmly in control of every decision that matters."

**On screen:** Show the dashboard landing page.

---

### [0:30 – 1:00] Architecture Overview (30 seconds)

**Voiceover:**
> "The system is built on the AWS Strands Agents SDK. Seven purpose-built tool functions form the agent's workflow. The agent orchestrates them autonomously in live mode — or we can run them deterministically in mock mode for offline demos and testing.
>
> At the centre of the workflow is a mandatory human approval gate. The agent drafts and recommends — it cannot act without an operator's sign-off."

**On screen:** Show the Mermaid architecture diagram from the README (open in browser or display as image).

---

### [1:00 – 2:30] Live Workflow Demo — Severe Weather Scenario

**Voiceover:**
> "Let's run the Severe Weather scenario. An ice storm is approaching the New England grid territory — demand surge expected, reserve margin tightening."

**Actions:**
1. Select "Severe Weather" in the sidebar dropdown.
2. Click **Run Agent Workflow**.
3. Narrate as each step lights up in the timeline:
   - "Step 1: get_grid_snapshot — the agent retrieves current demand, capacity, and reserve."
   - "Step 2: retrieve_runbook — the relevant Storm Response procedure is loaded."
   - "Step 3: assess_risk — deterministic rules score this at severity 4 of 5, priority P2."
   - "Step 4: generate_mitigation_steps — six ordered actions, each with a responsible role and timeframe."
   - "Step 5: draft_work_order — a structured draft document, clearly marked PENDING APPROVAL."
   - "Step 6: request_human_approval — this is the mandatory HITL gate. The agent halts here."
   - "Step 7: record_audit_event — the workflow completion is logged with a content hash."

**On screen:** Dashboard timeline with all steps showing DONE. Overall status: AWAITING_HUMAN_APPROVAL.

---

### [2:30 – 3:15] Risk Assessment & Work Order Detail

**Voiceover:**
> "The Risk Assessment tab shows a severity gauge, load factor, and reserve margin. The Mitigation Plan tab shows our six ordered steps — each with responsible roles and timeframes pulled directly from the synthetic runbook."

**Actions:**
1. Click the **📊 Risk** tab — show severity gauge and metrics.
2. Click the **🛠️ Mitigation Plan** tab — scroll through the steps.
3. Click the **📋 Work Order** tab — show the structured DRAFT document.

---

### [3:15 – 3:45] Human Approval Gate

**Voiceover:**
> "This is the most important part of the design. The Work Order tab shows the approval gate — the agent cannot proceed until I, the operator, make a decision.
>
> I'll review the work order, add a brief rationale, and approve it."

**Actions:**
1. Scroll to the Human Approval Gate section on the Work Order tab.
2. Type a rationale: "Reviewed. Storm protocol activation and crew staging approved."
3. Click **Approve Work Order**.
4. Show the success message and the badge changing to APPROVED.

---

### [3:45 – 4:20] Audit Trail

**Voiceover:**
> "Every action in the workflow — and my approval decision — is recorded in an immutable append-only audit log. Each record is SHA-256 hashed for tamper detection. This is the accountability trail that regulators and post-incident reviewers need."

**Actions:**
1. Scroll to the Audit Trail section at the bottom of the dashboard.
2. Show the `WORKFLOW_COMPLETED` and `APPROVED` records.
3. Briefly switch to terminal and run:
   ```
   type data\audit_log.jsonl
   ```
   Show the raw JSONL records.

---

### [4:20 – 4:40] CLI Demo & Tests

**Voiceover:**
> "The system also ships with a rich CLI runner and a complete test suite. All 25-plus tests pass with zero cloud credentials — full mock mode."

**Actions:**
1. In terminal, run:
   ```
   python scripts/run_demo.py --scenario HIGH_DEMAND --approve
   ```
   Show the rich-formatted output.
2. Run:
   ```
   pytest tests/ -v --tb=short
   ```
   Show all tests passing.

---

### [4:40 – 5:00] Closing

**Voiceover:**
> "GridGuard Strands Operations Autopilot — autonomous triage, human-governed decisions, immutable accountability. Built with the AWS Strands Agents SDK for the Agents for Humans Hackathon.
>
> The full source code, tests, and documentation are on GitHub. To try it yourself: pip install, copy the .env.example, and run streamlit."

**On screen:** Show the GitHub repository URL and README.

---

## Post-Recording Checklist

- [ ] Trim dead air and pauses
- [ ] Add chapter markers at each section
- [ ] Add captions / subtitles
- [ ] Thumbnail: dashboard screenshot with APPROVED badge visible
- [ ] Upload to YouTube (unlisted) and link from Devpost
