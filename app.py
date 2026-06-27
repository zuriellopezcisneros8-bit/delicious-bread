import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

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
    categoria = db.Column(db.String(50), default='pan')
    stock_tienda = db.Column(db.Integer, nullable=True, default=None)

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
    es_relampago = db.Column(db.Boolean, default=False)
    pagado = db.Column(db.Boolean, default=False)
# === DENTRO DE CLASS PEDIDO ===
    @property
    def tipo_pedido(self):
        if not self.detalles:
            return 'puros_abarrotes'

        tiene_pan = False
        tiene_abarrotes = False

        for detalle in self.detalles:
            if detalle.producto:
                # Protegemos el código: si la categoría es None (vieja), asume 'pan'
                categoria_segura = detalle.producto.categoria.lower() if detalle.producto.categoria else 'pan'

                if categoria_segura == 'pan':
                    tiene_pan = True
                else:
                    tiene_abarrotes = True

        if tiene_pan and tiene_abarrotes:
            return 'combinado'
        elif tiene_pan:
            return 'puro_pan'
        else:
            return 'puros_abarrotes'
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
La navegación está protegida por ZCAWS que significa ZMARTH CIBERSECURITY AND ADVANCED WEB SERVICES la cual tambien es una compañia nuestra, del grupo ZMARTH.

3. Creador:
Zuriel Zmarth, polímata tecnológico experto en ciberseguridad software, biotecnologia e IA.

4. CONFIDENCIALIDAD:
Si preguntan cuánto hemos ganado, contraseñas o secretos, responde:

"Lo siento, por protocolos de ciberseguridad esa información es confidencial.

5. Asesor Humano
Si alguien quiere hablar con un humano o un asesor no virtual solo si el usurio lo pide le dices que para hablar con un humano se comunique solamente via whatsApp al numero "4428534583"

6.​Instrucciones de Funcionamiento: Sistema de Pedidos "Delicious Bread"
​Horario de Pedidos: El sistema de pedidos está habilitado diariamente desde la 1:00 AM hasta las 4:00 PM.
​Bloqueo del Sistema: Al llegar las 4:00 PM, el sistema bloquea automáticamente la selección de artículos, impidiendo la creación de nuevos pedidos. Si el botón de selección está deshabilitado, indica que se encuentra fuera del horario de operación.
​Venta de Excedentes: Si al finalizar el horario principal existen productos sobrantes, el sistema se reactiva a partir de las 5:00 PM, permitiendo realizar pedidos sobre el inventario restante.
​Proceso de Pago y Validación: El método de pago es mediante transferencia bancaria o en efectivo en tienda. Para completar el proceso, es obligatorio presentar el comprobante de pago (ticket) en la tienda al momento de recoger los productos.
​Recogida de Pedidos: Los horarios de recogida inician a las 5:00 PM, asegurando que el pan esté recién horneado y caliente. Los clientes pueden seleccionar su horario de recogida dentro del rango de 5:00 PM a 7:00 PM.
​Recomendación de Calidad: Se recomienda acudir puntualmente a recoger el pedido dentro del horario establecido, ya que después de las 6:00 PM o 7:00 PM el pan pierde su temperatura original y ya no se encuentra recién hecho.

7. DELIVERY
Instrucción de Atención al Cliente: Políticas de Entrega
​Método Actual: Actualmente, el único método de entrega habilitado es el pick-up (recogida en tienda). Es indispensable que el cliente presente su número o código de pedido para retirar sus productos.
​Protocolo ante Solicitudes de Delivery: Si un usuario consulta por servicios de entrega a domicilio, se debe informar de manera directa que el servicio no se encuentra disponible bajo esa modalidad actualmente.
​Proyecto Futuro - Drones (ZCAWS Technologies): Para clientes interesados en innovaciones futuras, se debe explicar que estamos desarrollando un sistema de drones autónomos de última generación, bajo la dirección y respaldo de ZCWS Technologies. Este sistema integrará inteligencia artificial avanzada para las entregas, sin embargo, el proyecto continúa en fase de investigación y desarrollo, por lo que su implementación tomará tiempo.
​Posibilidad de Logística Humana: Es posible mencionar que estamos evaluando la probabilidad de integrar una red de repartidores humanos para las entregas a domicilio. No obstante, es fundamental aclarar que esta opción no es oficial ni está confirmada, ya que permanece bajo análisis.
​Prioridad de Comunicación: El desarrollo oficial y confirmado por la organización es el sistema de drones autónomos; cualquier otra modalidad de entrega debe ser tratada como una posibilidad no garantizada, cualquier cambio o actualizacion se avisara por anuncio dentro de la app.

8. UBICACION
Estamos ubicados en el nuevo desarrollo de casas, en la calle venustiano carranza #64 

9. Contexto Operativo para Zedith: Gestión de "Adquisición Relámpago"
​Como asistente de 'Delicious Bread', debes gestionar las solicitudes de disponibilidad inmediata basándote estrictamente en el estado de la Adquisición Relámpago. Utiliza los siguientes parámetros para guiar al cliente:
​El Significado (Disponibilidad Inmediata): La "Adquisición Relámpago" significa una sola cosa: hay producto listo para entrega inmediata en la boutique. Cuando esta opción se activa en el sistema, aparecerá un indicador con el número exacto de unidades disponibles en tiempo real (por ejemplo: "12 unidades" o "1 unidad").
​El Origen (¿Por qué hay stock extra?): Si el cliente pregunta, explícale que, para garantizar la perfección en nuestra producción artesanal, siempre horneamos un margen adicional de seguridad. Por ejemplo, si tenemos 90 pedidos programados, horneamos 100 piezas. Esas piezas excedentes de calidad premium son las que se liberan en esta modalidad.
​Horarios de Activación (Impredecibles): Aunque es muy común que esta ventana se active en la recta final del día (a partir de las 5:00 p.m. hasta las 7:00 p.m. o más tarde), la Adquisición Relámpago puede aparecer a cualquier hora del día sin excepción (incluso al mediodía), dependiendo del flujo y excedente de los hornos.
​Protocolo Estricto de Atención (Pedidos al Instante): Si un cliente te contacta buscando realizar un pedido al instante o exige disponibilidad inmediata, tu directiva es la siguiente:
​Verificación: Indícale que revise si la sección de "Adquisición Relámpago" está activa en el sistema.
​Si NO está activa: Infórmale con gran cortesía y firmeza que no hay disponibilidad inmediata en este momento. En este escenario, la única manera de adquirir nuestros productos es realizando un pedido anticipado (pre-orden) en los horarios regulares de recepción.
​Si SÍ está activa: Anímalo a proceder con la compra y el pago de manera inmediata para asegurar sus piezas, recordándole que el inventario se muestra en tiempo real y, al ser excedente limitado, se agota rápidamente.

10. ​Debes actuar como embajadora de la visión tecnológica de The Zmarth Organization. Si surge el tema o si un cliente muestra interés en tecnología avanzada, soluciones de software o necesidades de compras digitales, infórmale sobre nuestras dos grandes divisiones en desarrollo:
​Smart Market (Plataforma E-commerce Avanzada):
​Visión: Explica que estamos construyendo una plataforma integral tipo "Amazon" diseñada para el mercado moderno, enfocada en la distribución de productos de primera necesidad, incluyendo abarrotes, cremería y salchichonería.
​Innovación: Destaca que el sistema integrará tecnología de entrega con drones de inteligencia artificial, alineándonos con las tendencias globales de logística de última milla.
​Estado: Informa que el sistema está actualmente en desarrollo y que proyectamos el inicio de operaciones en los próximos meses.
​ZCAWS Technologies (División de Desarrollo y Ciberseguridad):
​Alcance: Somos la compañía detrás de la tecnología que el cliente está presenciando. Desarrollamos software a medida, aplicaciones, sistemas de ciberseguridad robustos y puntos de venta especializados.
​Servicio: Si un cliente pregunta quién creó nuestros sistemas o muestra interés en adquirir soluciones tecnológicas para sus propios proyectos, explícale que somos una empresa especializada en servicios web digitales, ciberseguridad de alto nivel y desarrollo de software.
​Protocolo de Contacto (Call to Action):
​Para cualquier duda, interés en alianzas, o solicitud de información sobre nuestros servicios de desarrollo (software o ciberseguridad), redirige al cliente directamente al canal oficial:
​WhatsApp: 4427972122.
​Tono: Mantén siempre un discurso visionario, profesional y seguro. Somos una compañía joven, pero altamente avanzada en el ecosistema digital.
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
                    model_name="gemini-2.5-flash",
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

# --- CÓDIGO CORREGIDO ---
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        telefono = request.form.get('telefono')
        correo = request.form.get('correo')
        contrasena = request.form.get('contrasena')
        
        # ERROR DETECTADO AQUÍ: 'telemetry' no existe, debe ser 'telefono'
        existe_usuario = Usuario.query.filter((Usuario.correo == correo) | (Usuario.telefono == telefono)).first()
        
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



from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from flask_socketio import SocketIO, emit
import random
import string
import os
import re
from datetime import datetime, timedelta

# (Las configuraciones iniciales de Cloudinary, DB, Mail y SocketIO se mantienen en la parte superior de su archivo)



@app.route('/perfil')
def perfil():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    usuario = db.session.get(Usuario, session['usuario_id'])
    mis_pedidos = Pedido.query.filter_by(usuario_id=usuario.id).order_by(Pedido.fecha_pedido.desc()).all()
    mis_especiales = PedidoEspecial.query.filter_by(correo_contacto=usuario.correo).order_by(PedidoEspecial.fecha_creacion.desc()).all()
    
    return render_template('perfil.html', usuario=usuario, pedidos=mis_pedidos, especiales=mis_especiales)



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

def cancelar_pedidos_vencidos():
    """
    Escanea pedidos activos y revoca automáticamente aquellos que superen 
    el margen de tolerancia de 1 hora respecto a la hora acordada de retiro.
    """
    pedidos_activos = Pedido.query.filter(Pedido.estado.notin_(['Entregado', 'Cancelado', 'Venta Flash Excedente'])).all()
    cambio_detectado = False
    
    for p in pedidos_activos:
        try:
            horario_str = p.horario_recogida.strip()
            if horario_str == 'Inmediato':
                continue
            
            try:
                hora_dt = datetime.strptime(horario_str, "%I:%M %p").time()
            except ValueError:
                hora_dt = datetime.strptime(horario_str, "%H:%M").time()
                
            fecha_base = p.fecha_pedido.date()
            fecha_hora_recogida_local = datetime.combine(fecha_base, hora_dt)
            
            # Cálculo exacto basado en la zona horaria de la sucursal (UTC -6)
            hora_actual_local = datetime.utcnow() - timedelta(hours=6)
            
            if hora_actual_local > fecha_hora_recogida_local + timedelta(hours=1):
                p.estado = 'Cancelado'
                cambio_detectado = True
                # Reincorporación automática de mercancía al stock de ofertas de oportunidad
                for detalle in p.detalles:
                    prod = db.session.get(Producto, detalle.producto_id)
                    if prod:
                        prod.stock_sobrante += detalle.cantidad
        except Exception as e:
            print(f"Error procesando el motor de expiración para pedido {p.id}: {e}")
            
    if cambio_detectado:
        db.session.commit()
        socketio.emit('actualizacion_global')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    # Ejecución sistemática del motor de limpieza temporal de pedidos
    cancelar_pedidos_vencidos()

    if request.method == 'POST' and 'nuevo_producto' in request.form:
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        precio = float(request.form.get('precio'))
        stock_sob = int(request.form.get('stock_sobrante', 0))
        categoria = request.form.get('categoria', 'pan')
        
        # === CAPTURA DE STOCK DE TIENDA ===
        stock_tienda_form = request.form.get('stock_tienda')
        # Si envían el campo vacío, se guarda como None (infinito, usado para el pan)
        stock_tienda_val = int(stock_tienda_form) if stock_tienda_form and stock_tienda_form.strip() else None
        
        file = request.files.get('imagen_file')
        imagen_url = None
        
        if file and file.filename != '':
            imagen_url = subir_a_cloudinary(file)

        nuevo_prod = Producto(
            nombre=nombre, 
            descripcion=descripcion, 
            precio=precio, 
            imagen_url=imagen_url, 
            stock_sobrante=stock_sob, 
            categoria=categoria,
            stock_tienda=stock_tienda_val
        )
        db.session.add(nuevo_prod)
        db.session.commit()
        
        socketio.emit('actualizacion_global')
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
        if detalle.producto: 
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

@app.route('/admin/anuncio/eliminar/<int:anuncio_id>', methods=['POST'])
def eliminar_anuncio(anuncio_id):
    if not session.get('admin_logged_in'): 
        return redirect(url_for('admin_login'))
    
    ad = db.session.get(Anuncio, anuncio_id)
    if ad:
        db.session.delete(ad)
        db.session.commit()
        flash('Anuncio publicitario removido con éxito.', 'success')
    else:
        flash('El anuncio especificado no pudo ser localizado.', 'error')
        
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
    
   
    socketio.emit('actualizacion_global')
    
    flash(f'El estado del producto fue actualizado exitosamente.', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/eliminar_producto/<int:producto_id>', methods=['POST'])
def eliminar_producto(producto_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    producto = Producto.query.get_or_404(producto_id)
    tiene_ventas = DetallePedido.query.filter_by(producto_id=producto_id).first()
    
    if tiene_ventas:
        # Si tiene ventas, el sistema lo protege y lo pausa. 
        # Aseguramos que no cambie su categoría original.
        producto.disponible = False
        db.session.commit()
        socketio.emit('actualizacion_global')
        flash('El producto tenía ventas registradas, así que se ha PAUSADO automáticamente para mantener tu historial. Su categoría original se mantiene intacta.', 'warning')
    else:
        try:
            db.session.delete(producto)
            db.session.commit()
            socketio.emit('actualizacion_global')
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
    
    # === ACTUALIZACIÓN DE STOCK DE TIENDA ===
    stock_tienda_form = request.form.get('stock_tienda')
    producto.stock_tienda = int(stock_tienda_form) if stock_tienda_form and stock_tienda_form.strip() else None
    
    categoria_form = request.form.get('categoria')
    if categoria_form:
        producto.categoria = categoria_form
    
    file = request.files.get('imagen_file')
    if file and file.filename != '':
        nueva_imagen_url = subir_a_cloudinary(file)
        if nueva_imagen_url:
            producto.imagen_url = nueva_imagen_url
        
    db.session.commit()
    socketio.emit('actualizacion_global')
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


@app.route('/procesar_sobrante', methods=['POST'])
def procesar_sobrante():
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'error': 'No autorizado. Inicie sesión.'}), 401
        
    usuario = db.session.get(Usuario, session['usuario_id'])
    
    # Soporte para estructurar la petición tanto por JSON asíncrono como por formularios tradicionales
    if request.is_json:
        data = request.get_json()
        producto_id = data.get('producto_id')
        cantidad_solicitada = int(data.get('cantidad', 1))
        horario = data.get('horario', 'Inmediato')
        metodo_pago = data.get('metodo_pago', 'Efectivo') # Máximo de seguridad de 20 caracteres
    else:
        producto_id = request.form.get('producto_id')
        cantidad_solicitada = int(request.form.get('canvas_cantidad', 1))
        horario = request.form.get('horario', 'Inmediato')
        metodo_pago = request.form.get('metodo_pago', 'Efectivo')
    
    producto = db.session.get(Producto, producto_id)
    
    if not producto or producto.stock_sobrante < cantidad_solicitada:
        return jsonify({'success': False, 'error': 'Lo sentimos, las piezas solicitadas ya han sido adquiridas por otro cliente.'})
    
    producto.stock_sobrante -= cantidad_solicitada
    monto_total = producto.precio * cantidad_solicitada
    
    nuevo_pedido = Pedido(
        usuario_id=usuario.id,
        horario_recogida=horario,
        metodo_pago=metodo_pago,
        monto_total=monto_total,
        codigo_recogida=generar_codigo(),
        estado='Venta Flash Excedente',
        es_relampago=True
    )
    db.session.add(nuevo_pedido)
    db.session.commit()
    
    detalle = DetallePedido(pedido_id=nuevo_pedido.id, producto_id=producto.id, cantidad=cantidad_solicitada)
    db.session.add(detalle)
    db.session.commit()
    
    # Sincronización global inmediata del stock remanente mediante WebSockets
    socketio.emit('actualizacion_global')
    
    return jsonify({
        'success': True,
        'codigo': nuevo_pedido.codigo_recogida,
        'mensaje': 'Adquisición Relámpago completada de forma exitosa. Puede pasar a la boutique a retirar su orden.'
    })


@app.route('/procesar_pedido', methods=['POST'])
def procesar_pedido():
    # 1. Validación de sesión
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
        
    # 2. Validación de día inhábil
    hoy = datetime.utcnow().date()
    if DiaInhabil.query.filter_by(fecha=hoy).first():
        return jsonify({'success': False, 'message': 'La boutique está cerrada hoy.'}), 403
        
    usuario = db.session.get(Usuario, session['usuario_id'])
    horario = request.form.get('horario')
    metodo_pago = request.form.get('metodo_pago')
    
    # === OBTENER HORA LOCAL (UTC - 6) ===
    hora_actual_local = (datetime.utcnow() - timedelta(hours=6)).hour

    productos = Producto.query.all()
    monto_total = 0
    detalles_a_crear = []
    
    # 3. Procesamiento y validación estricta por categoría
    for prod in productos:
        cant = request.form.get(f'cantidad_{prod.id}', 0)
        if cant and int(cant) > 0:
            cantidad = int(cant)

            categoria_segura = prod.categoria.lower() if prod.categoria else 'pan'
            es_tienda = categoria_segura != 'pan'
            
            # === REGLA 1: BLOQUEO EXCLUSIVO PARA PAN DESPUÉS DE LAS 4 PM ===
            if not es_tienda and (hora_actual_local >= 16 or hora_actual_local < 1):
                return jsonify({
                    'success': False, 
                    'message': f'La recepción de {prod.nombre} ha cerrado por hoy. Solo artículos de tienda están disponibles.'
                }), 400

            # === REGLA 2: CONTROL DE STOCK EXCLUSIVO PARA TIENDA ===
            if es_tienda and prod.stock_tienda is not None:
                # Validar que no pidan más de lo que hay
                if cantidad > prod.stock_tienda:
                    return jsonify({
                        'success': False, 
                        'message': f'Inventario insuficiente para {prod.nombre}. Solo quedan {prod.stock_tienda} unidades en Atelier.'
                    }), 400
                
                # Restar el stock provisionalmente
                prod.stock_tienda -= cantidad
                
                # Si el stock llega a 0, inhabilitar automáticamente
                if prod.stock_tienda <= 0:
                    prod.stock_tienda = 0
                    prod.disponible = False

            monto_total += prod.precio * float(cantidad)
            detalle = DetallePedido(producto_id=prod.id, cantidad=cantidad)
            detalles_a_crear.append(detalle)
            
    # 4. Creación del pedido
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
        
        # 5. Asignación de detalles
        for d in detalles_a_crear:
            d.pedido_id = nuevo_pedido.id
            db.session.add(d)
        db.session.commit()
        
        # ---> SINCRONIZACIÓN EN TIEMPO REAL ZMARTHNET <---
        socketio.emit('actualizacion_global')
        
        return jsonify({
            'success': True,
            'codigo': nuevo_pedido.codigo_recogida
        })

    return jsonify({'success': False, 'message': 'Pedido vacío'}), 400


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
        
        # ---> SINCRONIZACIÓN EN TIEMPO REAL ZMARTHNET <---
        socketio.emit('actualizacion_global')
        
        flash('Solicitud de evento enviada. El comprobante está bajo verificación manual.', 'success')
        return redirect(url_for('index'))
        
    productos = Producto.query.all()
    return render_template('pedido_especial.html', productos=productos)

@app.route('/admin/pedido/<int:pedido_id>/estado', methods=['POST'])
def actualizar_estado(pedido_id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido:
        nuevo_estado = request.form.get('estado')
        pedido.estado = nuevo_estado
        db.session.commit()

        # ---> SINCRONIZACIÓN EN TIEMPO REAL ZMARTHNET <---
        socketio.emit('actualizacion_global')

    return redirect(url_for('admin'))


@app.route('/admin/pedido/<int:pedido_id>/pagar', methods=['POST'])
def marcar_pagar_pedido(pedido_id):
    if not session.get('admin_logged_in'): 
        return redirect(url_for('admin_login'))
    
    pedido = Pedido.query.get_or_404(pedido_id)
    # Cambiamos el estado a pagado
    pedido.pagado = True
    db.session.commit()

    # Sincronización inmediata con ZMARTHNET
    socketio.emit('actualizacion_global')

    return redirect(url_for('admin'))

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