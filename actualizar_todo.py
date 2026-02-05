import os
import time
import sqlite3

def limpiar_productos_antiguos(minutos_tolerancia=30):
    """Borra productos que no se actualizaron en esta corrida"""
    print("🧹 Limpiando productos descatalogados...")
    conn = sqlite3.connect("catalogo_productos.db")
    cursor = conn.cursor()
    
    # La lógica es: Si corriste el script hace 5 minutos, los productos vigentes 
    # tienen fecha de "hace 0 minutos". Los que no se encontraron hoy, 
    # tienen fecha vieja. Borramos los viejos.
    cursor.execute(f'''
        DELETE FROM productos 
        WHERE Fecha_Actualizacion < datetime('now', '-{minutos_tolerancia} minutes')
    ''')
    borrados = cursor.rowcount
    conn.commit()
    conn.close()
    print(f"🗑️ Se eliminaron {borrados} productos que ya no existen.")

def ejecutar(archivo):
    print(f"\n🚀 EJECUTANDO: {archivo}...")
    # Ejecuta el archivo python esperando a que termine
    os.system(f'python "{archivo}"')

if __name__ == "__main__":
    inicio = time.time()
    
    # 1. EJECUTAR LOS 3 SCRAPERS EN ORDEN
    ejecutar("elit.py")
    ejecutar("altavista.py")
    ejecutar("compra_gamer.py") # Asegurate que el nombre del archivo sea exacto (espacios, mayusculas)
    
    # 2. BORRAR LOS QUE YA NO ESTÁN
    # Damos 60 minutos de tolerancia por si el internet estuvo lento
    limpiar_productos_antiguos(minutos_tolerancia=60)
    
    fin = time.time()
    tiempo_total = round((fin - inicio) / 60, 1)
    
    print(f"\n✨ ACTUALIZACIÓN COMPLETA EN {tiempo_total} MINUTOS ✨")
    print("Ya puedes abrir app.py")
    input("Presiona ENTER para salir.")