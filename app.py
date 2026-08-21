import os
import io
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
app.secret_key = 'krbna_secret_key_2026'

# ضبط مسار العمل على PythonAnywhere
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# الاتصال بـ Firebase
cred_path = os.path.join(BASE_DIR, 'serviceAccountKey.json')
if not firebase_admin._apps:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ⚠️ اكتب إيميلك الشخصي هنا ليصبح هو الحساب الوحيد المصرح له بفتح التقارير
ADMIN_EMAIL = "mohamedbelal.s2@gmail.com"


@app.route('/')
def index():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', user_email=session.get('user_email'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        if email:
            session['user_email'] = email
            return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# 🔒 صفحة التقارير - مخصصة للأدمن فقط
@app.route('/reports')
def create_report():
    # لو المستخدم مش الأدمن يرجعه للرئيسية فوراً
    if session.get('user_email') != ADMIN_EMAIL:
        flash("عفواً، هذه الصفحة مخصصة للأدمن فقط!", "danger")
        return redirect(url_for('index'))
    
    return render_template('create_report.html')


# 📥 تحميل ملف التقرير Excel/CSV - للأدمن فقط
@app.route('/download-report')
def download_report():
    if session.get('user_email') != ADMIN_EMAIL:
        return "غير مسموح لك بتحميل التقرير", 403

    docs = db.collection('items').stream()
    content = "ID,Title,Code,Created By\n"
    for doc in docs:
        d = doc.to_dict()
        content += f"{doc.id},{d.get('title','')},{d.get('code_number','')},{d.get('created_by','')}\n"

    mem = io.BytesIO()
    mem.write(content.encode('utf-8-sig'))
    mem.seek(0)

    return send_file(mem, mimetype='text/csv', as_attachment=True, download_name='krbna_report.csv')


if __name__ == '__main__':
    app.run(debug=True)
