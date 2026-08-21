import os
import sys
import io
import qrcode
from PIL import Image
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file

import firebase_admin
from firebase_admin import credentials, firestore

# ---------------------------------------------------------
# 1. إعداد التطبيق والمسارات
# ---------------------------------------------------------
app = Flask(__name__)
app.secret_key = 'krbna_secure_secret_key_2026'  # مفتاح تشفير الـ Session

# ضبط مجلد العمل الرئيسي لضمان العثور على الملفات على PythonAnywhere
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# ---------------------------------------------------------
# 2. تهيئة Firebase Admin SDK
# ---------------------------------------------------------
cred_path = os.path.join(BASE_DIR, 'serviceAccountKey.json')

if not firebase_admin._apps:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# البريد الإلكتروني للمسؤول (الأدمن) المسموح له بفتح التقارير
ADMIN_EMAIL = "mohamedbelal.s2@gmail.com"  # 👈 استبدله ببريدك الإلكتروني الحقيقي

# ---------------------------------------------------------
# 3. المسارات (Routes)
# ---------------------------------------------------------

@app.route('/')
def index():
    """الصفحة الرئيسية - عرض البيانات من Firestore"""
    if 'user_email' not in session:
        return redirect(url_for('login'))
    
    try:
        items_ref = db.collection('items')
        docs = items_ref.stream()
        data_list = [doc.to_dict() | {'id': doc.id} for doc in docs]
    except Exception as e:
        data_list = []
        flash(f"حدث خطأ أثناء جلب البيانات: {str(e)}", "danger")

    return render_template('index.html', items=data_list, user_email=session.get('user_email'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """صفحة تسجيل الدخول"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # تحقق مبسط من الدخول (يمكنك ربطه مع Firebase Auth حسب رغبتك)
        if email and password:
            session['user_email'] = email
            flash("تم تسجيل الدخول بنجاح!", "success")
            return redirect(url_for('index'))
        else:
            flash("بيانات الدخول غير صحيحة", "danger")

    return render_template('login.html')


@app.route('/logout')
def logout():
    """تسجيل الخروج"""
    session.clear()
    flash("تم تسجيل الخروج بنجاح", "info")
    return redirect(url_for('login'))


@app.route('/add-data', methods=['GET', 'POST'])
def add_data():
    """إضافة بيانات جديدة إلى Firebase"""
    if 'user_email' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        code_number = request.form.get('code_number')

        if not title or not code_number:
            flash("يرجى ملء جميع الحقول المطلوبة!", "warning")
            return redirect(url_for('add_data'))

        try:
            db.collection('items').add({
                'title': title,
                'description': description,
                'code_number': code_number,
                'created_by': session['user_email']
            })
            flash("تمت إضافة البيانات بنجاح!", "success")
            return redirect(url_for('index'))
        except Exception as e:
            flash(f"فشل في حفظ البيانات: {str(e)}", "danger")

    return render_template('add_data.html')


@app.route('/generate-qr/<text>')
def generate_qr(text):
    """توليد كود QR ديناميكياً وإرساله دون الحاجة لحفظه كملف في السيرفر"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    return send_file(img_io, mimetype='image/png')


@app.route('/reports')
def create_report():
    """صفحة التقارير - مخصصة للأدمن فقط"""
    if 'user_email' not in session:
        flash("يرجى تسجيل الدخول أولاً", "warning")
        return redirect(url_for('login'))

    # حماية الصفحة: التأكد من أن المستخدم الحالي هو الأدمن
    if session.get('user_email') != ADMIN_EMAIL:
        flash("عفواً، هذه الصفحة مخصصة للمسؤول فقط.", "danger")
        return redirect(url_for('index'))

    try:
        total_items = len(list(db.collection('items').stream()))
    except:
        total_items = 0

    return render_template('create_report.html', total_items=total_items)


@app.route('/download-report')
def download_report():
    """توليد وتنزيل ملف التقرير Excel/CSV للأدمن فقط"""
    if session.get('user_email') != ADMIN_EMAIL:
        flash("غير مسموح لك بتحميل التقارير.", "danger")
        return redirect(url_for('index'))

    try:
        docs = db.collection('items').stream()
        report_content = "ID,Title,Code,Created By\n"
        for doc in docs:
            d = doc.to_dict()
            report_content += f"{doc.id},{d.get('title','')},{d.get('code_number','')},{d.get('created_by','')}\n"

        # حفظ التقرير في الذاكرة بترميز utf-8-sig لدعم اللغة العربية في Excel
        mem = io.BytesIO()
        mem.write(report_content.encode('utf-8-sig'))
        mem.seek(0)

        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name='krbna_report.csv'
        )
    except Exception as e:
        flash(f"حدث خطأ أثناء تنزيل التقرير: {str(e)}", "danger")
        return redirect(url_for('create_report'))


# ---------------------------------------------------------
# 4. معالجة الأخطاء (Error Handlers)
# ---------------------------------------------------------

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return "<h1>Internal Server Error</h1><p>حدث خطأ داخلي، يرجى التحقق من Error Log.</p>", 500


if __name__ == '__main__':
    app.run(debug=True)
