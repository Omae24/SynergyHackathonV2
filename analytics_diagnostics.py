import os
import json
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import joblib

def run_analytics_and_modeling(db_path, dashboard_json_path, models_dir):
    print("--- STARTING ANALYTICS & MODELING STAGE ---")
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"SQLite database not found at: {db_path}")
        
    import sqlite3
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM depot_operations", conn)
    conn.close()
    print(f"Loaded {len(df)} cleaned records from SQLite database for diagnostics and training.")
    
    # Ensure times are parsed
    time_cols = [
        "gate_in_time", "security_check_time", "weighbridge_in_time",
        "bay_assigned_time", "loading_start_time", "loading_end_time",
        "weighbridge_out_time", "gate_out_time"
    ]
    for col in time_cols:
        df[col] = pd.to_datetime(df[col])
        
    # --- 1. STATISTICAL DIAGNOSTICS & BOTTLENECK ANALYSIS ---
    # Calculate durations for each stage in minutes
    df['stage1_gate_to_sec'] = (df['security_check_time'] - df['gate_in_time']).dt.total_seconds() / 60.0
    df['stage2_sec_to_wb_in'] = (df['weighbridge_in_time'] - df['security_check_time']).dt.total_seconds() / 60.0
    df['stage3_wb_in_to_bay'] = (df['bay_assigned_time'] - df['weighbridge_in_time']).dt.total_seconds() / 60.0
    df['stage4_bay_to_load_start'] = (df['loading_start_time'] - df['bay_assigned_time']).dt.total_seconds() / 60.0
    df['stage5_load_start_to_end'] = (df['loading_end_time'] - df['loading_start_time']).dt.total_seconds() / 60.0
    df['stage6_load_end_to_wb_out'] = (df['weighbridge_out_time'] - df['loading_end_time']).dt.total_seconds() / 60.0
    df['stage7_wb_out_to_gate_out'] = (df['gate_out_time'] - df['weighbridge_out_time']).dt.total_seconds() / 60.0
    
    stages = [
        ("Gate In -> Security Check", "stage1_gate_to_sec"),
        ("Security -> Weighbridge In", "stage2_sec_to_wb_in"),
        ("Weighbridge In -> Bay Assigned (Queue)", "stage3_wb_in_to_bay"),
        ("Bay Assigned -> Loading Start", "stage4_bay_to_load_start"),
        ("Loading Start -> Loading End", "stage5_load_start_to_end"),
        ("Loading End -> Weighbridge Out", "stage6_load_end_to_wb_out"),
        ("Weighbridge Out -> Gate Out", "stage7_wb_out_to_gate_out")
    ]
    
    bottleneck_list = []
    total_avg_tat = df['total_tat_minutes'].mean()
    for display_name, col_name in stages:
        avg_val = df[col_name].mean()
        bottleneck_list.append({
            "stage": display_name,
            "duration": round(avg_val, 2),
            "percentage": round((avg_val / total_avg_tat) * 100, 2)
        })
        
    print("\nBottleneck Analysis (Stage Durations):")
    for stage in bottleneck_list:
        print(f"  {stage['stage']}: {stage['duration']} mins ({stage['percentage']}%)")
        
    # Depot statistics
    depot_groups = df.groupby('depot_location')
    depot_stats = {}
    for name, group in depot_groups:
        depot_stats[name] = {
            "avg_tat": round(group['total_tat_minutes'].mean(), 2),
            "avg_queue": round(group['stage3_wb_in_to_bay'].mean(), 2),
            "total_demurrage_cost": round(group['demurrage_cost_kes'].sum(), 2),
            "demurrage_rate": round((group['demurrage_incurred'].sum() / len(group)) * 100, 2),
            "truck_count": len(group)
        }
        
    # Truck statistics
    truck_stats = {}
    for name, group in df.groupby('truck_type'):
        truck_stats[name] = {
            "avg_tat": round(group['total_tat_minutes'].mean(), 2),
            "demurrage_rate": round((group['demurrage_incurred'].sum() / len(group)) * 100, 2),
            "avg_loading_accuracy": round(group['loading_accuracy'].mean(), 2),
            "truck_count": len(group)
        }
        
    # Product statistics
    product_stats = {}
    for name, group in df.groupby('product_type'):
        product_stats[name] = {
            "avg_tat": round(group['total_tat_minutes'].mean(), 2),
            "demurrage_rate": round((group['demurrage_incurred'].sum() / len(group)) * 100, 2),
            "avg_accuracy": round(group['loading_accuracy'].mean(), 2),
            "truck_count": len(group)
        }
        
    # Monthly statistics
    df['year_month'] = df['gate_in_time'].dt.to_period('M').astype(str)
    monthly_stats = []
    for name, group in df.groupby('year_month'):
        monthly_stats.append({
            "month": name,
            "total_demurrage_cost": round(group['demurrage_cost_kes'].sum(), 2),
            "avg_tat": round(group['total_tat_minutes'].mean(), 2),
            "truck_count": len(group)
        })
    # Sort monthly stats chronologically
    monthly_stats = sorted(monthly_stats, key=lambda x: x['month'])
    
    # --- 2. PREDICTIVE MODELING ---
    # Feature engineering
    # Extract temporal features
    df['hour_of_day'] = df['gate_in_time'].dt.hour
    df['day_of_week'] = df['gate_in_time'].dt.dayofweek
    df['month_val'] = df['gate_in_time'].dt.month
    
    # Define features and targets
    feature_cols = [
        'depot_location', 'truck_type', 'product_type', 
        'ordered_volume_liters', 'assigned_bay', 
        'hour_of_day', 'day_of_week', 'month_val'
    ]
    
    X = df[feature_cols].copy()
    y_reg = df['total_tat_minutes']
    y_clf = df['demurrage_incurred']
    
    # One-hot encoding of categorical variables for models
    X_encoded = pd.get_dummies(X, columns=['depot_location', 'truck_type', 'product_type', 'assigned_bay'], drop_first=True)
    
    # Train-test split
    X_train, X_test, y_train_reg, y_test_reg = train_test_split(X_encoded, y_reg, test_size=0.2, random_state=42)
    _, _, y_train_clf, y_test_clf = train_test_split(X_encoded, y_clf, test_size=0.2, random_state=42)
    
    print("\nTraining models...")
    os.makedirs(models_dir, exist_ok=True)
    
    # 2.1 Regression Model (TAT prediction)
    reg_model = RandomForestRegressor(n_estimators=100, max_depth=5, min_samples_leaf=50, random_state=42, n_jobs=-1)
    reg_model.fit(X_train, y_train_reg)
    
    # Predict & Evaluate
    y_pred_reg = reg_model.predict(X_test)
    mae = mean_absolute_error(y_test_reg, y_pred_reg)
    rmse = np.sqrt(mean_squared_error(y_test_reg, y_pred_reg))
    r2 = r2_score(y_test_reg, y_pred_reg)
    print(f"Regression Model (TAT) Metrics:")
    print(f"  MAE: {mae:.2f} minutes")
    print(f"  RMSE: {rmse:.2f} minutes")
    print(f"  R2 Score: {r2:.4f}")
    
    # 2.2 Classification Model (Demurrage risk prediction)
    clf_model = RandomForestClassifier(n_estimators=100, max_depth=5, min_samples_leaf=50, random_state=42, n_jobs=-1)
    clf_model.fit(X_train, y_train_clf)
    
    # Predict & Evaluate
    y_pred_clf = clf_model.predict(X_test)
    y_prob_clf = clf_model.predict_proba(X_test)[:, 1]
    accuracy = accuracy_score(y_test_clf, y_pred_clf)
    precision = precision_score(y_test_clf, y_pred_clf)
    recall = recall_score(y_test_clf, y_pred_clf)
    f1 = f1_score(y_test_clf, y_pred_clf)
    roc_auc = roc_auc_score(y_test_clf, y_prob_clf)
    print(f"Classification Model (Demurrage) Metrics:")
    print(f"  Accuracy: {accuracy:.4f}")
    print(f"  Precision: {precision:.4f}")
    print(f"  Recall: {recall:.4f}")
    print(f"  F1 Score: {f1:.4f}")
    print(f"  ROC-AUC: {roc_auc:.4f}")
    
    # Save trained models
    reg_path = os.path.join(models_dir, "tat_regressor.joblib")
    clf_path = os.path.join(models_dir, "demurrage_classifier.joblib")
    joblib.dump(reg_model, reg_path)
    joblib.dump(clf_model, clf_path)
    print(f"Saved models to: {reg_path} and {clf_path}")
    
    # 2.3 Calculate Demurrage Savings Curve (What-If Simulation)
    print("Calculating demurrage savings curve...")
    savings_curve = []
    original_total_cost = df['demurrage_cost_kes'].sum()
    for r in range(0, 91, 5):
        simulated_queue = np.maximum(0, df['stage3_wb_in_to_bay'] - r)
        process_time = df['total_tat_minutes'] - df['stage3_wb_in_to_bay']
        simulated_tat = process_time + simulated_queue
        simulated_demurrage_incurred = (simulated_tat > 150.0).astype(int)
        
        sim_costs = []
        # Fast vector calculation of costs:
        # excess_tat = simulated_tat - 150.0
        # rate = demurrage_cost_kes / (total_tat_minutes - 150.0) if total_tat_minutes > 150.0 else 2213.9
        excess_tat = np.maximum(0, simulated_tat - 150.0)
        orig_excess = np.maximum(0.001, df['total_tat_minutes'] - 150.0)
        rates = np.where(df['total_tat_minutes'] > 150.0, df['demurrage_cost_kes'] / orig_excess, 2213.9)
        sim_costs = excess_tat * rates
        
        total_sim_cost = sim_costs.sum()
        dem_rate = (simulated_demurrage_incurred.sum() / len(df)) * 100
        savings_curve.append({
            "reduction_minutes": r,
            "simulated_demurrage_cost": round(total_sim_cost, 2),
            "simulated_demurrage_rate": round(dem_rate, 2),
            "cost_saved": round(original_total_cost - total_sim_cost, 2)
        })
    
    # Save one-hot columns list to align inputs in dashboard/predictions
    columns_path = os.path.join(models_dir, "model_columns.json")
    with open(columns_path, 'w') as f:
        json.dump(list(X_encoded.columns), f)
        
    # Get feature importances for regression
    importances = reg_model.feature_importances_
    features = X_encoded.columns
    feat_imp = sorted(
        [{"feature": f, "importance": round(imp * 100, 2)} for f, imp in zip(features, importances)],
        key=lambda x: x['importance'],
        reverse=True
    )[:10] # Top 10
    
    # --- 3. EXPORT DASHBOARD JSON DATA ---
    # Overall summary stats
    overall_stats = {
        "total_trucks": len(df),
        "total_demurrage_cost": round(df['demurrage_cost_kes'].sum(), 2),
        "demurrage_incurred_count": int(df['demurrage_incurred'].sum()),
        "demurrage_rate": round((df['demurrage_incurred'].sum() / len(df)) * 100, 2),
        "avg_tat": round(df['total_tat_minutes'].mean(), 2),
        "avg_accuracy": round(df['loading_accuracy'].mean(), 2),
        "avg_queue_time": round(df['stage3_wb_in_to_bay'].mean(), 2)
    }
    
    # Raw data sample for table representation (first 100 rows, serializable)
    sample_df = df.head(100).copy()
    for col in time_cols:
        sample_df[col] = sample_df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
    raw_sample = sample_df[[
        "transaction_id", "truck_id", "truck_type", "depot_location", 
        "product_type", "assigned_bay", "ordered_volume_liters", 
        "actual_loaded_liters", "gate_in_time", "gate_out_time", 
        "total_tat_minutes", "demurrage_cost_kes"
    ]].to_dict('records')
    
    dashboard_data = {
        "overall_stats": overall_stats,
        "bottlenecks": bottleneck_list,
        "depot_stats": depot_stats,
        "truck_stats": truck_stats,
        "product_stats": product_stats,
        "monthly_stats": monthly_stats,
        "feature_importances": feat_imp,
        "model_metrics": {
            "regression": {
                "mae": round(mae, 2),
                "rmse": round(rmse, 2),
                "r2": round(r2, 4)
            },
            "classification": {
                "accuracy": round(accuracy, 4),
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "roc_auc": round(roc_auc, 4)
            }
        },
        "raw_sample": raw_sample,
        "savings_curve": savings_curve
    }
    
    os.makedirs(os.path.dirname(dashboard_json_path), exist_ok=True)
    with open(dashboard_json_path, 'w') as f:
        json.dump(dashboard_data, f, indent=2)
    print(f"Saved dashboard data JSON to: {dashboard_json_path}")
    print("--- ANALYTICS & MODELING STAGE COMPLETED ---")
    return True

if __name__ == "__main__":
    DB_PATH = os.path.join("dataset", "kpc_depot.db")
    DASHBOARD_JSON_PATH = os.path.join("dataset", "dashboard_data.json")
    MODELS_DIR = "models"
    run_analytics_and_modeling(DB_PATH, DASHBOARD_JSON_PATH, MODELS_DIR)
