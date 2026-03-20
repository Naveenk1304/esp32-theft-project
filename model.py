import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib
import os
from generate_data import generate_default_data

class TheftDetector:
    def __init__(self, training_data_path='training_data.csv', model_path='theft_model.pkl'):
        self.training_data_path = training_data_path
        self.model_path = model_path
        self.model = None
        self.load_or_train()

    def train(self):
        print("Training AI model...")
        # If file not found -> create default dataset
        if not os.path.exists(self.training_data_path):
            print(f"{self.training_data_path} not found. Creating default dataset...")
            generate_default_data(self.training_data_path)

        try:
            df = pd.read_csv(self.training_data_path)
            # Features: current, power, energy
            X = df[['current', 'power', 'energy']]
            # Label: theft (0 = normal, 1 = theft)
            y = df['theft']

            self.model = RandomForestClassifier(n_estimators=100, random_state=42)
            self.model.fit(X, y)
            
            # Save the model
            joblib.dump(self.model, self.model_path)
            print("Model trained and saved successfully.")
        except Exception as e:
            print(f"Error during training: {e}")

    def load_or_train(self):
        if os.path.exists(self.model_path):
            print("Loading existing AI model...")
            try:
                self.model = joblib.load(self.model_path)
            except:
                self.train()
        else:
            self.train()

    def predict(self, current, power, energy):
        if self.model is None:
            return 0 # Default to Normal if model failed
        
        try:
            features = [[current, power, energy]]
            prediction = self.model.predict(features)
            return int(prediction[0])
        except Exception as e:
            print(f"Prediction error: {e}")
            return 0

if __name__ == "__main__":
    detector = TheftDetector()
    print(f"Sample normal prediction: {detector.predict(1.2, 270, 0.5)}")
    print(f"Sample theft prediction: {detector.predict(8.0, 1800, 2.5)}")
