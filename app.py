from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from firebase_admin import db
from forms import RegistrationForm, LoginForm  # Import the form class
from flask_bcrypt import Bcrypt
import re
from flask_session import Session
from flask import session
import cv2
from tensorflow.keras.models import load_model  # type: ignore
import numpy as np
import time
from datetime import datetime
import pickle
import face_recognition
import firebase
import smtplib
from email.mime.text import MIMEText
from email_validator import validate_email, EmailNotValidError

app = Flask(__name__)


app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True

Session(app)


app.config['SECRET_KEY'] = '767183cec49283610f68147af7ac0191'

# Load the pre-trained face detection model
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Load the pre-trained classification model


bcrypt = Bcrypt()

# Regular expression for email validation
email_pattern = re.compile(r'^[\w.-]+\.gcit@rub\.edu\.bt$')


# Function to check if an email is valid
def is_valid_email(email):
    return bool(email_pattern.match(email))


# Load precomputed encodings
def load_encodings():
    print("Loading Encode File ...")
    with open('EncodeFile.p', 'rb') as file:
        encodeListKnownWithIds = pickle.load(file)
    print("Encode File Loaded")
    return encodeListKnownWithIds

# Initialize known face encodings and names
known_face_encodings, known_face_names = load_encodings()

@app.route('/')
def landing_page():
    if 'logged_in' in session:
        user_name = session.get('user_name')
        user_email = session.get('user_email')
        user_role = session.get('user_role')
        if user_role == 'Lecturer':
            return render_template('dashboard.html', user_name=user_name, user_email=user_email)
        else:
            return render_template('SClass.html')
    return render_template('home.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        password = form.password.data
        confirm_password = form.confirm_password.data

        classes = []
        subjects = []
        # Check if email matches the specified pattern
        if not is_valid_email(email):
            flash('Please use a valid GCIT email address.', 'error')
            return redirect(url_for('register'))

        # Check if email is already registered
        lecturer_ref = db.reference('lecturers')
        existing_lecturers = lecturer_ref.order_by_child('email').equal_to(email).get()
        if existing_lecturers:
            flash('Email already registered.', 'error')
            return redirect(url_for('register'))

        # Hash the password
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        # Add lecturer information to Firebase Realtime Database
        new_lecturer_ref = lecturer_ref.push()
        new_lecturer_ref.set({
            'name': name,
            'email': email,
            'password': hashed_password,
            'role': 'Lecturer',  # Set default role to "Lecturer"
            'classes': classes,
            'subjects': subjects
        })

        return redirect(url_for('login'))

    return render_template('signup.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        # Check if email exists in the lecturers collection
        lecturer_ref = db.reference('lecturers')
        lecturer = lecturer_ref.order_by_child('email').equal_to(email).get()

        # Check if email exists in the students collection if not found in lecturers
        if not lecturer:
            student_ref = db.reference('students')
            student = student_ref.order_by_child('email').equal_to(email).get()

        # If email exists in either lecturers or students collection
        if lecturer or student:
            # Check if the password is correct
            user = lecturer if lecturer else student
            user_id = list(user.keys())[0]
            user_data = user[user_id]
            hashed_password = user_data.get('password')

            if bcrypt.check_password_hash(hashed_password, password):
                # If the user is a lecturer, redirect to dashboard.html
                session['logged_in'] = True
                session['user_email'] = email
                session['user_name'] = user_data.get('name')
                session['user_role'] = user_data.get('role')
                print(session)
                if lecturer:
                    return redirect(url_for('dashboard'))
                # If the user is a student, redirect to class.html
                else:
                    return redirect(url_for('sclass'))
            else:
                flash('Incorrect Password.', 'error')
        else:
            flash("User doesn't exist.", 'error')

    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing_page'))


@app.route('/dashboard')
def dashboard():
    if 'logged_in' in session:
        user_name = session.get('user_name')
        user_email = session.get('user_email')
        user_role = session.get('user_role')
        # Logic for authenticated user...
        if user_role == 'Student':
            return redirect(url_for('sclass'))
        else:
            return render_template('dashboard.html', user_name=user_name, user_email=user_email)
    else:
        return redirect(url_for('login'))

 
@app.route('/classes')
def classes():
    if 'logged_in' in session:
        user_name = session.get('user_name')
        user_email = session.get('user_email')
        user_role = session.get('user_role')
        
        # Get the lecturer's email from the session
        lecturer_email = session.get('user_email')
        # Assuming lecturer_data is the OrderedDict obtained from the query
      
        # Query the database to get the lecturer's data using their email
        lecturers_ref = db.reference('lecturers')
        lecturer_query = lecturers_ref.order_by_child('email').equal_to(lecturer_email)
        lecturer_data = lecturer_query.get()
        lecturer_id = list(lecturer_data.keys())[0]  # Get the lecturer's ID
        lecturer_classes = lecturer_data[lecturer_id].get('classes', [])  # Get the lecturer's classes
        print(lecturer_classes)
        # Assuming there's only one lecturer with the given email
        lecturer_id = list(lecturer_data.keys())[0] if lecturer_data else None
        if lecturer_id:
            # Get the lecturer's classes
            lecturer_classes = lecturer_data[lecturer_id].get('classes', [])
        else:
            lecturer_classes = []
        print(lecturers_ref.order_by_child('email').get())
        # Render the template with the lecturer's classes
        return render_template('Class.html', user_name=user_name, user_email=user_email, lecturer_classes=lecturer_classes)
    else:
        return redirect(url_for('login'))


def predict_face(cap, encodeListKnown, studentIds):
    while True:
        success, img = cap.read()
        if not success:
            break

        img = cv2.resize(img, (640, 480))
        imgS = cv2.resize(img, (0, 0), None, 0.25, 0.25)
        imgS = cv2.cvtColor(imgS, cv2.COLOR_BGR2RGB)

        faceCurFrame = face_recognition.face_locations(imgS)
        encodeCurFrame = face_recognition.face_encodings(imgS, faceCurFrame)

        if faceCurFrame:
            for encodeFace, faceLoc in zip(encodeCurFrame, faceCurFrame):
                matches = face_recognition.compare_faces(encodeListKnown, encodeFace)
                faceDis = face_recognition.face_distance(encodeListKnown, encodeFace)
                matchIndex = np.argmin(faceDis)

                if matches[matchIndex]:
                    id = studentIds[matchIndex]
                    print("Recognized ID:", id)
                    return id

    return None


def gen_frames():
    cap = cv2.VideoCapture(0)
    cap.set(3, 640)
    cap.set(4, 480)

    encodeListKnown, studentIds = load_encodings()

    while True:
        class_name = predict_face(cap, encodeListKnown, studentIds)
        if class_name:
            print(f'Recognized class name: {class_name}')
        else:
            print('No face recognized')

        success, frame = cap.read()
        if not success:
            break

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.1)  # Add a small delay to control frame rate

    cap.release()


@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/get_predictions', methods=['POST'])
def get_predictions():
    selected_class = request.get_json().get('selected_class')
    print("Selected class:", selected_class)

    video = cv2.VideoCapture(0)
    success, frame = video.read()

    if success:
        predicted_face_name = predict_face(video, known_face_encodings, known_face_names)

        if predicted_face_name:
            lec_ref = db.reference('lecturers')
            #lec query
            lec_query = lec_ref.order_by_child('email').equal_to(session.get('user_email')).get()
            classes_list = list(lec_query.values())[0]['classes']

            # Find the index of selected_class in classes_list
            class_index = classes_list.index(selected_class)

            # Get the subjects list from the dictionary
            subjects_list = list(lec_query.values())[0]['subjects']
            print("class index",class_index)
            print("class list",classes_list)
            print("subject list",subjects_list)
            # Get the subject at the class_index
            if class_index < len(subjects_list):
                selected_subject_code = subjects_list[class_index]
                print(selected_subject_code)
            collection_name = f'{selected_class}_{selected_subject_code}_attendance'
            sid = predicted_face_name
            print(collection_name,sid)
            print(selected_class,type(selected_class))

            # std query
            student_ref = db.reference('student_info')
            std_query = student_ref.order_by_child('std_id').get()
            student_details = None
            print(predicted_face_name)
            # Iterate through each section and its students
            for section, students in std_query.items():
                for key, student in students.items():
                    print(student['std_id'],type(student['std_id']))
                    print(predicted_face_name,type(predicted_face_name))
                    if student['std_id'] == int(predicted_face_name):
                        student_details = student
                        print("s d", student_details)
                        break
                if student_details:
                    break

            # Print the student details
            if student_details:
                print("detaillss",student_details)
            else:
                print("Student not found")
            print('classss',student_details['section'])
            if selected_class == student_details['section']:
                print("attendance for",selected_class,selected_subject_code)
                take_attendance(selected_class,selected_subject_code,sid)
                # Here, you can add additional logic to process the prediction if needed
                predictions = [{"class": student_details['section'], "name": student_details['name'], "std_id": predicted_face_name}]
                return jsonify(predictions)
        else:
            return jsonify([])

    return jsonify([])


def take_attendance(class_name, subject_name, sid):
    date = datetime.now().strftime("%d-%m-%y")
    attendance_data = {
        date: 1
    }

    attendance_ref = db.reference(f"{class_name}_{subject_name}_attendance")
    s_id = str(sid)
    attendance_query = attendance_ref.child(s_id)
    attendance_query.update(attendance_data)

    # Get the lecturer's email from the session
    lecturer_email = session.get('user_email')

    # Get the lecturer's reference
    lecturers_ref = db.reference('lecturers')
    lecturer_query = lecturers_ref.order_by_child('email').equal_to(lecturer_email).get()

    if lecturer_query:
        # The user is a lecturer
        lecturer_id = list(lecturer_query.keys())[0]
        lecturer_data = lecturer_query[lecturer_id]
        lecturer_classes = lecturer_data.get('classes', [])
        lecturer_subjects = lecturer_data.get('subjects', [])

        # Find the index of the current class and subject in the lecturer's lists
        class_index = lecturer_classes.index(class_name)
        subject_index = lecturer_subjects.index(subject_name)

        # Create a new attendance list document in the "attendance_lists" collection
        attendance_lists_ref = db.reference('attendance_lists')
        attendance_list_key = f"{class_name}_{subject_name}"
        attendance_list_ref = attendance_lists_ref.child(attendance_list_key)

        # Check if the date already exists in the attendance list
        existing_attendance_list = attendance_list_ref.get()
        if existing_attendance_list and date in existing_attendance_list:
            # The date already exists in the attendance list, no need to add it again
            return

        # Add the new date to the attendance list
        if existing_attendance_list:
            new_attendance_list = existing_attendance_list
            new_attendance_list.append(date)
        else:
            new_attendance_list = [date]
        attendance_list_ref.set(new_attendance_list)


@app.route('/update_attendance', methods=['POST'])
def update_attendance():
    data = request.get_json()
    class_code = data.get('class_code')
    date = data.get('date')
    student_id = data.get('student_id')
    new_status = data.get('new_status')
    subject = data.get('subject_name')
    print(data)
    print(class_code)
    print(date)
    print(student_id)
    print(new_status)
    print(subject)
    if not class_code or not date or not student_id or new_status is None:
        return jsonify({'error': 'Missing required parameters'}), 400

    # Update the attendance data in the database
    ref = db.reference(f'{class_code}_{subject}_attendance/{student_id}/{date}')
    ref.set(1 if new_status == 'Present' else 0)

    return jsonify({'message': 'Attendance updated successfully'})


@app.route('/fetch_attendance_details', methods=['GET'])
def fetch_attendance_details():
    class_name = request.args.get('class')
    subject_name = request.args.get('subject')
    date = request.args.get('date')

    lec_ref = db.reference('lecturers')
    lec_query = lec_ref.order_by_child('email').equal_to(session.get('user_email')).get()

    if not lec_query:
        return jsonify({'error': 'Lecturer not found'}), 404

    lec_id = list(lec_query.keys())[0]
    current_data = lec_query[lec_id]
    current_classes = current_data.get('classes', [])
    current_subjects = current_data.get('subjects', [])

    if class_name not in current_classes or subject_name not in current_subjects:
        return jsonify({'error': 'Class or subject not found'}), 404

    # Fetch the list of students in the current class
    students_ref = db.reference('student_info').child(class_name).get()
    students = []
    if students_ref:
        for student_id, student_info in students_ref.items():
            students.append({
                'std_id': str(student_info['std_id']),
                'name': student_info['name'],
                'enrollment': student_info['std_id']
            })

    attendance_data = []
    for student in students:
        std_id = student['std_id']
        ref = db.reference(f'{class_name}_{subject_name}_attendance/{std_id}/{date}')
        data = ref.get()
        status = 'Present' if data == 1 else 'Absent'
        attendance_data.append({
            'name': student['name'],
            'enrollment': student['std_id'],
            'status': status
        })

    return render_template('class_attendance_table.html', attendance_data=attendance_data)


@app.route('/fetch_attendance', methods=['GET'])
def fetch_attendance():
    # Get the date from the request parameters
    date = request.args.get('date')
    if not date:
        return jsonify({'error': 'Date parameter is missing'}), 400

    lec_ref = db.reference('lecturers')
    lec_query = lec_ref.order_by_child('email').equal_to(session.get('user_email')).get()

    if not lec_query:
        return jsonify({'error': 'Lecturer not found'}), 404

    lec_id = list(lec_query.keys())[0]
    current_data = lec_query[lec_id]
    current_classes = current_data.get('classes', [])
    current_subjects = current_data.get('subjects', [])

    attendance_records = []

    for i in range(min(len(current_classes), len(current_subjects))):
        class_name = current_classes[i]
        subject_name = current_subjects[i]
        attendance_list_ref = db.reference(f'attendance_lists/{class_name}_{subject_name}')
        attendance_list = attendance_list_ref.get()

        if attendance_list and date in attendance_list:
            # The attendance data for the given date exists
            attendance_ref_name = f'{class_name}_{subject_name}_attendance'
            print(attendance_ref_name)

            # Fetch the list of students in the current class
            students_ref = db.reference('student_info').child(class_name).get()
            print("student ref ", students_ref)
            students = []
            if students_ref:
                for student_id, student_info in students_ref.items():
                    students.append(str(student_info['std_id']))
            print("student list", students)

            total_students = len(students)
            present_count = 0
            absent_count = 0

            for std_id in students:
                # Build the reference path to the attendance data for each student for the given date
                ref = db.reference(f'{attendance_ref_name}/{std_id}/{date}')
                data = ref.get()
                # print(f"data for {std_id} on {date}:", data)

                if data == 1:
                    present_count += 1
                elif data == 0:
                    absent_count += 1
                else:
                    print(f"No data for student {std_id} on {date}")

            if total_students > 0:
                attendance_percentage = (present_count / total_students) * 100
            else:
                attendance_percentage = 0

            attendance_records.append({
                'class_name': class_name,
                'subject_name': subject_name,
                'total_students': total_students,
                'present': present_count,
                'absent': absent_count,
                'average': f'{attendance_percentage:.2f}%',
                'date': date
            })
        else:
            # The attendance data for the given date does not exist
            attendance_records.append({
                'class_name': class_name,
                'subject_name': subject_name,
                'message': f'No attendance data available for {class_name} - {subject_name} on {date}'
            })

    print("attendance_records", attendance_records)
    return jsonify(attendance_records)


@app.route('/view_attendance', methods=['GET'])
def view_attendance():
    if 'logged_in' in session:
        user_name = session.get('user_name')
        user_email = session.get('user_email')
        user_role = session.get('user_role')
        # Logic for authenticated user...
        if user_role == 'Student':
            return redirect(url_for('sclass'))
        else:
            class_name = request.args.get('class')
            subject_name = request.args.get('subject')
            date = request.args.get('date')
            print("date",date)
            # Use the date passed from the dashboard if available, else use today's date
            if not date:
                date = datetime.now().strftime('%d-%m-%y')
            
            if not all([class_name, subject_name, date]):
                return "Missing parameters", 400

            attendance_ref_name = f'{class_name}_{subject_name}_attendance'
            print(attendance_ref_name)
            students_ref = db.reference('student_info').child(class_name).get()
            print("s ref",students_ref)
            attendance_data = []

            if students_ref:
                for student_id, student_info in students_ref.items():
                    sid = student_info.get('std_id')
                    ref = db.reference(f'{attendance_ref_name}/{sid}/{date}')
                    print(sid)
                    print("attendance",ref.get())
                    status = ref.get()
                    # Retrieve the student's name using the student_id
                    student_name = student_info.get('name', 'Unknown')
                    attendance_data.append({
                        'name': student_name,
                        'enrollment': student_info.get('std_id', 'Unknown'),
                        'status': 'Present' if status == 1 else 'Absent',
                    })
            print(attendance_data)
            return render_template('class_attendance.html', class_name=class_name, subject_name=subject_name, date=date, attendance_data=attendance_data,user_name=user_name, user_email=user_email)
    else:
        return redirect(url_for('login'))


@app.route('/video_popup')
def video_popup():
    print("argssss",request.args.get('class'))
    return render_template('video_popup.html')


@app.route('/cam')
def cam():
    if 'logged_in' in session:
        user_name = session.get('user_name')
        user_email = session.get('user_email')
        user_role = session.get('user_role')
        # Logic for authenticated user...
        if user_role == 'Student':
            return redirect(url_for('sclass'))
        else:
             lecturer_email = user_email

        lecturers_ref = db.reference('lecturers')
        lecturer_query = lecturers_ref.order_by_child('email').equal_to(lecturer_email)
        lecturer_data = lecturer_query.get()
        lecturer_id = list(lecturer_data.keys())[0]  # Get the lecturer's ID
        lecturer_classes = lecturer_data[lecturer_id].get('classes', [])  # Get the lecturer's classes
        print("class",lecturer_classes)
        # Assuming there's only one lecturer with the given email
        lecturer_id = list(lecturer_data.keys())[0] if lecturer_data else None
        if lecturer_id:
            # Get the lecturer's classes
            lecturer_classes = lecturer_data[lecturer_id].get('classes', [])
        else:
            lecturer_classes = []
        print(lecturers_ref.order_by_child('email').get())
        return render_template('cam.html', user_name=user_name, user_email=user_email,lecturer_classes=lecturer_classes)
    else:
        return redirect(url_for('login'))


# Function to fetch classes and modules from Firebase Realtime Database
def get_classes_and_modules():
    # Reference to the database
    class_ref = db.reference('class')
    dep_ref = db.reference('departments')

    # Fetch classes data
    classes_data = class_ref.get()
    if isinstance(classes_data, list):  # Check if classes_data is a list
        classes_dict = {item['code']: item for item in classes_data}
    else:
        classes_dict = classes_data

    if classes_dict:
        classes_list = [{'code': code, 'name': data['name']} for code, data in classes_dict.items()]
    else:
        classes_list = []

    # Fetch departments data
    departments_data = dep_ref.get()
    if isinstance(departments_data, list):  # Check if departments_data is a list
        departments_dict = {item['code']: item for item in departments_data}
    else:
        departments_dict = departments_data

    if departments_dict:
        departments_list = [{'code': code, 'name': data['name']} for code, data in departments_dict.items()]
    else:
        departments_list = []

    print("Classes Data:", classes_list)
    print("Departments Data:", departments_list)

    return classes_list, departments_list



# Route for rendering the class selection page
@app.route('/class-selection')
def class_selection():
    if 'logged_in' in session:
        user_name = session.get('user_name')
        user_email = session.get('user_email')
        user_role = session.get('user_role')
        # Logic for authenticated user...
        if user_role == 'Student':
            return redirect(url_for('sclass'))
        else:
            # Get classes and departments data from the database
            classes_data, departments_data = get_classes_and_modules()
            return render_template('add_class.html', classes=classes_data, departments=departments_data, user_name=user_name, user_email=user_email)
    else:
        return redirect(url_for('login'))
   
@app.route('/add-class-module', methods=['POST'])
def add_class_module():
    if request.method == 'POST':
        # Get the selected class and module from the form
        selected_class = request.form.get('selected_class')
        selected_module = request.form.get('selected_department')

        # Get the lecturer's email and name from the hidden input fields
        lecturer_email = session.get('user_email')
        lecturer_name = session.get('user_name')
        # Update the lecturer's details in the database with the selected class and module
        lecturer_ref = db.reference('lecturers')
        lecturer_query = lecturer_ref.order_by_child('email').equal_to(lecturer_email).get()

        # Assuming there's only one lecturer with the given email
        lecturer_id = list(lecturer_query.keys())[0]
       # Retrieve the current classes and subjects
        current_data = lecturer_query[lecturer_id]
        current_classes = current_data.get('classes', [])
        current_subjects = current_data.get('subjects', [])

        # Append the new class and subject
        current_classes.append(selected_class)
        current_subjects.append(selected_module)

        # Update the database with the modified data
        lecturer_ref.child(lecturer_id).update({
            'classes': current_classes,
            'subjects': current_subjects
        })

        new_collection_name = f"{selected_class}_{selected_module}_attendance"
        student_ref = db.reference('student_info')
        student_query = student_ref.child(selected_class).get()
        print(selected_class)
        # print("attendanceeee gi denlu",student_query)
        students = []
        if student_query:
            for student_id, student_info in student_query.items():
                students.append(str(student_info['std_id']))
        print("attendance 2.0",students)
        print(new_collection_name)
        # Create new collection and add student IDs as documents
        attendance_ref = db.reference(new_collection_name)
        for std in students:
            print("iddd",std)
            std_ref = attendance_ref.child(std)  # You can add data later

            std_ref.set({})
       
        # Redirect to a success page or back to the class selection page
        return redirect(url_for('classes'))

    # Handle cases where the request method is not POST
    print("done")

    return redirect(url_for('class_selection'))

@app.route('/get-students', methods=['POST'])
def get_students():
    selected_class = request.form.get('selected_class')

    # Query the database to get students based on the selected class
    students_ref = db.reference('student_info')
    lec_ref = db.reference('lecturers')

    #lec query
    lec_query = lec_ref.order_by_child('email').equal_to(session.get('user_email')).get()
    classes_list = list(lec_query.values())[0]['classes']

    # Find the index of selected_class in classes_list
    class_index = classes_list.index(selected_class)

    # Get the subjects list from the dictionary
    subjects_list = list(lec_query.values())[0]['subjects']

    # Get the subject at the class_index
    if class_index < len(subjects_list):
        selected_subject_code = subjects_list[class_index]
        print(selected_subject_code)
    else:
        print("Index out of range for subjects list")

    subject_ref = db.reference('departments')
    departments = subject_ref.get()
    print("departments",departments)
    # Find the department name that matches the selected subject code
    selected_department_name = None
    for department in departments:
        if department['code'] == selected_subject_code:
            selected_department_name = department['name']
            break

    print(selected_department_name)
    # students_query = students_ref.order_by_child('section').equal_to(selected_class)
    students_query = students_ref.child(selected_class)
    students_data = students_query.get()

    # Prepare the list of students
    students = []
    if students_data:
        for student_id, student_info in students_data.items():
            students.append(student_info)

    # Return the students and selected department name as JSON
    return jsonify({'students': students, 'selected_department_name': selected_department_name})


@app.route('/sclass')
def sclass():
    if 'logged_in' in session:
        user_name = session.get('user_name')
        user_email = session.get('user_email')
        print(session)
        subject_ref = db.reference('departments')
        subjects = subject_ref.get()
        subject_codes = [subject['code'] for subject in subjects]
        print(subject_codes)
        return render_template('SClass.html', user_name=user_name, user_email=user_email, subject_codes=subject_codes)
    else:
        return redirect(url_for('login'))


@app.route('/fetch_student_attendance', methods=['GET'])
def fetch_student_attendance():
    class_code = request.args.get('class')
    date = request.args.get('date')
    user_class = session.get('user_name')

    if not class_code or not date:
        return jsonify({'error': 'Missing parameters'}), 400

    # Fetch the attendance data for the given class and date
    attendance_ref = db.reference(f'{user_class}_{class_code}_attendance')
    if not attendance_ref.get():
        # Attendance data collection doesn't exist
        return jsonify({'error': f'Either not enrolled or no attendance for {class_code}'}), 404

    attendance_list_ref = db.reference(f'attendance_lists/{user_class}_{class_code}')
    attendance_list = attendance_list_ref.get()
    if attendance_list and date in attendance_list:
        total_class_taken = len(attendance_list)
        students_ref = db.reference('student_info').child(user_class).get()
        students = []
        if students_ref:
            for student_id, student_info in students_ref.items():
                class_taken_ref = db.reference(f'{user_class}_{class_code}_attendance/{student_info["std_id"]}')
                class_taken_query = class_taken_ref.get()
                if class_taken_query:
                    class_taken = len(class_taken_query)
                else:
                    class_taken = 0
                overall_average = (class_taken/total_class_taken)*100 if total_class_taken else 0
                students.append({
                    'std_id': str(student_info['std_id']),
                    'name': student_info['name'],
                    'enrollment': student_info['std_id'],
                    'total_class_taken': total_class_taken,
                    'classes_attended': class_taken,
                    'overall_average': f"{overall_average:.2f}"
                })
                print("info",student_info)
                print("email",student_info['email'])
                if total_class_taken%10 == 0:
                    if overall_average < 90:
                        # Send email to the student
                        try:
                            rec_email = student_info['email']
                            validate_email(rec_email)
                            send_email(rec_email, f"Attendance falling short for {class_code}", f"Hello {student_info['name']}, Your overall attendance average so far is: {overall_average}%. Please don't skip your class.Thank You")
                        except EmailNotValidError as e:
                            print(f"Error sending email to {student_info['name']}: {e}")

        attendance_data = []
        for student in students:
            std_id = student['std_id']
            ref = db.reference(f'{user_class}_{class_code}_attendance/{std_id}/{date}')
            data = ref.get()
            status = 'Present' if data == 1 else 'Absent'
            attendance_data.append({
                'name': student['name'],
                'enrollment': student['enrollment'],
                'status': status,
                'total_class_taken': student['total_class_taken'],
                'classes_attended': student['classes_attended'],
                'overall_average': student['overall_average']
            })

        return jsonify(attendance_data)
    else:
        return jsonify({'error': f'No attendance data available for {user_class} - {class_code} on {date}'}), 404


def send_email(receiver_email, subject, body):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = 'mongarparjeet@gmail.com'
        msg['To'] = receiver_email

        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.starttls()
            smtp.login('mongarparjeet@gmail.com', 'ujbo rusr kcok anud')
            smtp.send_message(msg)
    except Exception as e:
        print(f"Error sending email: {e}")


if __name__ == '__main__':
    app.run(debug=True)


