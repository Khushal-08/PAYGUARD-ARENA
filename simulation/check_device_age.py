import pandas as pd
import numpy as np

def check_device_age():
    print("Loading data...")
    df = pd.read_csv("ml/data/simulated_baseline.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    legit = df[df['label'] == 'Legit'].copy()
    fraud = df[df['label'] == 'Fraud'].copy()
    
    # Calculate global minimum for each device
    legit['device_first_seen'] = legit.groupby('device_id')['timestamp'].transform('min')
    legit['device_age_days'] = (legit['timestamp'] - legit['device_first_seen']).dt.total_seconds() / 86400.0
    
    fraud['device_first_seen'] = fraud.groupby('device_id')['timestamp'].transform('min')
    fraud['device_age_days'] = (fraud['timestamp'] - fraud['device_first_seen']).dt.total_seconds() / 86400.0
    
    print("\nLegitimate Device Age Distribution:")
    print(legit['device_age_days'].describe())
    
    print("\nFraud Device Age Distribution:")
    print(fraud['device_age_days'].describe())
    
    print("\nBinned over time (Legit):")
    bins = [-1, 5, 10, 30, 60, 90, 100]
    print(pd.cut(legit['device_age_days'], bins=bins).value_counts(normalize=True).sort_index() * 100)

if __name__ == "__main__":
    check_device_age()
