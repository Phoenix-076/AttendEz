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
