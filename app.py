from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash # NUEVO: Seguridad de contraseñas
from flask_mail import Mail, Message # NUEVO: Sistema de correos
import random
import string
import os # <-- ¡Esta es la línea que faltaba/se borró!
from datetime import datetime, timedelta

app = Flask(__name__)
import os
# ...
db_uri = os.environ.get('DATABASE_URL') or 'sqlite:///delicious_bread.db'
if db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'zmarth_executive_secure_key_2026'

# Configuración de 6 meses (180 días) para la sesión
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=180)

# ================= CONFIGURACIÓN DE CORREO (NUEVO) =================
# Para Gmail, necesitas generar una "Contraseña de Aplicación" en los ajustes de seguridad de tu cuenta.
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'deliciousbread8@gmail.com'
app.config['MAIL_PASSWORD'] = 'omzi mgmg hpsz hmfh'    
app.config['MAIL_DEFAULT_SENDER'] = 'DELICIOUS BREAD'

mail = Mail(app)
# =================================================================

# Configuración para la subida de fotos
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

# ================= MODELOS DE BASE DE DATOS =================
# (Tus modelos se mantienen exactamente igual, están perfectos)

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(15), unique=True, nullable=False)
    correo = db.Column(db.String(100), unique=True, nullable=False)
    contrasena = db.Column(db.String(255), nullable=False) # Aumenté el tamaño para el hash
    pedidos = db.relationship('Pedido', backref='cliente', lazy=True)

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    precio = db.Column(db.Float, nullable=False)
    imagen_url = db.Column(db.String(500), nullable=True)
    disponible = db.Column(db.Boolean, default=True)

class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    horario_recogida = db.Column(db.String(20), nullable=False) # Aumentado por si el string es largo
    metodo_pago = db.Column(db.String(20), nullable=False)
    monto_total = db.Column(db.Float, nullable=False)
    estado = db.Column(db.String(30), default='Pendiente')
    codigo_recogida = db.Column(db.String(10), unique=True, nullable=False)
    fecha_pedido = db.Column(db.DateTime, default=datetime.utcnow)
    detalles = db.relationship('DetallePedido', backref='pedido', lazy=True)

class DetallePedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    producto = db.relationship('Producto')

class DiaInhabil(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, unique=True, nullable=False)
    motivo = db.Column(db.String(200), nullable=True)

def generar_codigo():
    caracteres = string.ascii_uppercase + string.digits
    return f"DB-{''.join(random.choice(caracteres) for _ in range(4))}"

# ================= CONTROL DE AUTENTICACIÓN =================

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        telefono = request.form.get('telefono')
        correo = request.form.get('correo')
        contrasena = request.form.get('contrasena')
        
        existe_usuario = Usuario.query.filter((Usuario.correo == correo) | (Usuario.telefono == telefono)).first()
        if existe_usuario:
            flash('El correo o teléfono ya se encuentra registrado.', 'error')
            return redirect(url_for('registro'))
            
        # NUEVO: Encriptamos la contraseña antes de guardarla
        contrasena_hash = generate_password_hash(contrasena)
        nuevo_usuario = Usuario(nombre=nombre, telefono=telefono, correo=correo, contrasena=contrasena_hash)
        db.session.add(nuevo_usuario)
        db.session.commit()
        
        session['usuario_id'] = nuevo_usuario.id
        return redirect(url_for('index'))
        
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form.get('correo')
        contrasena = request.form.get('contrasena')
        
        usuario = Usuario.query.filter_by(correo=correo).first()
        
        # NUEVO: Comparamos el hash con la contraseña ingresada
        if usuario and check_password_hash(usuario.contrasena, contrasena):
            session.permanent = True # <-- LÍNEA AGREGADA AQUÍ
            session['usuario_id'] = usuario.id
            return redirect(url_for('index'))
        else:
            flash('Credenciales incorrectas. Verifique sus datos.', 'error')
            return redirect(url_for('login'))
            
    return render_template('login.html')
@app.route('/logout')
def logout():
    session.pop('usuario_id', None)
    return redirect(url_for('login'))

# ================= TIENDA PRINCIPAL =================

# ================= TIENDA PRINCIPAL CORREGIDA =================

@app.route('/', methods=['GET'])
def index():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    # CORRECCIÓN 1: Usar la sintaxis moderna db.session.get()
    usuario = db.session.get(Usuario, session['usuario_id'])
    
    # CORRECCIÓN 2: Candado por si la base de datos cambió y el usuario ya no existe
    if not usuario:
        session.pop('usuario_id', None) # Limpiamos la sesión dañada
        return redirect(url_for('login')) # Lo mandamos a loguearse de nuevo
        
    productos = Producto.query.all()
    
    # Verificar si el día de hoy está inhabilitado
    hoy = datetime.utcnow().date()
    dia_bloqueado = DiaInhabil.query.filter_by(fecha=hoy).first()
    tienda_abierta = False if dia_bloqueado else True
    motivo_cierre = dia_bloqueado.motivo if dia_bloqueado else ""
    
    return render_template('index.html', 
                           productos=productos, 
                           usuario=usuario, 
                           nombre_usuario=usuario.nombre,
                           tienda_abierta=tienda_abierta,
                           motivo_cierre=motivo_cierre)
@app.route('/procesar_pedido', methods=['POST'])
def procesar_pedido():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    # Candado de seguridad por si intentan forzar la compra
    hoy = datetime.utcnow().date()
    if DiaInhabil.query.filter_by(fecha=hoy).first():
        flash('La boutique está cerrada el día de hoy. No es posible procesar el pedido.', 'error')
        return redirect(url_for('index'))
        
    usuario = Usuario.query.get(session['usuario_id'])
    horario = request.form.get('horario')
    metodo_pago = request.form.get('metodo_pago')
    
    productos = Producto.query.all()
    monto_total = 0
    detalles_a_crear = []
    
    for prod in productos:
        cant = request.form.get(f'cantidad_{prod.id}', 0)
        if cant and int(cant) > 0:
            cantidad = int(cant)
            monto_total += prod.precio * float(cantidad)
            detalle = DetallePedido(producto_id=prod.id, cantidad=cantidad)
            detalles_a_crear.append(detalle)
            
    if detalles_a_crear:
        nuevo_pedido = Pedido(
            usuario_id=usuario.id,
            horario_recogida=horario,
            metodo_pago=metodo_pago,
            monto_total=monto_total,
            codigo_recogida=generar_codigo()
        )
        db.session.add(nuevo_pedido)
        db.session.commit()
        
        for d in detalles_a_crear:
            d.pedido_id = nuevo_pedido.id
            db.session.add(d)
        db.session.commit()
        
        # Enviar ticket de compra (Esto se queda para los días normales)
        try:
            asunto = f"Tu Ticket de Delicious Bread - {nuevo_pedido.codigo_recogida}"
            msg = Message(asunto, recipients=[usuario.correo])
            msg.html = render_template('correo_ticket.html', pedido=nuevo_pedido, usuario=usuario, detalles=detalles_a_crear)
            mail.send(msg)
            flash('Pedido procesado y ticket enviado a tu correo.', 'success')
        except Exception as e:
            print(f"Error enviando correo: {e}")
            flash('Pedido procesado, pero hubo un error enviando el ticket al correo.', 'warning')
        
        return redirect(url_for('perfil'))

    return redirect(url_for('index'))

# ================= PERFIL DEL CLIENTE =================

@app.route('/perfil')
def perfil():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    usuario = Usuario.query.get(session['usuario_id'])
    mis_pedidos = Pedido.query.filter_by(usuario_id=usuario.id).order_by(Pedido.fecha_pedido.desc()).all()
    return render_template('perfil.html', usuario=usuario, pedidos=mis_pedidos)

# ================= PANEL ADMINISTRATIVO =================

# Contraseña maestra para el administrador (Cámbiala por la que prefieras)
app.config['ADMIN_PASSWORD'] = 'ZmarthAdmin26'

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == app.config['ADMIN_PASSWORD']:
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        else:
            flash('Acceso denegado. Clave incorrecta.', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    if request.method == 'POST' and 'nuevo_producto' in request.form:
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        precio = float(request.form.get('precio'))
        file = request.files.get('imagen_file')
        imagen_url = None
        
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
            imagen_url = f"/static/uploads/{unique_filename}"
        
        nuevo_prod = Producto(nombre=nombre, descripcion=descripcion, precio=precio, imagen_url=imagen_url)
        db.session.add(nuevo_prod)
        db.session.commit()
        return redirect(url_for('admin'))

    filtro = request.args.get('filtro', 'hoy')
    todos_pedidos = Pedido.query.order_by(Pedido.fecha_pedido.desc()).all()
    hoy = datetime.utcnow().date()
    
    pedidos_filtrados = []
    for p in todos_pedidos:
        fecha_p = p.fecha_pedido.date()
        if filtro == 'hoy' and fecha_p == hoy: pedidos_filtrados.append(p)
        elif filtro == 'ayer' and fecha_p == (hoy - timedelta(days=1)): pedidos_filtrados.append(p)
        elif filtro == 'semana' and (hoy - fecha_p).days <= 7: pedidos_filtrados.append(p)
        elif filtro == 'mes' and hoy.month == fecha_p.month and hoy.year == fecha_p.year: pedidos_filtrados.append(p)
        elif filtro == 'todos': pedidos_filtrados.append(p)

    pedidos_activos = [p for p in pedidos_filtrados if p.estado != 'Entregado']
    pedidos_entregados = [p for p in pedidos_filtrados if p.estado == 'Entregado']

    produccion_total = {}
    for p in pedidos_activos:
        for detalle in p.detalles:
            prod_nombre = detalle.producto.nombre
            produccion_total[prod_nombre] = produccion_total.get(prod_nombre, 0) + detalle.cantidad

    productos = Producto.query.all()
    
    # NUEVO: Obtenemos los días bloqueados
    dias_bloqueados_lista = DiaInhabil.query.order_by(DiaInhabil.fecha.asc()).all()

    return render_template('admin.html', 
                           pedidos_activos=pedidos_activos, 
                           pedidos_entregados=pedidos_entregados,
                           produccion=produccion_total,
                           productos=productos,
                           filtro_actual=filtro,
                           dias_bloqueados_lista=dias_bloqueados_lista) # Pasamos a la plantilla

@app.route('/admin/pedido/<int:pedido_id>/estado', methods=['POST'])
def actualizar_estado(pedido_id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido:
        nuevo_estado = request.form.get('estado')
        pedido.estado = nuevo_estado
        db.session.commit()

        # NUEVO: Restauramos el correo automático cuando está Listo
        if nuevo_estado == 'Listo':
            try:
                asunto = f"Tu pedido está listo - {pedido.codigo_recogida}"
                cuerpo = f"""
                <div style="background-color: #0A0A0A; padding: 30px; font-family: Arial, sans-serif; text-align: center;">
                    <div style="background-color: #2B1D14; max-width: 500px; margin: 0 auto; padding: 30px; border-radius: 16px; border: 1px solid #4A3320;">
                        <h2 style="color: #E8D8C8; margin-top: 0;">¡Tu pedido está listo!</h2>
                        <p style="color: #C2B2A3; font-size: 16px;">Hola <strong>{pedido.cliente.nombre}</strong>,</p>
                        <p style="color: #C2B2A3; font-size: 16px;">Tu orden <strong style="color: #E8D8C8;">{pedido.codigo_recogida}</strong> ya te está esperando.</p>
                        <p style="color: #C2B2A3; font-size: 16px;">Ya puedes pasar a recogerlo.</p>
                        <hr style="border: none; border-top: 1px solid #4A3320; margin: 20px 0;">
                        <p style="font-size: 12px; color: #888;">Ecosistema Zmarth - Delicious Bread</p>
                    </div>
                </div>
                """
                msg = Message(asunto, recipients=[pedido.cliente.correo])
                msg.html = cuerpo
                mail.send(msg)
            except Exception as e:
                print(f"Error correo: {e}")

    return redirect(url_for('admin'))

@app.route('/admin/inhabilitar_dias', methods=['POST'])
def inhabilitar_dias():
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    fecha_inicio_str = request.form.get('fecha_inicio')
    fecha_fin_str = request.form.get('fecha_fin')
    motivo = request.form.get('motivo') or "Mantenimiento del Atelier"

    if fecha_inicio_str and fecha_fin_str:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
        
        delta = fecha_fin - fecha_inicio
        for i in range(delta.days + 1):
            dia_actual = fecha_inicio + timedelta(days=i)
            # Solo agregar si no existe ya
            if not DiaInhabil.query.filter_by(fecha=dia_actual).first():
                nuevo_dia = DiaInhabil(fecha=dia_actual, motivo=motivo)
                db.session.add(nuevo_dia)
                
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/habilitar_dia/<int:dia_id>', methods=['POST'])
def habilitar_dia(dia_id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    dia = DiaInhabil.query.get_or_404(dia_id)
    db.session.delete(dia)
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/producto/toggle/<int:producto_id>', methods=['POST'])
def toggle_producto(producto_id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    producto = Producto.query.get_or_404(producto_id)
    producto.disponible = not producto.disponible
    db.session.commit()
    return redirect(url_for('admin'))

from sqlalchemy.exc import IntegrityError
import os

@app.route('/admin/eliminar_producto/<int:producto_id>', methods=['POST'])
def eliminar_producto(producto_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    producto = Producto.query.get_or_404(producto_id)
    
    # Verificamos si este producto tiene ventas asociadas usando el ID correcto
    tiene_ventas = DetallePedido.query.filter_by(producto_id=producto_id).first()
    
    if tiene_ventas:
        # Si tiene ventas, no lo borramos, lo pausamos para evitar errores
        producto.disponible = False
        db.session.commit()
        flash('El producto tenía ventas registradas, así que se ha PAUSADO automáticamente para mantener tu historial.', 'warning')
    else:
        # Si no tiene ventas, lo borramos físicamente
        try:
            if producto.imagen_url:
                filename = producto.imagen_url.split('/')[-1]
                # Aseguramos la ruta correcta usando app.root_path
                filepath = os.path.join(app.root_path, 'static', 'uploads', filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
            
            db.session.delete(producto)
            db.session.commit()
            flash('Producto eliminado permanentemente del catálogo.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al eliminar: {str(e)}', 'danger')
            
    return redirect(url_for('admin'))

@app.route('/admin/producto/editar/<int:producto_id>', methods=['POST'])
def editar_producto(producto_id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    producto = Producto.query.get_or_404(producto_id)
    
    producto.nombre = request.form.get('nombre')
    producto.descripcion = request.form.get('descripcion')
    producto.precio = float(request.form.get('precio'))
    
    # Lógica opcional si sube nueva foto, si no, se queda la anterior
    file = request.files.get('imagen_file')
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        producto.imagen_url = f"/static/uploads/{unique_filename}"
        
    db.session.commit()
    return redirect(url_for('admin'))

from datetime import datetime
# Asegúrate de importar tu librería de correos (ej. flask_mail)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)