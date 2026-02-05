from flask import Flask, render_template, request, g, session, redirect, url_for
import sqlite3
import re
import os
import subprocess  # <--- NECESARIO PARA EJECUTAR EL SCRAPER
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

# --- FUNCIÓN VITAL: CREAR DB SI NO EXISTE (Evita error 500 en Render) ---
def init_db_if_needed():
    if not os.path.exists(DATABASE):
        print("⚠️ DB no encontrada. Creando estructura vacía...")
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS productos (
            Categoria TEXT, Producto TEXT, Precio TEXT, Imagen_URL TEXT, 
            Archivo_Local TEXT, Pagina TEXT, Fecha_Actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP, 
            UNIQUE(Producto, Pagina))''')
        conn.commit()
        conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

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

# --- UTILIDADES DE PRECIO Y TEXTO ---
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

def limpiar_titulo(t):
    return str(t).upper().replace("ASUS", "").replace("GIGABYTE", "").replace("MSI", "").replace("ASROCK", "")

def son_el_mismo_producto(prod_a, prod_b):
    return False, 0 # Simplificado para el ejemplo (Tu lógica original va aquí si la tienes)

# --- RUTAS ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['password'] == PASSWORD_ADMIN:
            session['logged_in'] = True
            return redirect(url_for('oportunidades'))
        else: error = "❌ Contraseña incorrecta"
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

@app.route('/')
def index():
    init_db_if_needed() # Aseguramos que la DB exista antes de leer
    try:
        cur = get_db().cursor()
        cur.execute("SELECT * FROM productos")
        rows = cur.fetchall()
    except: return "<h1>Base de datos vacía o error. Ve a /admin para actualizar.</h1>"

    productos = []
    for row in rows:
        p = dict(row)
        pn, pt = procesar_precio(p['Precio'])
        p['Precio_Numerico'] = pn; p['Precio_Venta'] = pt
        productos.append(p)
    
    # Filtros simples
    busqueda = request.args.get('q', '').strip().upper()
    cat = request.args.get('cat', '')
    if cat: productos = [x for x in productos if x['Categoria'] == cat]
    if busqueda: productos = [x for x in productos if busqueda in x['Producto'].upper()]
    
    cats = sorted(list(set([x['Categoria'] for x in productos])))
    
    return render_template('catalogo.html', productos=productos, categorias=[{'Categoria':c} for c in cats])

@app.route('/oportunidades')
@login_required 
def oportunidades():
    return render_template('oportunidades.html', oportunidades=[])

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    init_db_if_needed()
    mensaje = ""
    
    if request.method == 'POST':
        # --- AQUÍ ESTÁ LA MAGIA: DETECTAR EL BOTÓN DE ACTUALIZAR ---
        if 'btn_actualizar' in request.form:
            try:
                # Ejecutamos el script en SEGUNDO PLANO (Popen) para no congelar la web
                subprocess.Popen(["python", "actualizar_todo.py"])
                mensaje = "🚀 Actualización iniciada en segundo plano. Espera 5-10 min."
            except Exception as e:
                mensaje = f"❌ Error al ejecutar script: {e}"
        
        # Guardar configuración normal
        elif 'guardar_config' in request.form:
            try:
                CONFIGURACION['margen'] = float(request.form.get('margen', 0))
                mensaje = "✅ Configuración guardada."
            except: pass

    return render_template('admin.html', config=CONFIGURACION, mensaje=mensaje)

if __name__ == '__main__':
    init_db_if_needed()
    app.run(debug=True)