from flask import Flask, request, jsonify
import pandas as pd
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from machine_model.train_model import train_model
from settings import SECRET_KEY,DATABASE_URL
import jwt
import datetime
from functools import wraps
from flask_cors import CORS


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
app.config.from_pyfile('settings.py')
app.config['SQLALCHEMY_DATABASE_URI'] =DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = SECRET_KEY

db = SQLAlchemy(app)

class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Exercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    age = db.Column(db.Integer, nullable=False)
    height = db.Column(db.Float, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    duration = db.Column(db.Float, nullable=False)  
    heart_rate = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    body_temp = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    calories = db.Column(db.Float, nullable=False) 
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

with app.app_context():
    db.create_all()

model_pipeline = train_model()

def generate_jwt(user_id):
    token = jwt.encode({
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)  
    }, app.config['SECRET_KEY'], algorithm="HS256")
    return token

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = Users.query.filter_by(id=data['user_id']).first()
        except:
            return jsonify({'message': 'Token is invalid!'}), 401

        return f(current_user, *args, **kwargs)
    return decorated

@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    hashed_password = generate_password_hash(password)

    existing_user = Users.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'message': 'User already exists!'}), 409

    new_user = Users(username=username, email=email, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    token = generate_jwt(new_user.id)

    return jsonify({
        'message': 'User Sign Up successfully!',
        'token': token,
        'username': new_user.username 
    }), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    user = Users.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password, password):
        return jsonify({'message': 'Invalid credentials!'}), 401

    token = generate_jwt(user.id)

    return jsonify({
        'message': 'Login successful!',
        'token': token,
        'username': user.username 
    }), 200

@app.route('/exercise', methods=['POST'])
@token_required
def save_exercise(current_user):
    data = request.json
    age = data.get('age')
    height = data.get('height')
    weight = data.get('weight')
    duration = data.get('duration')
    heart_rate = data.get('heart_rate')
    gender = data.get('gender')
    body_temp = data.get('body_temp')

    if not all([age, height, weight, duration, heart_rate, gender, body_temp]):
        return jsonify({'message': 'Missing data'}), 400

    
    exercise_data = pd.DataFrame({
        'Age': age,
        'Height': height,
        'Weight': weight,
        'Duration': duration,
        'Heart_Rate': heart_rate,
        'Gender':gender.lower(),
        'Body_Temp': body_temp
    },index=[0])

    try:
        calories = model_pipeline.predict(exercise_data)  
        calories = calories.tolist()  
    except Exception as e:
        return jsonify({'message': f'Error in prediction: {str(e)}'}), 500
    new_exercise = Exercise(
        age=age,
        height=height,
        weight=weight,
        duration=duration,
        heart_rate=heart_rate,
        gender=gender,
        body_temp=body_temp,
        user_id=current_user.id,
        calories=calories[0] 
    )
    db.session.add(new_exercise)
    db.session.commit()

    return jsonify({'message': 'Exercise data saved successfully!', 'calories': calories}), 201


@app.route('/exercise/<int:id>', methods=['PUT'])
@token_required
def edit_exercise(current_user, id):
    exercise = Exercise.query.filter_by(id=id, user_id=current_user.id).first()

    if not exercise:
        return jsonify({'message': 'Exercise not found or not authorized to edit'}), 404

    data = request.json
    age = data.get('age', exercise.age)
    height = data.get('height', exercise.height)
    weight = data.get('weight', exercise.weight)
    duration = data.get('duration', exercise.duration)
    heart_rate = data.get('heart_rate', exercise.heart_rate)
    gender = data.get('gender', exercise.gender)
    body_temp = data.get('body_temp', exercise.body_temp)

    exercise_data = pd.DataFrame({
        'Age': age,
        'Height': height,
        'Weight': weight,
        'Duration': duration,
        'Heart_Rate': heart_rate,
        'Gender': gender.lower(),
        'Body_Temp': body_temp
    }, index=[0])

    try:
        calories = model_pipeline.predict(exercise_data)  
        calories = calories.tolist()  
    except Exception as e:
        return jsonify({'message': f'Error in prediction: {str(e)}'}), 500
    exercise.age = age
    exercise.height = height
    exercise.weight = weight
    exercise.duration = duration
    exercise.heart_rate = heart_rate
    exercise.gender = gender
    exercise.body_temp = body_temp
    exercise.calories = calories[0]

    db.session.commit()

    return jsonify({'message': 'Exercise data updated successfully!', 'calories': calories}), 200



@app.route('/exercise/<int:id>', methods=['DELETE'])
@token_required
def delete_exercise(current_user, id):
    exercise = Exercise.query.filter_by(id=id, user_id=current_user.id).first()

    if not exercise:
        return jsonify({'message': 'Exercise not found or not authorized to delete'}), 404

    db.session.delete(exercise)
    db.session.commit()

    return jsonify({'message': 'Exercise deleted successfully!'}), 200

@app.route('/get-exercise', methods=['GET'])
@token_required
def get_exercises(current_user):
    exercises = Exercise.query.filter_by(user_id=current_user.id).all()

    if not exercises:
        return jsonify({'message': 'No exercise data found for the user'}), 200

    exercise_list = []
    for exercise in exercises:
        exercise_data = {
            'id': exercise.id,
            'age': exercise.age,
            'height': exercise.height,
            'weight': exercise.weight,
            'duration': exercise.duration,
            'heart_rate': exercise.heart_rate,
            'gender': exercise.gender,
            'body_temp': exercise.body_temp,
            'calories': exercise.calories,
            'timestamp': exercise.timestamp
        }
        exercise_list.append(exercise_data)

    return jsonify({'exercises': exercise_list}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=True)

