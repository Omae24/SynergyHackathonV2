import os
import sqlite3
import pandas as pd
import great_expectations as gx
from great_expectations.expectations import (
    ExpectColumnValuesToBeUnique,
    ExpectColumnValuesToNotBeNull,
    ExpectColumnValuesToBeInSet,
    ExpectColumnValuesToBeBetween
)

def run_validation_and_load(transformed_path, clean_csv_path, db_path):
    print("--- STARTING LOAD STAGE (QUALITY GATE) ---")
    if not os.path.exists(transformed_path):
        raise FileNotFoundError(f"Transformed dataset not found at: {transformed_path}")
        
    df = pd.read_csv(transformed_path)
    print(f"Loaded {len(df)} rows for validation.")
    
    # 1. Great Expectations Ephemeral Context Setup
    context = gx.get_context()
    
    # Add pandas data source and asset
    data_source = context.data_sources.add_pandas("kpc_pipeline_datasource")
    data_asset = data_source.add_dataframe_asset("kpc_transformed_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("kpc_batch_def")
    
    # Create Expectation Suite
    suite = context.suites.add(gx.ExpectationSuite("kpc_quality_gate_suite"))
    
    # Define expectations
    expectations = [
        ExpectColumnValuesToNotBeNull(column="transaction_id"),
        ExpectColumnValuesToBeUnique(column="transaction_id"),
        ExpectColumnValuesToBeInSet(
            column="depot_location", 
            value_set=["Nairobi", "Kisumu", "Mombasa", "Eldoret", "Nakuru"]
        ),
        ExpectColumnValuesToBeInSet(
            column="product_type",
            value_set=[
                "Automotive Gas Oil (AGO)", 
                "Illuminating Kerosene (IK)", 
                "Jet A1", 
                "Premium Motor Spirit (PMS)"
            ]
        ),
        ExpectColumnValuesToBeBetween(
            column="ordered_volume_liters", 
            min_value=30000, 
            max_value=60000
        ),
        ExpectColumnValuesToBeBetween(
            column="actual_loaded_liters", 
            min_value=20000, 
            max_value=65000
        ),
        ExpectColumnValuesToBeBetween(
            column="loading_accuracy", 
            min_value=95.0, 
            max_value=105.0
        ),
        ExpectColumnValuesToBeBetween(
            column="total_tat_minutes", 
            min_value=30.0, 
            max_value=1000.0
        ),
        ExpectColumnValuesToBeInSet(
            column="demurrage_incurred", 
            value_set=[0, 1]
        )
    ]
    
    for exp in expectations:
        suite.add_expectation(exp)
        
    print(f"Expectation Suite defined with {len(expectations)} validation checks.")
    
    # Add validation definition and run validation
    validation_definition = context.validation_definitions.add(
        gx.ValidationDefinition(
            name="kpc_validation_def",
            data=batch_def,
            suite=suite
        )
    )
    
    print("Running data quality validation...")
    validation_result = validation_definition.run(batch_parameters={"dataframe": df})
    
    # Inspect validation result
    if not validation_result.success:
        print("\n[ERROR] DATA QUALITY GATE FAILED! Review unexpected results:")
        for res in validation_result.results:
            if not res.success:
                print(f"  Failed: {res.expectation_config.type} on column '{res.expectation_config.kwargs.get('column')}'")
                print(f"  Details: {res.result}")
        raise ValueError("Data validation failed. Data loaded is rejected.")
        
    print("--- DATA QUALITY GATE PASSED ---")
    print("All Great Expectations validation checks passed successfully!")
    
    # 2. Load Clean CSV
    os.makedirs(os.path.dirname(clean_csv_path), exist_ok=True)
    df.to_csv(clean_csv_path, index=False)
    print(f"Clean CSV file successfully loaded to: {clean_csv_path}")
    
    # 3. Load to SQLite Database
    print(f"Connecting to SQLite database at {db_path}...")
    conn = sqlite3.connect(db_path)
    
    # Drop existing table if any and load fresh data
    df.to_sql("depot_operations", conn, if_exists="replace", index=False)
    
    # Verify load
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM depot_operations")
    row_count = cursor.fetchone()[0]
    conn.close()
    
    print(f"Successfully loaded {row_count} rows into 'depot_operations' table in {db_path}.")
    print("--- LOAD STAGE COMPLETED ---")
    return True

if __name__ == "__main__":
    TRANSFORMED_PATH = os.path.join("dataset", "kpc_depot_transformed.csv")
    CLEAN_CSV_PATH = os.path.join("dataset", "kpc_depot_clean.csv")
    DB_PATH = os.path.join("dataset", "kpc_depot.db")
    run_validation_and_load(TRANSFORMED_PATH, CLEAN_CSV_PATH, DB_PATH)
