import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import qrcode
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# 1. تهيئة الاتصال بـ Firebase باستخدام الملف السرّي
cred = credentials.Certificate('serviceAccountKey.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# 2. إعداد المجلدات المحلية لحفظ ملفات الـ PDF وصور الـ QR
UPLOADS_FOLDER = os.path.join('static', 'uploads')
QR_FOLDER = os.path.join('static', 'qrcodes')
os.makedirs(UPLOADS_FOLDER, exist_ok=True)
os.makedirs(QR_FOLDER, exist_ok=True)

app.config['UPLOADS_FOLDER'] = UPLOADS_FOLDER
app.config['QR_FOLDER'] = QR_FOLDER


# 3. صفحة الأدمن (إدخال التقرير وتوليد الـ QR Code)
@app.route('/', methods=['GET', 'POST'])
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    qr_url = None
    report_link = None
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        prep_date = request.form['prep_date']
        preparer = request.form['preparer']
        pdf_file = request.files.get('pdf_file')

        # توليد كود فريد للتقرير مكون من 8 أرقام/حروف
        report_id = str(uuid.uuid4())[:8]

        # حفظ ملف الـ PDF إن وجد
        pdf_filename = None
        if pdf_file and pdf_file.filename != '':
            pdf_filename = f"{report_id}_{pdf_file.filename}"
            pdf_file.save(os.path.join(app.config['UPLOADS_FOLDER'], pdf_filename))

        # ** حفظ البيانات في Firebase Firestore **
        doc_ref = db.collection('reports').document(report_id)
        doc_ref.set({
            'title': title,
            'description': description,
            'prep_date': prep_date,
            'preparer': preparer,
            'pdf_filename': pdf_filename
        })

        # إنشاء رابط التقرير المباشر
        report_link = request.host_url.rstrip('/') + url_for('view_report', report_id=report_id)

        # توليد صورة الـ QR Code
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(report_link)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        qr_filename = f"{report_id}.png"
        qr_path = os.path.join(app.config['QR_FOLDER'], qr_filename)
        qr_img.save(qr_path)

        # مسار صورة الـ QR للعرض في الصفحة
        qr_url = url_for('static', filename=f'qrcodes/{qr_filename}')

    return render_template('admin.html', qr_url=qr_url, report_link=report_link)


# 4. صفحة عرض التقرير للعميل (عند مسح الـ QR Code)
@app.route('/report/<report_id>')
def view_report(report_id):
    # ** جلب بيانات التقرير من Firebase **
    doc_ref = db.collection('reports').document(report_id)
    doc = doc_ref.get()

    if not doc.exists:
        return "التقرير غير موجود أو تم حذفه من النظام", 404

    report_data = doc.to_dict()
    report_data['id'] = doc.id

    return render_template('report.html', report=report_data)


# 5. رابط تحميل ملف الـ PDF المرفق
@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOADS_FOLDER'], filename, as_attachment=True)


if __name__ == '__main__':
    # تشغيل خادم التطوير المحلي
    app.run(debug=True, host='0.0.0.0', port=5000)