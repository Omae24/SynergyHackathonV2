import os
import pandas as pd
import numpy as np

def clean_data(extracted_path, clean_path):
    print("--- STARTING TRANSFORMATION STAGE ---")
    if not os.path.exists(extracted_path):
        raise FileNotFoundError(f"Extracted dataset not found at: {extracted_path}")
        
    df = pd.read_csv(extracted_path)
    print(f"Loaded {len(df)} rows for transformation.")
    
    # 1. Deduplicate rows
    initial_len = len(df)
    df = df.drop_duplicates()
    print(f"Dropped {initial_len - len(df)} duplicate rows. New shape: {df.shape}")
    
    # 2. Strip whitespaces from string columns
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).str.strip()
        
    # 3. Standardize depot_location to title-case (sentence case)
    # This standardizes NAIROBI, Nairobi, kisumu, Mombasa, etc.
    df['depot_location'] = df['depot_location'].str.title()
    print("Standardized depot locations. Unique values now:", df['depot_location'].unique())
    
    # 4. Correct actual_loaded_liters where they are -1
    # formula: actual_loaded_liters = round((loading_accuracy / 100) * ordered_volume_liters)
    neg_actual_mask = df['actual_loaded_liters'] < 0
    num_neg_actual = neg_actual_mask.sum()
    if num_neg_actual > 0:
        df.loc[neg_actual_mask, 'actual_loaded_liters'] = (
            (df.loc[neg_actual_mask, 'loading_accuracy'] / 100.0) * 
            df.loc[neg_actual_mask, 'ordered_volume_liters']
        ).round().astype(int)
        print(f"Corrected {num_neg_actual} rows with negative actual_loaded_liters using loading_accuracy.")
        
    # 5. Fix timestamps and chronology
    time_cols = [
        "gate_in_time", "security_check_time", "weighbridge_in_time",
        "bay_assigned_time", "loading_start_time", "loading_end_time",
        "weighbridge_out_time", "gate_out_time"
    ]
    
    # Convert all to datetime
    for col in time_cols:
        df[col] = pd.to_datetime(df[col], errors='coerce')
        
    # We will compute the typical durations from non-null data to use for imputation
    medians = {
        'gate_in_to_sec': 12.0,      # median is ~12 mins
        'sec_to_wb_in': 13.0,        # median is ~13 mins
        'wb_in_to_bay': 83.5,        # median is ~83.5 mins
        'bay_to_load_start': 7.0,    # median is ~7 mins
        'load_start_to_end': 59.0,   # median is ~59 mins
        'load_end_to_wb_out': 14.0,  # median is ~14 mins
        'wb_out_to_gate_out': 9.0     # median is ~10 mins (we use 9 mins)
    }
    
    # Let's perform robust imputation row-by-row to ensure logical chronological integrity
    records = df.to_dict('records')
    fixed_count = 0
    imputed_count = 0
    
    for row in records:
        # Check and impute gate_in_time and gate_out_time if missing
        if pd.isnull(row['gate_in_time']) and not pd.isnull(row['gate_out_time']):
            row['gate_in_time'] = row['gate_out_time'] - pd.to_timedelta(row['total_tat_minutes'], unit='m')
            imputed_count += 1
        elif pd.isnull(row['gate_out_time']) and not pd.isnull(row['gate_in_time']):
            row['gate_out_time'] = row['gate_in_time'] + pd.to_timedelta(row['total_tat_minutes'], unit='m')
            imputed_count += 1
        elif pd.isnull(row['gate_in_time']) and pd.isnull(row['gate_out_time']):
            # Both missing! Impute gate_in from bay_assigned_time
            # bay_assigned = gate_in + 12 + 13 + wb_in_to_bay
            # So gate_in = bay_assigned - 12 - 13 - 83.5
            total_pre_bay = medians['gate_in_to_sec'] + medians['sec_to_wb_in'] + medians['wb_in_to_bay']
            row['gate_in_time'] = row['bay_assigned_time'] - pd.to_timedelta(total_pre_bay, unit='m')
            row['gate_out_time'] = row['gate_in_time'] + pd.to_timedelta(row['total_tat_minutes'], unit='m')
            imputed_count += 2
            
        # Ensure gate_out_time is at least gate_in_time + total_tat_minutes
        expected_gate_out = row['gate_in_time'] + pd.to_timedelta(row['total_tat_minutes'], unit='m')
        # If gate_out_time is inconsistent with total_tat_minutes, correct it
        if abs((row['gate_out_time'] - expected_gate_out).total_seconds()) > 60:
            # We trust gate_in_time and total_tat_minutes
            row['gate_out_time'] = expected_gate_out
            fixed_count += 1
            
        # Forward pass to fill missing / fix out-of-order intermediate timestamps
        # 1. security_check_time: must be after gate_in_time
        if pd.isnull(row['security_check_time']) or row['security_check_time'] < row['gate_in_time']:
            row['security_check_time'] = row['gate_in_time'] + pd.to_timedelta(medians['gate_in_to_sec'], unit='m')
            fixed_count += 1
            
        # 2. weighbridge_in_time: must be after security_check_time
        if pd.isnull(row['weighbridge_in_time']) or row['weighbridge_in_time'] < row['security_check_time']:
            row['weighbridge_in_time'] = row['security_check_time'] + pd.to_timedelta(medians['sec_to_wb_in'], unit='m')
            fixed_count += 1
            
        # 3. bay_assigned_time: must be after weighbridge_in_time
        if row['bay_assigned_time'] < row['weighbridge_in_time']:
            # Since bay_assigned_time is never null, if it is out-of-order, we adjust weighbridge_in_time backwards if possible,
            # or push bay_assigned_time forward. Let's make bay_assigned_time = weighbridge_in_time + 5 mins
            row['bay_assigned_time'] = row['weighbridge_in_time'] + pd.to_timedelta(5, unit='m')
            fixed_count += 1
            
        # 4. loading_start_time: must be after bay_assigned_time
        if row['loading_start_time'] < row['bay_assigned_time']:
            row['loading_start_time'] = row['bay_assigned_time'] + pd.to_timedelta(medians['bay_to_load_start'], unit='m')
            fixed_count += 1
            
        # 5. loading_end_time: must be after loading_start_time
        if row['loading_end_time'] < row['loading_start_time']:
            row['loading_end_time'] = row['loading_start_time'] + pd.to_timedelta(medians['load_start_to_end'], unit='m')
            fixed_count += 1
            
        # 6. weighbridge_out_time: must be after loading_end_time
        if pd.isnull(row['weighbridge_out_time']) or row['weighbridge_out_time'] < row['loading_end_time']:
            row['weighbridge_out_time'] = row['loading_end_time'] + pd.to_timedelta(medians['load_end_to_wb_out'], unit='m')
            fixed_count += 1
            
        # 7. gate_out_time: must be after weighbridge_out_time
        if row['gate_out_time'] < row['weighbridge_out_time']:
            # Adjust gate_out_time to be weighbridge_out_time + 9 mins, and re-adjust total_tat_minutes
            row['gate_out_time'] = row['weighbridge_out_time'] + pd.to_timedelta(medians['wb_out_to_gate_out'], unit='m')
            row['total_tat_minutes'] = round((row['gate_out_time'] - row['gate_in_time']).total_seconds() / 60.0, 1)
            fixed_count += 1

    df_cleaned = pd.DataFrame(records)
    
    # 6. Convert Demurrage Cost from USD to KES (Exchange Rate: 1 USD = 130 KES)
    usd_to_kes_rate = 130.0
    df_cleaned['demurrage_cost_kes'] = (df_cleaned['demurrage_cost_usd'] * usd_to_kes_rate).round(2)
    df_cleaned = df_cleaned.drop(columns=['demurrage_cost_usd'])
    print("Converted demurrage cost column to KES (renamed to demurrage_cost_kes).")
    
    # Format times back as strings
    for col in time_cols:
        df_cleaned[col] = df_cleaned[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        
    print(f"Chronology alignment completed: Imputed {imputed_count} timestamps, fixed {fixed_count} ordering anomalies.")
    
    # Save to clean intermediate path
    os.makedirs(os.path.dirname(clean_path), exist_ok=True)
    df_cleaned.to_csv(clean_path, index=False)
    print(f"Transformed data saved to: {clean_path}")
    print("--- TRANSFORMATION STAGE COMPLETED ---")
    return df_cleaned

if __name__ == "__main__":
    EXTRACTED_PATH = os.path.join("dataset", "kpc_depot_extracted.csv")
    CLEANED_PATH = os.path.join("dataset", "kpc_depot_transformed.csv")
    clean_data(EXTRACTED_PATH, CLEANED_PATH)
