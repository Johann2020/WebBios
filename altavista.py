import time
import sqlite3
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ==========================================
#      ZONA DE CONFIGURACIÓN
# ==========================================
URL_LOGIN = "https://www.altavistasa.com.ar/iniciar-sesion?back=my-account"
TU_EMAIL = "gelrothjohann@gmail.com"
TU_PASSWORD = "92q7KKqiT2w7uXT"
NOMBRE_DB = "catalogo_productos.db"

# Mapa de categorías
MAPA_DE_CATEGORIAS = {
    "Impresoras Laser": "https://www.altavistasa.com.ar/123-impresoras-laser",
    "Impresoras sistema continuo": "https://www.altavistasa.com.ar/125-impresoras-sistema-continuo",
    "Notebooks": "https://www.altavistasa.com.ar/218-notebooks",
    "Notebooks Consumo": "https://www.altavistasa.com.ar/220-notebooks-consumo",    
    "Notebooks Corporativo": "https://www.altavistasa.com.ar/221-notebooks-corporativo", 
    "Adaptadores de red": "https://www.altavistasa.com.ar/160-adaptadores-de-red",
    "Extensores": "https://www.altavistasa.com.ar/161-extensores",
    "Discos SSD": "https://www.altavistasa.com.ar/199-discos-ssd",
    "Motherboards": "https://www.altavistasa.com.ar/205-motherboards",
    "Procesadores AMD": "https://www.altavistasa.com.ar/207-microprocesadores?q=Marca-AMD",
    "Procesadores INTEL": "https://www.altavistasa.com.ar/207-microprocesadores?q=Marca-INTEL",
    "Memorias RAM PC": "https://www.altavistasa.com.ar/203-memorias",
    "Fuentes": "https://www.altavistasa.com.ar/200-fuentes",
    "Placas de Video": "https://www.altavistasa.com.ar/206-placas-de-video",
    "Gabinetes": "https://www.altavistasa.com.ar/201-gabinetes",
    "Monitores": "https://www.altavistasa.com.ar/224-monitorestv"
}

REGLAS_UNIFICACION = {
    "Notebooks Consumo": "Notebooks",
    "Notebooks Corporativo": "Notebooks",
    "Impresoras Laser": "Impresoras",
    "Impresoras sistema continuo": "Impresoras",
    "Memorias": "Memorias RAM" 
}

REEMPLAZOS_TITULO = {
    "MICRO ": "PROCESADOR ", "MOTHER ": "MOTHERBOARD ", "MEMORIA RAM ": "MEMORIA ",
    "NOTEBOOK ": "LAPTOP ", "VIDEO GEFORCE": "PLACA VIDEO GEFORCE", "VIDEO RADEON": "PLACA VIDEO RADEON"
}

def limpiar_titulo(t):
    if not t: return "SIN TITULO"
    t = t.upper() 
    for o, n in REEMPLAZOS_TITULO.items(): t = t.replace(o.upper(), n.upper())
    return t 

def asegurar_tabla():
    """Crea la tabla si no existe para evitar errores"""
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

def main():
    print("--- 🟠 INICIANDO ALTAVISTA (MODO OCULTO / HEADLESS) ---")
    asegurar_tabla()
    
    # ... en tus archivos .py ...

options = webdriver.ChromeOptions()
options.add_argument("--headless=new") 
options.add_argument("--no-sandbox")            # <--- NECESARIO EN SERVIDOR
options.add_argument("--disable-dev-shm-usage") # <--- NECESARIO EN SERVIDOR
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")

# ESTO ES NECESARIO PARA RENDER: Le decimos dónde instalamos Chrome
import os
if os.environ.get('RENDER'):
    options.binary_location = "/opt/render/project/.render/chrome/opt/google/chrome/chrome"

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    total_guardados = 0

    try:
        print("   -> Iniciando sesión...")
        driver.get(URL_LOGIN)
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.NAME, "email"))).send_keys(TU_EMAIL)
        driver.find_element(By.NAME, "password").send_keys(TU_PASSWORD)
        driver.find_element(By.ID, "submit-login").click()
        time.sleep(3)

        for nombre_cat, url in MAPA_DE_CATEGORIAS.items():
            cat_final = REGLAS_UNIFICACION.get(nombre_cat, nombre_cat)
            print(f"   -> Escaneando: {nombre_cat}...")
            
            page = 1
            while True:
                # Construir URL
                target_url = url if page == 1 else f"{url}?page={page}"
                
                print(f"      --> Pag {page}...", end="\r")
                driver.get(target_url)
                time.sleep(1) # Pausa breve
                
                # --- FRENO 1: Detectar redirección al inicio ---
                # Si pedimos pag 5 y la URL actual no tiene "page=5", es que nos mandó a la 1
                current_url = driver.current_url
                if page > 1 and f"page={page}" not in current_url:
                    print(f"      [X] Fin detectado (Redirección automática).")
                    break
                
                soup = BeautifulSoup(driver.page_source, "html.parser")
                items = soup.find_all("article", class_="product-miniature")
                
                if not items:
                    print(f"      [X] Fin detectado (Sin productos).")
                    break
                
                batch = []
                for item in items:
                    try:
                        tit = limpiar_titulo(item.find("h2", class_="product-title").text.strip())
                        prc = item.find("span", class_="price").text.strip()
                        img = item.find("img")
                        img_url = img.get("data-full-size-image-url") or img.get("src") if img else "Sin imagen"
                        batch.append((cat_final, tit, prc, img_url, "No imagen", "Altavista"))
                    except: continue
                
                if batch:
                    conn = sqlite3.connect(NOMBRE_DB)
                    c = conn.cursor()
                    c.executemany("INSERT OR REPLACE INTO productos (Categoria, Producto, Precio, Imagen_URL, Archivo_Local, Pagina) VALUES (?, ?, ?, ?, ?, ?)", batch)
                    conn.commit()
                    conn.close()
                    total_guardados += len(batch)
                
                # --- FRENO 2: Verificar botón "Siguiente" ---
                # Altavista usa un enlace rel="next". Si no está, es la última página.
                boton_siguiente = soup.find("a", attrs={"rel": "next"})
                if not boton_siguiente:
                    print(f"      [X] Fin detectado (Última página).")
                    break
                
                page += 1

        print(f"\n✅ ALTAVISTA FINALIZADO. Total importados: {total_guardados}")

    except Exception as e:
        print(f"\n❌ Error Altavista: {e}")
    finally:
        if driver: driver.quit()

if __name__ == "__main__":
    main()