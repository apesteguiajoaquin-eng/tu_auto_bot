import os
import requests
from flask import Flask, request

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "tuauto2026")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
GRAPH_API_VERSION = "v24.0"

# =========================
# DATOS TEMPORALES
# =========================

clientes = {}

# Choferes autorizados para la prueba
choferes = {
    "5493446614703": {
        "nombre": "Chofer 1",
        "estado": "DESCONECTADO",
        "ubicacion": None
    },
    "5493446411551": {
        "nombre": "Chofer 2",
        "estado": "DESCONECTADO",
        "ubicacion": None
    }
}


@app.route("/", methods=["GET"])
def inicio():
    return "TU AUTO BOT ONLINE", 200


@app.route("/webhook", methods=["GET"])
def verificar_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Error de verificacion", 403


def enviar_mensaje(numero, texto):
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{PHONE_NUMBER_ID}/messages"

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
            "ENVIO:",
            numero,
            respuesta.status_code,
            respuesta.text
        )

    except Exception as error:
        print("ERROR ENVIANDO MENSAJE:", error)


def pedir_ubicacion(numero, texto=None):

    if texto is None:
        texto = (
            "🚗 TU AUTO\n\n"
            "Para buscarte necesito saber dónde estás.\n\n"
            "Tocá el botón de abajo y compartí tu ubicación."
        )

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{PHONE_NUMBER_ID}/messages"

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
                "text": texto
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
            "PEDIDO UBICACION:",
            numero,
            respuesta.status_code,
            respuesta.text
        )

    except Exception as error:
        print("ERROR PIDIENDO UBICACION:", error)


# =========================
# CHOFERES
# =========================

def procesar_chofer(numero, mensaje):

    chofer = choferes[numero]

    tipo = mensaje.get("type")

    # UBICACION DEL CHOFER
    if tipo == "location":

        ubicacion = mensaje.get("location", {})

        latitud = ubicacion.get("latitude")
        longitud = ubicacion.get("longitude")

        if latitud is None or longitud is None:
            enviar_mensaje(
                numero,
                "⚠️ No pude leer tu ubicación. Intentá enviarla nuevamente."
            )
            return

        chofer["ubicacion"] = {
            "latitud": latitud,
            "longitud": longitud
        }

        chofer["estado"] = "DISPONIBLE"

        enviar_mensaje(
            numero,
            "🟢 TU AUTO\n\n"
            "Estás ACTIVO y DISPONIBLE.\n\n"
            "Ya podés recibir pedidos."
        )

        print(
            "CHOFER DISPONIBLE:",
            numero,
            chofer["ubicacion"]
        )

        return

    if tipo != "text":
        return

    texto = (
        mensaje.get("text", {})
        .get("body", "")
        .strip()
        .lower()
    )

    # ACTIVAR
    if texto == "activar":

        chofer["estado"] = "ESPERANDO_UBICACION"

        pedir_ubicacion(
            numero,
            "🚗 TU AUTO - CHOFER\n\n"
            "Para ACTIVARTE necesito tu ubicación.\n\n"
            "Compartila usando el botón de abajo."
        )

        return

    # DESCONECTAR
    if texto in [
        "desconectar",
        "desactivar"
    ]:

        chofer["estado"] = "DESCONECTADO"
        chofer["ubicacion"] = None

        enviar_mensaje(
            numero,
            "🔴 TU AUTO\n\n"
            "Quedaste DESCONECTADO.\n\n"
            "No recibirás nuevos pedidos.\n\n"
            "Cuando quieras volver escribí:\n"
            "ACTIVAR"
        )

        return

    # ESTADO
    if texto == "estado":

        estado = chofer["estado"]

        enviar_mensaje(
            numero,
            f"🚗 TU AUTO\n\n"
            f"Tu estado actual es:\n"
            f"{estado}"
        )

        return

    # AYUDA
    enviar_mensaje(
        numero,
        "🚗 TU AUTO - CHOFER\n\n"
        "Comandos disponibles:\n\n"
        "ACTIVAR\n"
        "DESCONECTAR\n"
        "ESTADO"
    )


# =========================
# BUSCAR CHOFER
# =========================

def buscar_chofer(cliente_numero):

    viaje = clientes.get(cliente_numero)

    if not viaje:
        return

    disponibles = []

    for numero, datos in choferes.items():

        if (
            datos["estado"] == "DISPONIBLE"
            and datos["ubicacion"] is not None
        ):
            disponibles.append(numero)

    print("NUEVO VIAJE")
    print("Cliente:", cliente_numero)
    print("Origen:", viaje["origen"])
    print("Destino:", viaje["destino"])
    print("Choferes disponibles:", disponibles)

    if not disponibles:

        enviar_mensaje(
            cliente_numero,
            "🚗 TU AUTO\n\n"
            "En este momento estamos buscando un conductor disponible.\n"
            "Aguardá un momento."
        )

        return

    # POR AHORA TOMAMOS EL PRIMERO.
    # En el siguiente módulo se ordenarán por distancia.
    chofer_numero = disponibles[0]

    enviar_mensaje(
        chofer_numero,
        "🚗 NUEVO PEDIDO TU AUTO\n\n"
        f"Destino: {viaje['destino']}\n\n"
        "Próximamente podrás ACEPTAR o RECHAZAR el viaje."
    )


# =========================
# CLIENTES
# =========================

def procesar_cliente(numero, mensaje):

    tipo = mensaje.get("type")

    if numero not in clientes:

        clientes[numero] = {
            "estado": "NUEVO",
            "origen": None,
            "destino": None
        }

    cliente = clientes[numero]

    # UBICACION CLIENTE
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
            "Ahora escribime a dónde querés ir.\n\n"
            "Ejemplo: Hospital Bicentenario"
        )

        return

    if tipo != "text":
        return

    texto = (
        mensaje.get("text", {})
        .get("body", "")
        .strip()
    )

    texto_minuscula = texto.lower()

    # DESTINO
    if cliente["estado"] == "ESPERANDO_DESTINO":

        cliente["destino"] = texto
        cliente["estado"] = "BUSCANDO_CHOFER"

        enviar_mensaje(
            numero,
            "✅ Pedido recibido.\n\n"
            f"📍 Destino: {texto}\n\n"
            "🚗 Estamos buscando un conductor disponible..."
        )

        buscar_chofer(numero)

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


# =========================
# PROCESAR MENSAJE
# =========================

def procesar_mensaje(mensaje):

    numero = mensaje.get("from")

    if not numero:
        return

    # Si es un número autorizado,
    # siempre se procesa como chofer.
    if numero in choferes:

        procesar_chofer(
            numero,
            mensaje
        )

        return

    # Los demás números son clientes.
    procesar_cliente(
        numero,
        mensaje
    )


# =========================
# WEBHOOK
# =========================

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

        print("ERROR:", error)

    return "EVENT_RECEIVED", 200


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
