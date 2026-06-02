import os
import urllib.request
from fastapi import FastAPI, Form, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.twiml.voice_response import VoiceResponse, Dial
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env
load_dotenv()

app = FastAPI(title="Twilio VoIP - Arquitectura Híbrida Premium")

# Configurar middleware de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Credenciales de Twilio
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_API_KEY = os.getenv("TWILIO_API_KEY")
TWILIO_API_SECRET = os.getenv("TWILIO_API_SECRET")
TWILIO_TWIML_APP_SID = os.getenv("TWILIO_TWIML_APP_SID")

# Número celular del Asesor para desvíos PSTN (Leído de .env)
ADVISOR_PHONE_NUMBER = os.getenv("ADVISOR_PHONE_NUMBER", "+573001234567")

# Carpeta local para almacenar los audios descargados automáticamente
RECORDINGS_DIR = os.path.join(os.path.dirname(__file__), "recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)

def descargar_audio_background(recording_url: str, call_sid: str):
    """
    Función que descarga de manera asíncrona el archivo de audio
    desde Twilio y lo almacena localmente en la carpeta 'recordings'.
    """
    ruta_archivo = os.path.join(RECORDINGS_DIR, f"{call_sid}.mp3")
    try:
        print(f"[Descarga Automática] Iniciando descarga de llamada: {call_sid}...")
        # Descarga el archivo de audio MP3 desde la URL de Twilio
        urllib.request.urlretrieve(recording_url, ruta_archivo)
        print(f"[Descarga Automática] ¡Éxito! Archivo guardado localmente en: {ruta_archivo}")
    except Exception as e:
        print(f"[Descarga Automática] Error al descargar audio de {call_sid}: {str(e)}")

@app.get("/")
async def get_frontend():
    frontend_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return HTMLResponse(content="<h1>Archivo index.html no encontrado.</h1>", status_code=404)

@app.get("/token/{identity}")
async def get_token(identity: str):
    if not all([TWILIO_ACCOUNT_SID, TWILIO_API_KEY, TWILIO_API_SECRET, TWILIO_TWIML_APP_SID]):
        return JSONResponse(
            status_code=500,
            content={"error": "Faltan configurar variables de entorno de Twilio en el archivo .env"}
        )
    try:
        token = AccessToken(
            TWILIO_ACCOUNT_SID,
            TWILIO_API_KEY,
            TWILIO_API_SECRET,
            identity=identity
        )
        voice_grant = VoiceGrant(
            outgoing_application_sid=TWILIO_TWIML_APP_SID,
            incoming_allow=True
        )
        token.add_grant(voice_grant)
        return JSONResponse(content={"token": token.to_jwt()})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Error al generar el token de Twilio: {str(e)}"}
        )

@app.post("/incoming-call")
async def incoming_call(request: Request, routing: str = "webrtc"):
    """
    ENDPOINT DE CONTROL DE FLUJO DINÁMICO:
    Maneja el enrutamiento de la llamada entrante según el query parameter 'routing'.
    - Si routing=webrtc (defecto): llama al softphone del navegador.
    - Si routing=pstn: desvía la llamada al celular configurado en .env (ADVISOR_PHONE_NUMBER).
    """
    try:
        form_data = await request.form()
        from_number = form_data.get("From", "Desconocido")
        print(f"[Incoming Call Webhook] Nueva llamada de: {from_number} | Modo Enrutamiento: {routing}")

        response = VoiceResponse()
        response.say("Conectando su llamada con un asesor disponible. Esta conversación será grabada.", language="es-MX")
        
        base_url = str(request.base_url).rstrip('/')
        recording_callback_url = f"{base_url}/recording-status"
        
        dial = Dial(
            record="record-from-answer-dual",
            recording_status_callback=recording_callback_url,
            recording_status_callback_event="completed"
        )
        
        if routing.lower() == "pstn":
            # CASO B: Desviar llamada a celular del asesor
            dial.number(ADVISOR_PHONE_NUMBER)
            print(f"[Incoming Call Webhook] Redirigiendo llamada a celular PSTN ({ADVISOR_PHONE_NUMBER})")
        else:
            # CASO A: Enrutar al navegador (WebRTC Client)
            dial.client("asesor_juan")
            print("[Incoming Call Webhook] Redirigiendo llamada a cliente WebRTC (asesor_juan)")
            
        response.append(dial)
        return HTMLResponse(content=str(response), media_type="application/xml")
        
    except Exception as e:
        print(f"Error crítico en incoming-call: {str(e)}")
        err_response = VoiceResponse()
        err_response.say("Error interno de enrutamiento.", language="es-MX")
        return HTMLResponse(content=str(err_response), media_type="application/xml")

@app.post("/recording-status")
async def recording_status(request: Request, background_tasks: BackgroundTasks):
    """
    WEBHOOK DE ESTADO DE GRABACIÓN CON DESCARGA AUTOMÁTICA:
    Recibe la URL del audio estéreo de Twilio y programa su descarga automática local.
    """
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        recording_url = form_data.get("RecordingUrl")
        recording_status = form_data.get("RecordingStatus")
        recording_duration = form_data.get("RecordingDuration", "0")
        
        print("\n" + "="*70)
        print("🔴 REGISTRO DE GRABACIÓN RECIBIDO (DUAL-CHANNEL)")
        print(f"ID Llamada (Call SID) : {call_sid}")
        print(f"Estado de Grabación   : {recording_status}")
        print(f"Duración de Audio     : {recording_duration} segundos")
        print(f"URL de Grabación (MP3): {recording_url}")
        print("="*70 + "\n")
        
        # Si la grabación se completó con éxito, procedemos a descargarla automáticamente
        if recording_url and call_sid and recording_status == "completed":
            # Nos aseguramos de pedir la versión .mp3
            if not recording_url.endswith(".mp3"):
                recording_url = f"{recording_url}.mp3"
            
            # Programar la descarga en segundo plano usando FastAPI BackgroundTasks
            background_tasks.add_task(descargar_audio_background, recording_url, call_sid)
            
        return {"status": "success", "message": "Grabación procesada y programada para descarga"}
    except Exception as e:
        print(f"Error procesando webhook de grabación: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error interno en recording-status: {str(e)}"}
        )