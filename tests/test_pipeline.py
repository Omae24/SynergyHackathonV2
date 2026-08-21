import os
import pytest
import pandas as pd
import sqlite3
from extract import extract_data
from transform import clean_data
from load import run_validation_and_load

# We use absolute or relative paths for testing
RAW_TEST_PATH = os.path.join("dataset", "kpc_depot_raw.csv")
EXTRACTED_TEST_PATH = os.path.join("dataset", "kpc_depot_extracted.csv")
TRANSFORMED_TEST_PATH = os.path.join("dataset", "kpc_depot_transformed.csv")
CLEAN_TEST_PATH = os.path.join("dataset", "kpc_depot_clean.csv")
DB_TEST_PATH = os.path.join("dataset", "kpc_depot.db")

def test_extraction():
    """Verify that extraction runs and generates a file with correct schema."""
    df = extract_data(RAW_TEST_PATH, EXTRACTED_TEST_PATH)
    assert os.path.exists(EXTRACTED_TEST_PATH)
    assert len(df) > 0
    assert "transaction_id" in df.columns
    assert "depot_location" in df.columns

def test_transformation():
    """Verify that cleaning removes duplicates, standardizes strings, and fixes missing data."""
    # Ensure extracted file exists
    if not os.path.exists(EXTRACTED_TEST_PATH):
        extract_data(RAW_TEST_PATH, EXTRACTED_TEST_PATH)
        
    df_clean = clean_data(EXTRACTED_TEST_PATH, TRANSFORMED_TEST_PATH)
    assert os.path.exists(TRANSFORMED_TEST_PATH)
    
    # Check duplicate removal (should be 5500 unique transaction_ids)
    assert df_clean["transaction_id"].duplicated().sum() == 0
    
    # Check casing standardization
    assert set(df_clean["depot_location"].unique()).issubset({"Nairobi", "Kisumu", "Mombasa", "Eldoret", "Nakuru"})
    
    # Check negative volume correction (no negative values)
    assert (df_clean["actual_loaded_liters"] < 0).sum() == 0
    
    # Verify reconstructed row (TXN-02572) has correct actual loaded liters
    # TXN-02572 had -1 actual_loaded_liters, ordered_volume = 45000, loading_accuracy = 99.89
    # Reconstructed actual = round((99.89 / 100) * 45000) = 44950.5 rounds to 44950
    txn_rec = df_clean[df_clean["transaction_id"] == "TXN-02572"]
    if len(txn_rec) > 0:
        assert txn_rec["actual_loaded_liters"].values[0] in [44950, 44951]

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
    df_db = pd.read_sql("SELECT * FROM depot_operations", conn)
    conn.close()
    
    assert len(df_db) == 5500
    assert "transaction_id" in df_db.columns

def test_models_exist():
    """Verify that models and feature columns are trained and saved."""
    assert os.path.exists(os.path.join("models", "tat_regressor.joblib"))
    assert os.path.exists(os.path.join("models", "demurrage_classifier.joblib"))
    assert os.path.exists(os.path.join("models", "model_columns.json"))

def test_prediction_logic():
    """Verify that we can load models and run a prediction on a sample payload."""
    import joblib
    import json
    
    reg = joblib.load(os.path.join("models", "tat_regressor.joblib"))
    clf = joblib.load(os.path.join("models", "demurrage_classifier.joblib"))
    with open(os.path.join("models", "model_columns.json"), 'r') as f:
        columns = json.load(f)
        
    # Construct dummy input matching one-hot schema
    input_df = pd.DataFrame(0, index=[0], columns=columns)
    if "ordered_volume_liters" in input_df.columns:
        input_df["ordered_volume_liters"] = 45000
    if "hour_of_day" in input_df.columns:
        input_df["hour_of_day"] = 12
        
    # Predict
    pred_tat = reg.predict(input_df)[0]
    pred_prob = clf.predict_proba(input_df)[0, 1]
    
    assert isinstance(pred_tat, float)
    assert 0.0 <= pred_prob <= 1.0
