import os
import requests
from flask import Flask, request

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "tuauto2026")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
GRAPH_API_VERSION = "v24.0"

clientes = {}


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
        "text": {"body": texto}
    }

    respuesta = requests.post(url, headers=headers, json=payload, timeout=20)
    print(respuesta.status_code, respuesta.text)


def pedir_ubicacion(numero):
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
                "text": "🚗 TU AUTO\n\nPara buscarte necesito saber dónde estás.\n\nTocá el botón de abajo y compartí tu ubicación."
            },
            "action": {"name": "send_location"}
        }
    }

    respuesta = requests.post(url, headers=headers, json=payload, timeout=20)
    print(respuesta.status_code, respuesta.text)


def buscar_chofer(cliente_numero):
    viaje = clientes.get(cliente_numero)
    if not viaje:
        return

    print("NUEVO VIAJE")
    print("Cliente:", cliente_numero)
    print("Origen:", viaje["origen"])
    print("Destino:", viaje["destino"])

    # Proximo modulo:
    # - choferes disponibles
    # - ubicacion GPS
    # - orden por cercania / turno
    # - aceptar viaje
    # - asignacion automatica


def procesar_mensaje(mensaje):
    numero = mensaje.get("from")
    if not numero:
        return

    tipo = mensaje.get("type")

    if numero not in clientes:
        clientes[numero] = {
            "estado": "NUEVO",
            "origen": None,
            "destino": None
        }

    cliente = clientes[numero]

    if tipo == "location":
        ubicacion = mensaje.get("location", {})

        cliente["origen"] = {
            "latitud": ubicacion.get("latitude"),
            "longitud": ubicacion.get("longitude")
        }
        cliente["estado"] = "ESPERANDO_DESTINO"

        enviar_mensaje(
            numero,
            "📍 Ubicación recibida.\n\nAhora escribime a dónde querés ir.\n\nEjemplo: Hospital Bicentenario"
        )
        return

    if tipo == "text":
        texto = mensaje.get("text", {}).get("body", "").strip()
        texto_minuscula = texto.lower()

        if cliente["estado"] == "ESPERANDO_DESTINO":
            cliente["destino"] = texto
            cliente["estado"] = "BUSCANDO_CHOFER"

            enviar_mensaje(
                numero,
                f"✅ Pedido recibido.\n\n📍 Destino: {texto}\n\n🚗 Estamos buscando un conductor disponible..."
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

        if any(palabra in texto_minuscula for palabra in palabras_viaje):
            cliente["estado"] = "ESPERANDO_UBICACION"
            enviar_mensaje(numero, "👋 Hola. Soy el asistente automático de TU AUTO.")
            pedir_ubicacion(numero)
            return

        enviar_mensaje(
            numero,
            "🚗 TU AUTO\n\nPara solicitar un vehículo escribí:\n\nNECESITO AUTO"
        )


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
    puerto = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=puerto)
