import time
import random
import requests
import datetime

API_URL = "http://localhost:8000/api/stream/beneficiary"

PILLARS = ["Scholarship", "Plus", "Vocational", "Tech"]
REGIONS = ["North Eastern", "Coastal", "Eastern", "Central", "Nairobi", "Nyanza", "Rift Valley", "Western"]
CONSENT_STATUSES = ["Consented", "Pending", "Withdrawn"]
CONSENT_TYPES = ["Digital Signature", "SMS OTP", "Physical Form"]

FIRST_NAMES = ["James", "John", "David", "Joseph", "Mercy", "Grace", "Mary", "Faith", "Asha", "Halima", "Moses", "Jane", "Alice", "Peter", "Charles"]
LAST_NAMES = ["Kipchoge", "Ouma", "Wambui", "Kiprop", "Mohamed", "Otieno", "Mwangi", "Cherono", "Karanja", "Ekiru", "Njoroge", "Kamau", "Onyango"]

def generate_valid_beneficiary(index):
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    national_id = str(random.randint(28000000, 39000000))
    email = f"{first.lower()}.{last.lower()}@gmail.com"
    phone = f"07{random.randint(10000000, 99999999)}"
    
    if random.random() > 0.5:
        phone = f"07{random.randint(10, 99)} {random.randint(100, 999)} {random.randint(100, 999)}"
        
    pillar = random.choice(PILLARS)
    region = random.choice(REGIONS)
    consent = random.choice(CONSENT_STATUSES)
    consent_type = random.choice(CONSENT_TYPES) if consent != "Pending" else "None"
    
    return {
        "beneficiary_id": f"INK-2026-{2000 + index}",
        "full_name": f"{first} {last}",
        "national_id": national_id,
        "email": email,
        "phone": phone,
        "pillar": pillar,
        "region": region,
        "consent_status": consent,
        "consent_type": consent_type,
        "consent_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") if consent != "Pending" else "",
        "status": "Active"
    }

def generate_invalid_beneficiary(index):
    record = generate_valid_beneficiary(index)
    error_type = random.choice(["invalid_pillar", "invalid_region", "missing_name", "invalid_email"])
    
    if error_type == "invalid_pillar":
        record["pillar"] = "CorporateSocialResponsibility"
    elif error_type == "invalid_region":
        record["region"] = "Kampala"
    elif error_type == "missing_name":
        record["full_name"] = ""
    elif error_type == "invalid_email":
        record["email"] = "not_an_email_address"
        
    return record

def run_simulation():
    print("Starting Inuka Beneficiary Stream Simulator in 3 seconds...")
    time.sleep(3)
    
    index = 50
    while True:
        index += 1
        if random.random() > 0.2:
            payload = generate_valid_beneficiary(index)
            is_valid = True
        else:
            payload = generate_invalid_beneficiary(index)
            is_valid = False
            
        print(f"\n[Simulator] Streaming event INK-2026-{2000 + index} (Valid={is_valid})...")
        try:
            # Increased timeout to 15.0s to accommodate heavy local Great Expectations runs
            r = requests.post(API_URL, json=payload, timeout=15.0)
            print(f"[Simulator] Response Code: {r.status_code}. Response: {r.text}")
        except Exception as e:
            print(f"[Simulator ERROR] Failed to send POST: {e}")
            
        time.sleep(5)

if __name__ == "__main__":
    run_simulation()
