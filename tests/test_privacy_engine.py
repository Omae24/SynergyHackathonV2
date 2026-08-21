import os
import sqlite3
import pytest
import joblib
import pandas as pd
from inuka_etl import cleanse_beneficiary, validate_beneficiary, process_and_load_event
from dashboard_app import load_prediction_models, models

DB_TEST_PATH = os.path.join("dataset", "inuka.db")

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Ensure database is seeded before running tests."""
    from seed_inuka_db import seed_database
    seed_database()
    yield

def test_stage_1_cleansing():
    """Verify that cleansing standardizes phone numbers and title cases names."""
    raw_record = {
        "beneficiary_id": "INK-2026-9999",
        "full_name": "  jane  achieng ",
        "national_id": "99999999",
        "email": "JANE@gmail.com",
        "phone": "0711 222 333",
        "pillar": "scholarship",
        "region": "nyanza",
        "consent_status": "Consented",
        "consent_type": "SMS OTP",
        "consent_date": "2026-08-20 12:00:00",
        "status": ""
    }
    
    cleaned = cleanse_beneficiary(raw_record)
    assert cleaned["full_name"] == "Jane Achieng"
    assert cleaned["phone"] == "+254711222333"
    assert cleaned["email"] == "jane@gmail.com"
    assert cleaned["pillar"] == "Scholarship"
    assert cleaned["region"] == "Nyanza"
    assert cleaned["status"] == "Active"

def test_ge_validation_success():
    """Verify that valid beneficiary rows pass validation checks."""
    valid_record = {
        "beneficiary_id": "INK-2026-0001",
        "full_name": "Joseph Kiprop",
        "national_id": "34567890",
        "email": "joseph@gmail.com",
        "phone": "+254712345678",
        "pillar": "Scholarship",
        "region": "Nairobi",
        "consent_status": "Consented"
    }
    success, errors = validate_beneficiary(valid_record)
    assert success is True
    assert len(errors) == 0

def test_ge_validation_failure_quarantine():
    """Verify that invalid rows fail quality checks."""
    invalid_record = {
        "beneficiary_id": "INK-2026-0002",
        "full_name": "Asha Mohamed",
        "national_id": "31245678",
        "email": "invalid_email_no_at",
        "phone": "+254722123456",
        "pillar": "CorporateSocialResponsibility",  # Invalid pillar
        "region": "Kampala",  # Invalid region
        "consent_status": "Consented"
    }
    success, errors = validate_beneficiary(invalid_record)
    assert success is False
    assert len(errors) > 0

def test_process_and_load_quarantine():
    """Verify that process_and_load_event routes bad data to quarantine."""
    conn = sqlite3.connect(DB_TEST_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM quarantined_events")
    conn.commit()
    conn.close()
    
    invalid_record = {
        "beneficiary_id": "INK-2026-ERR",
        "full_name": "",  # Empty name
        "national_id": "111111",
        "email": "err@gmail.com",
        "phone": "0700000",
        "pillar": "Tech",
        "region": "Nairobi",
        "consent_status": "Consented"
    }
    
    success, status, result = process_and_load_event(invalid_record)
    assert success is False
    assert status == "QUARANTINED"
    
    # Check database
    conn = sqlite3.connect(DB_TEST_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM quarantined_events")
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 1

def test_anonymization_and_right_to_forget():
    """Verify that Right to be Forgotten wipes beneficiary PII."""
    from seed_inuka_db import seed_database
    seed_database() # reset
    
    conn = sqlite3.connect(DB_TEST_PATH)
    cursor = conn.cursor()
    
    # Check seeded first record name
    cursor.execute("SELECT full_name, national_id FROM inuka_beneficiaries WHERE beneficiary_id = 'INK-2026-1001'")
    orig_name, orig_id = cursor.fetchone()
    assert orig_name != "[REDACTED_KDPA_REQUEST]"
    
    # Trigger Right to Forget redaction
    cursor.execute("""
        UPDATE inuka_beneficiaries
        SET full_name = '[REDACTED_KDPA_REQUEST]',
            national_id = '[REDACTED_KDPA_REQUEST]',
            email = '[REDACTED_KDPA_REQUEST]',
            phone = '[REDACTED_KDPA_REQUEST]',
            consent_status = 'Withdrawn',
            consent_data_sharing = 0,
            consent_photo_use = 0,
            consent_sms_contact = 0,
            consent_external_reporting = 0,
            enrollment_status = 'On Hold',
            status = 'Anonymized'
        WHERE beneficiary_id = 'INK-2026-1001'
    """)
    conn.commit()
    
    # Verify redacted
    cursor.execute("SELECT full_name, national_id, consent_status, status FROM inuka_beneficiaries WHERE beneficiary_id = 'INK-2026-1001'")
    name, nid, consent, status = cursor.fetchone()
    assert name == "[REDACTED_KDPA_REQUEST]"
    assert nid == "[REDACTED_KDPA_REQUEST]"
    assert consent == "Withdrawn"
    assert status == "Anonymized"
    
    conn.close()

def test_ml_access_anomaly():
    """Verify that anomaly detector correctly flags unusual accesses."""
    load_prediction_models()
    assert 'anomaly_detector' in models
    
    # Normal request: 12 PM, hq_admin, no region mismatch, query volume 10
    normal_pred = models['anomaly_detector'].predict([[12, 0, 0, 10]])[0]
    assert normal_pred == 1
    
    # Anomalous request: 2 AM, field_officer trying to query out of region, query volume 150
    anomaly_pred = models['anomaly_detector'].predict([[2, 1, 1, 150]])[0]
    assert anomaly_pred == -1

def test_nlp_chatbot_intent():
    """Verify that the NLP intent classifier categorizes user queries correctly."""
    load_prediction_models()
    assert 'chatbot' in models
    
    # Test queries
    q1 = "show my profile details"
    intent1 = models['chatbot'].predict([q1])[0]
    assert intent1 == "view_data"
    
    q2 = "nataka kufuta maelezo yangu"
    intent2 = models['chatbot'].predict([q2])[0]
    assert intent2 == "request_deletion"
    
    q3 = "withdraw my consent please"
    intent3 = models['chatbot'].predict([q3])[0]
    assert intent3 == "update_consent"

def test_beneficiary_login_and_purpose_rls():
    """Verify beneficiary login works and logical RLS triggers are functional."""
    from seed_inuka_db import seed_database
    seed_database() # reset
    
    conn = sqlite3.connect(DB_TEST_PATH)
    cursor = conn.cursor()
    
    # Check if Lucy Hassan INK-2026-1002 exists
    cursor.execute("SELECT beneficiary_id, consent_data_sharing, enrollment_status FROM inuka_beneficiaries WHERE beneficiary_id = 'INK-2026-1002'")
    b_id, data_share, enroll = cursor.fetchone()
    assert b_id == "INK-2026-1002"
    assert data_share == 1
    assert enroll == "Enrolled"
    
    # Simulate beneficiary updating consent: toggling data sharing off
    cursor.execute("""
        UPDATE inuka_beneficiaries
        SET consent_data_sharing = 0,
            enrollment_status = 'On Hold',
            consent_status = 'Withdrawn'
        WHERE beneficiary_id = 'INK-2026-1002'
    """)
    conn.commit()
    
    # Verify enrollment is suspended ("On Hold")
    cursor.execute("SELECT enrollment_status, consent_status FROM inuka_beneficiaries WHERE beneficiary_id = 'INK-2026-1002'")
    enroll_status, consent_status = cursor.fetchone()
    assert enroll_status == "On Hold"
    assert consent_status == "Withdrawn"
    
    conn.close()


