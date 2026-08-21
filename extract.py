import os
import pandas as pd

def extract_data(raw_path, extracted_path):
    print("--- STARTING EXTRACTION STAGE ---")
    if not os.path.exists(raw_path):
        raise FileNotFoundError(f"Raw dataset not found at: {raw_path}")
        
    print(f"Reading raw data from {raw_path}...")
    df = pd.read_csv(raw_path)
    print(f"Extracted {len(df)} rows and {len(df.columns)} columns.")
    
    # Save raw data to extraction stage area
    os.makedirs(os.path.dirname(extracted_path), exist_ok=True)
    df.to_csv(extracted_path, index=False)
    print(f"Data saved to intermediate path: {extracted_path}")
    print("--- EXTRACTION STAGE COMPLETED ---")
    return df

if __name__ == "__main__":
    RAW_PATH = os.path.join("dataset", "kpc_depot_raw.csv")
    EXTRACTED_PATH = os.path.join("dataset", "kpc_depot_extracted.csv")
    extract_data(RAW_PATH, EXTRACTED_PATH)
