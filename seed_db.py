import sqlite3
import os

DB_PATH = os.path.join("dataset", "kpc_depot.db")

def seed_database():
    print(f"Connecting to SQLite database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Create and Seed Users Table
    print("Creating and seeding 'users' table...")
    cursor.execute("DROP TABLE IF EXISTS users")
    cursor.execute("""
        CREATE TABLE users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            depot TEXT NOT NULL,
            truck_reg TEXT
        )
    """)
    
    users_data = [
        ("hq_manager", "password", "hq_manager", "All", None),
        ("nairobi_manager", "password", "depot_manager", "Nairobi", None),
        ("kisumu_manager", "password", "depot_manager", "Kisumu", None),
        ("driver_123", "password", "truck_driver", "Nairobi", "KBX-1234"),
        ("driver_456", "password", "truck_driver", "Kisumu", "KCB-5678"),
        ("driver_999", "password", "truck_driver", "Kisumu", "KCD-9999")
    ]
    cursor.executemany("INSERT INTO users VALUES (?, ?, ?, ?, ?)", users_data)
    
    # 2. Create and Seed Bay Telemetry Table
    print("Creating and seeding 'bay_telemetry' table...")
    cursor.execute("DROP TABLE IF EXISTS bay_telemetry")
    cursor.execute("""
        CREATE TABLE bay_telemetry (
            depot_location TEXT NOT NULL,
            assigned_bay TEXT NOT NULL,
            pump_pressure REAL NOT NULL,
            status TEXT NOT NULL,
            PRIMARY KEY (depot_location, assigned_bay)
        )
    """)
    
    depots = ["Nairobi", "Kisumu", "Mombasa", "Eldoret", "Nakuru"]
    bays = [f"Loading Bay {i}" for i in range(1, 13)]
    
    telemetry_data = []
    for depot in depots:
        for bay in bays:
            telemetry_data.append((depot, bay, 10.0, "Normal"))
            
    cursor.executemany("INSERT INTO bay_telemetry VALUES (?, ?, ?, ?)", telemetry_data)
    
    # 3. Create and Seed Active Queue Table
    print("Creating and seeding 'active_queue' table...")
    cursor.execute("DROP TABLE IF EXISTS active_queue")
    cursor.execute("""
        CREATE TABLE active_queue (
            truck_reg TEXT PRIMARY KEY,
            depot_location TEXT NOT NULL,
            assigned_bay TEXT NOT NULL,
            product_type TEXT NOT NULL,
            truck_type TEXT NOT NULL,
            ordered_volume_liters INTEGER NOT NULL,
            current_stage TEXT NOT NULL,
            elapsed_minutes INTEGER NOT NULL,
            entry_time TEXT NOT NULL
        )
    """)
    
    active_trucks = [
        # Nairobi Active Trucks
        ("KBX-1234", "Nairobi", "Loading Bay 3", "Premium Motor Spirit (PMS)", "Tanker (45k Liters)", 45000, "Bay Assigned (Queue)", 45, "2026-08-19 22:00:00"),
        ("KCF-8888", "Nairobi", "Loading Bay 1", "Automotive Gas Oil (AGO)", "Tanker (30k Liters)", 30000, "Loading Start -> Loading End", 20, "2026-08-19 22:15:00"),
        ("KCA-1111", "Nairobi", "Loading Bay 3", "Premium Motor Spirit (PMS)", "Tanker (30k Liters)", 30000, "Security -> Weighbridge In", 12, "2026-08-19 22:40:00"),
        
        # Kisumu Active Trucks
        ("KCB-5678", "Kisumu", "Loading Bay 3", "Automotive Gas Oil (AGO)", "Tanker (30k Liters)", 30000, "Loading Start -> Loading End", 15, "2026-08-19 22:20:00"),
        ("KCD-9999", "Kisumu", "Loading Bay 3", "Premium Motor Spirit (PMS)", "Tanker (60k Liters)", 60000, "Bay Assigned (Queue)", 85, "2026-08-19 21:10:00"),
        ("KCE-7777", "Kisumu", "Loading Bay 2", "Illuminating Kerosene (IK)", "Tanker (30k Liters)", 30000, "Security -> Weighbridge In", 10, "2026-08-19 22:45:00"),
        ("KCG-5555", "Kisumu", "Loading Bay 3", "Automotive Gas Oil (AGO)", "Tanker (45k Liters)", 45000, "Gate In -> Security Check", 5, "2026-08-19 22:50:00")
    ]
    cursor.executemany("INSERT INTO active_queue VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", active_trucks)
    
    conn.commit()
    conn.close()
    print("Database seeding completed successfully.")

if __name__ == "__main__":
    seed_database()
