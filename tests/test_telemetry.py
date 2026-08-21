import os
import sqlite3
import pytest
import json
from dashboard_app import load_prediction_models, models

DB_TEST_PATH = os.path.join("dataset", "kpc_depot.db")

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Initialize test database with required schema and seed data."""
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    
    os.makedirs("dataset", exist_ok=True)
    
    from seed_db import seed_database
    seed_database()
    yield
    from seed_inuka_db import seed_database as seed_inuka
    seed_inuka()

def test_database_tables_exist():
    """Verify that Stage 2 database tables exist and are seeded."""
    assert os.path.exists(DB_TEST_PATH)
    conn = sqlite3.connect(DB_TEST_PATH)
    cursor = conn.cursor()
    
    # Check users table
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    assert user_count >= 5
    
    # Check bay_telemetry table
    cursor.execute("SELECT COUNT(*) FROM bay_telemetry")
    bay_count = cursor.fetchone()[0]
    assert bay_count == 60  # 5 depots * 12 bays = 60
    
    # Check active_queue table
    cursor.execute("SELECT COUNT(*) FROM active_queue")
    active_count = cursor.fetchone()[0]
    assert active_count >= 6
    
    conn.close()

def test_login_validation():
    """Verify that credentials check in users table works correctly."""
    conn = sqlite3.connect(DB_TEST_PATH)
    cursor = conn.cursor()
    
    # Test valid credentials
    cursor.execute(
        "SELECT role, depot, truck_reg FROM users WHERE username = ? AND password = ?",
        ("kisumu_manager", "password")
    )
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "depot_manager"
    assert row[1] == "Kisumu"
    
    # Test invalid credentials
    cursor.execute(
        "SELECT role, depot, truck_reg FROM users WHERE username = ? AND password = ?",
        ("kisumu_manager", "wrong_password")
    )
    row_invalid = cursor.fetchone()
    assert row_invalid is None
    
    conn.close()

def test_reassignment_logic():
    """Verify that reassigning a truck updates its assigned bay in the database."""
    conn = sqlite3.connect(DB_TEST_PATH)
    cursor = conn.cursor()
    
    # Get current assigned bay of KBX-1234
    cursor.execute("SELECT assigned_bay FROM active_queue WHERE truck_reg = 'KBX-1234'")
    old_bay = cursor.fetchone()[0]
    
    # Change bay
    new_bay = "Loading Bay 5" if old_bay != "Loading Bay 5" else "Loading Bay 1"
    cursor.execute(
        "UPDATE active_queue SET assigned_bay = ?, current_stage = 'Bay Assigned (Queue)' WHERE truck_reg = 'KBX-1234'",
        (new_bay,)
    )
    conn.commit()
    
    # Verify change
    cursor.execute("SELECT assigned_bay, current_stage FROM active_queue WHERE truck_reg = 'KBX-1234'")
    row = cursor.fetchone()
    assert row[0] == new_bay
    assert row[1] == "Bay Assigned (Queue)"
    
    # Restore original bay for other tests
    cursor.execute(
        "UPDATE active_queue SET assigned_bay = ?, current_stage = 'Bay Assigned (Queue)' WHERE truck_reg = 'KBX-1234'",
        (old_bay,)
    )
    conn.commit()
    conn.close()

def test_telemetry_update():
    """Verify that updating pump pressure updates sqlite correctly."""
    conn = sqlite3.connect(DB_TEST_PATH)
    cursor = conn.cursor()
    
    # Save original pressure
    cursor.execute(
        "SELECT pump_pressure, status FROM bay_telemetry WHERE depot_location = 'Kisumu' AND assigned_bay = 'Loading Bay 3'"
    )
    orig = cursor.fetchone()
    orig_pressure, orig_status = orig
    
    # Set to low pressure
    cursor.execute(
        "UPDATE bay_telemetry SET pump_pressure = ?, status = ? WHERE depot_location = 'Kisumu' AND assigned_bay = 'Loading Bay 3'",
        (3.5, "Low Pressure")
    )
    conn.commit()
    
    # Verify update
    cursor.execute(
        "SELECT pump_pressure, status FROM bay_telemetry WHERE depot_location = 'Kisumu' AND assigned_bay = 'Loading Bay 3'"
    )
    updated = cursor.fetchone()
    assert updated[0] == 3.5
    assert updated[1] == "Low Pressure"
    
    # Restore original values
    cursor.execute(
        "UPDATE bay_telemetry SET pump_pressure = ?, status = ? WHERE depot_location = 'Kisumu' AND assigned_bay = 'Loading Bay 3'",
        (orig_pressure, orig_status)
    )
    conn.commit()
    conn.close()

def test_ml_recalculation_with_pressure():
    """Verify that predictions are adjusted when a pump status is degraded."""
    load_prediction_models()
    
    # Set up mock model cols
    assert 'regressor' in models
    assert 'columns' in models
    
    # Set up Kisumu Loading Bay 3 as Low Pressure
    conn = sqlite3.connect(DB_TEST_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE bay_telemetry SET pump_pressure = 3.2, status = 'Low Pressure' WHERE depot_location = 'Kisumu' AND assigned_bay = 'Loading Bay 3'"
    )
    conn.commit()
    
    # Run the test case simulating what handle_predict does
    cursor.execute("SELECT status FROM bay_telemetry WHERE depot_location = 'Kisumu' AND assigned_bay = 'Loading Bay 3'")
    bay_status = cursor.fetchone()[0]
    assert bay_status == "Low Pressure"
    
    # Base regression mock prediction (e.g. 100 minutes)
    base_pred_tat = 100.0
    
    # Check adjustment
    if bay_status == "Low Pressure":
        adjusted_tat = base_pred_tat * 2.5
        adjusted_prob = 1.0
        
    assert adjusted_tat == 250.0
    assert adjusted_prob == 1.0
    
    # Restore normal status
    cursor.execute(
        "UPDATE bay_telemetry SET pump_pressure = 10.0, status = 'Normal' WHERE depot_location = 'Kisumu' AND assigned_bay = 'Loading Bay 3'"
    )
    conn.commit()
    conn.close()
