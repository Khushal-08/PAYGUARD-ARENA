# Payguard Arena - Competition Hardening Audit Recommendation Report

## Categorization Key
*   **[A] Must-Fix:** Critical integrity or resilience gaps. Fixing these is mandatory before the submission deadline.
*   **[B] High-Value-Safe:** Improvements that enhance presentation or documentation quality without risking the core architecture. (Pending your review before execution).
*   **[C] Do-Not-Touch:** Locked models, architecture, or features. Modifying these is strictly off-limits due to the proximity of the deadline.

---

## [A] Must-Fix (COMPLETED)
These critical items were identified during the audit and have already been resolved to secure the environment:
1.  **Demo Resilience (Frontend Cold-Start Timeout):** The React frontend originally lacked a timeout for its `fetch()` calls. If the Render instance hit a cold-start (~51 seconds), the UI would hang instead of instantly degrading to the honest fallback snapshot. **Status: Fixed** via `fetchWithTimeout` (5000ms AbortController).
2.  **Fidelity Evaluation (Taxonomy Mismatch):** The original evaluation falsely attempted to compute Jensen-Shannon divergence across mismatched taxonomies (UUIDs vs ProductCD) and misinterpreted the KS-statistics. **Status: Fixed** by removing the invalid metric and honestly reporting the genuine Kolmogorov-Smirnov distribution values.

---

## [B] High-Value-Safe (PENDING REVIEW)
These items are safe to implement but require your explicit approval before I proceed:
1.  **Architecture Diagram Generation (DOCX Update):** Generate the definitive monospace/ASCII architecture diagram—incorporating the explicit defense retraining step between adaptive attack generation and Round 3 evaluation. I will format this perfectly for you to copy/paste into your solution walkthrough DOCX.
2.  *(Optional)* **Additional README/Documentation Polish:** Any final cosmetic cleanup in the repository markdown files to ensure the GitHub submission looks pristine for the judges.

---

## [C] Do-Not-Touch (LOCKED)
These items were evaluated and explicitly locked down. Attempting to modify them would jeopardize the submission:
1.  **Live Endpoint Architecture (Relational Features):** Adding real-time graph features (`device_unique_accounts_7d`, etc.) would require a stateful Feature Store. This is too risky right now and has instead been successfully documented as a formal "Future Extension".
2.  **Model Retraining & Baseline Integrity:** The `xgboost_baseline_round_1.pkl` and `baseline_results.json` are strictly locked to the 9-feature constraint. No experimental features will touch this canonical pipeline.
3.  **Ephemeral File Dependencies:** I audited `/defend/score` and the other API routes. All loaded JSON and PKL dependencies are safely tracked in Git. No ephemeral filesystem fixes are necessary.
4.  **Generative AI Loop:** The Gemini API integrations remain completely decoupled from the real-time `/defend/score` path, ensuring the core defense latency sits comfortably at ~315ms (network round-trip).
