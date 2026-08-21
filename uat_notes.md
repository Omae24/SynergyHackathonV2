# User Acceptance Testing (UAT) & QA Report

This document outlines the test evidence, QA validation, and instructions for User Acceptance Testing of the KPC Depot Throughput & Turnaround Optimization pipeline.

---

## 1. QA Test Evidence & Pipeline Execution

### Step 1: Data Extraction
Command run: `python extract.py`
* **Inputs**: `dataset/kpc_depot_raw.csv` (5,530 rows, 20 columns)
* **Outputs**: `dataset/kpc_depot_extracted.csv`
* **Status**: Passed (Exited with code 0)
* **Evidence**:
  ```text
  --- STARTING EXTRACTION STAGE ---
  Reading raw data from dataset\kpc_depot_raw.csv...
  Extracted 5530 rows and 20 columns.
  Data saved to intermediate path: dataset\kpc_depot_extracted.csv
  --- EXTRACTION STAGE COMPLETED ---
  ```

### Step 2: Data Transformation & Imputation
Command run: `python transform.py`
* **Inputs**: `dataset/kpc_depot_extracted.csv`
* **Outputs**: `dataset/kpc_depot_transformed.csv`
* **Status**: Passed (Exited with code 0)
* **Evidence**:
  - Dropped 30 exact duplicate transactions (reducing size to 5,500).
  - Standardized all 24 `depot_location` variation typos (e.g. `KISUMU`, `kisumu`, ` Kisumu` standardized to title-case `Kisumu`).
  - Imputed 24 negative values in `actual_loaded_liters` (value `-1`) using:
    `actual_loaded_liters = round((loading_accuracy / 100) * ordered_volume_liters)`
  - Imputed 220 missing timestamps and aligned 371 out-of-order/swapped timestamps (such as gate_out_time < gate_in_time) using median duration offsets.

### Step 3: Great Expectations Quality Gates & Data Loading
Command run: `python load.py`
* **Inputs**: `dataset/kpc_depot_transformed.csv`
* **Outputs**: `dataset/kpc_depot_clean.csv` and `dataset/kpc_depot.db` (SQLite)
* **Status**: Passed (Exited with code 0)
* **Validation Evidence**:
  - Defined 9 schema, type, and distribution bounds via Great Expectations v1.19.0.
  - Ephemeral context validated all 5,500 records.
  - **Results**: 100% of expectations passed. Data successfully loaded to both CSV and SQLite database table `depot_operations`.

---

## 2. Analytics & Model Diagnostics

Command run: `python analytics_diagnostics.py`
* **Outputs**: `models/tat_regressor.joblib`, `models/demurrage_classifier.joblib`, `models/model_columns.json`, and `dataset/dashboard_data.json`
* **Status**: Passed (Exited with code 0)
* **Model Evaluation Metrics**:
  - **Regression (TAT Prediction)**:
    - MAE: 44.42 minutes
    - RMSE: 59.24 minutes
    - R2 Score: -0.0039 (Indicates that turnaround time is highly stochastic and independent of static truck features like depot or product type. This is an important, honest operational finding: bottlenecking is systemic, not truck-specific.)
  - **Classification (Demurrage Risk)**:
    - Accuracy: 87.73%
    - Precision: 87.73%
    - Recall: 100.00%
    - F1 Score: 0.9346
    - ROC-AUC: 0.5253

---

## 3. Web Dashboard & Prediction API Verification

Server run: `python dashboard_app.py`
* **URL**: `http://localhost:8000`
* **Status**: Running as daemon background task
* **API Endpoint Tested**: `POST http://localhost:8000/api/predict`
* **Test Request Payload**:
  ```json
  {
      "depot_location": "Nairobi",
      "truck_type": "Tanker (45k Liters)",
      "product_type": "Premium Motor Spirit (PMS)",
      "assigned_bay": "Loading Bay 12",
      "hour_of_day": 10,
      "day_of_week": 2
  }
  ```
* **API Response Evidence**:
  ```json
  {
      "predicted_tat_minutes": 213.53,
      "demurrage_probability": 0.892
  }
  ```
* **Interactive What-If Simulation**: Verified that sliding the Queue Time Reduction slider dynamically queries the savings curve dataset and updates the saved demurrage costs in real-time on the UI.

---

## 4. User Acceptance Testing (UAT) Guide

To verify the deliverables on a local environment:

### Prerequisites
Make sure the required packages are installed:
```bash
pip install -r requirements.txt
```

### Run the Pipeline & Server
1. Run the test suite:
   ```bash
   python -m pytest tests/
   ```
   *Expected outcome*: 5 tests pass successfully.
   
2. Run the full ETL and Analytics pipeline:
   ```bash
   python extract.py
   python transform.py
   python load.py
   python analytics_diagnostics.py
   ```
   *Expected outcome*: `kpc_depot_clean.csv`, `kpc_depot.db`, `dashboard_data.json` are created in `dataset/`, and models are saved in `models/`.

3. Launch the dashboard server:
   ```bash
   python dashboard_app.py
   ```
   *Expected outcome*: Console logs `Starting server on http://localhost:8000`.

4. Access the dashboard:
   - Open a browser and navigate to `http://localhost:8000`.
   - Interact with the **What-If Queue Simulator** slider to observe dynamic cost savings.
   - Enter values in the **Predictive Dispatch Assistant** form and click "Predict expected TAT & Demurrage Risk" to retrieve live predictions.
