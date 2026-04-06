import pandas as pd
from sklearn.tree import DecisionTreeClassifier
import pickle

# sample dataset
data = {
    "current": [1, 1.2, 1.5, 2, 2.2, 5, 6, 7],
    "power": [200, 220, 250, 300, 330, 800, 900, 1000],
    "theft": [0,0,0,0,0,1,1,1]
}

df = pd.DataFrame(data)

X = df[["current","power"]]
y = df["theft"]

model = DecisionTreeClassifier()
model.fit(X, y)

# save model
with open("model.pkl", "wb") as f:
    pickle.dump(model, f)

print("Model trained and saved!")