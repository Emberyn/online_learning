from flask import Flask
from flask_login import LoginManager
import os
from db import get_db_connection

app = Flask(__name__)
app.secret_key = 'your_secret_key_here_change_it_in_production'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login' # Updated to blueprint endpoint

@login_manager.user_loader
def load_user(user_id):
    from routes.auth import User
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user_data = cursor.fetchone()
            if user_data:
                return User(user_data['id'], user_data['username'], user_data['role'], user_data['name'])
    except Exception as e:
        print(f"Error loading user: {e}")
    finally:
        conn.close()
    return None

# Register Blueprints
from routes.auth import auth_bp
from routes.main import main_bp
from routes.admin import admin_bp
from routes.teacher import teacher_bp
from routes.student import student_bp

app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(teacher_bp)
app.register_blueprint(student_bp)

if __name__ == '__main__':
    app.run(debug=True)


