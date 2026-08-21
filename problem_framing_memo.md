# PROBLEM FRAMING MEMO
**To:** KPC Inuka Foundation Board & Compliance Committee  
**From:** Synergy Hackathon Data Governance Team  
**Date:** August 21, 2026  
**Subject:** Beneficiary Privacy, Consent Compliance, & KDPA Data Governance Framework

---

## Executive Summary
The rapid digitization of beneficiary profiles across the four pillars of the **KPC Inuka Foundation** (Scholarship, Plus, Vocational, Tech) exposes the foundation to severe operational, financial, and legal liabilities. Under the **Kenya Data Protection Act (KDPA)**, non-compliance with data processing permissions carries statutory penalties of up to **KES 5 Million** or 1% of annual turnover, alongside severe reputational risks. 

With 1,000 active beneficiary records, data is accessed by multiple internal actors (HQ Directors, Pillar Coordinators, Regional Field Officers, and Auditors). Sharing unmasked datasets containing names, National IDs, phone numbers, and emails violates core KDPA principles.

This memo frames the problem boundaries, quantifies the compliance risks, and outlines our deployed technical solutions for the Inuka Portal.

---

## The Challenge: Privacy, Consent, & Ingestion Quality

### 1. The PII Exposure Bottleneck
* **The Risk**: Raw contact details (Names, National IDs, phone numbers, emails) are exposed to various coordinators. External report dissemination and unauthorized internal access patterns increase the probability of data breaches.
* **The Solution**: Server-side dynamic Column-Level Security (CLS) that automatically masks personal data for non-authorized roles (like Auditors), combined with Row-Level Security (RLS) restricting regional officers to their specific depots.

### 2. Ingestion Quality Control (Great Expectations Gates)
Raw field registration data often contains missing fields, incorrect regions, or invalid phone numbers. Manual data scrubbing wastes hours of administrative time:
* **The Risk**: Corrupted databases lead to audit validation failures and misdirected stipend payouts.
* **The Solution**: In-memory Great Expectations validation suites that intercept streamed registration events and quarantine non-compliant payloads automatically.

### 3. Granular Consent Purposes Management
* **The Policy**: Under the KDPA, beneficiaries must have the right to choose how their data is processed (Stipend sharing, media photos, SMS notifications, and external donor reporting).
* **The Risk**: A fellow must be able to withdraw consent or request profile erasure ("Right to be Forgotten" under Section 40) at any time. Manually processing these requests takes up to **14 business days** per request, causing massive compliance latency.
* **The Solution**: Live self-service desk where beneficiaries toggle preferences instantly, and a chatbot rights engine that handles requests in Swahili and English.

```
+---------------------------------------------------------------------------------+
          INUKA DATA INGESTION & CONSENT MANAGEMENT PIPELINE
                                                                                 
  [Field Event] -> [GE Quality Gate] -> [Clean Database] -> [Dynamic RLS/CLS Query]
        |                |                                         |              
        v                v                                         v              
  (Quarantine)      (Reject Bad)                           (Obfuscate PII)        
                                                           - Mask Names, Emails   
                                                           - Exclude Region       
+---------------------------------------------------------------------------------+
```

---

## Proposed Technical Interventions
We have successfully deployed the following modules to address these gaps:

1. **Bilingual Compliance Chatbot Rights Engine**: 
   - Uses NLP intent classifier to process user requests in English and Swahili.
   - Dynamically compiles real-time pillar and regional compliance status reports (e.g. counting total fellows, active consent rates, and active profile erasures).
2. **Export Compliant Donor Report Tool**:
   - A prominent dashboard button that exports the active directory view into a fully anonymized CSV, completely redacting sensitive PII columns for external donor audits.
3. **Great Expectations Ingestion Stream**:
   - Cleanses, standardizes, and validates registrations in real time, routing failures to quarantine logs.
