from flask import Flask, render_template, request, g, session, redirect, url_for
import sqlite3
import re
import os
import sys
import subprocess
import traceback  # <--- NUEVO: Para mostrar errores en pantalla
from functools import wraps
from thefuzz import fuzz 

app = Flask(__name__)
DATABASE = "catalogo_productos.db"

# SEGURIDAD
app.secret_key = "super_secreto_clave_maestra"
PASSWORD_ADMIN = "JGDigital88" 

CONFIGURACION = {
    "margen": 30.0,
    "envio": 0.0,
    "alias": {} 
}

# --- FUNCIÓN VITAL: CREAR DB SI NO EXISTE ---
def init_db_if_needed():
    if not os.path.exists(DATABASE):
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS productos (
            Categoria TEXT, Producto TEXT, Precio TEXT, Imagen_URL TEXT, 
            Archivo_Local TEXT, Pagina TEXT, Fecha_Actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP, 
            UNIQUE(Producto, Pagina))''')
        conn.commit()
        conn.close()

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None: db.close()

# --- DECORADOR LOGIN ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# --- UTILIDADES ---
def procesar_precio(precio_texto):
    try:
        limpio = str(precio_texto).replace('$', '').replace('&nbsp;', '').strip()
        if ',' in limpio and '.' in limpio: limpio = limpio.replace('.', '').replace(',', '.')
        elif ',' in limpio: limpio = limpio.replace(',', '.')
        elif '.' in limpio: limpio = limpio.replace('.', '')
        costo = float(limpio)
        precio_final = (costo * (1 + (CONFIGURACION['margen']/100))) + CONFIGURACION['envio']
        texto = f"$ {precio_final:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return precio_final, texto
    except: return 0.0, "Consultar"

def son_el_mismo_producto(prod_a, prod_b):
    return False, 0 

# ==========================================
#   RUTAS (CON DIAGNÓSTICO DE ERRORES)
# ==========================================

@app.route('/')
def index():
    try:
        init_db_if_needed()
        cur = get_db().cursor()
        cur.execute("SELECT * FROM productos")
        rows = cur.fetchall()

        productos = []
        for row in rows:
            p = dict(row)
            pn, pt = procesar_precio(p['Precio'])
            p['Precio_Numerico'] = pn; p['Precio_Venta'] = pt
            productos.append(p)
        
        # Filtros
        busqueda = request.args.get('q', '').strip().upper()
        cat = request.args.get('cat', '')
        orden = request.args.get('orden', '')

        if cat: productos = [x for x in productos if x['Categoria'] == cat]
        if busqueda: productos = [x for x in productos if busqueda in x['Producto'].upper()]

        cats = sorted(list(set([x['Categoria'] for x in productos])))
        
        # Ordenamiento
        if orden == 'menor': productos.sort(key=lambda x: x['Precio_Numerico'])
        elif orden == 'mayor': productos.sort(key=lambda x: x['Precio_Numerico'], reverse=True)

        return render_template('catalogo.html', 
                             productos=productos, 
                             categorias=[{'Categoria':c} for c in cats],
                             cat_activa=cat,
                             busqueda_actual=busqueda,
                             orden_actual=orden)

    except Exception as e:
        # ¡AQUÍ ESTÁ EL SALVAVIDAS!
        # Si algo falla, te mostrará el error real en la pantalla
        return f"""
        <h1>⚠️ ERROR DEL SISTEMA</h1>
        <h3>Por favor envíame una foto de este error:</h3>
        <pre style="background:#f4f4f4; padding:15px; border:1px solid #ccc;">{traceback.format_exc()}</pre>
        """

@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        error = None
        if request.method == 'POST':
            if request.form['password'] == PASSWORD_ADMIN:
                session['logged_in'] = True
                return redirect(url_for('oportunidades'))
            else: error = "❌ Contraseña incorrecta"
        return render_template('login.html', error=error)
    except Exception as e: return f"Error en Login: {e}"

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

@app.route('/oportunidades')
@login_required 
def oportunidades():
    try:
        return render_template('oportunidades.html', oportunidades=[])
    except Exception as e: return f"Error Oportunidades: {traceback.format_exc()}"

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    try:
        init_db_if_needed()
        mensaje = ""
        
        if request.method == 'POST':
            if 'btn_actualizar' in request.form:
                # Usamos sys.executable para asegurar que use el Python correcto
                subprocess.Popen([sys.executable, "actualizar_todo.py"])
                mensaje = "🚀 Actualización iniciada en segundo plano."
            
            elif 'guardar_config' in request.form:
                CONFIGURACION['margen'] = float(request.form.get('margen', 0))
                CONFIGURACION['envio'] = float(request.form.get('envio', 0))
                mensaje = "✅ Configuración guardada."

        return render_template('admin.html', config=CONFIGURACION, mensaje=mensaje)
    except Exception as e: return f"Error Admin: {traceback.format_exc()}"

if __name__ == '__main__':
    init_db_if_needed()
    app.run(debug=True)