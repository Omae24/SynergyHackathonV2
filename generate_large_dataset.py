import csv
import os
import random
from datetime import datetime, timedelta

RAW_CSV_PATH = os.path.join("dataset", "inuka_beneficiary_raw.csv")
os.makedirs("dataset", exist_ok=True)

PILLARS = ["Scholarship", "Plus", "Vocational", "Tech"]
REGIONS = ["North Eastern", "Coastal", "Eastern", "Central", "Nairobi", "Nyanza", "Rift Valley", "Western"]
CONSENT_STATUSES = ["Consented", "Pending", "Withdrawn"]
CONSENT_TYPES = ["Digital Signature", "SMS OTP", "Physical Form"]

FIRST_NAMES = [
    "Joseph", "Asha", "Grace", "David", "Emmanuel", "Mercy", "Kevin", "Fatuma", "Daniel", "Faith", 
    "John", "Sarah", "Brian", "Lydia", "Peter", "Anita", "James", "Mary", "Simon", "Esther", 
    "Paul", "Zainab", "Collins", "Rachael", "Andrew", "Halima", "Francis", "Ruth", "Geoffrey", "Catherine",
    "Moses", "Jane", "Alice", "Charles", "Rose", "Michael", "Agnes", "Philip", "Joyce", "Patrick",
    "Wycliffe", "Beatrice", "Stephen", "Lucy", "Evans", "Florence", "Julius", "Eunice", "Robert", "Gladys"
]

LAST_NAMES = [
    "Kiprop", "Mohamed", "Wambui", "Ochieng", "Kipruto", "Mwangi", "Otieno", "Ali", "Kamau", "Chepkemoi", 
    "Mwangi", "Cherono", "Wekesa", "Nyambura", "Onyango", "Wangari", "Sang", "Achieng", "Ndwiga", "Muthoni", 
    "Ekiru", "Hassan", "Koech", "Wanjiku", "Ombati", "Ibrahim", "Kiarie", "Jebet", "Omondi", "Nduku",
    "Karanja", "Juma", "Mutua", "Kariuki", "Maina", "Njoroge", "Odhiambo", "Wanyama", "Kimani", "Kipkorir",
    "Nyangau", "Barasa", "Simiyu", "Nekesa", "Wamalwa", "Chelimo", "Lagat", "Kiptoo", "Kemei", "Rotich"
]

def generate_dataset():
    print(f"Generating 1,000 mock beneficiary records with consent purposes...")
    
    records = []
    
    for i in range(1, 1001):
        beneficiary_id = f"INK-2026-{1000 + i:04d}"
        
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        full_name = f"{first} {last}"
        
        national_id = str(20000000 + i * 17 + random.randint(100, 999))[:8]
        email = f"{first.lower()}.{last.lower()}.{i}@inuka.org"
        phone = f"+254 7{random.randint(10, 99)} {random.randint(100, 999)} {random.randint(100, 999)}"
        
        pillar = random.choice(PILLARS)
        region = random.choice(REGIONS)
        
        # Consent compliance mix (80% Consented, 15% Pending, 5% Withdrawn)
        rand = random.random()
        if rand < 0.80:
            consent_status = "Consented"
            enrollment_status = "Enrolled"
            consent_type = random.choice(CONSENT_TYPES)
            days_ago = random.randint(1, 200)
            consent_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
            # Consented defaults
            consent_data_sharing = 1
            consent_photo_use = 1 if random.random() > 0.40 else 0
            consent_sms_contact = 1 if random.random() > 0.25 else 0
            consent_external_reporting = 1 if random.random() > 0.35 else 0
        elif rand < 0.95:
            consent_status = "Pending"
            enrollment_status = "Pending Review"
            consent_type = "None"
            consent_date = ""
            consent_data_sharing = 0
            consent_photo_use = 0
            consent_sms_contact = 0
            consent_external_reporting = 0
        else:
            consent_status = "Withdrawn"
            enrollment_status = "On Hold"
            consent_type = random.choice(CONSENT_TYPES)
            days_ago = random.randint(1, 50)
            consent_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
            consent_data_sharing = 0
            consent_photo_use = 0
            consent_sms_contact = 0
            consent_external_reporting = 0
            
        status = "Active"
        
        records.append({
            "beneficiary_id": beneficiary_id,
            "full_name": full_name,
            "national_id": national_id,
            "email": email,
            "phone": phone,
            "pillar": pillar,
            "region": region,
            "consent_status": consent_status,
            "consent_type": consent_type,
            "consent_date": consent_date,
            "status": status,
            "enrollment_status": enrollment_status,
            "consent_data_sharing": consent_data_sharing,
            "consent_photo_use": consent_photo_use,
            "consent_sms_contact": consent_sms_contact,
            "consent_external_reporting": consent_external_reporting
        })
        
    with open(RAW_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)
        
    print(f"Dataset generated successfully at {RAW_CSV_PATH}")

if __name__ == "__main__":
    generate_dataset()
