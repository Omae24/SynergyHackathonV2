# KPC Inuka Foundation Data Privacy & Compliance Portal
## 6-Slide Pitch Deck
**Focus: KDPA Consent Management, ML Security Anomaly Detection, & Dynamic Data Masking**

---

# Slide 1: Title & Executive Summary
## Inuka Fellowship Data Privacy & Consent Portal
### Securing Beneficiary Data Rights (KDPA) & Compliance Operations
* **Core Goal**: Protect KPC Inuka Foundation against KDPA compliance liabilities (up to KES 5M in statutory fines) while automating data privacy safeguards.
* **Scale**: Processes a digitized directory of **1,000 active fellows** across **8 official regions of Kenya** and **4 program pillars** (Scholarship, Plus, Vocational, Tech).
* **Impact**: Saves **34 administrative hours/week** and guarantees zero PII leaks.

---

# Slide 2: The Core Compliance Challenges
## Digitizing Beneficiary Records Safely
1. **PII Exposure Risk**: Sharing contact details (Names, National IDs, phone numbers, emails) in raw files with coordinators and donors violates data minimization laws.
2. **Data Ingestion Quality**: Registrations submitted from the field often contain syntax errors, missing signatures, or wrong formats.
3. **Rights Execution Latency**: Manually processing beneficiary requests to verify, withdraw, or delete profiles ("Right to be Forgotten" under Section 40) takes up to **14 business days** per request.

---

# Slide 3: Event-Driven Quality Gates (ETL Ingestion)
## Automated Validation with Great Expectations
* **Real-time API Endpoint**: Receives field registrations via `/api/stream/beneficiary` and automatically standardizes formatting (standardizing phone numbers, casing names).
* **Boundary Validation**: Validates inputs in-memory against 9 Great Expectations rules (validating email, regions, and pillars).
* **Zero-Pollution Quarantine**: Valid records write directly to the database, while faulty registries route to a quarantine log, ensuring database integrity.

---

# Slide 4: RLS, CLS, & ML Threat Detection
## Zero-Trust Privacy Gateway
* **Row-Level Security (RLS)**: Enforced dynamically on the database query layer. Nyanza Field Officers are strictly bound to Nyanza records. Scholarship Coordinators are restricted to Scholarship records.
* **Column-Level Security (CLS)**: Personal identifiers are masked server-side (`J*. Oum***`, `*****805`) for compliance auditors, beneficiaries, and unauthorized queries.
* **ML Anomaly Detection**: An Isolation Forest model monitors access patterns (checking query volumes, time-of-day, and regional boundaries) to auto-mask PII and flag potential threats in the access ledger.

---

# Slide 5: Chatbot Rights Engine & Compliant Exporter
## Automated Consent Control & Audits
* **Bilingual Rights Agent**: Handles data requests in Swahili and English. Allows fellows to check profile details, update consent purposes, or execute data purges.
* **External Compliant Export**: A prominent **Export Compliant Donor Report (CSV)** button allows compliance auditors to instantly download masked, donor-safe datasets for external audits.
* **Direct Self-Service**: Beneficiaries log in directly to adjust permissions for Stipends, Photos, SMS, or Audits.

---

# Slide 6: Quantified Impact & Strategic ROI
## Operational Savings Compiled
* **Compliance Savings**: Saves **24 hours/week** of manual access logging and **10 hours/week** of manual data cleansing.
* **Rights SLA Compliance**: Reduces profile erasure ("Right to be Forgotten") cycle times from **14 business days to less than 1 second**.
* **Zero-Pollution boundary**: Quarantines registrations containing bad formats before they write to active directory.
* **Legal Shield**: Dynamic PII masking and right-to-be-forgotten controls prevent KDPA statutory fine exposure (up to KES 5M).
