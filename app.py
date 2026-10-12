import os
import math
import time
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ============================================================
# CONFIGURACION
# ============================================================

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "tuauto2026")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
GRAPH_API_VERSION = "v24.0"

# Choferes autorizados para esta prueba
CHOFERES_AUTORIZADOS = {
    "5493446614703": {
        "nombre": "Chofer 1"
    },
    "5493446411551": {
        "nombre": "Chofer 2"
    }
}

# ============================================================
# MEMORIA TEMPORAL
# Para esta etapa de prueba.
# Luego se reemplaza por una base de datos persistente.
# ============================================================

clientes = {}
viajes = {}
contador_viajes = 1

choferes = {}

for numero, datos in CHOFERES_AUTORIZADOS.items():
    choferes[numero] = {
        "numero": numero,
        "nombre": datos["nombre"],
        "activo": False,
        "estado": "DESCONECTADO",
        "latitud": None,
        "longitud": None,
        "viaje_actual": None,
        "ultima_actualizacion": None
    }


# ============================================================
# UTILIDADES
# ============================================================

def ahora():
    return int(time.time())


def distancia_km(lat1, lon1, lat2, lon2):
    """
    Calcula distancia aproximada entre dos coordenadas
    utilizando la formula de Haversine.
    """

    radio_tierra = 6371.0

    lat1 = math.radians(float(lat1))
    lon1 = math.radians(float(lon1))
    lat2 = math.radians(float(lat2))
    lon2 = math.radians(float(lon2))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return radio_tierra * c


def obtener_choferes_disponibles(origen):
    disponibles = []

    if not origen:
        return disponibles

    lat_cliente = origen.get("latitud")
    lon_cliente = origen.get("longitud")

    if lat_cliente is None or lon_cliente is None:
        return disponibles

    for numero, chofer in choferes.items():

        if not chofer["activo"]:
            continue

        if chofer["estado"] != "DISPONIBLE":
            continue

        if chofer["latitud"] is None or chofer["longitud"] is None:
            continue

        distancia = distancia_km(
            lat_cliente,
            lon_cliente,
            chofer["latitud"],
            chofer["longitud"]
        )

        disponibles.append({
            "numero": numero,
            "nombre": chofer["nombre"],
            "distancia_km": round(distancia, 2)
        })

    disponibles.sort(key=lambda x: x["distancia_km"])

    return disponibles


# ============================================================
# WHATSAPP
# ============================================================

def enviar_mensaje(numero, texto):
    """
    Si WhatsApp/WAIA todavia no esta conectado,
    el motor igualmente funciona.
    """

    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print(f"[SIMULACION MENSAJE] Para {numero}: {texto}")
        return False

    url = (
        f"https://graph.facebook.com/"
        f"{GRAPH_API_VERSION}/"
        f"{PHONE_NUMBER_ID}/messages"
    )

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": numero,
        "type": "text",
        "text": {
            "body": texto
        }
    }

    try:
        respuesta = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=20
        )

        print(
            "WHATSAPP:",
            respuesta.status_code,
            respuesta.text
        )

        return respuesta.ok

    except Exception as error:
        print("ERROR WHATSAPP:", error)
        return False


def pedir_ubicacion(numero):

    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print(
            f"[SIMULACION UBICACION] "
            f"Solicitar ubicacion a {numero}"
        )
        return False

    url = (
        f"https://graph.facebook.com/"
        f"{GRAPH_API_VERSION}/"
        f"{PHONE_NUMBER_ID}/messages"
    )

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "interactive",
        "interactive": {
            "type": "location_request_message",
            "body": {
                "text":
                    "🚗 TU AUTO\n\n"
                    "Para buscarte necesito saber dónde estás.\n\n"
                    "Tocá el botón y compartí tu ubicación."
            },
            "action": {
                "name": "send_location"
            }
        }
    }

    try:
        respuesta = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=20
        )

        print(
            "WHATSAPP UBICACION:",
            respuesta.status_code,
            respuesta.text
        )

        return respuesta.ok

    except Exception as error:
        print("ERROR UBICACION:", error)
        return False


# ============================================================
# MOTOR DE CHOFERES
# ============================================================

def activar_chofer(numero):

    chofer = choferes.get(numero)

    if not chofer:
        return False

    chofer["activo"] = True
    chofer["estado"] = "DISPONIBLE"
    chofer["ultima_actualizacion"] = ahora()

    return True


def desconectar_chofer(numero):

    chofer = choferes.get(numero)

    if not chofer:
        return False

    chofer["activo"] = False
    chofer["estado"] = "DESCONECTADO"
    chofer["viaje_actual"] = None
    chofer["ultima_actualizacion"] = ahora()

    return True


def actualizar_ubicacion_chofer(numero, latitud, longitud):

    chofer = choferes.get(numero)

    if not chofer:
        return False

    chofer["latitud"] = float(latitud)
    chofer["longitud"] = float(longitud)
    chofer["ultima_actualizacion"] = ahora()

    return True


# ============================================================
# MOTOR DE VIAJES
# ============================================================

def crear_viaje(cliente_numero, origen, destino):

    global contador_viajes

    viaje_id = contador_viajes
    contador_viajes += 1

    disponibles = obtener_choferes_disponibles(origen)

    viaje = {
        "id": viaje_id,
        "cliente": cliente_numero,
        "origen": origen,
        "destino": destino,
        "estado": "BUSCANDO_CHOFER",
        "chofer_asignado": None,
        "candidatos": disponibles,
        "indice_candidato": 0,
        "creado": ahora()
    }

    viajes[viaje_id] = viaje

    ofrecer_siguiente_chofer(viaje_id)

    return viaje


def ofrecer_siguiente_chofer(viaje_id):

    viaje = viajes.get(viaje_id)

    if not viaje:
        return False

    candidatos = viaje["candidatos"]
    indice = viaje["indice_candidato"]

    while indice < len(candidatos):

        candidato = candidatos[indice]
        numero = candidato["numero"]

        chofer = choferes.get(numero)

        if (
            chofer
            and chofer["activo"]
            and chofer["estado"] == "DISPONIBLE"
        ):

            viaje["indice_candidato"] = indice
            viaje["chofer_ofrecido"] = numero
            viaje["estado"] = "ESPERANDO_RESPUESTA"

            chofer["estado"] = "OFERTA"
            chofer["viaje_actual"] = viaje_id

            enviar_mensaje(
                numero,
                "🚗 NUEVO VIAJE\n\n"
                f"Viaje #{viaje_id}\n"
                f"Destino: {viaje['destino']}\n"
                f"Distancia al pasajero: "
                f"{candidato['distancia_km']} km\n\n"
                "Respondé:\n"
                "ACEPTAR\n"
                "o\n"
                "RECHAZAR"
            )

            return True

        indice += 1
        viaje["indice_candidato"] = indice

    viaje["estado"] = "SIN_CHOFER"

    return False


def aceptar_viaje(numero):

    chofer = choferes.get(numero)

    if not chofer:
        return False, "Chofer no autorizado"

    viaje_id = chofer.get("viaje_actual")

    if not viaje_id:
        return False, "No tenés viajes pendientes"

    viaje = viajes.get(viaje_id)

    if not viaje:
        return False, "El viaje no existe"

    if viaje.get("chofer_ofrecido") != numero:
        return False, "Este viaje no está ofrecido a este chofer"

    viaje["estado"] = "ASIGNADO"
    viaje["chofer_asignado"] = numero

    chofer["estado"] = "OCUPADO"

    cliente = viaje["cliente"]

    enviar_mensaje(
        cliente,
        "🚗 TU AUTO\n\n"
        f"Chofer asignado: {chofer['nombre']}.\n"
        "Tu vehículo está en camino."
    )

    return True, f"Viaje #{viaje_id} asignado"


def rechazar_viaje(numero):

    chofer = choferes.get(numero)

    if not chofer:
        return False, "Chofer no autorizado"

    viaje_id = chofer.get("viaje_actual")

    if not viaje_id:
        return False, "No tenés viajes pendientes"

    viaje = viajes.get(viaje_id)

    if not viaje:
        return False, "Viaje inexistente"

    chofer["estado"] = "DISPONIBLE"
    chofer["viaje_actual"] = None

    viaje["indice_candidato"] += 1

    ofrecer_siguiente_chofer(viaje_id)

    return True, f"Viaje #{viaje_id} rechazado"


# ============================================================
# PROCESAMIENTO DE WHATSAPP
# ============================================================

def procesar_chofer(numero, mensaje):

    tipo = mensaje.get("type")

    if tipo == "location":

        ubicacion = mensaje.get("location", {})

        lat = ubicacion.get("latitude")
        lon = ubicacion.get("longitude")

        if lat is not None and lon is not None:

            actualizar_ubicacion_chofer(
                numero,
                lat,
                lon
            )

            enviar_mensaje(
                numero,
                "📍 Ubicación del chofer actualizada."
            )

        return

    if tipo != "text":
        return

    texto = (
        mensaje
        .get("text", {})
        .get("body", "")
        .strip()
        .upper()
    )

    if texto == "ACTIVAR":

        activar_chofer(numero)

        enviar_mensaje(
            numero,
            "🟢 Estás ACTIVO y DISPONIBLE.\n\n"
            "Ahora compartí tu ubicación."
        )

        return

    if texto == "DESCONECTAR":

        desconectar_chofer(numero)

        enviar_mensaje(
            numero,
            "🔴 Quedaste DESCONECTADO."
        )

        return

    if texto == "ESTADO":

        chofer = choferes[numero]

        enviar_mensaje(
            numero,
            "🚗 TU AUTO - CHOFER\n\n"
            f"Estado: {chofer['estado']}\n"
            f"Activo: {'Sí' if chofer['activo'] else 'No'}"
        )

        return

    if texto == "ACEPTAR":

        ok, respuesta = aceptar_viaje(numero)
        enviar_mensaje(numero, respuesta)

        return

    if texto == "RECHAZAR":

        ok, respuesta = rechazar_viaje(numero)
        enviar_mensaje(numero, respuesta)

        return

    enviar_mensaje(
        numero,
        "🚗 TU AUTO - CHOFER\n\n"
        "Comandos disponibles:\n"
        "ACTIVAR\n"
        "ESTADO\n"
        "ACEPTAR\n"
        "RECHAZAR\n"
        "DESCONECTAR"
    )


def procesar_cliente(numero, mensaje):

    if numero not in clientes:

        clientes[numero] = {
            "estado": "NUEVO",
            "origen": None,
            "destino": None
        }

    cliente = clientes[numero]

    tipo = mensaje.get("type")

    if tipo == "location":

        ubicacion = mensaje.get("location", {})

        cliente["origen"] = {
            "latitud": ubicacion.get("latitude"),
            "longitud": ubicacion.get("longitude")
        }

        cliente["estado"] = "ESPERANDO_DESTINO"

        enviar_mensaje(
            numero,
            "📍 Ubicación recibida.\n\n"
            "Ahora escribime a dónde querés ir."
        )

        return

    if tipo != "text":
        return

    texto = (
        mensaje
        .get("text", {})
        .get("body", "")
        .strip()
    )

    texto_minuscula = texto.lower()

    if cliente["estado"] == "ESPERANDO_DESTINO":

        cliente["destino"] = texto
        cliente["estado"] = "BUSCANDO_CHOFER"

        enviar_mensaje(
            numero,
            "✅ Pedido recibido.\n\n"
            f"📍 Destino: {texto}\n\n"
            "🚗 Buscando conductor disponible..."
        )

        viaje = crear_viaje(
            numero,
            cliente["origen"],
            texto
        )

        cliente["viaje_id"] = viaje["id"]

        return

    palabras_viaje = [
        "necesito auto",
        "necesito un auto",
        "quiero auto",
        "quiero un auto",
        "pedir auto",
        "pedir un auto",
        "necesito remis",
        "necesito remís"
    ]

    if any(
        palabra in texto_minuscula
        for palabra in palabras_viaje
    ):

        cliente["estado"] = "ESPERANDO_UBICACION"

        enviar_mensaje(
            numero,
            "👋 Hola. Soy el asistente automático de TU AUTO."
        )

        pedir_ubicacion(numero)

        return

    enviar_mensaje(
        numero,
        "🚗 TU AUTO\n\n"
        "Para solicitar un vehículo escribí:\n\n"
        "NECESITO AUTO"
    )


def procesar_mensaje(mensaje):

    numero = mensaje.get("from")

    if not numero:
        return

    # Si es uno de los numeros autorizados,
    # se procesa como chofer.
    if numero in CHOFERES_AUTORIZADOS:
        procesar_chofer(numero, mensaje)
        return

    # Cualquier otro numero se procesa como cliente.
    procesar_cliente(numero, mensaje)


# ============================================================
# RUTAS PRINCIPALES
# ============================================================

@app.route("/", methods=["GET"])
def inicio():

    return jsonify({
        "sistema": "TU AUTO",
        "estado": "ONLINE",
        "motor": "DESPACHO V1",
        "choferes_prueba": len(choferes)
    })


@app.route("/webhook", methods=["GET"])
def verificar_webhook():

    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Error de verificacion", 403


@app.route("/webhook", methods=["POST"])
def recibir_webhook():

    datos = request.get_json(silent=True)

    if not datos:
        return "OK", 200

    try:

        for entrada in datos.get("entry", []):

            for cambio in entrada.get("changes", []):

                valor = cambio.get("value", {})

                for mensaje in valor.get("messages", []):

                    procesar_mensaje(mensaje)

    except Exception as error:

        print("ERROR WEBHOOK:", error)

    return "EVENT_RECEIVED", 200


# ============================================================
# API DE PRUEBA
# NO NECESITA WHATSAPP
# ============================================================

@app.route("/prueba", methods=["GET"])
def prueba():

    return jsonify({
        "ok": True,
        "mensaje": "Motor de TU AUTO funcionando",
        "instrucciones": {
            "ver_choferes": "/prueba/choferes",
            "activar_chofer_1": "/prueba/activar/5493446614703",
            "activar_chofer_2": "/prueba/activar/5493446411551"
        }
    })


@app.route("/prueba/choferes", methods=["GET"])
def prueba_choferes():

    return jsonify(choferes)


@app.route("/prueba/activar/<numero>", methods=["GET"])
def prueba_activar(numero):

    if numero not in choferes:

        return jsonify({
            "ok": False,
            "error": "Chofer no autorizado"
        }), 404

    activar_chofer(numero)

    return jsonify({
        "ok": True,
        "mensaje": "Chofer activado",
        "chofer": choferes[numero]
    })


@app.route("/prueba/desconectar/<numero>", methods=["GET"])
def prueba_desconectar(numero):

    if numero not in choferes:

        return jsonify({
            "ok": False,
            "error": "Chofer no autorizado"
        }), 404

    desconectar_chofer(numero)

    return jsonify({
        "ok": True,
        "mensaje": "Chofer desconectado",
        "chofer": choferes[numero]
    })


@app.route("/prueba/ubicacion/<numero>", methods=["GET"])
def prueba_ubicacion(numero):

    if numero not in choferes:

        return jsonify({
            "ok": False,
            "error": "Chofer no autorizado"
        }), 404

    lat = request.args.get("lat")
    lon = request.args.get("lon")

    if lat is None or lon is None:

        return jsonify({
            "ok": False,
            "error": "Faltan lat y lon"
        }), 400

    actualizar_ubicacion_chofer(
        numero,
        lat,
        lon
    )

    return jsonify({
        "ok": True,
        "mensaje": "Ubicacion actualizada",
        "chofer": choferes[numero]
    })


@app.route("/prueba/viaje", methods=["GET"])
def prueba_viaje():

    lat = request.args.get("lat")
    lon = request.args.get("lon")
    destino = request.args.get(
        "destino",
        "Hospital Bicentenario"
    )

    if lat is None or lon is None:

        return jsonify({
            "ok": False,
            "error": "Faltan lat y lon"
        }), 400

    origen = {
        "latitud": float(lat),
        "longitud": float(lon)
    }

    viaje = crear_viaje(
        "CLIENTE_PRUEBA",
        origen,
        destino
    )

    return jsonify({
        "ok": True,
        "viaje": viaje
    })


@app.route("/prueba/aceptar/<numero>", methods=["GET"])
def prueba_aceptar(numero):

    ok, mensaje = aceptar_viaje(numero)

    return jsonify({
        "ok": ok,
        "mensaje": mensaje
    })


@app.route("/prueba/rechazar/<numero>", methods=["GET"])
def prueba_rechazar(numero):

    ok, mensaje = rechazar_viaje(numero)

    return jsonify({
        "ok": ok,
        "mensaje": mensaje
    })


@app.route("/prueba/viajes", methods=["GET"])
def prueba_ver_viajes():

    return jsonify(viajes)


@app.route("/estado", methods=["GET"])
def estado_general():

    return jsonify({
        "sistema": "TU AUTO",
        "choferes": choferes,
        "viajes": viajes,
        "clientes": clientes
    })


# ============================================================
# INICIO
# ============================================================

if __name__ == "__main__":

    puerto = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=puerto
    )
