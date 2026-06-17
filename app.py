from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from flask_socketio import SocketIO, emit
import random
import string
import os
import re
from datetime import datetime, timedelta

import cloudinary
import cloudinary.uploader

app = Flask(__name__)

socketio = SocketIO(app, cors_allowed_origins="*") 

# ================= CONFIGURACIÓN DE CLOUDINARY =================
cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET')
)

def subir_a_cloudinary(file):
    if file and file.filename != '':
        upload_result = cloudinary.uploader.upload(file)
        return upload_result.get("secure_url")
    return None

# ================= CONFIGURACIÓN DE BASE DE DATOS =================
db_uri = os.environ.get('DATABASE_URL')

if not db_uri:
    db_uri = 'postgresql://tu_usuario:tu_contraseña@tu_servidor.neon.tech/neondb?sslmode=require'

# Corrección automática de dialecto para SQLAlchemy
if db_uri and db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)

# Eliminación de channel_binding para evitar fallos de descifrado SSL en Render + Neon
if db_uri:
    db_uri = db_uri.replace("&channel_binding=require", "").replace("?channel_binding=require", "?")

print("DATABASE_URL:", db_uri)
print("Conectando a Neon...")

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 1. Usar SQLAlchemy Engine Options & 2. Configurar el Pool
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_size': 5,
    'max_overflow': 10
}

app.secret_key = 'zmarth_executive_secure_key_2026'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=180)

# ================= CONFIGURACIÓN DE CORREO =================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'deliciousbread8@gmail.com'
app.config['MAIL_PASSWORD'] = 'omzi mgmg hpsz hmfh'    
app.config['MAIL_DEFAULT_SENDER'] = 'DELICIOUS BREAD'

mail = Mail(app)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

db = SQLAlchemy(app)

# 5. Función de Diagnóstico de Conexión
def verificar_db():
    try:
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        print("✓ Base conectada")
    except Exception as e:
        print(f"✗ Error de conexión: {e}")

# ================= MODELOS DE BASE DE DATOS =================

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(15), unique=True, nullable=False)
    correo = db.Column(db.String(100), unique=True, nullable=False)
    contrasena = db.Column(db.String(255), nullable=False)
    pedidos = db.relationship('Pedido', backref='cliente', lazy=True)

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    precio = db.Column(db.Float, nullable=False)
    imagen_url = db.Column(db.String(500), nullable=True)
    disponible = db.Column(db.Boolean, default=True)
    stock_sobrante = db.Column(db.Integer, default=0)

class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    horario_recogida = db.Column(db.String(20), nullable=False)
    metodo_pago = db.Column(db.String(20), nullable=False)
    monto_total = db.Column(db.Float, nullable=False)
    estado = db.Column(db.String(30), default='Pendiente')
    codigo_recogida = db.Column(db.String(10), unique=True, nullable=False)
    fecha_pedido = db.Column(db.DateTime, default=datetime.utcnow)
    detalles = db.relationship('DetallePedido', backref='pedido', lazy=True)
    comprobante_url = db.Column(db.String(500), nullable=True)

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

class Anuncio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=True)
    imagen_url = db.Column(db.String(500), nullable=False)
    enlace_destino = db.Column(db.String(500), nullable=True)
    activo = db.Column(db.Boolean, default=True)

class PedidoEspecial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre_contacto = db.Column(db.String(100), nullable=False)
    telefono_contacto = db.Column(db.String(15), nullable=False)
    correo_contacto = db.Column(db.String(100), nullable=False)
    metodo_entrega = db.Column(db.String(20), nullable=False)  
    direccion_texto = db.Column(db.String(300), nullable=True)
    numero_casa = db.Column(db.String(20), nullable=True)
    referencias = db.Column(db.Text, nullable=True)
    latitud = db.Column(db.Float, nullable=True)
    longitud = db.Column(db.Float, nullable=True)
    monto_total = db.Column(db.Float, nullable=False)
    monto_anticipo = db.Column(db.Float, nullable=False)  
    comprobante_url = db.Column(db.String(500), nullable=True)
    anticipo_validado = db.Column(db.Boolean, default=False)
    estado = db.Column(db.String(50), default='Pendiente de Validación')  
    codigo_recogida = db.Column(db.String(15), unique=True, nullable=False)
    fecha_evento = db.Column(db.String(50), nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    detalles = db.relationship('DetallePedidoEspecial', backref='pedido_especial', lazy=True)

class DetallePedidoEspecial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_especial_id = db.Column(db.Integer, db.ForeignKey('pedido_especial.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    producto = db.relationship('Producto')

def generar_codigo():
    caracteres = string.ascii_uppercase + string.digits
    return f"DB-{''.join(random.choice(caracteres) for _ in range(4))}"

def generar_codigo_especial():
    caracteres = string.ascii_uppercase + string.digits
    return f"ZCW-EV-{''.join(random.choice(caracteres) for _ in range(5))}"

# ================= IA ZEDITH =================

import os
import re
import random
import traceback
import google.generativeai as genai
from flask import request, jsonify, session

# ================= CARGA DE LLAVES =================

API_KEYS = []

for i in range(1, 51):
    key = os.environ.get(f'GEMINI_KEY_{i}')
    if key:
        API_KEYS.append(key)

print("===================================")
print(f"LLAVES GEMINI DETECTADAS: {len(API_KEYS)}")
print("===================================")

# ================= PROMPT BASE =================

system_instruction_base = """
Eres Zedith, la asistente ejecutiva de inteligencia artificial de 'Delicious Bread'.

Tu tono es sofisticado, cálido, profesional, seguro y apasionado.

CONOCIMIENTO CORPORATIVO:

1. Render:
Si preguntan por pantalla negra o "render ejecutando", es nuestro servicio de hospedaje web.

2. Seguridad:
La navegación está protegida por ZCAWS, del grupo ZMARTH.

3. Creador:
Zuriel Zmarth, polímata tecnológico experto en ciberseguridad e IA.

4. CONFIDENCIALIDAD:
Si preguntan cuánto hemos ganado, contraseñas o secretos, responde:

"Lo siento, por protocolos de ciberseguridad esa información es confidencial."
"""

# ================= API CHAT =================

@app.route('/api/chat', methods=['POST'])
def chat_zedith():

    print("\n================ NUEVA CONSULTA ================\n")

    try:
        data = request.json

        print("JSON RECIBIDO:")
        print(data)

        user_message = data.get('message', '').strip()

        print("MENSAJE:")
        print(user_message)

        if not user_message:
            return jsonify({
                "error": "No hay mensaje"
            }), 400

        # ================= HISTORIAL =================

        if 'zedith_historial' not in session:
            session['zedith_historial'] = []
            es_primer_mensaje = True
        else:
            es_primer_mensaje = len(session['zedith_historial']) == 0

        # ================= NOMBRE CLIENTE =================

        nombre_cliente = "Cliente"

        if 'usuario_id' in session:
            # 6. Modificación del endpoint y control preventivo de errores 500
            try:
                usuario = db.session.get(
                    Usuario,
                    session['usuario_id']
                )
                if usuario:
                    nombre_cliente = usuario.nombre
            except Exception as e:
                print(f"Error recuperando usuario (Exception manejada de SQLAlchemy): {e}")
                # 7. Rollback y remoción preventiva en fallos
                db.session.rollback()
                db.session.remove()
                nombre_cliente = "Cliente"

        # ================= PRODUCTOS =================

        try:
            productos_db = Producto.query.all()
            inventario_lista = [
                f"- {p.nombre}: ${p.precio} MXN ({'Disponible' if p.disponible else 'Agotado'})"
                for p in productos_db
            ]
        except Exception as e:
            print(f"Error recuperando productos: {e}")
            db.session.rollback()
            db.session.remove()
            inventario_lista = []

        inventario_texto = "\n".join(inventario_lista)

        # ================= RASTREO DE PEDIDOS =================

        estado_pedido = "El cliente no ha consultado ningún pedido específico."

        codigo_match = re.search(
            r'(DB-[A-Z0-9]{4}|ZCW-EV-[A-Z0-9]{5})',
            user_message,
            re.IGNORECASE
        )

        if codigo_match:

            codigo = codigo_match.group(0).upper()

            try:
                pedido = Pedido.query.filter_by(
                    codigo_recogida=codigo
                ).first()

                if not pedido:
                    pedido = PedidoEspecial.query.filter_by(
                        codigo_recogida=codigo
                    ).first()

                if pedido:
                    estado_pedido = (
                        f"El pedido {codigo} "
                        f"se encuentra en estado: {pedido.estado}"
                    )
                else:
                    estado_pedido = (
                        f"El código {codigo} "
                        f"no existe en la base de datos."
                    )
            except Exception as e:
                print(f"Error rastreando pedido: {e}")
                db.session.rollback()
                db.session.remove()
                estado_pedido = f"No fue posible consultar el estado del código {codigo} temporalmente."

        # ================= HISTORIAL TEXTO =================

        historial_texto = ""

        if session['zedith_historial']:

            historial_texto += "\n[HISTORIAL]\n"

            for msg in session['zedith_historial']:

                historial_texto += (
                    f"{msg['role']}: "
                    f"{msg['content']}\n"
                )

        regla_saludo = (
            f"ESTRICTO: Es el primer mensaje. "
            f"Saluda a {nombre_cliente}."
            if es_primer_mensaje
            else
            "Continúa la conversación normalmente."
        )

        prompt_enriquecido = f"""
{historial_texto}

[DATOS EN TIEMPO REAL]

Cliente: {nombre_cliente}

Estado Pedido:
{estado_pedido}

Catálogo:
{inventario_texto}

[INSTRUCCIÓN]

{regla_saludo}

Cliente:
{user_message}

Zedith:
"""

        print("\n========== PROMPT ==========\n")
        print(prompt_enriquecido[:3000])

        # ================= VALIDACIÓN DE LLAVES =================

        if not API_KEYS:

            print("ERROR: NO SE DETECTARON LLAVES GEMINI")

            return jsonify({
                "reply": "Sistemas IA fuera de línea. No se encontraron llaves."
            }), 500

        llaves_disponibles = API_KEYS.copy()
        random.shuffle(llaves_disponibles)

        intentos_maximos = min(
            3,
            len(llaves_disponibles)
        )

        print(f"INTENTOS MÁXIMOS: {intentos_maximos}")

        # ================= GENERACIÓN =================

        for i in range(intentos_maximos):

            try:

                print(f"\nINTENTO #{i+1}")

                key_actual = llaves_disponibles[i]

                print(
                    f"KEY TERMINA EN: "
                    f"{key_actual[-6:]}"
                )

                genai.configure(
                    api_key=key_actual
                )

                model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    system_instruction=system_instruction_base
                )

                print("ENVIANDO A GEMINI...")

                response = model.generate_content(
                    prompt_enriquecido
                )

                print("RESPUESTA RECIBIDA")

                print(response)

                if not hasattr(response, "text"):

                    print("ERROR: response.text NO EXISTE")

                    continue

                respuesta_texto = response.text.strip()

                print("\nRESPUESTA IA:")
                print(respuesta_texto)

                historial_actual = session['zedith_historial']

                historial_actual.append({
                    "role": "Cliente",
                    "content": user_message
                })

                historial_actual.append({
                    "role": "Zedith",
                    "content": respuesta_texto
                })

                session['zedith_historial'] = historial_actual[-4:]

                session.modified = True

                return jsonify({
                    "reply": respuesta_texto
                })

            except Exception as e:

                print("\n====================================")
                print(f"ERROR EN INTENTO #{i+1}")
                print(type(e).__name__)
                print(str(e))
                print("====================================")

                traceback.print_exc()

                continue

        print("\nTODOS LOS INTENTOS FALLARON\n")

        return jsonify({
            "reply": "Disculpe, mis sistemas de IA están experimentando una incidencia temporal."
        }), 500

    except Exception as e:

        print("\n=========== ERROR GLOBAL ===========")
        traceback.print_exc()
        print("====================================")

        return jsonify({
            "reply": "Se produjo un error interno del sistema."
        }), 500

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        telefono = request.form.get('telefono')
        correo = request.form.get('correo')
        contrasena = request.form.get('contrasena')
        
        existe_usuario = Usuario.query.filter((Usuario.correo == correo) | (Usuario.telefono == telemetry)).first()
        if existe_usuario:
            flash('El correo o teléfono ya se encuentra registrado.', 'error')
            return redirect(url_for('registro'))
            
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
        
        if usuario and check_password_hash(usuario.contrasena, contrasena):
            session.permanent = True
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

@app.route('/', methods=['GET'])
def index():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    usuario = db.session.get(Usuario, session['usuario_id'])
    
    if not usuario:
        session.pop('usuario_id', None)
        return redirect(url_for('login'))
        
    productos = Producto.query.all()
    anuncios = Anuncio.query.filter_by(activo=True).all()
    
    productos_sobrantes = [p for p in productos if p.stock_sobrante > 0]
    
    hoy = datetime.utcnow().date()
    dia_bloqueado = DiaInhabil.query.filter_by(fecha=hoy).first()
    tienda_abierta = False if dia_bloqueado else True
    motivo_cierre = dia_bloqueado.motivo if dia_bloqueado else ""
    
    return render_template('index.html', 
                           productos=productos, 
                           productos_sobrantes=productos_sobrantes,
                           anuncios=anuncios,
                           usuario=usuario, 
                           nombre_usuario=usuario.nombre,
                           tienda_abierta=tienda_abierta,
                           motivo_cierre=motivo_cierre)

@app.route('/procesar_pedido', methods=['POST'])
def procesar_pedido():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    hoy = datetime.utcnow().date()
    if DiaInhabil.query.filter_by(fecha=hoy).first():
        flash('La boutique está cerrada el día de hoy. No es posible procesar el pedido.', 'error')
        return redirect(url_for('index'))
        
    usuario = db.session.get(Usuario, session['usuario_id'])
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

@app.route('/procesar_sobrante', methods=['POST'])
def procesar_sobrante():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    usuario = db.session.get(Usuario, session['usuario_id'])
    producto_id = request.form.get('producto_id')
    cantidad_solicitada = int(request.form.get('canvas_cantidad', 1))
    horario = request.form.get('horario', 'Inmediato')
    metodo_pago = request.form.get('metodo_pago', 'Efectivo')
    
    producto = db.session.get(Producto, producto_id)
    
    if not producto or producto.stock_sobrante < cantidad_solicitada:
        flash('Lo sentimos, las piezas solicitadas ya han sido adquiridas por otro cliente.', 'error')
        return redirect(url_for('index'))
    
    producto.stock_sobrante -= cantidad_solicitada
    monto_total = producto.precio * cantidad_solicitada
    
    nuevo_pedido = Pedido(
        usuario_id=usuario.id,
        horario_recogida=horario,
        metodo_pago=metodo_pago,
        monto_total=monto_total,
        codigo_recogida=generar_codigo(),
        estado='Venta Flash Excedente'
    )
    db.session.add(nuevo_pedido)
    db.session.commit()
    
    detalle = DetallePedido(pedido_id=nuevo_pedido.id, producto_id=producto.id, cantidad=cantidad_solicitada)
    db.session.add(detalle)
    db.session.commit()
    
    try:
        asunto = f"Ticket de Producto Excedente - {nuevo_pedido.codigo_recogida}"
        msg = Message(asunto, recipients=[usuario.correo])
        msg.html = render_template('correo_ticket.html', pedido=nuevo_pedido, usuario=usuario, detalles=[detalle])
        mail.send(msg)
        flash('¡Adquisición relámpago completada! Ticket enviado.', 'success')
    except Exception as e:
        print(f"Error correo venta flash: {e}")
        flash('Adquisición procesada, error al despachar la notificación por correo.', 'warning')
        
    return redirect(url_for('perfil'))

@app.route('/perfil')
def perfil():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    usuario = db.session.get(Usuario, session['usuario_id'])
    mis_pedidos = Pedido.query.filter_by(usuario_id=usuario.id).order_by(Pedido.fecha_pedido.desc()).all()
    mis_especiales = PedidoEspecial.query.filter_by(correo_contacto=usuario.correo).order_by(PedidoEspecial.fecha_creacion.desc()).all()
    
    return render_template('perfil.html', usuario=usuario, pedidos=mis_pedidos, especiales=mis_especiales)

@app.route('/pedido_especial', methods=['GET', 'POST'])
def pedido_especial():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        telefono = request.form.get('telefono')
        correo = request.form.get('correo')
        metodo_entrega = request.form.get('metodo_entrega')  
        fecha_evento = request.form.get('fecha_evento')
        
        direccion = request.form.get('direccion')
        numero_casa = request.form.get('numero_casa')
        referencias = request.form.get('referencias')
        lat = request.form.get('latitud')
        lng = request.form.get('longitud')
        
        productos = Producto.query.all()
        monto_total = 0
        detalles_especiales = []
        
        for prod in productos:
            cant = request.form.get(f'cantidad_especial_{prod.id}', 0)
            if cant and int(cant) > 0:
                cantidad = int(cant)
                monto_total += prod.precio * float(cantidad)
                detalles_especiales.append(DetallePedidoEspecial(producto_id=prod.id, cantidad=cantidad))
                
        if not detalles_especiales:
            flash('Debe seleccionar al menos un producto para cotizar su evento.', 'error')
            return redirect(url_for('pedido_especial'))
            
        monto_anticipo = monto_total * 0.50
        
        file = request.files.get('comprobante_pago')
        comprobante_url = None
        if file and file.filename != '':
            comprobante_url = subir_a_cloudinary(file)
            
        nuevo_especial = PedidoEspecial(
            nombre_contacto=nombre,
            telefono_contacto=telefono,
            correo_contacto=correo,
            metodo_entrega=metodo_entrega,
            direccion_texto=direccion,
            numero_casa=numero_casa,
            referencias=referencias,
            latitud=float(lat) if lat else None,
            longitud=float(lng) if lng else None,
            monto_total=monto_total,
            monto_anticipo=monto_anticipo,
            comprobante_url=comprobante_url,
            codigo_recogida=generar_codigo_especial(),
            fecha_evento=fecha_evento
        )
        db.session.add(nuevo_especial)
        db.session.commit()
        
        for det in detalles_especiales:
            det.pedido_especial_id = nuevo_especial.id
            db.session.add(det)
        db.session.commit()
        
        try:
            asunto = f"Cotización de Orden Especial Recibida - {nuevo_especial.codigo_recogida}"
            cuerpo = f"""
            <h2>Ecosistema Zmarth - Confirmación de Recepción</h2>
            <p>Hola {nombre}, hemos registrado tu solicitud de pedido especial para el día {fecha_evento}.</p>
            <p><strong>Código de Seguimiento:</strong> {nuevo_especial.codigo_recogida}</p>
            <p><strong>Monto Total:</strong> ${monto_total:,.2f} MXN</p>
            <p><strong>Anticipo Requerido (50%):</strong> ${monto_anticipo:,.2f} MXN</p>
            <p>Tu comprobante está siendo evaluado manualmente en nuestro Atelier Administrativo. Te notificaremos vía correo en cuanto la producción sea iniciada.</p>
            """
            msg = Message(asunto, recipients=[correo])
            msg.html = cuerpo
            mail.send(msg)
            flash('Solicitud de evento enviada. El comprobante está bajo verificación manual.', 'success')
        except Exception as e:
            print(f"Error correo orden especial: {e}")
            flash('Solicitud guardada con éxito, pero la notificación por correo falló.', 'warning')
            
        return redirect(url_for('index'))
        
    productos = Producto.query.all()
    return render_template('pedido_especial.html', productos=productos)

# ================= PANEL ADMINISTRATIVO EXPANDIDO =================

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
        stock_sob = int(request.form.get('stock_sobrante', 0))
        
        file = request.files.get('imagen_file')
        imagen_url = None
        
        if file and file.filename != '':
            imagen_url = subir_a_cloudinary(file)
        
        nuevo_prod = Producto(nombre=nombre, descripcion=descripcion, precio=precio, imagen_url=imagen_url, stock_sobrante=stock_sob)
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
    dias_bloqueados_lista = DiaInhabil.query.order_by(DiaInhabil.fecha.asc()).all()
    
    anuncios_lista = Anuncio.query.all()
    pedidos_especiales_lista = PedidoEspecial.query.order_by(PedidoEspecial.fecha_creacion.desc()).all()

    return render_template('admin.html', 
                           pedidos_activos=pedidos_activos, 
                           pedidos_entregados=pedidos_entregados,
                           produccion=produccion_total,
                           productos=productos,
                           filtro_actual=filtro,
                           dias_bloqueados_lista=dias_bloqueados_lista,
                           anuncios_lista=anuncios_lista,
                           pedidos_especiales_lista=pedidos_especiales_lista)

@app.route('/admin/anuncio/nuevo', methods=['POST'])
def nuevo_anuncio():
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    titulo = request.form.get('titulo')
    enlace = request.form.get('enlace_destino')
    file = request.files.get('anuncio_file')
    
    if file and file.filename != '':
        img_url = subir_a_cloudinary(file)
        if img_url:
            ad = Anuncio(titulo=titulo, imagen_url=img_url, enlace_destino=enlace)
            db.session.add(ad)
            db.session.commit()
            flash('Anuncio publicitario integrado exitosamente.', 'success')
        else:
            flash('Hubo un error al procesar la imagen del anuncio.', 'error')
            
    return redirect(url_for('admin'))

@app.route('/admin/pedido_especial/<int:pedido_id>/validar', methods=['POST'])
def validar_anticipo_especial(pedido_id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    especial = PedidoEspecial.query.get_or_404(pedido_id)
    accion = request.form.get('accion')  
    
    if accion == 'aprobar':
        especial.anticipo_validado = True
        especial.estado = 'En Producción'
        db.session.commit()
        
        try:
            asunto = f"¡Producción Iniciada! Anticipo Validado - {especial.codigo_recogida}"
            cuerpo = f"""
            <div style="background-color: #0A0A0A; padding: 30px; font-family: Arial, sans-serif; text-align: center;">
                <div style="background-color: #1A1A1A; max-width: 550px; margin: 0 auto; padding: 30px; border-radius: 12px; border: 1px solid #333; text-align: left;">
                    <h2 style="color: #E8D8C8; text-align: center;">Anticipo Verificado</h2>
                    <p style="color: #CCC;">Hola <strong>{especial.nombre_contacto}</strong>,</p>
                    <p style="color: #CCC;">Hemos verificado con éxito tu depósito del 50% correspondiente a <strong>${especial.monto_anticipo:,.2f} MXN</strong>.</p>
                    <p style="color: #E8D8C8; font-size: 16px; font-weight: bold; text-align: center; background: #222; padding: 10px; border-radius: 6px;">
                        Estado de tu orden: COMENZAR A TRABAJAR PEDIDO
                    </p>
                    <p style="color: #AAA; font-size: 14px;">Tu entrega bajo modalidad <strong>{especial.metodo_entrega}</strong> está agendada para la fecha estipulada.</p>
                    <hr style="border: none; border-top: 1px solid #333; margin: 20px 0;">
                    <p style="font-size: 11px; color: #666; text-align: center;">ZMARTH CREATIVE SERVICES — DELICIOUS BREAD ATELIER</p>
                </div>
            </div>
            """
            msg = Message(asunto, recipients=[especial.correo_contacto])
            msg.html = cuerpo
            mail.send(msg)
            flash('Anticipo aprobado y orden enviada a la línea de producción.', 'success')
        except Exception as e:
            print(f"Error despachando correo de producción: {e}")
            flash('Orden actualizada a producción, pero falló la notificación por correo.', 'warning')
            
    elif accion == 'completar':
        especial.estado = 'Entregado'
        db.session.commit()
        flash('Pedido Especial marcado como entregado de manera definitiva.', 'success')
        
    return redirect(url_for('admin'))

@app.route('/admin/pedido/<int:pedido_id>/estado', methods=['POST'])
def actualizar_estado(pedido_id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido:
        nuevo_estado = request.form.get('estado')
        pedido.estado = nuevo_estado
        db.session.commit()

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

@app.route('/admin/eliminar_producto/<int:producto_id>', methods=['POST'])
def eliminar_producto(producto_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    producto = Producto.query.get_or_404(producto_id)
    tiene_ventas = DetallePedido.query.filter_by(producto_id=producto_id).first()
    
    if tiene_ventas:
        producto.disponible = False
        db.session.commit()
        flash('El producto tenía ventas registradas, así que se ha PAUSADO automáticamente para mantener tu historial.', 'warning')
    else:
        try:
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
    producto.stock_sobrante = int(request.form.get('stock_sobrante', 0))
    
    file = request.files.get('imagen_file')
    if file and file.filename != '':
        nueva_imagen_url = subir_a_cloudinary(file)
        if nueva_imagen_url:
            producto.imagen_url = nueva_imagen_url
        
    db.session.commit()
    return redirect(url_for('admin'))

# ================= SUBIDA DE COMPROBANTES (TIENDA REGULAR) =================
@app.route('/subir_comprobante/<int:pedido_id>', methods=['POST'])
def subir_comprobante(pedido_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    pedido = Pedido.query.get_or_404(pedido_id)
    
    if pedido.usuario_id != session['usuario_id']:
        flash('Acceso denegado.', 'error')
        return redirect(url_for('perfil'))
        
    file = request.files.get('comprobante_pago')
    if file and file.filename != '':
        url_nube = subir_a_cloudinary(file)
        
        if url_nube:
            pedido.comprobante_url = url_nube
            db.session.commit()
            flash('Comprobante anexado exitosamente. Entrará a revisión.', 'success')
        else:
            flash('Hubo un error al procesar el comprobante.', 'error')
        
    return redirect(url_for('perfil'))

# ================= CIBERSEGURIDAD BÓVEDA DE USUARIOS =================
@app.route('/admin/api/usuarios', methods=['POST'])
def obtener_usuarios_seguros():
    if not session.get('admin_logged_in'): return jsonify({"error": "No autorizado"}), 403
    
    data = request.json
    pin_ingresado = data.get('pin', '')
    PIN_MAESTRO = "ZMARTH-007" 
    
    if pin_ingresado != PIN_MAESTRO:
        return jsonify({"error": "PIN Inválido. Protocolo de intrusión activado."}), 401
        
    usuarios = Usuario.query.all()
    lista_usuarios = [{"id": u.id, "nombre": u.nombre, "correo": u.correo, "telefono": u.telefono, "hash": u.contrasena[:15]+"..."} for u in usuarios]
    return jsonify({"usuarios": lista_usuarios})

# ================= DIAGNÓSTICO E INICIALIZACIÓN DE CONTEXTO =================
with app.app_context():
    try:
        db.create_all()
        print("====== DIAGNÓSTICO DE BASE DE DATOS ======\n¡ÉXITO! Tablas listas.")
        verificar_db()
    except Exception as e:
        print(f"❌ ERROR CRÍTICO AL CREAR TABLAS: {e}")

# 8. Corregir la inicialización final del servidor para Flask-SocketIO
if __name__ == '__main__':
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=True
    )