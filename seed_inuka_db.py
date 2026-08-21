import sqlite3
import os
import csv
import random
from datetime import datetime

DB_PATH = os.path.join("dataset", "kpc_depot.db")
RAW_CSV_PATH = os.path.join("dataset", "inuka_beneficiary_raw.csv")

def seed_database():
    print(f"Connecting to SQLite database at {DB_PATH} for Inuka seeding...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Create inuka_beneficiaries table
    print("Creating 'inuka_beneficiaries' table...")
    cursor.execute("DROP TABLE IF EXISTS inuka_beneficiaries")
    cursor.execute("""
        CREATE TABLE inuka_beneficiaries (
            beneficiary_id TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            national_id TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            pillar TEXT NOT NULL,
            region TEXT NOT NULL,
            consent_status TEXT NOT NULL,
            consent_type TEXT,
            consent_date TEXT,
            status TEXT NOT NULL,
            enrollment_status TEXT NOT NULL DEFAULT 'Enrolled',
            consent_data_sharing INTEGER DEFAULT 1,
            consent_photo_use INTEGER DEFAULT 0,
            consent_sms_contact INTEGER DEFAULT 0,
            consent_external_reporting INTEGER DEFAULT 0
        )
    """)

    # 2. Create quarantined_events table
    print("Creating 'quarantined_events' table...")
    cursor.execute("DROP TABLE IF EXISTS quarantined_events")
    cursor.execute("""
        CREATE TABLE quarantined_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            raw_payload TEXT NOT NULL,
            failure_reasons TEXT NOT NULL
        )
    """)

    # 3. Create privacy_audit_log table
    print("Creating 'privacy_audit_log' table...")
    cursor.execute("DROP TABLE IF EXISTS privacy_audit_log")
    cursor.execute("""
        CREATE TABLE privacy_audit_log (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            operator TEXT NOT NULL,
            action_type TEXT NOT NULL,
            target_beneficiary_id TEXT,
            details TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            is_anomaly INTEGER DEFAULT 0
        )
    """)

    # 4. Create and Seed users table
    print("Seeding 'users' table...")
    cursor.execute("DROP TABLE IF EXISTS users")
    cursor.execute("""
        CREATE TABLE users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            depot TEXT NOT NULL,
            truck_reg TEXT NOT NULL
        )
    """)

    users_data = [
        ("hq_director", "password", "hq_admin", "All", "All"),
        ("scholarship_hq", "password", "pillar_coord", "All", "Scholarship"),
        ("tech_hq", "password", "pillar_coord", "All", "Tech"),
        ("nyanza_field", "password", "field_officer", "Nyanza", "All"),
        ("nairobi_field", "password", "field_officer", "Nairobi", "All"),
        ("coastal_field", "password", "field_officer", "Coastal", "All"),
        ("kdpa_auditor", "password", "compliance_auditor", "All", "All")
    ]
    cursor.executemany("INSERT INTO users VALUES (?, ?, ?, ?, ?)", users_data)

    # 5. Create financial_reconciliation table
    print("Creating 'financial_reconciliation' table...")
    cursor.execute("DROP TABLE IF EXISTS financial_reconciliation")
    cursor.execute("""
        CREATE TABLE financial_reconciliation (
            reconciliation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            beneficiary_id TEXT NOT NULL,
            full_name TEXT NOT NULL,
            month TEXT NOT NULL,
            attendance_rate REAL NOT NULL,
            disbursed_amount REAL NOT NULL,
            expected_amount REAL NOT NULL,
            discrepancy_reason TEXT,
            status TEXT NOT NULL,
            FOREIGN KEY(beneficiary_id) REFERENCES inuka_beneficiaries(beneficiary_id)
        )
    """)

    # 6. Populate inuka_beneficiaries from raw CSV
    if os.path.exists(RAW_CSV_PATH):
        print(f"Reading beneficiaries from {RAW_CSV_PATH}...")
        with open(RAW_CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            beneficiaries = []
            recon_records = []
            
            # Setup deterministic seed for reproducible discrepancies
            random.seed(42)
            
            for index, row in enumerate(reader):
                b_id = row['beneficiary_id']
                name = row['full_name']
                pillar = row['pillar']
                region = row['region']
                consent_status = row['consent_status']
                consent_type = row['consent_type'] if row['consent_type'] != 'None' else None
                consent_date = row['consent_date'] if row['consent_date'] != '' else None
                status = row['status']
                enroll_status = row['enrollment_status']
                sharing = int(row['consent_data_sharing'])
                photo = int(row['consent_photo_use'])
                sms = int(row['consent_sms_contact'])
                ext_report = int(row['consent_external_reporting'])
                
                beneficiaries.append((
                    b_id, name, row['national_id'], row['email'], row['phone'],
                    pillar, region, consent_status, consent_type, consent_date, status,
                    enroll_status, sharing, photo, sms, ext_report
                ))
                
                # --- Generate Financial Reconciliation Data ---
                month = "August 2026"
                
                # Default normal calculations
                attendance = round(random.uniform(75.0, 100.0), 1)
                expected = 5000.00 if (consent_status == "Consented" and attendance >= 75.0) else 0.00
                disbursed = expected
                reason = None
                recon_status = "Matched"
                
                # Inject 5 Low Attendance Discrepancies (stipend paid despite low attendance)
                if index in [10, 250, 450, 720, 910]:
                    attendance = round(random.uniform(50.0, 70.0), 1) # < 75%
                    expected = 0.00
                    disbursed = 5000.00
                    reason = f"Low attendance ({attendance}%) payout violation"
                    recon_status = "Discrepancy"
                    
                # Inject 3 Consent Violation Discrepancies (withdrawn consent but still paid)
                elif index in [55, 330, 805] and consent_status == "Withdrawn":
                    attendance = round(random.uniform(80.0, 95.0), 1)
                    expected = 0.00
                    disbursed = 5000.00
                    reason = "Withdrawn consent payout violation"
                    recon_status = "Discrepancy"
                    
                # Standard case for other low attendance or withdrawn cases
                else:
                    if consent_status == "Withdrawn" or consent_status == "Pending":
                        expected = 0.00
                        disbursed = 0.00
                    elif attendance < 75.0:
                        expected = 0.00
                        disbursed = 0.00
                
                recon_records.append((
                    b_id, name, month, attendance, disbursed, expected, reason, recon_status
                ))
                
            cursor.executemany("""
                INSERT INTO inuka_beneficiaries 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, beneficiaries)
            
            cursor.executemany("""
                INSERT INTO financial_reconciliation (beneficiary_id, full_name, month, attendance_rate, disbursed_amount, expected_amount, discrepancy_reason, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, recon_records)
            
            print(f"Seeded {len(beneficiaries)} beneficiaries and {len(recon_records)} financial records.")
    else:
        print("[WARNING] Raw CSV not found. Seeding skipped.")

    # 7. Seed dummy compliance audit logs
    dummy_logs = [
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "system", "SYSTEM_STARTUP", None, "Inuka Privacy Database, Consent Purposes, and Financial Ledgers initialized.", "127.0.0.1", 0)
    ]
    cursor.executemany("""
        INSERT INTO privacy_audit_log (timestamp, operator, action_type, target_beneficiary_id, details, ip_address, is_anomaly)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, dummy_logs)

    conn.commit()
    conn.close()
    print("Inuka database seeding completed successfully.")

if __name__ == "__main__":
    seed_database()
