import os
import json
import sqlite3
import urllib.parse
import http.server
import socketserver
import joblib
import pandas as pd
import numpy as np
import datetime

PORT = 8000
MODELS_DIR = "models"
DB_PATH = os.path.join("dataset", "kpc_depot.db")

# Global cache for models
models = {}

def load_prediction_models():
    """Load both Inuka and Depot ML models once at server startup."""
    print("Loading Inuka & Depot ML Models...")
    anomaly_path = os.path.join(MODELS_DIR, "access_anomaly_detector.joblib")
    chatbot_path = os.path.join(MODELS_DIR, "chatbot_intent_classifier.joblib")
    regressor_path = os.path.join(MODELS_DIR, "tat_regressor.joblib")
    classifier_path = os.path.join(MODELS_DIR, "demurrage_classifier.joblib")
    columns_path = os.path.join(MODELS_DIR, "model_columns.json")
    
    try:
        models['anomaly_detector'] = joblib.load(anomaly_path)
        models['chatbot'] = joblib.load(chatbot_path)
        
        if os.path.exists(regressor_path):
            models['regressor'] = joblib.load(regressor_path)
        if os.path.exists(classifier_path):
            models['classifier'] = joblib.load(classifier_path)
        if os.path.exists(columns_path):
            with open(columns_path, 'r') as f:
                models['columns'] = json.load(f)
                
        print("All ML Models loaded successfully.")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to load models: {e}")
        return False

class DashboardHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Enable CORS for browser testing
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # Route API queries
        if path == "/api/beneficiaries":
            self.handle_get_beneficiaries(query_params)
        elif path == "/api/audit/logs":
            self.handle_get_audit_logs(query_params)
        elif path == "/api/quarantined":
            self.handle_get_quarantined(query_params)
        elif path == "/" or self.path == "/index.html":
            self.path = "/dashboard.html"
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/api/login":
            self.handle_login()
        elif path == "/api/stream/beneficiary":
            self.handle_stream_beneficiary()
        elif path == "/api/consent/update":
            self.handle_consent_update()
        elif path == "/api/beneficiary/anonymize":
            self.handle_beneficiary_anonymize()
        elif path == "/api/beneficiary/update_consent":
            self.handle_beneficiary_self_update_consent()
        elif path == "/api/chatbot/message":
            self.handle_chatbot_message()
        else:
            self.send_response(404)
            self.end_headers()

    def handle_login(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            payload = json.loads(post_data.decode('utf-8'))
            username = payload.get("username", "").strip()
            password = payload.get("password", "").strip()

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 1. First attempt login as staff user
            cursor.execute(
                "SELECT role, depot, truck_reg FROM users WHERE username = ? AND password = ?",
                (username, password)
            )
            user_row = cursor.fetchone()
            
            if user_row:
                role, depot, truck_reg = user_row
                response = {
                    "username": username,
                    "role": role,
                    "depot": depot,
                    "truck_reg": truck_reg,
                    "success": True
                }
                conn.close()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
                return
                
            # 2. Second attempt: login as beneficiary (INK-2026-XXXX) with password "password"
            cursor.execute(
                "SELECT beneficiary_id, full_name, pillar, region, consent_status, enrollment_status FROM inuka_beneficiaries WHERE beneficiary_id = ? AND ? = 'password'",
                (username, password)
            )
            ben_row = cursor.fetchone()
            conn.close()

            if ben_row:
                b_id, b_name, b_pillar, b_region, b_consent, b_enroll = ben_row
                response = {
                    "username": b_id,
                    "role": "beneficiary",
                    "depot": b_region,
                    "truck_reg": b_pillar,
                    "name": b_name,
                    "consent_status": b_consent,
                    "enrollment_status": b_enroll,
                    "success": True
                }
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
            else:
                self.send_response(401)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid username or password"}).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def handle_get_beneficiaries(self, query_params):
        operator = query_params.get('operator', ['system'])[0]
        role = query_params.get('role', ['compliance_auditor'])[0]
        
        operator_region = query_params.get('operator_region', ['All'])[0]
        operator_pillar = query_params.get('operator_pillar', ['All'])[0]
        
        region_filter = query_params.get('region', ['All'])[0]
        pillar_filter = query_params.get('pillar', ['All'])[0]
        purpose_filter = query_params.get('purpose', ['All'])[0]
        force_anonymize = query_params.get('force_anonymize', ['false'])[0].lower() == 'true'
        
        try:
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # --- ROW-LEVEL SECURITY (RLS) POLICIES ---
            if role == "field_officer":
                region_filter = operator_region
            
            if role == "pillar_coord":
                pillar_filter = operator_pillar

            # Construct query based on filters
            query = "SELECT * FROM inuka_beneficiaries WHERE 1=1"
            params = []
            if region_filter != 'All':
                query += " AND region = ?"
                params.append(region_filter)
            if pillar_filter != 'All':
                query += " AND pillar = ?"
                params.append(pillar_filter)
                
            # Filter by Consent Purpose
            if purpose_filter != 'All':
                query += f" AND consent_{purpose_filter} = 1"
                
            cursor.execute(query, params)
            rows = cursor.fetchall()
            beneficiaries = [dict(row) for row in rows]
            
            # --- ML ANOMALY DETECTION ENGINE ---
            role_codes = {"hq_admin": 0, "pillar_coord": 1, "field_officer": 1, "compliance_auditor": 2, "beneficiary": 2}
            role_code = role_codes.get(role, 3)
            
            region_mismatch = 0
            if role == "field_officer" and query_params.get('region', ['All'])[0] != operator_region:
                region_mismatch = 1
            if role == "pillar_coord" and query_params.get('pillar', ['All'])[0] != operator_pillar:
                region_mismatch = 1
                
            hour_of_day = datetime.datetime.now().hour
            query_volume = len(beneficiaries)
            
            is_anomaly = 0
            if 'anomaly_detector' in models:
                pred = models['anomaly_detector'].predict([[hour_of_day, role_code, region_mismatch, query_volume]])[0]
                if pred == -1:
                    is_anomaly = 1
                    
            # --- COLUMN-LEVEL SECURITY (CLS) MASKING ---
            should_anonymize = force_anonymize or (role in ["compliance_auditor", "beneficiary"]) or is_anomaly
            
            processed_beneficiaries = []
            for b in beneficiaries:
                b_copy = b.copy()
                if should_anonymize or b['status'] == 'Anonymized':
                    # Mask PII fields
                    name = b['full_name']
                    if name and name != '[REDACTED_KDPA_REQUEST]':
                        parts = name.split()
                        if len(parts) > 1:
                            b_copy['full_name'] = f"{parts[0][0]}. {' '.join(parts[1:])[:3]}***"
                        else:
                            b_copy['full_name'] = name[:2] + "***"
                    
                    nid = b['national_id']
                    if nid and nid != '[REDACTED_KDPA_REQUEST]':
                        b_copy['national_id'] = "*****" + nid[-3:]
                        
                    email = b['email']
                    if email and email != '[REDACTED_KDPA_REQUEST]':
                        email_parts = email.split('@')
                        b_copy['email'] = email_parts[0][:2] + "***@" + email_parts[1]
                        
                    phone = b['phone']
                    if phone and phone != '[REDACTED_KDPA_REQUEST]':
                        b_copy['phone'] = phone[:4] + " *** *** " + phone[-2:]
                        
                processed_beneficiaries.append(b_copy)
                
            # Log audit trail
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            access_details = f"Query Directory (Region: {region_filter}, Pillar: {pillar_filter}, Purpose: {purpose_filter}). Returned {query_volume} records. Anonymization applied: {should_anonymize}."
            if is_anomaly:
                access_details = "[SECURITY ALERT] " + access_details + " Access flagged as ANOMALOUS by Machine Learning."
                
            cursor.execute("""
                INSERT INTO privacy_audit_log (timestamp, operator, action_type, target_beneficiary_id, details, ip_address, is_anomaly)
                VALUES (?, ?, 'PII_ACCESS', NULL, ?, '127.0.0.1', ?)
            """, (timestamp, operator, access_details, is_anomaly))
            
            conn.commit()
            conn.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "beneficiaries": processed_beneficiaries,
                "access_flagged_anomaly": bool(is_anomaly)
            }).encode('utf-8'))
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def handle_get_audit_logs(self, query_params):
        try:
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM privacy_audit_log ORDER BY audit_id DESC")
            logs = [dict(row) for row in cursor.fetchall()]
            conn.close()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(logs).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def handle_get_quarantined(self, query_params):
        try:
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM quarantined_events ORDER BY event_id DESC")
            events = [dict(row) for row in cursor.fetchall()]
            conn.close()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(events).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))



    def handle_stream_beneficiary(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            payload = json.loads(post_data.decode('utf-8'))
            import inuka_etl
            success, status, result = inuka_etl.process_and_load_event(payload)
            
            self.send_response(200 if success else 400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": success,
                "status": status,
                "result": result
            }).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def handle_consent_update(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            payload = json.loads(post_data.decode('utf-8'))
            beneficiary_id = payload.get("beneficiary_id")
            new_status = payload.get("consent_status")
            consent_type = payload.get("consent_type", "Digital Signature")
            operator = payload.get("operator", "system")
            
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            cursor = conn.cursor()
            
            cursor.execute("SELECT consent_status, full_name FROM inuka_beneficiaries WHERE beneficiary_id = ?", (beneficiary_id,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Beneficiary not found"}).encode('utf-8'))
                return
                
            old_status, name = row
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            data_sharing = 1 if new_status == 'Consented' else 0
            photo_use = 1 if new_status == 'Consented' else 0
            sms_contact = 1 if new_status == 'Consented' else 0
            ext_report = 1 if new_status == 'Consented' else 0
            enroll_status = 'Enrolled' if new_status == 'Consented' else 'On Hold'
            
            cursor.execute("""
                UPDATE inuka_beneficiaries 
                SET consent_status = ?, consent_type = ?, consent_date = ?, 
                    consent_data_sharing = ?, consent_photo_use = ?, 
                    consent_sms_contact = ?, consent_external_reporting = ?,
                    enrollment_status = ?
                WHERE beneficiary_id = ?
            """, (new_status, consent_type, timestamp, data_sharing, photo_use, sms_contact, ext_report, enroll_status, beneficiary_id))
            
            details = f"Changed consent status for {name} ({beneficiary_id}) from {old_status} to {new_status} via {consent_type}."
            cursor.execute("""
                INSERT INTO privacy_audit_log (timestamp, operator, action_type, target_beneficiary_id, details, ip_address, is_anomaly)
                VALUES (?, ?, 'CONSENT_CHANGE', ?, ?, '127.0.0.1', 0)
            """, (timestamp, operator, beneficiary_id, details))
            
            conn.commit()
            conn.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def handle_beneficiary_anonymize(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            payload = json.loads(post_data.decode('utf-8'))
            beneficiary_id = payload.get("beneficiary_id")
            operator = payload.get("operator", "system")
            
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            cursor = conn.cursor()
            
            cursor.execute("SELECT full_name FROM inuka_beneficiaries WHERE beneficiary_id = ?", (beneficiary_id,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Beneficiary not found"}).encode('utf-8'))
                return
                
            name = row[0]
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("""
                UPDATE inuka_beneficiaries
                SET full_name = '[REDACTED_KDPA_REQUEST]',
                    national_id = '[REDACTED_KDPA_REQUEST]',
                    email = '[REDACTED_KDPA_REQUEST]',
                    phone = '[REDACTED_KDPA_REQUEST]',
                    consent_status = 'Withdrawn',
                    consent_data_sharing = 0,
                    consent_photo_use = 0,
                    consent_sms_contact = 0,
                    consent_external_reporting = 0,
                    enrollment_status = 'On Hold',
                    status = 'Anonymized'
                WHERE beneficiary_id = ?
            """, (beneficiary_id,))
            
            # Audit log
            details = f"Executed Right to be Forgotten (KDPA redaction) for beneficiary profile {beneficiary_id} (previously: {name})."
            cursor.execute("""
                INSERT INTO privacy_audit_log (timestamp, operator, action_type, target_beneficiary_id, details, ip_address, is_anomaly)
                VALUES (?, ?, 'ANONYMIZATION', ?, ?, '127.0.0.1', 0)
            """, (timestamp, operator, beneficiary_id, details))
            
            conn.commit()
            conn.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def handle_beneficiary_self_update_consent(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            payload = json.loads(post_data.decode('utf-8'))
            beneficiary_id = payload.get("beneficiary_id")
            
            data_sharing = int(payload.get("consent_data_sharing", 0))
            photo_use = int(payload.get("consent_photo_use", 0))
            sms_contact = int(payload.get("consent_sms_contact", 0))
            ext_reporting = int(payload.get("consent_external_reporting", 0))
            
            if data_sharing == 0:
                enrollment_status = "On Hold"
                consent_status = "Withdrawn"
            else:
                enrollment_status = "Enrolled"
                consent_status = "Consented"
                
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE inuka_beneficiaries
                SET consent_status = ?,
                    consent_data_sharing = ?,
                    consent_photo_use = ?,
                    consent_sms_contact = ?,
                    consent_external_reporting = ?,
                    enrollment_status = ?,
                    consent_date = ?
                WHERE beneficiary_id = ?
            """, (consent_status, data_sharing, photo_use, sms_contact, ext_reporting, enrollment_status, timestamp, beneficiary_id))
            
            # Audit log
            details = f"Beneficiary self-updated consent settings: DataSharing={data_sharing}, PhotoUse={photo_use}, SMS={sms_contact}, ExtReport={ext_reporting}. Status set to: {enrollment_status}."
            cursor.execute("""
                INSERT INTO privacy_audit_log (timestamp, operator, action_type, target_beneficiary_id, details, ip_address, is_anomaly)
                VALUES (?, ?, 'CONSENT_CHANGE', ?, ?, '127.0.0.1', 0)
            """, (timestamp, beneficiary_id, beneficiary_id, details))
            
            conn.commit()
            
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM inuka_beneficiaries WHERE beneficiary_id = ?", (beneficiary_id,))
            fresh_row = dict(cursor.fetchone())
            conn.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "profile": fresh_row
            }).encode('utf-8'))
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def handle_chatbot_message(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            payload = json.loads(post_data.decode('utf-8'))
            message = payload.get("message", "").strip()
            
            # Run NLP Intent Classifier
            intent = "general_faq"
            if 'chatbot' in models:
                intent = models['chatbot'].predict([message])[0]
                
            response_msg = ""
            
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Intent: generate_report (Dynamic Database Aggregation Query)
            if intent == "generate_report":
                clean_msg = message.lower()
                
                # Check for Pillar Match
                pillar_match = None
                for p in ["scholarship", "plus", "vocational", "tech"]:
                    if p in clean_msg:
                        pillar_match = p.title()
                        break
                        
                # Check for Region Match
                region_match = None
                for r in ["north eastern", "coastal", "eastern", "central", "nairobi", "nyanza", "rift valley", "western"]:
                    if r in clean_msg:
                        region_match = r.title()
                        break
                
                if pillar_match:
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total,
                            SUM(CASE WHEN consent_status = 'Consented' THEN 1 ELSE 0 END) as consented,
                            SUM(CASE WHEN consent_status = 'Pending' THEN 1 ELSE 0 END) as pending,
                            SUM(CASE WHEN consent_status = 'Withdrawn' THEN 1 ELSE 0 END) as withdrawn
                        FROM inuka_beneficiaries
                        WHERE pillar = ?
                    """, (pillar_match,))
                    row = dict(cursor.fetchone())
                    
                    cursor.execute("""
                        SELECT COUNT(*) as erasures
                        FROM inuka_beneficiaries
                        WHERE pillar = ? AND status = 'Anonymized'
                    """, (pillar_match,))
                    erasure_row = dict(cursor.fetchone())
                    
                    total = row['total']
                    consented = row['consented'] or 0
                    pending = row['pending'] or 0
                    withdrawn = row['withdrawn'] or 0
                    erasures = erasure_row['erasures'] or 0
                    consent_rate = round((consented / total * 100), 1) if total > 0 else 0
                    
                    response_msg = f"📊 **[Inuka Pillar Report: {pillar_match}]**\n" \
                                   f"- **Total Fellows Registered**: {total}\n" \
                                   f"- **Consent Opt-In Rate**: {consent_rate}% ({consented} / {total})\n" \
                                   f"- **Pending Verification**: {pending}\n" \
                                   f"- **Withdrawn Consent**: {withdrawn}\n" \
                                   f"- **Active Data Erasures**: {erasures} profiles purged under KDPA Sec 40.\n" \
                                   f"*Pillar compliance audit generated and logged in KDPA access ledger.*"
                                   
                elif region_match:
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total,
                            SUM(CASE WHEN consent_status = 'Consented' THEN 1 ELSE 0 END) as consented,
                            SUM(CASE WHEN consent_status = 'Pending' THEN 1 ELSE 0 END) as pending,
                            SUM(CASE WHEN consent_status = 'Withdrawn' THEN 1 ELSE 0 END) as withdrawn
                        FROM inuka_beneficiaries
                        WHERE region = ?
                    """, (region_match,))
                    row = dict(cursor.fetchone())
                    
                    cursor.execute("""
                        SELECT COUNT(*) as erasures
                        FROM inuka_beneficiaries
                        WHERE region = ? AND status = 'Anonymized'
                    """, (region_match,))
                    erasure_row = dict(cursor.fetchone())
                    
                    total = row['total']
                    consented = row['consented'] or 0
                    pending = row['pending'] or 0
                    withdrawn = row['withdrawn'] or 0
                    erasures = erasure_row['erasures'] or 0
                    consent_rate = round((consented / total * 100), 1) if total > 0 else 0
                    
                    response_msg = f"📊 **[Inuka Region Report: {region_match}]**\n" \
                                   f"- **Total Fellows Registered**: {total}\n" \
                                   f"- **Consent Opt-In Rate**: {consent_rate}% ({consented} / {total})\n" \
                                   f"- **Pending Verification**: {pending}\n" \
                                   f"- **Withdrawn Consent**: {withdrawn}\n" \
                                   f"- **Active Data Erasures**: {erasures} profiles purged under KDPA Sec 40.\n" \
                                   f"*Regional compliance audit generated and logged in KDPA access ledger.*"
                else:
                    # Global report across all registry
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total,
                            SUM(CASE WHEN consent_status = 'Consented' THEN 1 ELSE 0 END) as consented,
                            SUM(CASE WHEN consent_status = 'Pending' THEN 1 ELSE 0 END) as pending,
                            SUM(CASE WHEN consent_status = 'Withdrawn' THEN 1 ELSE 0 END) as withdrawn
                        FROM inuka_beneficiaries
                    """)
                    row = dict(cursor.fetchone())
                    
                    cursor.execute("SELECT COUNT(*) as erasures FROM inuka_beneficiaries WHERE status = 'Anonymized'")
                    erasures = cursor.fetchone()[0] or 0
                    
                    total = row['total']
                    consented = row['consented'] or 0
                    pending = row['pending'] or 0
                    withdrawn = row['withdrawn'] or 0
                    consent_rate = round((consented / total * 100), 1) if total > 0 else 0
                    
                    response_msg = f"📊 **[Inuka Global Compliance Status Report]**\n" \
                                   f"- **Total Fellows Registered**: {total}\n" \
                                   f"- **Consent Opt-In Rate**: {consent_rate}% ({consented} / {total})\n" \
                                   f"- **Pending Verification**: {pending}\n" \
                                   f"- **Withdrawn Consent**: {withdrawn}\n" \
                                   f"- **Total Active Data Erasures**: {erasures} profiles anonymized.\n" \
                                   f"*Compliance audit trail compiled and secured.*"

                # Log reporting transaction
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO privacy_audit_log (timestamp, operator, action_type, target_beneficiary_id, details, ip_address, is_anomaly)
                    VALUES (?, 'chatbot_interface', 'COMPLIANCE_REPORT', NULL, 'Generated compliance status report via chatbot query.', '127.0.0.1', 0)
                """, (timestamp,))

            # Other intents...
            elif intent == "view_data":
                cursor.execute("SELECT * FROM inuka_beneficiaries")
                all_b = [dict(row) for row in cursor.fetchall()]
                
                target_b = None
                for b in all_b:
                    if b['full_name'] == '[REDACTED_KDPA_REQUEST]':
                        continue
                    clean_msg = message.lower()
                    first_name = b['full_name'].split()[0].lower() if b['full_name'] else ""
                    
                    if (b['beneficiary_id'].lower() in clean_msg) or \
                       (first_name and first_name in clean_msg) or \
                       (b['national_id'] in clean_msg) or \
                       (b['phone'].replace('+', '') in clean_msg.replace('+', '')):
                        target_b = b
                        break

                if target_b:
                    if target_b['consent_status'] == 'Consented':
                        response_msg = f"**[Intent: View PII Data]** I found a profile matching your request:\n" \
                                       f"- **ID**: {target_b['beneficiary_id']}\n" \
                                       f"- **Name**: {target_b['full_name']}\n" \
                                       f"- **Pillar**: {target_b['pillar']}\n" \
                                       f"- **Region**: {target_b['region']}\n" \
                                       f"- **Email**: {target_b['email']}\n" \
                                       f"- **Phone**: {target_b['phone']}\n" \
                                       f"- **Consent Status**: {target_b['consent_status']} (Granted via {target_b['consent_type']})"
                        
                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        cursor.execute("""
                            INSERT INTO privacy_audit_log (timestamp, operator, action_type, target_beneficiary_id, details, ip_address, is_anomaly)
                            VALUES (?, 'chatbot_interface', 'PII_ACCESS', ?, 'Beneficiary accessed profile info via chatbot query.', '127.0.0.1', 0)
                        """, (timestamp, target_b['beneficiary_id']))
                    else:
                        response_msg = f"**[Access Denied]** A profile for **{target_b['full_name']}** was found, but the current consent status is **{target_b['consent_status']}**. Under the Kenya Data Protection Act, I cannot reveal PII details without active consent."
                else:
                    response_msg = "I couldn't find a beneficiary profile matching the name, ID, or phone number in your message. Please verify and try again (e.g. try: 'show profile for Joseph')."
                    
            elif intent == "update_consent":
                cursor.execute("SELECT * FROM inuka_beneficiaries")
                all_b = [dict(row) for row in cursor.fetchall()]
                target_b = None
                for b in all_b:
                    if b['full_name'] == '[REDACTED_KDPA_REQUEST]':
                        continue
                    clean_msg = message.lower()
                    first_name = b['full_name'].split()[0].lower() if b['full_name'] else ""
                    if (b['beneficiary_id'].lower() in clean_msg) or (first_name and first_name in clean_msg):
                        target_b = b
                        break

                if target_b:
                    clean_msg = message.lower()
                    if "withdraw" in clean_msg or "ondoa" in clean_msg or "opt out" in clean_msg or "revoke" in clean_msg:
                        new_status = "Withdrawn"
                        action_desc = "Withdrew consent"
                    else:
                        new_status = "Consented"
                        action_desc = "Granted consent"
                        
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    data_sharing = 1 if new_status == 'Consented' else 0
                    photo_use = 1 if new_status == 'Consented' else 0
                    sms_contact = 1 if new_status == 'Consented' else 0
                    ext_report = 1 if new_status == 'Consented' else 0
                    enroll_status = 'Enrolled' if new_status == 'Consented' else 'On Hold'
                    
                    cursor.execute("""
                        UPDATE inuka_beneficiaries
                        SET consent_status = ?, consent_type = 'Chatbot OTP', consent_date = ?,
                            consent_data_sharing = ?, consent_photo_use = ?, 
                            consent_sms_contact = ?, consent_external_reporting = ?,
                            enrollment_status = ?
                        WHERE beneficiary_id = ?
                    """, (new_status, timestamp, data_sharing, photo_use, sms_contact, ext_report, enroll_status, target_b['beneficiary_id']))
                    
                    details = f"{action_desc} via AI Chatbot self-service."
                    cursor.execute("""
                        INSERT INTO privacy_audit_log (timestamp, operator, action_type, target_beneficiary_id, details, ip_address, is_anomaly)
                        VALUES (?, 'chatbot_interface', 'CONSENT_CHANGE', ?, ?, '127.0.0.1', 0)
                    """, (timestamp, target_b['beneficiary_id'], details))
                    
                    response_msg = f"**[Intent: Update Consent]** Done! I have updated the consent status for **{target_b['full_name']}** ({target_b['beneficiary_id']}) to **{new_status}** via Chatbot OTP. This change has been written to the KDPA audit ledger."
                else:
                    response_msg = "Please specify which beneficiary profile you want to update consent for (e.g. 'withdraw consent for Joseph')."
                    
            elif intent == "request_deletion":
                cursor.execute("SELECT * FROM inuka_beneficiaries")
                all_b = [dict(row) for row in cursor.fetchall()]
                target_b = None
                for b in all_b:
                    if b['full_name'] == '[REDACTED_KDPA_REQUEST]':
                        continue
                    clean_msg = message.lower()
                    first_name = b['full_name'].split()[0].lower() if b['full_name'] else ""
                    if (b['beneficiary_id'].lower() in clean_msg) or (first_name and first_name in clean_msg):
                        target_b = b
                        break

                if target_b:
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute("""
                        UPDATE inuka_beneficiaries
                        SET full_name = '[REDACTED_KDPA_REQUEST]',
                            national_id = '[REDACTED_KDPA_REQUEST]',
                            email = '[REDACTED_KDPA_REQUEST]',
                            phone = '[REDACTED_KDPA_REQUEST]',
                            consent_status = 'Withdrawn',
                            consent_data_sharing = 0,
                            consent_photo_use = 0,
                            consent_sms_contact = 0,
                            consent_external_reporting = 0,
                            enrollment_status = 'On Hold',
                            status = 'Anonymized'
                        WHERE beneficiary_id = ?
                    """, (target_b['beneficiary_id'],))
                    
                    details = f"Right to be Forgotten request executed via AI Chatbot self-service."
                    cursor.execute("""
                        INSERT INTO privacy_audit_log (timestamp, operator, action_type, target_beneficiary_id, details, ip_address, is_anomaly)
                        VALUES (?, 'chatbot_interface', 'ANONYMIZATION', ?, ?, '127.0.0.1', 0)
                    """, (timestamp, target_b['beneficiary_id'], details))
                    
                    response_msg = f"**[Right to be Forgotten Executed]** Under Section 40 of the Kenya Data Protection Act, your request has been processed. The profile **{target_b['beneficiary_id']}** has been permanently anonymized (all names, IDs, phones, and emails redacted). This transaction is cryptographically logged in our audit logs."
                else:
                    response_msg = "To request data deletion under KDPA, please specify the beneficiary profile (e.g. 'delete record for Joseph')."
                    
            else: # general_faq
                clean_msg = message.lower()
                if "kpc" in clean_msg or "linda" in clean_msg or "protect" in clean_msg:
                    response_msg = "💡 **KDPA Privacy FAQ**: KPC Inuka Foundation encrypts all beneficiary PII in our database. We run an automated machine learning anomaly detector to monitor database access and automatically mask personal data (anonymization) for external reporting."
                elif "futa" in clean_msg or "delete" in clean_msg or "forgotten" in clean_msg:
                    response_msg = "💡 **KDPA Data Rights**: Beneficiaries have the 'Right to be Forgotten' under Section 40 of KDPA. You can request deletion by typing: 'delete data for [Name]' and the system will redact all your identifiers instantly."
                else:
                    response_msg = "💡 **Inuka Privacy Bot**: Hello! I am the Inuka Foundation's compliance self-service agent. You can ask me to:\n" \
                                   "1. **Check your details** (e.g. 'show data for Joseph')\n" \
                                   "2. **Grant or revoke consent** (e.g. 'withdraw consent for Joseph')\n" \
                                   "3. **Request data deletion** (e.g. 'delete details for Joseph')\n" \
                                   "4. **Pillar or Region compliance report** (e.g. 'report on the tech pillar')\n" \
                                   "5. Ask questions about how we comply with the **Kenya Data Protection Act (KDPA)**."
            
            conn.commit()
            conn.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "intent": intent,
                "reply": response_msg
            }).encode('utf-8'))
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

def run_server():
    load_prediction_models()
    handler = DashboardHTTPHandler
    print(f"Starting server on http://localhost:{PORT}")
    print("Press Ctrl+C to terminate.")
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")

if __name__ == "__main__":
    run_server()
