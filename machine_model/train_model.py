from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OrdinalEncoder
from sklearn.compose import ColumnTransformer
from xgboost import XGBRegressor
import pandas as pd


def train_model():
    calories = pd.read_csv("./machine_model/calories.csv")
    exercise = pd.read_csv("./machine_model/exercise.csv")
    data = pd.merge(calories, exercise, on='User_ID')
    X = data.drop(columns=['User_ID', 'Calories'])
    y = data['Calories']
    
    # X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    preprocessor = ColumnTransformer(transformers=[
        ('ordinal', OrdinalEncoder(), ['Gender']),
        ('num', StandardScaler(), ['Age', 'Height', 'Weight', 'Duration', 'Heart_Rate', 'Body_Temp']),
    ])
    
    pipeline = Pipeline([
        ('preprocessor', preprocessor),
        ('model',XGBRegressor())
    ])

    pipeline.fit(X, y)
    print("Model trained successfully!")
    return pipeline