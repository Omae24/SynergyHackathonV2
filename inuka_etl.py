import pandas as pd
import re
import os
import sqlite3
import datetime
import great_expectations as gx
from great_expectations.expectations import (
    ExpectColumnValuesToNotBeNull,
    ExpectColumnValuesToBeInSet,
    ExpectColumnValuesToMatchRegex
)

DB_PATH = os.path.join("dataset", "kpc_depot.db")
REGIONS_SET = ["North Eastern", "Coastal", "Eastern", "Central", "Nairobi", "Nyanza", "Rift Valley", "Western"]

# Global Great Expectations Setup
print("Initializing Great Expectations context for Inuka ETL...")
context = gx.get_context()

# Reuse or add data source
try:
    data_source = context.data_sources.add_pandas("inuka_streaming_datasource")
except Exception:
    data_source = context.data_sources.get("inuka_streaming_datasource")

# Reuse or add data asset
try:
    data_asset = data_source.add_dataframe_asset("inuka_event_asset")
except Exception:
    data_asset = data_source.get_asset("inuka_event_asset")

# Reuse or add batch definition
try:
    batch_def = data_asset.add_batch_definition_whole_dataframe("inuka_event_batch_def")
except Exception:
    batch_def = data_asset.get_batch_definition("inuka_event_batch_def")

# Reuse or add expectation suite
try:
    suite = context.suites.add(gx.ExpectationSuite("inuka_quality_suite"))
except Exception:
    suite = context.suites.get("inuka_quality_suite")

# Populate expectations if empty
if not suite.expectations:
    suite.add_expectation(ExpectColumnValuesToNotBeNull(column="beneficiary_id"))
    suite.add_expectation(ExpectColumnValuesToNotBeNull(column="full_name"))
    suite.add_expectation(ExpectColumnValuesToBeInSet(
        column="pillar",
        value_set=["Scholarship", "Plus", "Vocational", "Tech"]
    ))
    suite.add_expectation(ExpectColumnValuesToBeInSet(
        column="region",
        value_set=REGIONS_SET
    ))
    suite.add_expectation(ExpectColumnValuesToBeInSet(
        column="consent_status",
        value_set=["Consented", "Pending", "Withdrawn"]
    ))
    suite.add_expectation(ExpectColumnValuesToMatchRegex(
        column="email",
        regex=r"^[^@]+@[^@]+\.[^@]+$"
    ))

# Reuse or add validation definition
try:
    validation_def = context.validation_definitions.add(
        gx.ValidationDefinition(
            name="inuka_validation_def",
            data=batch_def,
            suite=suite
        )
    )
except Exception:
    validation_def = context.validation_definitions.get("inuka_validation_def")


def cleanse_beneficiary(data: dict) -> dict:
    """Stage 1 Cleanse Logic: Clean and format fields to ensure operational integrity."""
    cleaned = data.copy()
    
    # Map empty strings to None so they trigger NotNull quality checks
    for k, v in list(cleaned.items()):
        if str(v).strip() == "":
            cleaned[k] = None
    
    # 1. Clean name (Title Case, collapsing extra whitespace)
    if 'full_name' in cleaned and cleaned['full_name']:
        name_str = str(cleaned['full_name']).strip()
        collapsed_name = " ".join(name_str.split())
        cleaned['full_name'] = collapsed_name.title()
        
    # 2. Standardize Kenyan phone number to E.164
    if 'phone' in cleaned and cleaned['phone']:
        phone = str(cleaned['phone']).replace(" ", "").strip()
        if phone.startswith("07"):
            phone = "+254" + phone[1:]
        elif phone.startswith("01"):
            phone = "+254" + phone[1:]
        elif phone.startswith("7") or phone.startswith("1"):
            phone = "+254" + phone
        cleaned['phone'] = phone
        
    # 3. Clean email
    if 'email' in cleaned and cleaned['email']:
        cleaned['email'] = str(cleaned['email']).strip().lower()
        
    # 4. Standardize pillar to Sentence Case
    if 'pillar' in cleaned and cleaned['pillar']:
        p = str(cleaned['pillar']).strip().lower()
        if p == 'scholarship':
            cleaned['pillar'] = 'Scholarship'
        elif p == 'plus':
            cleaned['pillar'] = 'Plus'
        elif p == 'vocational':
            cleaned['pillar'] = 'Vocational'
        elif p == 'tech':
            cleaned['pillar'] = 'Tech'
            
    # 5. Standardize region
    if 'region' in cleaned and cleaned['region']:
        r = str(cleaned['region']).strip().title()
        # Map some common abbreviations/slang if needed
        if r.lower() == 'north-eastern':
            r = 'North Eastern'
        elif r.lower() == 'riftvalley':
            r = 'Rift Valley'
        cleaned['region'] = r
        
    # 6. Default status if not provided
    if 'status' not in cleaned or not cleaned['status']:
        cleaned['status'] = 'Active'
        
    return cleaned


def validate_beneficiary(data: dict) -> tuple:
    """Run in-memory validation using Great Expectations suite."""
    df = pd.DataFrame([data])
    
    try:
        res = validation_def.run(batch_parameters={"dataframe": df})
        
        if res.success:
            return True, []
        else:
            errors = []
            for validation_result in res.results:
                if not validation_result.success:
                    col = validation_result.expectation_config.kwargs.get('column')
                    exp_type = validation_result.expectation_config.type
                    errors.append(f"Validation failed on column '{col}' for check '{exp_type}'")
            return False, errors
    except Exception as ex:
        errors = []
        if not data.get("beneficiary_id"):
            errors.append("beneficiary_id cannot be null")
        if not data.get("full_name"):
            errors.append("full_name cannot be null")
        if data.get("pillar") not in ["Scholarship", "Plus", "Vocational", "Tech"]:
            errors.append("pillar must be Scholarship, Plus, Vocational, or Tech")
        if data.get("region") not in REGIONS_SET:
            errors.append(f"region must be one of {REGIONS_SET}")
        if data.get("consent_status") not in ["Consented", "Pending", "Withdrawn"]:
            errors.append("consent_status must be Consented, Pending, or Withdrawn")
        if data.get("email") and not re.match(r"^[^@]+@[^@]+\.[^@]+$", data.get("email")):
            errors.append("email format is invalid")
            
        return len(errors) == 0, errors


def process_and_load_event(data: dict) -> tuple:
    """Processes, cleanses, validates, and loads a single beneficiary stream event."""
    conn = None
    try:
        # 1. Cleanse data
        cleaned = cleanse_beneficiary(data)
        
        # 2. Validate
        is_valid, errors = validate_beneficiary(cleaned)
        
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        cursor = conn.cursor()
        
        if is_valid:
            # Determine consent purpose values and enrollment status matching logic
            consent_status = cleaned['consent_status']
            if consent_status == "Consented":
                enrollment_status = "Enrolled"
                consent_data_sharing = 1
                consent_photo_use = 1
                consent_sms_contact = 1
                consent_external_reporting = 1
            elif consent_status == "Pending":
                enrollment_status = "Pending Review"
                consent_data_sharing = 0
                consent_photo_use = 0
                consent_sms_contact = 0
                consent_external_reporting = 0
            else: # Withdrawn
                enrollment_status = "On Hold"
                consent_data_sharing = 0
                consent_photo_use = 0
                consent_sms_contact = 0
                consent_external_reporting = 0

            # 3. Load all 16 columns to inuka_beneficiaries
            cursor.execute("""
                INSERT OR REPLACE INTO inuka_beneficiaries 
                (beneficiary_id, full_name, national_id, email, phone, pillar, region, 
                 consent_status, consent_type, consent_date, status, enrollment_status,
                 consent_data_sharing, consent_photo_use, consent_sms_contact, consent_external_reporting)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cleaned['beneficiary_id'],
                cleaned['full_name'],
                cleaned['national_id'],
                cleaned['email'],
                cleaned['phone'],
                cleaned['pillar'],
                cleaned['region'],
                cleaned['consent_status'],
                cleaned.get('consent_type'),
                cleaned.get('consent_date'),
                cleaned['status'],
                enrollment_status,
                consent_data_sharing,
                consent_photo_use,
                consent_sms_contact,
                consent_external_reporting
            ))
            
            # Log successful ingestion in the compliance audit trail
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO privacy_audit_log (timestamp, operator, action_type, target_beneficiary_id, details, ip_address, is_anomaly)
                VALUES (?, 'streaming_pipeline', 'BENEFICIARY_INGEST', ?, ?, '127.0.0.1', 0)
            """, (timestamp, cleaned['beneficiary_id'], f"Real-time stream registered beneficiary: {cleaned['full_name']} under {cleaned['pillar']} pillar."))
            
            conn.commit()
            return True, "SUCCESS", cleaned
        else:
            # 4. Route to quarantined_events
            import json
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO quarantined_events (timestamp, raw_payload, failure_reasons)
                VALUES (?, ?, ?)
            """, (timestamp, json.dumps(data), "; ".join(errors)))
            
            conn.commit()
            return False, "QUARANTINED", errors
            
    except Exception as e:
        import traceback
        print(f"[ERROR in process_and_load_event] {e}")
        traceback.print_exc()
        return False, "ERROR", [str(e)]
    finally:
        if conn:
            conn.close()
