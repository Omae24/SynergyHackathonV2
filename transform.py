import os
import pandas as pd

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
        
    # 3. Clean full name (Title Case, collapsing extra whitespace)
    if 'full_name' in df.columns:
        df['full_name'] = df['full_name'].apply(lambda x: " ".join(str(x).split()).title() if pd.notnull(x) else x)
        
    # 4. Standardize phone number to E.164
    if 'phone' in df.columns:
        def clean_phone(phone_val):
            if pd.isnull(phone_val):
                return phone_val
            phone = str(phone_val).replace(" ", "").strip()
            if phone.startswith("07"):
                phone = "+254" + phone[1:]
            elif phone.startswith("01"):
                phone = "+254" + phone[1:]
            elif phone.startswith("7") or phone.startswith("1"):
                phone = "+254" + phone
            return phone
            
        df['phone'] = df['phone'].apply(clean_phone)
        
    # Save transformed data to intermediate path
    os.makedirs(os.path.dirname(clean_path), exist_ok=True)
    df.to_csv(clean_path, index=False)
    print(f"Transformed data saved to: {clean_path}")
    print("--- TRANSFORMATION STAGE COMPLETED ---")
    return df

if __name__ == "__main__":
    EXTRACTED_PATH = os.path.join("dataset", "inuka_beneficiary_extracted.csv")
    CLEANED_PATH = os.path.join("dataset", "inuka_beneficiary_transformed.csv")
    clean_data(EXTRACTED_PATH, CLEANED_PATH)
