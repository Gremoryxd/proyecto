from flask import Flask, render_template, request, url_for, redirect, session
import os
from PIL import Image
import qrcode
import uuid
from datetime import datetime
from fpdf import FPDF
import requests
import json
from barcode import Code128
from barcode.writer import ImageWriter
import hashlib
import time

# LIBRERÍAS PARA GOOGLE DRIVE
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

from google import genai
from google.genai import types

app = Flask(__name__)
app.secret_key = 'Ferna_Cloud_2026'

# ======================================================
# CONFIGURACIÓN
# ======================================================
MI_API_KEY_GEMINI = "TU_API_KEY"
MI_WEBHOOK_GOOGLE_SHEETS = "TU_URL_DE_APPS_SCRIPT"

# CONFIGURACIÓN DRIVE
SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'credenciales-drive.json' # Asegúrate que el archivo se llame así
ID_CARPETA_DRIVE = 'TU_ID_DE_CARPETA_DRIVE'
# ======================================================

CARPETAS = ['static/uploads', 'static/qrs', 'static/pdfs', 'static/barcodes']
for c in CARPETAS: os.makedirs(c, exist_ok=True)

# --- FUNCIÓN PARA SUBIR A DRIVE ---
def subir_a_drive(ruta_local, nombre_archivo, mime_type):
    try:
        creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('drive', 'v3', credentials=creds)
        
        metadatos = {'name': nombre_archivo, 'parents': [ID_CARPETA_DRIVE]}
        media = MediaFileUpload(ruta_local, mimetype=mime_type)
        archivo_drive = service.files().create(body=metadatos, media_body=media, fields='id, webViewLink').execute()
        
        return archivo_drive.get('webViewLink')
    except Exception as e:
        print(f"Error subiendo a Drive: {e}")
        return None

# (Mantén aquí tus funciones de analizar_ia y crear_comprobante_pdf del código anterior)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        archivo = request.files['foto']
        estado_pago = request.form.get('estado')
        
        if archivo:
            nombre_unico = str(uuid.uuid4())
            ruta_foto = f"static/uploads/{nombre_unico}.png"
            archivo.save(ruta_foto)
            
            # 1. Analizar con IA
            res_ia = analizar_ia(ruta_foto)
            serial = f"FAC-{datetime.now().strftime('%y%m')}-{nombre_unico[:4].upper()}"
            
            # 2. Generar QR y Barcode locales temporalmente
            ruta_qr = f"static/qrs/{serial}.png"
            qrcode.make(serial).save(ruta_qr)
            
            # 3. Generar PDF
            ruta_pdf = crear_comprobante_pdf(res_ia, serial, estado_pago)
            
            # 4. SUBIR A DRIVE (La joya de la corona)
            link_foto_drive = subir_a_drive(ruta_foto, f"FOTO_{serial}.png", 'image/png')
            link_pdf_drive = subir_a_drive(ruta_pdf, f"DOC_{serial}.pdf", 'application/pdf')

            # 5. Enviar a Google Sheets (ahora con los links de Drive)
            try:
                requests.post(MI_WEBHOOK_GOOGLE_SHEETS, json={
                    "accion": "INSERT", 
                    "lugar": res_ia['lugar'], 
                    "monto": res_ia['monto'], 
                    "serial": serial, 
                    "estado": estado_pago,
                    "link_pdf": link_pdf_drive # Agrega esta columna en tu Apps Script
                })
            except: pass

            # 6. LIMPIEZA TOTAL (Para que el servidor no se llene)
            # Borramos los archivos locales porque ya están en Drive
            for f in [ruta_foto, ruta_qr, ruta_pdf]:
                if os.path.exists(f): os.remove(f)

            session['mensaje'] = "✅ ¡Factura procesada y guardada en tu Google Drive de 5TB!"
            return redirect(url_for('index'))

    return render_template('index.html', mensaje=session.pop('mensaje', None))

if __name__ == '__main__':
    app.run(debug=True)