import os
import pytest
import pandas as pd
import sqlite3
from extract import extract_data
from transform import clean_data
from load import run_validation_and_load

RAW_TEST_PATH = os.path.join("dataset", "inuka_beneficiary_raw.csv")
EXTRACTED_TEST_PATH = os.path.join("dataset", "inuka_beneficiary_extracted.csv")
TRANSFORMED_TEST_PATH = os.path.join("dataset", "inuka_beneficiary_transformed.csv")
CLEAN_TEST_PATH = os.path.join("dataset", "inuka_beneficiary_clean.csv")
DB_TEST_PATH = os.path.join("dataset", "inuka.db")

def test_extraction():
    """Verify that extraction runs and generates a file with correct schema."""
    df = extract_data(RAW_TEST_PATH, EXTRACTED_TEST_PATH)
    assert os.path.exists(EXTRACTED_TEST_PATH)
    assert len(df) > 0
    assert "beneficiary_id" in df.columns
    assert "full_name" in df.columns

def test_transformation():
    """Verify that cleaning removes duplicates, standardizes strings, and standardizes formats."""
    if not os.path.exists(EXTRACTED_TEST_PATH):
        extract_data(RAW_TEST_PATH, EXTRACTED_TEST_PATH)
        
    df_clean = clean_data(EXTRACTED_TEST_PATH, TRANSFORMED_TEST_PATH)
    assert os.path.exists(TRANSFORMED_TEST_PATH)
    
    # Check duplicate removal
    assert df_clean["beneficiary_id"].duplicated().sum() == 0
    
    # Check names title casing
    # Wait, check if any name is not Title Cased
    sample_names = df_clean["full_name"].tolist()
    for name in sample_names:
        assert name == name.title()

    # Check phone standardization
    sample_phones = df_clean["phone"].dropna().tolist()
    for phone in sample_phones:
        assert phone.startswith("+254")

def test_load_and_validation():
    """Verify that Great Expectations validation succeeds and data loads into CSV/SQLite."""
    if not os.path.exists(TRANSFORMED_TEST_PATH):
        clean_data(EXTRACTED_TEST_PATH, TRANSFORMED_TEST_PATH)
        
    success = run_validation_and_load(TRANSFORMED_TEST_PATH, CLEAN_TEST_PATH, DB_TEST_PATH)
    assert success is True
    assert os.path.exists(CLEAN_TEST_PATH)
    assert os.path.exists(DB_TEST_PATH)
    
    # Query database
    conn = sqlite3.connect(DB_TEST_PATH)
    df_db = pd.read_sql("SELECT * FROM inuka_beneficiaries", conn)
    conn.close()
    
    assert len(df_db) > 0
    assert "beneficiary_id" in df_db.columns
