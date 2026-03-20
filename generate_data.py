import pandas as pd
import numpy as np
import os

def generate_default_data(file_path='training_data.csv'):
    # Set random seed for reproducibility
    np.random.seed(42)

    # Generate Normal Data (Label: 0)
    n_normal = 100
    normal_current = np.random.uniform(0.5, 2.0, n_normal)
    normal_power = normal_current * 230 + np.random.normal(0, 10, n_normal)
    normal_energy = np.cumsum(normal_power / 3600 / 1000) 
    normal_label = [0] * n_normal

    # Generate Theft Data (Label: 1) - significantly higher current/power
    n_theft = 100
    theft_current = np.random.uniform(5.0, 10.0, n_theft)
    theft_power = theft_current * 230 + np.random.normal(0, 50, n_theft)
    theft_energy = np.cumsum(theft_power / 3600 / 1000)
    theft_label = [1] * n_theft

    # Combine data
    data = {
        'current': np.concatenate([normal_current, theft_current]),
        'power': np.concatenate([normal_power, theft_power]),
        'energy': np.concatenate([normal_energy, theft_energy]),
        'theft': np.concatenate([normal_label, theft_label])
    }

    df = pd.DataFrame(data)
    df.to_csv(file_path, index=False)
    print(f"{file_path} generated successfully.")

if __name__ == "__main__":
    generate_default_data()
