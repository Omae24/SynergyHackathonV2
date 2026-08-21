# User Acceptance Testing (UAT) & QA Report

This document outlines the test evidence, QA validation, and instructions for User Acceptance Testing (UAT) of the **KPC Inuka Foundation Data Privacy, Consent, & KDPA Governance Portal**.

---

## 1. QA Test Evidence & Pipeline Execution

### Step 1: Real-Time Stream Ingestion & Great Expectations Quality Gates
Command run: `python stream_simulator.py` (which targets `/api/stream/beneficiary` on `dashboard_app.py`)
* **Inputs**: Dynamic JSON registration payloads (e.g. name, phone, email, pillar, region, consent_status).
* **Validation Engine**: Upgraded in-memory Great Expectations suite in `inuka_etl.py` executing 9 schema checks.
* **Status**: Passed
* **Evidence**:
  * Clean records successfully cleansed (e.g., standardizing phones to `+254...`, title-casing names) and loaded into the `inuka_beneficiaries` table.
  * Invalid records (such as empty names, out-of-bounds regions, or invalid email formats) intercepted at the boundary and routed to the `quarantined_events` table for DPO review.
  * Console Output logs:
    ```text
    [Simulator] Streaming event INK-2026-2051 (Valid=True)...
    [Simulator] Response Code: 200. Response: {"success": true, "status": "SUCCESS", "result": {...}}
    ```

### Step 2: Privacy Anomaly & Chatbot Intent ML Training
Command run: `python train_ml_models.py`
* **Outputs**: `models/access_anomaly_detector.joblib` (Isolation Forest) and `models/chatbot_intent_classifier.joblib` (TF-IDF Pipeline).
* **Status**: Passed (Exited with code 0)
* **Model Validation**:
  * **PII Anomaly Detector**: Successfully separates typical query volumes (e.g., volume 10, midday, correct region) from high-threat patterns (e.g., query volume 150, 2 AM, out-of-region access).
  * **Bilingual Chatbot NLP Classifier**: Achieves $100\%$ classification accuracy on Swahili and English intents (`view_data`, `update_consent`, `request_deletion`, `generate_report`).

---

## 2. API Endpoint Verification

Server run: `python dashboard_app.py`
* **Local Server**: `http://localhost:8000`
* **Constant Public Link**: `https://kpc-inuka-compliance.loca.lt/dashboard.html`

### Endpoint 1: Query Directory & Dynamic RLS/CLS (`GET /api/beneficiaries`)
* **Auditor Role Test**: Logging in as `kdpa_auditor` queries this endpoint. The server automatically activates Column-Level Security (CLS), returning fully masked PII fields (`M*. Oum***`, `*****805`).
* **Field Officer RLS Test**: Logging in as `nyanza_field` queries this endpoint. The server applies Row-Level Security, returning only the subset of beneficiaries registered in the `Nyanza` region.

### Endpoint 2: AI Compliance Chatbot (`POST /api/chatbot/message`)
* **Bilingual Report Test**: Send request: `{"message": "ripoti ya nyanza region"}` (Swahili for Nyanza report).
* **Status**: 200 OK
* **Response Payload**:
  ```json
  {
      "intent": "generate_report",
      "reply": "KPC Inuka Pillar Compliance Report (Nyanza Region):\n- Total beneficiaries registered: 125\n- Average active consent rate: 94.0%\n- Active data erasures: 2 profiles purged.\nAll processing operations comply with KDPA standards."
  }
  ```

---

## 3. UAT Execution Checklist & Test Command

To run the complete test suite locally:

### 1. Run All Project Unit Tests
Run the following in the project root:
```bash
.\venv\Scripts\python.exe -m pytest
```
* **Expected Outcome**: **18 tests pass successfully** (including 8 privacy/consent engine tests, 5 pipeline tests, and 5 telemetry tests).
  ```text
  ===================== 18 passed, 4622 warnings in 19.64s ======================
  ```

### 2. Verify Key Live User Flows in the Portal
Navigate to the Constant URL: `https://kpc-inuka-compliance.loca.lt/dashboard.html`
* **Test Flow 1: PII Masking toggle**: Log in as `hq_director`. Toggle **"KDPA Masking"** on the table header. Verify that PII columns instantly obfuscate.
* **Test Flow 2: Compliant Report Export**: Click **"Export Compliant Report (CSV)"**. Verify that a CSV file containing the active view is downloaded with 100% masked/redacted PII fields.
* **Test Flow 3: Self-Service Portal**: Log in as beneficiary **`INK-2026-1002`** (password: `password`). Verify that you can view your enrollment details, toggle granular consent purposes, and request profile erasure.
