from flask import Flask, render_template, request, g, session, redirect, url_for
import sqlite3
import re
from functools import wraps
from thefuzz import fuzz 

app = Flask(__name__)
DATABASE = "catalogo_productos.db"

# ==========================================
#   🔐 CONFIGURACIÓN DE SEGURIDAD
# ==========================================
# Cambia esta clave por una palabra secreta cualquiera (para encriptar cookies)
app.secret_key = "super_secreto_clave_maestra"

# 👇 TU CONTRASEÑA DE ACCESO 👇
PASSWORD_ADMIN = "JGDigital88" 

CONFIGURACION = {
    "margen": 30.0,
    "envio": 0.0,
    "alias": {} 
}

# ==========================================
#   DECORADOR DE SEGURIDAD (EL GUARDIA)
# ==========================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Si no hay sesión iniciada, lo mandamos al login
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
#   BASE DE DATOS Y UTILIDADES
# ==========================================
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
    except:
        return 0.0, "Consultar"

# Lógica Local (TheFuzz)
def limpiar_titulo(titulo):
    t = titulo.upper()
    return t.replace("ASUS", "").replace("GIGABYTE", "").replace("MSI", "").replace("ASROCK", "").replace("ZOTAC", "")

def extraer_numeros_clave(texto):
    numeros = re.findall(r'\b\d{3,5}\b', texto)
    modelos = re.findall(r'\b[Ii][3579]\b', texto)
    return set(numeros + modelos)

def son_el_mismo_producto(prod_a, prod_b):
    t1 = limpiar_titulo(prod_a)
    t2 = limpiar_titulo(prod_b)
    nums1 = extraer_numeros_clave(t1)
    nums2 = extraer_numeros_clave(t2)
    if nums1 and nums2:
        if not nums1.intersection(nums2):
            return False, 0 
    similitud = fuzz.token_set_ratio(t1, t2)
    if similitud >= 80: return True, similitud
    return False, similitud

# ==========================================
#   RUTAS DE ACCESO (LOGIN/LOGOUT)
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['password'] == PASSWORD_ADMIN:
            session['logged_in'] = True
            # Si intentaba ir a un sitio específico, lo devolvemos ahí
            next_url = request.args.get('next')
            return redirect(next_url or url_for('oportunidades'))
        else:
            error = "❌ Contraseña incorrecta"
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

# ==========================================
#   RUTAS PRINCIPALES
# ==========================================

@app.route('/')
def index():
    cur = get_db().cursor()
    cur.execute("SELECT * FROM productos WHERE 1=1")
    raw_data = cur.fetchall()
    
    productos = []
    for row in raw_data:
        p = dict(row)
        pn, pt = procesar_precio(p['Precio'])
        p['Precio_Numerico'] = pn
        p['Precio_Venta'] = pt
        p['Pagina'] = CONFIGURACION['alias'].get(p['Pagina'], p['Pagina'])
        productos.append(p)
    
    busqueda = request.args.get('q', '').strip()
    cat = request.args.get('cat', '')
    orden = request.args.get('orden', '')
    
    prod_filtrados = productos
    if cat: prod_filtrados = [x for x in prod_filtrados if x['Categoria'] == cat]
    if busqueda: prod_filtrados = [x for x in prod_filtrados if busqueda.upper() in x['Producto'].upper()]
    
    cats_set = sorted(list(set([x['Categoria'] for x in productos])))
    cats = [{'Categoria': c} for c in cats_set]

    if orden == 'menor': prod_filtrados.sort(key=lambda x: x['Precio_Numerico'])
    elif orden == 'mayor': prod_filtrados.sort(key=lambda x: x['Precio_Numerico'], reverse=True)
    else: prod_filtrados.sort(key=lambda x: x['Producto'])

    return render_template('catalogo.html', productos=prod_filtrados, categorias=cats, cat_activa=cat, busqueda_actual=busqueda, orden_actual=orden)

# 🔒 RUTA PROTEGIDA
@app.route('/oportunidades')
@login_required 
def oportunidades():
    print("--- ⚡ BUSCANDO OPORTUNIDADES (LOCAL) ---")
    cur = get_db().cursor()
    cur.execute("SELECT * FROM productos WHERE Precio != '$ 0' ORDER BY Categoria, Precio")
    raw_data = cur.fetchall()

    lista = []
    for row in raw_data:
        p = dict(row)
        pn, pt = procesar_precio(p['Precio'])
        if pn > 5000:
            p['Precio_Numerico'] = pn
            p['Precio_Venta'] = pt
            lista.append(p)

    oportunidades = []
    for i in range(len(lista)):
        p1 = lista[i]
        rango = min(len(lista), i + 40)
        for j in range(i + 1, rango):
            p2 = lista[j]
            if p1['Categoria'] != p2['Categoria']: continue
            if p1['Pagina'] == p2['Pagina']: continue
            ratio = p1['Precio_Numerico'] / p2['Precio_Numerico']
            if ratio > 1.8 or ratio < 0.55: continue 
            es_match, puntaje = son_el_mismo_producto(p1['Producto'], p2['Producto'])
            if es_match:
                if p1['Precio_Numerico'] < p2['Precio_Numerico']: barato, caro = p1, p2
                else: barato, caro = p2, p1
                diferencia = caro['Precio_Numerico'] - barato['Precio_Numerico']
                if diferencia > 5000:
                    oportunidades.append({"producto_barato": barato, "producto_caro": caro, "diferencia": diferencia, "certeza": puntaje})
    
    oportunidades.sort(key=lambda x: x['diferencia'], reverse=True)
    return render_template('oportunidades.html', oportunidades=oportunidades)

# 🔒 RUTA PROTEGIDA
@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    cur = get_db().cursor()
    cur.execute("SELECT DISTINCT Pagina FROM productos")
    proveedores = [row['Pagina'] for row in cur.fetchall() if row['Pagina']]
    mensaje = ""
    if request.method == 'POST':
        try:
            CONFIGURACION['margen'] = float(request.form.get('margen', 0))
            CONFIGURACION['envio'] = float(request.form.get('envio', 0))
            for p in proveedores:
                val = request.form.get(f"alias_{p}")
                if val: CONFIGURACION['alias'][p] = val
            mensaje = "¡Configuración Guardada!"
        except: mensaje = "Error en los valores"
        
    return render_template('admin.html', config=CONFIGURACION, proveedores=proveedores, mensaje=mensaje)

if __name__ == '__main__':
    app.run(debug=True)