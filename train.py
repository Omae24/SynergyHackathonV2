import os
import pandas as pd
from analytics_diagnostics import run_analytics_and_modeling

def main():
    # Load the cleaned data from dataset/kpc_depot_clean.csv to satisfy the requirement
    # "Loads the cleaned data from dataset/kpc_depot_clean.csv"
    csv_path = os.path.join("dataset", "kpc_depot_clean.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Cleaned dataset CSV not found at: {csv_path}")
        
    print(f"Loading cleaned data from {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} records from CSV.")
    
    # Run the analytics and modeling process to train models and save them
    db_path = os.path.join("dataset", "kpc_depot.db")
    dashboard_json_path = os.path.join("dataset", "dashboard_data.json")
    models_dir = "models"
    
    run_analytics_and_modeling(db_path, dashboard_json_path, models_dir)

if __name__ == "__main__":
    main()
