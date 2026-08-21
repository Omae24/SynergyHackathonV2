import os
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

MODELS_DIR = "models"
os.makedirs(MODELS_DIR, exist_ok=True)

def train_anomaly_detector():
    print("Training PII Access Anomaly Detector (Isolation Forest)...")
    
    np.random.seed(42)
    n_samples = 1000
    
    # Normal access records (95% of data)
    normal_hours = np.random.normal(12, 3, n_samples).astype(int)
    normal_hours = np.clip(normal_hours, 7, 21)
    normal_roles = np.random.choice([0, 1, 2], n_samples, p=[0.4, 0.5, 0.1])
    normal_mismatches = np.zeros(n_samples, dtype=int)
    normal_volumes = np.random.randint(1, 10, n_samples)
    
    # Introduce small number of anomalies (5% of data)
    anomaly_hours = np.random.choice([1, 2, 3, 4, 23], 50)
    anomaly_roles = np.random.choice([1, 3], 50, p=[0.5, 0.5])
    anomaly_mismatches = np.random.choice([0, 1], 50, p=[0.2, 0.8])
    anomaly_volumes = np.random.randint(50, 150, 50)
    
    X_normal = pd.DataFrame({
        'hour_of_day': normal_hours,
        'operator_role_code': normal_roles,
        'region_mismatch': normal_mismatches,
        'query_volume': normal_volumes
    })
    
    X_anomaly = pd.DataFrame({
        'hour_of_day': anomaly_hours,
        'operator_role_code': anomaly_roles,
        'region_mismatch': anomaly_mismatches,
        'query_volume': anomaly_volumes
    })
    
    X_train = pd.concat([X_normal, X_anomaly]).reset_index(drop=True)
    
    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(X_train)
    
    path = os.path.join(MODELS_DIR, "access_anomaly_detector.joblib")
    joblib.dump(model, path)
    print(f"PII Access Anomaly Detector saved to {path}")
    
    test_normal = [[12, 0, 0, 3]]
    test_anomaly = [[2, 1, 1, 120]]
    print(f"  Test Normal Prediction: {model.predict(test_normal)[0]} (Expected: 1)")
    print(f"  Test Anomaly Prediction: {model.predict(test_anomaly)[0]} (Expected: -1)")


def train_chatbot_intent_classifier():
    print("Training Bilingual Chatbot Intent Classifier (NLP)...")
    
    data = [
        # Intent: view_data
        ("show my details", "view_data"),
        ("what information do you store about me?", "view_data"),
        ("view profile", "view_data"),
        ("nataka kuona data yangu", "view_data"),
        ("onyesha habari zangu", "view_data"),
        ("angalia data yangu ya kibinafsi", "view_data"),
        ("check my information", "view_data"),
        ("retrieve profile details", "view_data"),
        ("nipe maelezo yangu", "view_data"),
        ("show records", "view_data"),
        ("show profile for joseph", "view_data"),
        ("angalia habari zangu", "view_data"),
        
        # Intent: update_consent
        ("i want to grant consent", "update_consent"),
        ("give permission to process my data", "update_consent"),
        ("withdraw consent", "update_consent"),
        ("nataka kuondoa kibali changu", "update_consent"),
        ("ondoa ridhaa yangu", "update_consent"),
        ("peana kibali", "update_consent"),
        ("change my consent preferences", "update_consent"),
        ("opt out", "update_consent"),
        ("opt in", "update_consent"),
        ("kubali maombi ya ridhaa", "update_consent"),
        ("withdraw consent for asha", "update_consent"),
        
        # Intent: request_deletion (Right to be Forgotten)
        ("delete my personal data", "request_deletion"),
        ("erase my details from your database", "request_deletion"),
        ("right to be forgotten request", "request_deletion"),
        ("futa kabisa habari zangu", "request_deletion"),
        ("toa faili langu kwenye mfumo", "request_deletion"),
        ("forget me", "request_deletion"),
        ("scrub my record", "request_deletion"),
        ("futa profile", "request_deletion"),
        ("nataka mfutie data yangu", "request_deletion"),
        ("delete my beneficiary account", "request_deletion"),
        ("delete data for joseph", "request_deletion"),
        ("delete my record for joseph", "request_deletion"),
        ("nataka kufuta maelezo yangu", "request_deletion"),
        ("kufuta", "request_deletion"),
        ("futa", "request_deletion"),
        ("futa data yangu", "request_deletion"),
        
        # Intent: general_faq (KDPA Privacy Regulations)
        ("is my data safe with you?", "general_faq"),
        ("how do you protect my privacy?", "general_faq"),
        ("sheria ya KDPA inasemaje?", "general_faq"),
        ("kpc inalinda vipi habari zangu?", "general_faq"),
        ("privacy policy information", "general_faq"),
        ("tell me about data protection regulations", "general_faq"),
        ("are my details encrypted?", "general_faq"),
        ("who has access to my PII?", "general_faq"),
        ("kibali changu kinatumika wapi?", "general_faq"),
        ("rights of data subject under Kenya Data Protection Act", "general_faq"),
        ("jinsi ya kulinda data yangu?", "general_faq"),

        # Intent: generate_report
        ("report on the tech pillar", "generate_report"),
        ("give me a report on vocational", "generate_report"),
        ("scholarship pillar status", "generate_report"),
        ("nyanza region audit report", "generate_report"),
        ("generate report for plus pillar", "generate_report"),
        ("ripoti ya pillar ya tech", "generate_report"),
        ("ripoti ya nyanza", "generate_report"),
        ("show stats for nairobi", "generate_report"),
        ("compliance report for eastern", "generate_report"),
        ("stats for rift valley", "generate_report"),
        ("western region status", "generate_report"),
        ("central pillar audit", "generate_report"),
        ("coastal region report", "generate_report"),
        ("north eastern report", "generate_report"),
        ("generate report", "generate_report")
    ]
    
    df = pd.DataFrame(data, columns=['text', 'intent'])
    
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(ngram_range=(1, 2), stop_words=None)),
        ('clf', LogisticRegression(random_state=42))
    ])
    
    pipeline.fit(df['text'], df['intent'])
    
    path = os.path.join(MODELS_DIR, "chatbot_intent_classifier.joblib")
    joblib.dump(pipeline, path)
    print(f"Chatbot Intent Classifier saved to {path}")
    
    test_queries = [
        "please erase all my data",
        "nataka kuona habari zangu",
        "is my information secure?",
        "nataka kuondoa kibali",
        "nataka kufuta maelezo yangu"
    ]
    for q in test_queries:
        pred = pipeline.predict([q])[0]
        print(f"  Query: '{q}' -> Predicted Intent: {pred}")


if __name__ == "__main__":
    train_anomaly_detector()
    train_chatbot_intent_classifier()
