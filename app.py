from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
import tempfile
from pdf_generator import generate_bulletin_pdf
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')  # Change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///school.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Helper function to determine appreciation based on subject average
def get_subject_appreciation(moy_cl, n_compo):
    if moy_cl is None or n_compo is None: # Handle cases where grades might be missing
        return "N/A"
    mg = (float(moy_cl) + 2 * float(n_compo)) / 3.0
    if mg >= 16: return "Très Bien"
    if mg >= 14: return "Bien"
    if mg >= 12: return "Assez Bien"
    if mg >= 10: return "Passable"
    if mg >= 8: return "Insuffisant"
    return "Faible"

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'teacher' or 'student'
    current_class_id = db.Column(db.Integer, db.ForeignKey('school_class.id'), nullable=True)
    current_class = db.relationship('SchoolClass', backref=db.backref('students', lazy='dynamic'))
    grades = db.relationship('Grade', backref='student', lazy=True)

class SchoolClass(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False) # e.g., "Terminale C", "Seconde A"
    # bulletin_structure = db.relationship('BulletinStructure', backref='school_class', uselist=False, lazy=True) # Optional: Link to a specific bulletin structure

    def __repr__(self):
        return f'<SchoolClass {self.name}>'

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(80), nullable=False)
    moy_cl = db.Column(db.Float, nullable=False)  # Moyenne de classe/continue
    n_compo = db.Column(db.Float, nullable=False) # Note de composition
    coef = db.Column(db.Integer, nullable=False)   # Coefficient
    appreciation = db.Column(db.String(100), nullable=True) # Appréciation par matière, nullable=True for flexibility
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow) # Retained date, with default
    period = db.Column(db.String(100), nullable=False) # Added period

class BulletinStructure(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    school_class_id = db.Column(db.Integer, db.ForeignKey('school_class.id'), unique=True, nullable=False)
    school_class = db.relationship('SchoolClass', backref=db.backref('bulletin_structure', uselist=False, lazy=True))
    # Store subject lists as comma-separated strings
    subjects_part1 = db.Column(db.Text, nullable=False) # e.g., "MATHS,PHYSIQUE,CHIMIE,GÉOLOGIE/BIO,PHILOSOPHIE,ANGLAIS"
    subjects_part2 = db.Column(db.Text, nullable=False) # e.g., "E.C.M,EPS,INFORMAT.,DESSIN TECH.,CONDUITE"
    # Add other fields if needed, like bulletin_title_override, etc.

# Define standard periods
STANDARD_PERIODS = ["1ère Période", "2e Période", "3e Période"]

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
            confirm_password = data.get('confirm_password')
            role = data.get('role')
            teacher_code = data.get('teacher_code')
            class_id_from_json = data.get('class_id') # Renamed for clarity
            class_id_to_check = class_id_from_json # Use this for validation if JSON
        else:
            username = request.form.get('username').strip() if request.form.get('username') else None
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            role = request.form.get('role')
            teacher_code = request.form.get('teacher_code')
            class_id_form = request.form.get('class_id') 
            class_id_to_check = class_id_form # Use this for validation if form

        # Helper function for validation errors
        def handle_error(message, template_vars=None):
            if request.is_json:
                return {'error': message}, 400
            flash(message, 'danger')
            # Pass school_classes to template even on error for GET request part
            all_school_classes = SchoolClass.query.order_by(SchoolClass.name).all()
            render_vars = {'school_classes': all_school_classes}
            if template_vars:
                render_vars.update(template_vars)
            return render_template('register.html', **render_vars)
        
        if not all([username, password, confirm_password, role]):
            return handle_error('All fields are required')

        if role == 'student' and not class_id_to_check:
            # For form submission, class_id_form might be an empty string if "Select Class..." is chosen
            # We treat this as an error, requiring a class selection for students.
            if not request.is_json: # Only flash if it's a form submission
                 return handle_error('Please select a class for the student.')
            # For JSON, if class_id is optional, this check might be different

        if len(username) < 3:
            return handle_error('Username must be at least 3 characters long')

        if len(password) < 6:
            return handle_error('Password must be at least 6 characters long')

        if password != confirm_password:
            return handle_error('Passwords do not match')

        if role == 'teacher' and teacher_code != 'SCHOOL2025':
            return handle_error('Invalid teacher registration code')

        if User.query.filter_by(username=username).first():
            return handle_error('Username already exists')

        user = User(
            username=username,
            password=generate_password_hash(password),
            role=role
        )        
        
        if role == 'student' and class_id_to_check and class_id_to_check.isdigit():
            user.current_class_id = int(class_id_to_check)
        
        db.session.add(user)
        db.session.commit()

        if request.is_json:
            return {
                'message': 'Registration successful!',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'role': user.role
                }
            }, 201

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    # For GET request
    all_school_classes = SchoolClass.query.order_by(SchoolClass.name).all()
    return render_template('register.html', school_classes=all_school_classes)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            if user.role == 'teacher':
                return redirect(url_for('teacher_interface'))
            else:
                return redirect(url_for('student_interface'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/teacher')
@login_required
def teacher_interface():
    if current_user.role != 'teacher':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    # Get selected class from request args, if any
    selected_class_name = request.args.get('class_name')

    # Get all defined bulletin structures/classes for the dropdown
    all_school_classes_with_structure = SchoolClass.query.join(BulletinStructure).order_by(SchoolClass.name).all()
    class_names_for_dropdown = [sc.name for sc in all_school_classes_with_structure]

    students_query = User.query.filter_by(role='student')
    target_class_id = None
    if selected_class_name:
        school_class_obj = SchoolClass.query.filter_by(name=selected_class_name).first()
        if school_class_obj:
            target_class_id = school_class_obj.id
            students_query = students_query.filter_by(current_class_id=target_class_id)
        else:
            # If a class name is selected but doesn't exist in SchoolClass, show no students
            students_query = students_query.filter(User.id == -1) # No students will match
    
    students = students_query.order_by(User.username).all()
    
    # Grades could also be filtered by selected class if desired, but not essential for this step
    grades = Grade.query.order_by(Grade.date.desc()).all()
    
    subjects_for_selected_class = []
    if selected_class_name:
        structure = BulletinStructure.query.join(SchoolClass).filter(SchoolClass.name == selected_class_name).first()
        if structure:
            subjects_part1 = [s.strip() for s in structure.subjects_part1.split(',') if s.strip()]
            subjects_part2 = [s.strip() for s in structure.subjects_part2.split(',') if s.strip()]
            subjects_for_selected_class = sorted(list(set(subjects_part1 + subjects_part2))) # Unique, sorted

    return render_template(
        'teacher.html', 
        students=students, 
        grades=grades, 
        defined_classes=class_names_for_dropdown,
        selected_class_name=selected_class_name,
        subjects_for_selected_class=subjects_for_selected_class,
        standard_periods=STANDARD_PERIODS
    )

@app.route('/add_grade', methods=['POST'])
@login_required
def add_grade():
    if current_user.role != 'teacher':
        return {'error': 'Access denied'}, 403
    
    student_id = request.form.get('student_id')
    subject = request.form.get('subject')
    if subject == 'Other':
        other_subject_name = request.form.get('other_subject_name', '').strip()
        if other_subject_name:
            subject = other_subject_name
        else:
            # Handle case where 'Other' is selected but no name provided, if necessary
            # For now, it will likely fail the 'subject' validation if it remains 'Other'
            # or you might want to flash an error specifically for this.
            flash('Please specify the subject name when selecting \"Other\".', 'warning')
            # We also need to pass back the class filter to the redirect
            selected_class_for_grade = request.form.get('selected_class_for_grade')
            redirect_url = url_for('teacher_interface')
            if selected_class_for_grade:
                redirect_url = url_for('teacher_interface', class_name=selected_class_for_grade)
            return redirect(redirect_url)

    try:
        moy_cl_str = request.form.get('moy_cl')
        n_compo_str = request.form.get('n_compo')
        coef_str = request.form.get('coef')
        
        moy_cl = float(moy_cl_str) if moy_cl_str else 0.0
        n_compo = float(n_compo_str) if n_compo_str else 0.0
        coef = int(coef_str) if coef_str else 0
    except ValueError:
        flash('Invalid number format for grades or coefficient.', 'danger')
        selected_class_for_grade = request.form.get('selected_class_for_grade')
        redirect_url = url_for('teacher_interface')
        if selected_class_for_grade:
            redirect_url = url_for('teacher_interface', class_name=selected_class_for_grade)
        return redirect(redirect_url)
        
    # Determine the period
    period = request.form.get('period') # New simpler way
    
    # Ensure all fields are present, including the new 'period' field
    if not all([student_id, subject, moy_cl_str, n_compo_str, coef_str, period]) or (subject == 'Other' and not request.form.get('other_subject_name','').strip()):
        flash('All fields (Student, Subject, Period, Moy.CL, N.Compo, Coef) are required. If "Other" subject, ensure it is specified.', 'danger')
        selected_class_for_grade = request.form.get('selected_class_for_grade')
        redirect_url = url_for('teacher_interface')
        if selected_class_for_grade:
            redirect_url = url_for('teacher_interface', class_name=selected_class_for_grade)
        return redirect(redirect_url)
    
    # Add validation for grade ranges if necessary (e.g., 0-20)
    if not (0 <= moy_cl <= 20 and 0 <= n_compo <= 20):
        flash('Grades must be between 0 and 20.', 'danger')
        return redirect(url_for('teacher_interface'))
    if coef <= 0:
        flash('Coefficient must be a positive number.', 'danger')
        return redirect(url_for('teacher_interface'))
    
    subject_appreciation = get_subject_appreciation(moy_cl, n_compo)

    grade = Grade(
        student_id=student_id,
        subject=subject,
        moy_cl=moy_cl,
        n_compo=n_compo,
        coef=coef,
        appreciation=subject_appreciation, # Use auto-generated appreciation
        period=period, # Add period to Grade object
        date=datetime.utcnow()
    )
    db.session.add(grade)
    db.session.commit()
    flash('Grade added successfully', 'success')
    return redirect(url_for('teacher_interface'))

@app.route('/update_grade/<int:grade_id>', methods=['PUT'])
@login_required
def update_grade(grade_id):
    if current_user.role != 'teacher':
        return {'error': 'Access denied'}, 403
    
    grade = db.session.get(Grade, grade_id) # Use db.session.get()
    if not grade:
        return {'error': 'Grade not found'}, 404
        
    data = request.get_json()
    if not data:
        return {'error': 'Invalid data'}, 400

    try:
        moy_cl = float(data.get('moy_cl', grade.moy_cl))
        n_compo = float(data.get('n_compo', grade.n_compo))
        coef = int(data.get('coef', grade.coef))
    except (ValueError, TypeError):
        return {'error': 'Invalid number format for grades or coefficient.'}, 400

    period = data.get('period', grade.period) # Get period for update

    # Add validation for grade ranges if necessary (e.g., 0-20)
    if not (0 <= moy_cl <= 20 and 0 <= n_compo <= 20):
         return {'error': 'Grades must be between 0 and 20.'}, 400
    if coef <= 0:
         return {'error': 'Coefficient must be a positive number.'}, 400

    grade.moy_cl = moy_cl
    grade.n_compo = n_compo
    grade.coef = coef
    grade.appreciation = get_subject_appreciation(moy_cl, n_compo) # Update with auto-generated appreciation
    grade.period = period # Update period
    # grade.date can be updated if needed, e.g., grade.date = datetime.utcnow()
    
    db.session.commit()
    return {'message': 'Grade updated successfully'}, 200

@app.route('/delete_grade/<int:grade_id>', methods=['DELETE'])
@login_required
def delete_grade(grade_id):
    if current_user.role != 'teacher':
        return {'error': 'Access denied'}, 403
    
    grade = Grade.query.get_or_404(grade_id)
    db.session.delete(grade)
    db.session.commit()
    return {'message': 'Grade deleted successfully'}, 200

@app.route('/student')
@login_required
def student_interface():
    if current_user.role != 'student':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    grades = Grade.query.filter_by(student_id=current_user.id).all()
    return render_template('student.html', grades=grades)

@app.route('/manage_bulletin_structures')
@login_required
def manage_bulletin_structures():
    if current_user.role != 'teacher':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    structures = BulletinStructure.query.join(SchoolClass).order_by(SchoolClass.name).all()
    all_school_classes = SchoolClass.query.order_by(SchoolClass.name).all()
    return render_template('manage_bulletin_structures.html', structures=structures, school_classes=all_school_classes)

@app.route('/add_bulletin_structure', methods=['POST'])
@login_required
def add_bulletin_structure():
    if current_user.role != 'teacher':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    school_class_id = request.form.get('school_class_id')
    subjects_part1 = request.form.get('subjects_part1')
    subjects_part2 = request.form.get('subjects_part2')

    if not all([school_class_id, subjects_part1, subjects_part2]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('manage_bulletin_structures'))

    existing_structure = BulletinStructure.query.filter_by(school_class_id=school_class_id).first()
    if existing_structure:
        school_class = db.session.get(SchoolClass, school_class_id)
        flash(f'A bulletin structure for class "{school_class.name if school_class else school_class_id}" already exists.', 'warning')
        return redirect(url_for('manage_bulletin_structures'))

    new_structure = BulletinStructure(
        school_class_id=school_class_id,
        subjects_part1=subjects_part1,
        subjects_part2=subjects_part2
    )
    db.session.add(new_structure)
    db.session.commit()
    flash('Bulletin structure added successfully!', 'success')
    return redirect(url_for('manage_bulletin_structures'))

@app.route('/delete_bulletin_structure/<int:structure_id>', methods=['POST'])
@login_required
def delete_bulletin_structure(structure_id):
    if current_user.role != 'teacher':
        flash('Access denied', 'danger')
        # For AJAX requests, might return JSON error, for form posts, redirect
        if request.is_json:
            return {'error': 'Access denied'}, 403
        return redirect(url_for('index'))

    structure = db.session.get(BulletinStructure, structure_id)
    if structure:
        db.session.delete(structure)
        db.session.commit()
        flash('Bulletin structure deleted successfully!', 'success')
        if request.is_json:
            return {'message': 'Bulletin structure deleted successfully!'}, 200
    else:
        flash('Bulletin structure not found.', 'danger')
        if request.is_json:
            return {'error': 'Bulletin structure not found'}, 404
            
    return redirect(url_for('manage_bulletin_structures'))

@app.route('/edit_bulletin_structure/<int:structure_id>', methods=['POST'])
@login_required
def edit_bulletin_structure(structure_id):
    if current_user.role != 'teacher':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    structure_to_edit = db.session.get(BulletinStructure, structure_id)
    if not structure_to_edit:
        flash('Bulletin structure not found.', 'danger')
        return redirect(url_for('manage_bulletin_structures'))

    new_school_class_id = request.form.get('school_class_id') # Changed from class_name
    subjects_part1 = request.form.get('subjects_part1')
    subjects_part2 = request.form.get('subjects_part2')

    if not all([new_school_class_id, subjects_part1, subjects_part2]):
        flash('All fields are required for update.', 'danger')
        return redirect(url_for('manage_bulletin_structures'))

    # Check if another structure with the new school_class_id already exists
    conflicting_structure = BulletinStructure.query.filter(
        BulletinStructure.school_class_id == new_school_class_id,
        BulletinStructure.id != structure_id 
    ).first()

    if conflicting_structure:
        conflicting_class = db.session.get(SchoolClass, new_school_class_id)
        flash(f'Another bulletin structure for the class "{conflicting_class.name if conflicting_class else new_school_class_id}" already exists.', 'warning')
        return redirect(url_for('manage_bulletin_structures'))

    structure_to_edit.school_class_id = new_school_class_id
    structure_to_edit.subjects_part1 = subjects_part1
    structure_to_edit.subjects_part2 = subjects_part2
    
    db.session.commit()
    flash('Bulletin structure updated successfully!', 'success')
    return redirect(url_for('manage_bulletin_structures'))

@app.route('/generate_report', methods=['GET', 'POST'])
@login_required
def generate_report():
    if current_user.role != 'student':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    # --- Data Retrieval and Structuring for PDF ---
    
    # Determine the period for the report
    # Option 1: Get it from request arguments (if student can select)
    requested_period = request.args.get('period') 
    
    # Option 2: Determine a default period (e.g., latest period with grades for this student)
    if not requested_period:
        latest_grade_for_period = Grade.query.filter_by(student_id=current_user.id).order_by(Grade.date.desc()).first()
        if latest_grade_for_period:
            requested_period = latest_grade_for_period.period
        else:
            # Fallback if no grades/period found, or set a default like "Overall" or current school period
            requested_period = "Période Actuelle" # Placeholder - Define how to get current school period

    student_data = {
        'school_name': 'Lycée Michel ALLAIRE', 
        'school_bp': '580',
        'school_tel': '21-32-11-20',
        'school_email': 'michelallaire2007@yahoo.fr',
        'school_tel_alt': '79 07 03 60',
        'academic_period': requested_period, # Use the determined period
        'student_name': current_user.username.upper(), 
        'class_name': current_user.current_class.name if current_user.current_class else 'Classe Inconnue',
        'school_stamp_path': None
    }

    # 2. Grades Data - Filter by the determined period
    all_student_grades_for_period = Grade.query.filter_by(student_id=current_user.id, period=requested_period).order_by(Grade.subject).all()

    # Convert Grade objects to list of dictionaries expected by pdf_generator
    formatted_grades = []
    for g in all_student_grades_for_period:
        formatted_grades.append({
            'subject': g.subject,
            'moy_cl': g.moy_cl,
            'n_compo': g.n_compo,
            'coef': g.coef,
            'appreciation': g.appreciation if g.appreciation else '' # Ensure not None
        })

    # TODO: Implement logic to split formatted_grades into grades_part1 and grades_part2
    # This logic depends on how you want to group subjects in the PDF.
    # Example: by a predefined list of subjects for part 1, or first N subjects.
    # For now, a simple split (e.g., first 6 subjects for part1, rest for part2)
    
    # Define subjects for Part 1 (as per the example image)
    default_subjects_part1_order = ['MATHS', 'PHYSIQUE', 'CHIMIE', 'GÉOLOGIE/BIO', 'PHILOSOPHIE', 'ANGLAIS']
    default_subjects_part2_order = ['E.C.M', 'EPS', 'INFORMAT.', 'DESSIN TECH.', 'CONDUITE'] # And any others

    subjects_part1_order = default_subjects_part1_order
    subjects_part2_order = default_subjects_part2_order

    if current_user.current_class_id: # Check if current_class_id exists
        # Fetch bulletin structure based on school_class_id
        bulletin_struct = BulletinStructure.query.filter_by(school_class_id=current_user.current_class_id).first()
        if bulletin_struct and bulletin_struct.school_class: # Ensure school_class is loaded
            subjects_part1_order = [s.strip() for s in bulletin_struct.subjects_part1.split(',') if s.strip()]
            subjects_part2_order = [s.strip() for s in bulletin_struct.subjects_part2.split(',') if s.strip()]
            app.logger.info(f"Using bulletin structure for class: {bulletin_struct.school_class.name}")
        elif current_user.current_class: # Fallback if structure not found but class exists
             app.logger.info(f"No specific bulletin structure for class: {current_user.current_class.name}. Using default.")
        else:
            app.logger.info("User has no current_class or structure not found. Using default bulletin structure.")
    else:
        app.logger.info("User has no current_class_id. Using default bulletin structure.")


    grades_part1 = []
    grades_part2 = []
    
    temp_formatted_grades = list(formatted_grades) # Create a copy to remove items from

    for subj_name in subjects_part1_order:
        found = False
        for i, grade_item in enumerate(temp_formatted_grades):
            if grade_item['subject'] == subj_name:
                grades_part1.append(temp_formatted_grades.pop(i))
                found = True
                break
        if not found: # Add placeholder if subject not found for this student
            grades_part1.append({'subject': subj_name, 'moy_cl': 0, 'n_compo': 0, 'coef': 0, 'appreciation': 'N/A'})
            
    # Any remaining grades or predefined Part 2 subjects
    for subj_name in subjects_part2_order:
        found = False
        for i, grade_item in enumerate(temp_formatted_grades):
            if grade_item['subject'] == subj_name:
                grades_part2.append(temp_formatted_grades.pop(i))
                found = True
                break
        if not found:
             grades_part2.append({'subject': subj_name, 'moy_cl': 0, 'n_compo': 0, 'coef': 0, 'appreciation': 'N/A'})
    
    # Add any other grades not in predefined lists to part 2 (or handle as needed)
    grades_part2.extend(temp_formatted_grades)


    if not grades_part1: # Ensure it's not empty for the PDF generator
        grades_part1 = [{'subject': 'N/A', 'moy_cl': 0, 'n_compo': 0, 'coef': 0, 'appreciation': '-'}]
    # grades_part2 can be empty if no subjects fall into it. The PDF generator should handle it.

    # 3. Summary Data (Requires significant calculation logic)
    # Helper function to calculate weighted average for a list of grades
    def calculate_moy_ponderee(grades_list):
        total_moy_coef = 0
        total_coef = 0
        for item in grades_list:
            m = item.get('moy_cl', 0)
            n = item.get('n_compo', 0)
            k = item.get('coef', 0)
            mg = (m + 2 * n) / 3.0 if k > 0 else 0.0
            total_moy_coef += mg * k
            total_coef += k
        return (total_moy_coef / total_coef) if total_coef > 0 else 0.0

    # Helper function to determine appreciation based on average
    def get_appreciation_for_average(avg):
        if avg >= 16: return "Très Bien"
        if avg >= 14: return "Bien"
        if avg >= 12: return "Assez Bien"
        if avg >= 10: return "Passable"
        if avg >= 8: return "Insuffisant"
        return "Faible"

    moy_p1_calc = calculate_moy_ponderee(grades_part1)
    moy_p2_calc = calculate_moy_ponderee(grades_part2)
    
    all_calculated_grades = grades_part1 + grades_part2 # Use the structured lists
    moy_annuelle_calc = calculate_moy_ponderee(all_calculated_grades)

    # Calculate rank and top student average for the current_user, class, and period
    current_rank = "N/A"
    rank_1_moy_val = "N/A"
    
    if current_user.current_class and requested_period:
        students_in_class = User.query.filter_by(current_class_id=current_user.current_class_id, role='student').all()
        student_averages = []
        for student_in_class in students_in_class:
            grades_for_student_in_class = Grade.query.filter_by(student_id=student_in_class.id, period=requested_period).all()
            if grades_for_student_in_class: # Only consider students with grades in this period
                # Convert to the dictionary format for calculate_moy_ponderee
                formatted_grades_for_calc = [
                    {'moy_cl': g.moy_cl, 'n_compo': g.n_compo, 'coef': g.coef}
                    for g in grades_for_student_in_class
                ]
                avg = calculate_moy_ponderee(formatted_grades_for_calc)
                student_averages.append({'student_id': student_in_class.id, 'average': avg})
        
        if student_averages:
            # Sort students by average descending
            student_averages.sort(key=lambda x: x['average'], reverse=True)
            
            # Find rank of current_user
            for i, data in enumerate(student_averages):
                if data['student_id'] == current_user.id:
                    current_rank = f"{i + 1}er/ère"
                    break # Found current student's rank
            
            # Get average of the top student (rank 1)
            if student_averages: # Check again in case current student had no grades and list became empty
                 rank_1_moy_val = f"{student_averages[0]['average']:.2f}/20".replace('.',',')

    summary_data = {
        'appr_p1': get_appreciation_for_average(moy_p1_calc), 
        'appr_p2': get_appreciation_for_average(moy_p2_calc), 
        'appr_globale': get_appreciation_for_average(moy_annuelle_calc), 
        'rank': current_rank,
        'date_generated': datetime.now().strftime('%d/%m/%Y'),
        'rank_1_moy': rank_1_moy_val, 
        'moy_p1_overall': f"{moy_p1_calc:.2f} /20".replace('.',','),
        'moy_p2_overall': f"{moy_p2_calc:.2f} /20".replace('.',','),
        'moy_annuelle': f"{moy_annuelle_calc:.2f} /20".replace('.',',')
    }
    # --- End of Data Retrieval and Structuring ---
    
    # Create a temporary file for the PDF
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
        pdf_path = temp_file.name
        # CALL THE NEW FUNCTION with the new data structure
        generate_bulletin_pdf(pdf_path, student_data, grades_part1, grades_part2, summary_data)
        
        try:
            response = send_file(
                pdf_path,
                as_attachment=True,
                download_name=f'report_card_{current_user.username}.pdf'
            )
            # Delete the file after it's been sent
            @response.call_on_close
            def cleanup():
                try:
                    os.remove(pdf_path)
                except Exception as e:
                    app.logger.error(f"Error deleting temporary PDF file: {e}")
            return response
        except Exception as e:
            # Clean up in case of error
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            app.logger.error(f"Error generating or sending report card for {current_user.username}: {e}", exc_info=True)
            flash(f'Error generating report card. Please contact support. Error: {e}', 'danger')
            return redirect(url_for('student_interface'))

# School Class Management Routes
@app.route('/manage_school_classes')
@login_required
def manage_school_classes():
    if current_user.role != 'teacher': # Or a new 'admin' role later
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    classes = SchoolClass.query.order_by(SchoolClass.name).all()
    return render_template('manage_school_classes.html', classes=classes)

@app.route('/add_school_class', methods=['POST'])
@login_required
def add_school_class():
    if current_user.role != 'teacher':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    class_name = request.form.get('class_name', '').strip()
    if not class_name:
        flash('Class name is required.', 'danger')
        return redirect(url_for('manage_school_classes'))
    
    existing_class = SchoolClass.query.filter_by(name=class_name).first()
    if existing_class:
        flash(f'A class named "{class_name}" already exists.', 'warning')
    else:
        new_class = SchoolClass(name=class_name)
        db.session.add(new_class)
        db.session.commit()
        flash(f'Class "{class_name}" added successfully!', 'success')
    return redirect(url_for('manage_school_classes'))

def create_default_school_classes():
    default_classes = [
        "10e", "11e Sc", "11e L", "11e SES", "11e SS", 
        "12e SE", "12e EXP", "12e SEco", "12e SS"
        # Ajoutez d'autres classes types ici si nécessaire
    ]
    for class_name in default_classes:
        if not SchoolClass.query.filter_by(name=class_name).first():
            new_class = SchoolClass(name=class_name)
            db.session.add(new_class)
    db.session.commit()

# Placeholder route, to be implemented later
@app.route('/assign_students_to_class/<int:class_id>')
@login_required
def assign_students_to_class_interface(class_id):
    # TODO: Implement student assignment to class interface
    flash(f'Student assignment interface for class ID {class_id} is not yet implemented.', 'info')
    return redirect(url_for('manage_school_classes'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Create default teacher account if it doesn't exist
        if not User.query.filter_by(username='teacher').first():
            teacher = User(
                username='teacher',
                password=generate_password_hash('password123'),
                role='teacher'
            )
            db.session.add(teacher)
        
        # Add some default bulletin structures if they don't exist
        default_structures_data = [
            {
                'class_name_to_find': 'Terminale C', 
                'subjects_part1': 'MATHS,PHYSIQUE,CHIMIE,PHILOSOPHIE,ANGLAIS,SVT',
                'subjects_part2': 'E.C.M,EPS,INFORMATIQUE,CONDUITE'
            },
            {
                'class_name_to_find': 'Seconde A',
                'subjects_part1': 'MATHS,FRANCAIS,ANGLAIS,HIST-GEO,PHYSIQUE-CHIMIE,SVT',
                'subjects_part2': 'E.C.M,EPS,LV2,ART PLASTIQUE'
            }
        ]
        for struct_data in default_structures_data:
            school_class_obj = SchoolClass.query.filter_by(name=struct_data['class_name_to_find']).first()
            if school_class_obj:
                if not BulletinStructure.query.filter_by(school_class_id=school_class_obj.id).first():
                    new_struct = BulletinStructure(
                        school_class_id=school_class_obj.id,
                        subjects_part1=struct_data['subjects_part1'],
                        subjects_part2=struct_data['subjects_part2']
                    )
                    db.session.add(new_struct)
            else:
                app.logger.warning(f"Default bulletin structure: Class '{struct_data['class_name_to_find']}' not found in SchoolClass table. Structure not created.")
        
        create_default_school_classes() # Call the function to create default classes
        
        db.session.commit() # Commit all pending changes (teacher, structures, classes)
    
    app.run(debug=True)
