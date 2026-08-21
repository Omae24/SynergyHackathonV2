import os
import sqlite3
import pandas as pd
import great_expectations as gx
from great_expectations.expectations import (
    ExpectColumnValuesToBeUnique,
    ExpectColumnValuesToNotBeNull,
    ExpectColumnValuesToBeInSet,
    ExpectColumnValuesToMatchRegex
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
    data_source = context.data_sources.add_pandas("inuka_pipeline_datasource")
    data_asset = data_source.add_dataframe_asset("inuka_transformed_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("inuka_batch_def")
    
    # Create Expectation Suite
    suite = context.suites.add(gx.ExpectationSuite("inuka_quality_gate_suite"))
    
    # Define expectations
    expectations = [
        ExpectColumnValuesToNotBeNull(column="beneficiary_id"),
        ExpectColumnValuesToBeUnique(column="beneficiary_id"),
        ExpectColumnValuesToNotBeNull(column="full_name"),
        ExpectColumnValuesToBeInSet(
            column="pillar",
            value_set=["Scholarship", "Plus", "Vocational", "Tech"]
        ),
        ExpectColumnValuesToBeInSet(
            column="region",
            value_set=["North Eastern", "Coastal", "Eastern", "Central", "Nairobi", "Nyanza", "Rift Valley", "Western"]
        ),
        ExpectColumnValuesToBeInSet(
            column="consent_status",
            value_set=["Consented", "Pending", "Withdrawn"]
        ),
        ExpectColumnValuesToMatchRegex(
            column="email",
            regex=r"^[^@]+@[^@]+\.[^@]+$"
        )
    ]
    
    for exp in expectations:
        suite.add_expectation(exp)
        
    print(f"Expectation Suite defined with {len(expectations)} validation checks.")
    
    # Add validation definition and run validation
    validation_definition = context.validation_definitions.add(
        gx.ValidationDefinition(
            name="inuka_validation_def",
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
    df.to_sql("inuka_beneficiaries", conn, if_exists="replace", index=False)
    conn.close()
    
    print(f"Successfully loaded {len(df)} rows into 'inuka_beneficiaries' table in {db_path}.")
    print("--- LOAD STAGE COMPLETED ---")
    return True

if __name__ == "__main__":
    TRANSFORMED_PATH = os.path.join("dataset", "inuka_beneficiary_transformed.csv")
    CLEAN_CSV_PATH = os.path.join("dataset", "inuka_beneficiary_clean.csv")
    DB_PATH = os.path.join("dataset", "inuka.db")
    run_validation_and_load(TRANSFORMED_PATH, CLEAN_CSV_PATH, DB_PATH)
