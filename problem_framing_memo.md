# PROBLEM FRAMING MEMO
**To:** KPC Inuka Foundation Board & Compliance Committee  
**From:** Synergy Hackathon Data Governance Team  
**Date:** August 21, 2026  
**Subject:** Beneficiary Privacy, Consent Compliance, & Financial Auditing Framework (KDPA Compliance)

---

## Executive Summary
The rapid digitization of beneficiary profiles across the four pillars of the **KPC Inuka Foundation** (Scholarship, Plus, Vocational, Tech) exposes the foundation to severe operational, financial, and legal liabilities. Under the **Kenya Data Protection Act (KDPA)**, non-compliance with data processing permissions carries statutory penalties of up to **KES 5 Million** or 1% of annual turnover, alongside severe reputational risks. 

Furthermore, KPC lacks an automated mechanism to reconcile monthly stipend disbursements against Monitoring & Evaluation (M&E) attendance logs. This has resulted in financial discrepancies—specifically, paying stipends to beneficiaries who either failed to meet the mandatory **75% class attendance threshold** or had withdrawn their data-processing consent. 

This memo frames the problem boundaries, quantifies the compliance risks, and outlines our deployed technical solutions for the Inuka Portal.

---

## The Challenge: Privacy, Quality, & Financial Auditing

### 1. The PII Exposure Bottleneck
With 1,000 active beneficiary records, data is accessed by multiple internal actors (HQ Directors, Pillar Coordinators, Regional Field Officers, and Auditors). Sharing unmasked datasets containing names, National IDs, phone numbers, and emails violates core KDPA principles:
* **The Risk**: External report dissemination and unauthorized internal access patterns increase the probability of data breaches.
* **The Solution**: Server-side dynamic Column-Level Security (CLS) that automatically masks personal data for non-authorized roles (like Auditors), combined with Row-Level Security (RLS) restricting regional officers to their specific depots.

### 2. Ingestion Quality Control (Great Expectations Gates)
Raw field registration data often contains missing fields, incorrect regions, or invalid phone numbers. Manual data scrubbing wastes hours of administrative time:
* **The Risk**: Corrupted databases lead to audit validation failures and misdirected stipend payouts.
* **The Solution**: In-memory Great Expectations validation suites that intercept streamed registration events and quarantine non-compliant payloads automatically.

### 3. Financial Disbursement Discrepancies (M&E Reconciliation)
To maintain donor transparency and protect foundation funds, stipend disbursements must align with student class attendance.
* **The Policy**: Beneficiaries must maintain a minimum **75% attendance rate** to qualify for their KES 5,000.00 monthly stipend. 
* **The Bottleneck**: Prior manual audits took weeks to cross-reference sheets, leading to cases where stipends were disbursed to students with low attendance or those who had withdrawn consent (status `On Hold`).

```
+---------------------------------------------------------------------------------+
          INUKA DATA INGESTION & FINANCIAL AUDITING PIPELINE
                                                                                 
  [Field Event] -> [GE Quality Gate] -> [Clean Database] -> [Disbursement Audit]   
        |                |                                         |              
        v                v                                         v              
  (Quarantine)      (Reject Bad)                           (Flag Discrepancy)     
                                                           - Attend < 75%         
                                                           - Consent Withdrawn    
+---------------------------------------------------------------------------------+
```

---

## Proposed Technical Interventions
We have successfully deployed the following modules to address these gaps:

1. **Bilingual Compliance Chatbot**: 
   - Uses NLP intent classification to process user requests in English and Swahili.
   - Dynamically compiles real-time pillar and regional compliance status reports (e.g. counting total fellows, active consent rates, and flagged payment anomalies).
2. **Automated Financial Reconciliation Widget**:
   - Compares actual disbursements against expected stipends based on M&E attendance and consent states.
   - Flags discrepancies (low attendance payouts or consent-withdrawn payouts) and provides a single-click "Recall Payout & Hold" corrective mechanism.
3. **Compliant External Reporting Export**:
   - A prominent dashboard tool that exports the active directory view into a fully anonymized CSV, completely redacting sensitive PII columns for external donor audits.
