import requests
import sqlite3
import time
import sys
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# CREDENCIALES
USER_ID = 17715        
TOKEN = "k79yemcmlui"  
URL_API = "https://clientes.elit.com.ar/v1/api/productos"
NOMBRE_DB = "catalogo_productos.db"

# 1. FILTRO DE CATEGORÍAS
CATEGORIAS_HABILITADAS = [
    "Notebooks", 
    "Procesadores AMD",   
    "Procesadores Intel", 
    "Motherboards", 
    "Memorias RAM",
    "Discos SSD", 
    "Discos Internos",
    "Discos Externos",
    "Discos Externos SSD", 
    "Placas de Video",
    "Fuentes", 
    "Gabinetes", 
    "Monitores", 
    "Impresoras",
    "Conectividad", 
    "Periféricos"
]

# 2. REGLAS DE UNIFICACIÓN
REGLAS_UNIFICACION = {
    "Notebooks Consumo": "Notebooks",
    "Notebooks Corporativo": "Notebooks",
    "Discos Solidos": "Discos SSD",
    "Discos Internos Ssd": "Discos SSD",
    "Discos Externos Ssd": "Discos Externos SSD",
    "Discos Internos": "Discos Internos", 
    "Mothers Amd": "Motherboards",
    "Mothers Intel": "Motherboards",
    
    # Mapeamos los nombres que vamos a forzar manualmente
    "Procesadores AMD": "Procesadores AMD",
    "Procesadores Intel": "Procesadores Intel",
    
    "Placas De Video Nvidia": "Placas de Video",
    "Placas De Video Amd": "Placas de Video"
}

REEMPLAZOS_TITULO = {
    "MICRO ": "PROCESADOR ", "MOTHER ": "MOTHERBOARD ", "MEMORIA RAM ": "MEMORIA ",
    "NOTEBOOK ": "LAPTOP ", "VIDEO GEFORCE": "PLACA VIDEO GEFORCE", "VIDEO RADEON": "PLACA VIDEO RADEON"
}

def limpiar_titulo(t):
    if not t: return "SIN NOMBRE"
    t = t.upper() 
    for original, nuevo in REEMPLAZOS_TITULO.items():
        t = t.replace(original.upper(), nuevo.upper())
    return t 

def asegurar_tabla():
    try:
        conn = sqlite3.connect(NOMBRE_DB)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS productos (
            Categoria TEXT, Producto TEXT, Precio TEXT, Imagen_URL TEXT, 
            Archivo_Local TEXT, Pagina TEXT, Fecha_Actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP, 
            UNIQUE(Producto, Pagina))''')
        conn.commit()
        conn.close()
    except Exception as e: print(f"❌ Error DB: {e}")

def importar_elit():
    print(f"--- 🔵 INICIANDO ELIT API (MODO DETECTIVE CPU) ---")
    asegurar_tabla()

    offset = 1; limit = 100; sigue_buscando = True; total_guardados = 0
    headers = {'Content-Type': 'application/json'}

    while sigue_buscando:
        try:
            response = requests.post(f"{URL_API}?limit={limit}&offset={offset}", 
                                   json={"user_id": USER_ID, "token": TOKEN}, 
                                   headers=headers, timeout=30, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                lista = data if isinstance(data, list) else data.get('resultado') or data.get('result') or data.get('data') or []
                
                if not lista: break
                
                datos_db = []
                for p in lista:
                    try:
                        # 1. Obtenemos datos crudos
                        cat_raw = (p.get('sub_categoria') or p.get('categoria') or "Varios").strip()
                        nombre_raw = p.get('nombre', 'Sin Nombre').upper()
                        
                        # ========================================================
                        # 🕵️‍♂️ DETECTOR INTELIGENTE DE MARCA (ELIT FIX)
                        # ========================================================
                        # Si Elit dice que es un procesador genérico, miramos el nombre.
                        es_procesador = "PROCESADOR" in cat_raw.upper() or "MICRO" in cat_raw.upper()
                        
                        if es_procesador:
                            if "AMD" in nombre_raw or "RYZEN" in nombre_raw or "ATHLON" in nombre_raw:
                                cat_raw = "Procesadores AMD" # Forzamos la categoría correcta
                            elif "INTEL" in nombre_raw or "CORE" in nombre_raw or "PENTIUM" in nombre_raw:
                                cat_raw = "Procesadores INTEL" # Forzamos la categoría correcta

                        # ========================================================

                        # 2. Unificación normal
                        cat_final = REGLAS_UNIFICACION.get(cat_raw, cat_raw.title())
                        
                        # 3. Filtro
                        if cat_final not in CATEGORIAS_HABILITADAS: 
                            continue 

                        nombre = limpiar_titulo(nombre_raw)
                        
                        # Precio
                        pb = float(p.get('precio', 0))
                        moneda = int(p.get('moneda', 1))
                        cotiz = float(p.get('cotizacion', 1))
                        precio_pesos = pb * cotiz if moneda == 2 else pb
                        iva = float(str(p.get('iva', 21)))
                        final = precio_pesos * (1 + (iva/100))
                        precio_fmt = f"$ {final:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        
                        img = p.get('imagenes')[0] if p.get('imagenes') else "Sin imagen"

                        datos_db.append((cat_final, nombre, precio_fmt, img, "No imagen", "Elit API"))
                    except Exception as e: 
                        continue 

                if datos_db:
                    conn = sqlite3.connect(NOMBRE_DB)
                    c = conn.cursor()
                    c.executemany("INSERT OR REPLACE INTO productos (Categoria, Producto, Precio, Imagen_URL, Archivo_Local, Pagina) VALUES (?, ?, ?, ?, ?, ?)", datos_db)
                    conn.commit()
                    conn.close()
                    total_guardados += len(datos_db)
                    print(f"   -> Lote: {len(datos_db)} items.")
                
                offset += limit
            else:
                sigue_buscando = False
        except Exception as e:
            print(f"❌ Error conectando a Elit: {e}")
            sigue_buscando = False

    print(f"✅ ELIT FINALIZADO. Total: {total_guardados}")

if __name__ == "__main__":
    importar_elit()