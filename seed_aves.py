from app import app, db, Coleccionable

# Lista Maestra de las 30 Especies de la Orden Alada Zmarth
# Nota: Si usa la carpeta local, guarde las fotos como 1.png, 2.png, etc. en static/img/aves/
AVES_DATA = [
    # --- TIER I: COMUNES (Base sumada ~50%) ---
    {"nombre": "Cernícalo Americano", "tier": 1, "prob": 8.5, "img": "/static/img/aves/1.png"},
    {"nombre": "Esmerejón", "tier": 1, "prob": 8.5, "img": "/static/img/aves/2.png"},
    {"nombre": "Elanio Común", "tier": 1, "prob": 8.3, "img": "/static/img/aves/3.png"},
    {"nombre": "Aguilucho Común", "tier": 1, "prob": 8.3, "img": "/static/img/aves/4.png"},
    {"nombre": "Gavilán Común", "tier": 1, "prob": 8.2, "img": "/static/img/aves/5.png"},
    {"nombre": "Lechuza de Campanario", "tier": 1, "prob": 8.2, "img": "/static/img/aves/6.png"},

    # --- TIER II: POCO COMUNES (Base sumada ~25%) ---
    {"nombre": "Halcón Mielero", "tier": 2, "prob": 4.2, "img": "/static/img/aves/7.png"},
    {"nombre": "Aguilucho Lagunero", "tier": 2, "prob": 4.2, "img": "/static/img/aves/8.png"},
    {"nombre": "Busardo Ratonero", "tier": 2, "prob": 4.2, "img": "/static/img/aves/9.png"},
    {"nombre": "Caracara Crestado", "tier": 2, "prob": 4.2, "img": "/static/img/aves/10.png"},
    {"nombre": "Halconcito Rojo", "tier": 2, "prob": 4.1, "img": "/static/img/aves/11.png"},
    {"nombre": "Águila Mora", "tier": 2, "prob": 4.1, "img": "/static/img/aves/12.png"},

    # --- TIER III: RARAS (Base sumada ~15%) ---
    {"nombre": "Halcón Peregrino", "tier": 3, "prob": 2.5, "img": "/static/img/aves/13.png"},
    {"nombre": "Águila Calva", "tier": 3, "prob": 2.5, "img": "/static/img/aves/14.png"},
    {"nombre": "Águila de Harris", "tier": 3, "prob": 2.5, "img": "/static/img/aves/15.png"},
    {"nombre": "Halcón Lanario", "tier": 3, "prob": 2.5, "img": "/static/img/aves/16.png"},
    {"nombre": "Halcón Mexicano", "tier": 3, "prob": 2.5, "img": "/static/img/aves/17.png"},
    {"nombre": "Azor Común", "tier": 3, "prob": 2.5, "img": "/static/img/aves/18.png"},

    # --- TIER IV: ÉPICAS (Base sumada ~8%) ---
    {"nombre": "Halcón Sacre", "tier": 4, "prob": 1.4, "img": "/static/img/aves/19.png"},
    {"nombre": "Águila Real", "tier": 4, "prob": 1.4, "img": "/static/img/aves/20.png"},
    {"nombre": "Águila Imperial Oriental", "tier": 4, "prob": 1.3, "img": "/static/img/aves/21.png"},
    {"nombre": "Águila Marina de Steller", "tier": 4, "prob": 1.3, "img": "/static/img/aves/22.png"},
    {"nombre": "Halcón Cardenal", "tier": 4, "prob": 1.3, "img": "/static/img/aves/23.png"},
    {"nombre": "Águila Monera", "tier": 4, "prob": 1.3, "img": "/static/img/aves/24.png"},

    # --- TIER V: LEGENDARIAS (Base sumada ~2%) ---
    {"nombre": "Águila Arpía", "tier": 5, "prob": 0.4, "img": "/static/img/aves/25.png"},
    {"nombre": "Águila Coronada", "tier": 5, "prob": 0.4, "img": "/static/img/aves/26.png"},
    {"nombre": "Halcón Negro Mayor", "tier": 5, "prob": 0.4, "img": "/static/img/aves/27.png"},
    {"nombre": "Águila Monarca", "tier": 5, "prob": 0.3, "img": "/static/img/aves/28.png"},
    {"nombre": "Halcón de Eleonora", "tier": 5, "prob": 0.3, "img": "/static/img/aves/29.png"},
    {"nombre": "Halcón Gerifalte", "tier": 5, "prob": 0.2, "img": "/static/img/aves/30.png"} # Cúspide Suprema
]

def sembrar_aves():
    with app.app_context():
        print("Sincronizando el catálogo de aves en la base de datos...")
        agregados = 0
        for ave in AVES_DATA:
            existe = Coleccionable.query.filter_by(nombre=ave["nombre"]).first()
            if not existe:
                nuevo = Coleccionable(
                    nombre=ave["nombre"],
                    tier=ave["tier"],
                    probabilidad_base=ave["prob"],
                    imagen_url=ave["img"]
                )
                db.session.add(nuevo)
                agregados += 1
        
        db.session.commit()
        print(f"¡Éxito! Se registraron {agregados} especies nuevas en el catálogo.")

if __name__ == '__main__':
    sembrar_aves()