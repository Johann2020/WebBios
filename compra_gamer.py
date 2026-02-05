import time
import sqlite3
import re 
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

NOMBRE_DB = "catalogo_productos.db"

MAPA_DE_CATEGORIAS = {
    "Procesadores AMD": "https://compragamer.com/productos?cate=27&sort=lower_price",
    "Procesadores INTEL": "https://compragamer.com/productos?cate=48&sort=lower_price",
    "Motherboards AMD": "https://compragamer.com/productos?cate=26&sort=lower_price",
    "Motherboards Intel": "https://compragamer.com/productos?cate=49&sort=lower_price",
    "Placas Video Nvidia": "https://compragamer.com/productos?cate=6&sort=lower_price",
    "Placas Video Radeon": "https://compragamer.com/productos?cate=62&sort=lower_price",
    
    # CLAVE: Nombre exacto para coincidir con los otros
    "Memorias RAM PC": "https://compragamer.com/productos?sort=lower_price&cate=15",
    "Memorias RAM Notebook": "https://compragamer.com/productos?sort=lower_price&cate=47",
    
    "Discos SSD": "https://compragamer.com/productos?cate=81&sort=lower_price",
    "Fuentes": "https://compragamer.com/productos?cate=34&sort=lower_price",
    "Gabinetes": "https://compragamer.com/productos?cate=7&sort=lower_price",
    "Monitores": "https://compragamer.com/productos?cate=5&sort=lower_price"
}

REGLAS_UNIFICACION = {
    "Motherboards AMD": "Motherboards", "Motherboards Intel": "Motherboards",
    "Placas Video Nvidia": "Placas de Video", "Placas Video Radeon": "Placas de Video",
}

REEMPLAZOS_TITULO = {
    "MICRO ": "PROCESADOR ", "MOTHER ": "MOTHERBOARD ", "MEMORIA RAM ": "MEMORIA ",
    "NOTEBOOK ": "LAPTOP ", "VIDEO GEFORCE": "PLACA VIDEO GEFORCE", "VIDEO RADEON": "PLACA VIDEO RADEON"
}

def limpiar_titulo(titulo_sucio):
    if not titulo_sucio: return "SIN TITULO"
    titulo_limpio = titulo_sucio.upper()
    for original, nuevo in REEMPLAZOS_TITULO.items():
        titulo_limpio = titulo_limpio.replace(original.upper(), nuevo.upper())
    return titulo_limpio

def main():
    print("--- 🟢 INICIANDO COMPRA GAMER (HEADLESS) ---")
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
    gran_lista_productos = []

    try:
        for nombre_cat_temp, url in MAPA_DE_CATEGORIAS.items():
            cat_final = REGLAS_UNIFICACION.get(nombre_cat_temp, nombre_cat_temp)
            print(f"   -> Escaneando: {nombre_cat_temp}")
            
            driver.get(url)
            time.sleep(3) 
            
            # Scroll para imagenes
            body = driver.find_element(By.TAG_NAME, 'body')
            for _ in range(6):
                body.send_keys(Keys.PAGE_DOWN)
                time.sleep(0.5)
            
            soup = BeautifulSoup(driver.page_source, "html.parser")
            tarjetas = soup.find_all("app-product-card")
            if not tarjetas: tarjetas = soup.select(".product-card")

            for card in tarjetas:
                try:
                    titulo_elem = card.find("div", class_="theme-name") or card.find("h3") or card.find("p", class_="description")
                    if not titulo_elem: continue
                    titulo_limpio = limpiar_titulo(titulo_elem.text.strip())

                    # FILTROS LIMPIEZA
                    if cat_final == "Procesadores" and ("MEMORIA" in titulo_limpio or "COOLER" in titulo_limpio): continue

                    texto_completo = card.get_text()
                    match_precio = re.search(r'\$\s*[0-9]{1,3}(?:\.[0-9]{3})*(?:,[0-9]{2})?', texto_completo)
                    precio_texto = match_precio.group(0).replace(" ", "") if match_precio else "$ 0"

                    img_url = "Sin imagen"
                    img_elem = card.find("img")
                    if img_elem:
                        # Lógica robusta de imagenes
                        posibles = [img_elem.get("data-src"), img_elem.get("src"), img_elem.get("srcset")]
                        for ruta in posibles:
                            if ruta and "http" in ruta and "base64" not in ruta:
                                img_url = ruta.split(",")[0].split(" ")[0]
                                break
                            if ruta and ruta.startswith("/"):
                                img_url = "https://compragamer.com" + ruta
                                break

                    gran_lista_productos.append((cat_final, titulo_limpio, precio_texto, img_url, "No imagen", "Compra Gamer"))
                except: continue

        if gran_lista_productos:
            conn = sqlite3.connect(NOMBRE_DB)
            c = conn.cursor()
            sql = 'INSERT OR REPLACE INTO productos (Categoria, Producto, Precio, Imagen_URL, Archivo_Local, Pagina) VALUES (?, ?, ?, ?, ?, ?)'
            c.executemany(sql, gran_lista_productos)
            conn.commit()
            conn.close()
            print(f"✅ COMPRA GAMER FINALIZADO. Total: {len(gran_lista_productos)}")
        else:
            print("❌ Compra Gamer vacio.")

    except Exception as e:
        print(f"❌ Error Compra Gamer: {e}")
    finally:
        if 'driver' in locals(): driver.quit()

if __name__ == "__main__":
    main()