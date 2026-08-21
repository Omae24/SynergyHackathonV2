# KPC Inuka Fellowship Data Privacy & Financial Reconciliation Portal

An enterprise-grade compliance portal and financial auditing engine developed for the **KPC Inuka Foundation** to manage beneficiary registrations, consent records, and monthly stipend disbursements in strict compliance with the **Kenya Data Protection Act (KDPA)**.

---

## 🚀 Key Features

### 1. Ingestion Pipeline & Quality Gates (Great Expectations)
* **Real-time API Endpoint**: Receives field registrations via `/api/stream/beneficiary` and cleanses formatting (E.164 phone normalization, Title Case naming).
* **Validation Boundary**: Filters incoming data against strict schema constraints using an in-memory **Great Expectations** suite (validating email syntax, official Kenyan regions, and valid pillars).
* **Quarantine Routing**: Invalid records are isolated in `quarantined_events` rather than polluting the active database directory.

### 2. Zero-Trust Access Gateway (RLS & CLS)
* **Row-Level Security (RLS)**: Enforced dynamically on the database query layer. Regional field officers can only access records matching their depot (e.g., Nyanza), and pillar coordinators only see their respective program data.
* **Column-Level Security (CLS)**: Dynamic server-side masking automatically hides PII (Names, National IDs, phone numbers, and emails) for non-authorized roles (like Compliance Auditors) or when anomalies are detected.
* **Consent Purposes Matrix**: Toggles separate permissions for Stipend Data Sharing, Photo Use, SMS Notifications, and External Donor Reporting.

### 3. ML Threat & Anomaly Detection
* **PII Access Monitoring**: An **Isolation Forest** model monitors API calls, flagging anomalous access patterns (based on query volume, time-of-day, and regional scope mismatches).
* **Automatic Safeguard**: Anomaly flags in the access ledger automatically override queries and force anonymization on all returned data to prevent leaks.

### 4. Automated Financial Reconciliation (Problem 10)
* **Reconciliation Widget**: Cross-references actual monthly disbursements against expected amounts calculated from class attendance sheets (Min 75% attendance required) and active data consent status.
* **Anomalous Flagging**: Instantly identifies over-payments made to students with low attendance or withdrawn consent.
* **Corrective Mechanism**: Allows coordinators to execute a single-click "Recall Payout & Hold" action to recall funds and place the fellowship account on hold.

### 5. Compliant External Export
* **Export Compliant Report (CSV)**: Exporter tool that extracts the active directory view into a fully anonymized CSV, ensuring donor audits are leak-safe.

---

## 🛠️ Installation & Getting Started

### 1. Clone & Setup Virtual Environment
```bash
git clone https://github.com/Omae24/SynergyHackathonV2.git
cd SynergyHackathonV2
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install fpdf2
```

### 2. Generate and Seed the Database (1,000 Records)
Generates 1,000 realistic beneficiary profiles across the 8 administrative regions of Kenya and seeds the database:
```bash
python generate_large_dataset.py
python seed_inuka_db.py
```

### 3. Train Machine Learning Models
```bash
python train_ml_models.py
```

### 4. Run the Web Server
```bash
python dashboard_app.py
```
Open `http://localhost:8000/dashboard.html` in your browser.

### 5. Run the Stream Simulator (Optional)
Simulates continuous incoming registration events from field registers:
```bash
python stream_simulator.py
```

---

## 🔐 Seeded Test Credentials
All passwords are set to `password` by default.

| Username | Role | Scope | PII Visibility |
|---|---|---|---|
| **`hq_director`** | HQ Admin | All Pillars, All Regions | Masked by default (Can toggle unmask) |
| **`scholarship_hq`** | Pillar Coordinator | Scholarship Only | Unmasked (Scholarship only) |
| **`tech_hq`** | Pillar Coordinator | Tech Only | Unmasked (Tech only) |
| **`nyanza_field`** | Field Officer | Nyanza Region Only | Unmasked (Nyanza only) |
| **`kdpa_auditor`** | Compliance Auditor | All | **100% Masked (Locked)** |
| **`INK-2026-1002`** | Beneficiary (Lucy Hassan) | Self Profile Only | Self Profile (Check/Revoke Consent) |

---

## 🧪 Running Automated Quality Tests
Verify the compliance metrics, cleansing rules, RLS blocks, and financial discrepancy triggers using Pytest:
```bash
python -m pytest tests/test_privacy_engine.py
```
