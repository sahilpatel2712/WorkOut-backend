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
        'Gender': gender.lower(),
        'Body_Temp': body_temp
    }, index=[0])

    try:
        calories = model_pipeline.predict(exercise_data)  
        calories = round(float(calories[0]),2)
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
        calories=calories 
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
    timestamp =  exercise.timestamp 
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
        calories = round(float(calories[0]),2)
    except Exception as e:
        return jsonify({'message': f'Error in prediction: {str(e)}'}), 500
    exercise.age = age
    exercise.height = height
    exercise.weight = weight
    exercise.duration = duration
    exercise.heart_rate = heart_rate
    exercise.gender = gender
    exercise.body_temp = body_temp
    exercise.calories = calories
    exercise.timestamp = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ") if isinstance(timestamp, str) else exercise.timestamp

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
    date_str = request.args.get('date')  
    if not date_str:
        return jsonify({'message': 'Date query parameter is missing'}), 400

    try:
        date_filter = datetime.datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return jsonify({'message': 'Invalid date format'}), 400

    exercises = Exercise.query.filter_by(user_id=current_user.id).filter(
        db.func.date(Exercise.timestamp) == date_filter.date()
    ).all()

    if not exercises:
        return jsonify({'message': 'No exercise data found for the given date'}), 200

    exercise_list = []
    total_calories = 0 

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
        total_calories += exercise.calories

    return jsonify({
        'exercises': exercise_list,
        'total_calories': round(total_calories,2) 
    }), 200


@app.route('/get-graph-data', methods=['POST'])
@token_required
def get_calories_data(current_user):
    data = request.json
    condition = data.get('condition', 'weekly') 

    if condition not in ['weekly', 'monthly', 'yearly']:
        return jsonify({'message': 'Invalid condition! Must be weekly, monthly, or yearly.'}), 400

    today = datetime.datetime.utcnow()
    bar_data = []
    avg_calories = 0
    
    if condition == 'weekly':
        start_of_week = today - datetime.timedelta(days=today.weekday())  
        days_passed = (today - start_of_week).days + 1  
        
        exercises = Exercise.query.filter(
            Exercise.user_id == current_user.id,
            db.func.date(Exercise.timestamp) >= start_of_week.date(),
            db.func.date(Exercise.timestamp) <= today.date()
        ).all()
        
        week_days = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
        daily_calories = {i: 0 for i in range(7)} 

        total_calories = 0
        for exercise in exercises:
            day_index = exercise.timestamp.weekday() 
            daily_calories[day_index] += exercise.calories
            total_calories += exercise.calories

        avg_calories = total_calories / days_passed 
        
        for i, day in enumerate(week_days):
            value = daily_calories[i]
            front_color = '#177AD5' if value > avg_calories else None
            bar_data.append({'value': round(value,2), 'label': day, 'frontColor': front_color if value > 0 else None})
    
    elif condition == 'monthly':
        start_of_year = today.replace(month=1, day=1)
        exercises = Exercise.query.filter(
            Exercise.user_id == current_user.id,
            db.func.date(Exercise.timestamp) >= start_of_year.date(),
            db.func.date(Exercise.timestamp) <= today.date()
        ).all()

        monthly_calories = {i: 0 for i in range(1, 13)}  
        total_calories = 0

        for exercise in exercises:
            month = exercise.timestamp.month
            monthly_calories[month] += exercise.calories
            if month <= today.month:  
                total_calories += exercise.calories

        months_passed = today.month
        avg_calories = total_calories / months_passed
        
        for i, month_name in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']):
            value = monthly_calories[i + 1]
            front_color = '#177AD5' if i + 1 <= today.month and value > avg_calories else None
            bar_data.append({'value': round(value,2), 'label': month_name, 'frontColor': front_color})

    # elif condition == 'yearly':
    #     start_of_year = today.replace(month=1, day=1)
    #     months_passed = today.month  
        
    #     exercises = Exercise.query.filter(
    #         Exercise.user_id == current_user.id,
    #         db.func.date(Exercise.timestamp) >= start_of_year.date(),
    #         db.func.date(Exercise.timestamp) <= today.date()
    #     ).all()

    #     total_calories = 0
    #     monthly_calories = {i: 0 for i in range(1, 13)}  

    #     for exercise in exercises:
    #         month = exercise.timestamp.month
    #         monthly_calories[month] += exercise.calories
    #         total_calories += exercise.calories

    #     avg_calories = total_calories / months_passed  
        
    #     for month in range(1, today.month + 1):
    #         value = monthly_calories[month]
    #         front_color = '#177AD5' if value > avg_calories else None
    #         bar_data.append({'value': value, 'label': f'{today.year}', 'frontColor': front_color})

    #     for month in range(today.month + 1, 13):
    #         bar_data.append({'value': 0, 'label': f'{today.year}'})
    return jsonify({
        'barData': bar_data,
        'avg_calories': round(avg_calories,2)
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)