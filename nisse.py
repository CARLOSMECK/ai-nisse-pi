#!/usr/bin/env python3
"""
AI-Nisse - En magisk nissedörr som pratar med barnen!

Huvudprogram som:
- Lyssnar på PIR-sensor för rörelsedetektering
- Genererar lekfulla nissesvar via OpenAI
- Konverterar text till tal via ElevenLabs
- Spelar upp ljudet via högtalare
"""

import os
import time
import logging
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

try:
    from gpiozero import MotionSensor
    PI_AVAILABLE = True
except ImportError:
    PI_AVAILABLE = False
    print("gpiozero inte tillgangligt - kor i testlage")

import openai
import requests

# ============================================================================
# KONFIGURATION
# ============================================================================

# Ladda miljövariabler från .env
load_dotenv()

# API-nycklar
OPENAI_API_KEY = os.getenv("openai_api_key")
ELEVENLABS_API_KEY = os.getenv("elevenlabs_api_key")

# GPIO-inställningar
PIR_PIN = 17  # GPIO17 (fysisk pin 11)

# Cooldown mellan triggers (sekunder)
COOLDOWN_SECONDS = 25

# ElevenLabs-inställningar
ELEVENLABS_VOICE_ID = "DUnzBkwtjRWXPr6wRbmL"  # Mad Scientist
ELEVENLABS_MODEL = "eleven_multilingual_v2"
ELEVENLABS_VOICE_SETTINGS = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": True
}

# Nisse-personlighet och tema
NISSE_PERSONALITY = """
Du är en tomtenisse som bor bakom denna lilla dörr.
Du pratar gammaldags och mysigt, som en riktig tomtenisse från svenska folksagorna.
Du använder uttryck som "ho ho", "nämen", "jösses".
Du mumlar lite för dig själv ibland.
Du är lite blyg och hemlighetsfull, men nyfiken på barnen.
Du pratar om saker nissar bryr sig om: gröten, tomten, att vakta huset, julförberedelser.
Du är godhjärtad men kan låtsas vara lite butter.
Du säger aldrig något läskigt - du är en snäll gårdstomte.
"""

CURRENT_THEME = """
Det är adventstid och du har fullt upp med julförberedelser bakom din lilla dörr.
Du kanske håller på att göra julklappar, räknar strumpor, eller kollar din lista över snälla barn.
Du har inte ätit din gröt ännu idag och det oroar dig lite.
"""

# ============================================================================
# LOGGNING
# ============================================================================

# Konfigurera loggning
log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "nisse.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# GPT - GENERERA NISSE-REPLIK
# ============================================================================

def generate_nisse_response() -> str:
    """Genererar en nissreplik via OpenAI GPT."""
    logger.info("Genererar nissreplik via GPT...")
    
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    prompt = f"""
{NISSE_PERSONALITY}

Dagens tema: {CURRENT_THEME}

Generera EN kort replik (max 1-2 meningar) som nissen säger när ett barn går förbi dörren.
Repliken ska vara:
- Som en äkta svensk tomtenisse skulle prata
- Använd nisseuttryck som "ho ho", "nämen", "jösses"
- Lite hemlighetsfull
- Barnvänlig och varm
- På svenska
- Som om nissen precis hörde att någon smyger utanför dörren

Svara ENDAST med repliken, inget annat.
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Du är en snäll tomtenisse som pratar gammaldags svenska med mysiga nisseuttryck."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.9
        )
        
        text = response.choices[0].message.content.strip()
        # Ta bort eventuella citattecken runt texten
        text = text.strip('"\'')
        
        logger.info(f"Nisse sager: {text}")
        return text
        
    except Exception as e:
        logger.error(f"GPT-fel: {e}")
        # Fallback-repliker om API:et inte fungerar
        fallbacks = [
            "Ho ho, vem smyger dar ute? Ar det nagon som vill ha julklappar?",
            "Nasmen, jag horde visst sma fotter! Har ni varit snalla, manniskobarnen?",
            "Kors i taansen, jag haller ju pa med groten har inne! Stanna dar ute nu!"
        ]
        import random
        return random.choice(fallbacks)

# ============================================================================
# ELEVENLABS - TEXT TILL TAL
# ============================================================================

def text_to_speech(text: str) -> str:
    """Konverterar text till tal via ElevenLabs och returnerar filsökväg."""
    logger.info("Konverterar text till tal via ElevenLabs...")
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    
    data = {
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": ELEVENLABS_VOICE_SETTINGS
    }
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Spara till temporär fil
        audio_path = tempfile.mktemp(suffix=".mp3", prefix="nisse_")
        with open(audio_path, "wb") as f:
            f.write(response.content)
        
        logger.info(f"Ljud sparat: {audio_path}")
        return audio_path
        
    except Exception as e:
        logger.error(f"ElevenLabs-fel: {e}")
        return None

# ============================================================================
# LJUDUPPSPELNING
# ============================================================================

def play_audio(audio_path: str) -> bool:
    """Spelar upp ljudfil via mpg123."""
    if not audio_path or not os.path.exists(audio_path):
        logger.error("Ingen ljudfil att spela upp")
        return False
    
    logger.info(f"Spelar upp: {audio_path}")
    
    try:
        # Använd mpg123 för att spela upp MP3
        result = subprocess.run(
            ["mpg123", "-q", audio_path],
            capture_output=True,
            timeout=60
        )
        
        if result.returncode == 0:
            logger.info("Uppspelning klar")
        else:
            logger.warning(f"mpg123 returnerade: {result.returncode}")
            
    except FileNotFoundError:
        logger.error("mpg123 ar inte installerat! Kor: sudo apt install mpg123")
        return False
    except subprocess.TimeoutExpired:
        logger.error("Uppspelning tog for lang tid")
        return False
    except Exception as e:
        logger.error(f"Uppspelningsfel: {e}")
        return False
    finally:
        # Städa upp ljudfilen
        try:
            os.remove(audio_path)
            logger.debug(f"Raderade: {audio_path}")
        except:
            pass
    
    return True

# ============================================================================
# NISSE-FLÖDE
# ============================================================================

def nisse_flow():
    """Kör hela Nisse-flödet: GPT -> TTS -> Uppspelning."""
    logger.info("=" * 50)
    logger.info("NISSE AKTIVERAD!")
    logger.info("=" * 50)
    
    start_time = time.time()
    
    # Steg 1: Generera replik
    text = generate_nisse_response()
    if not text:
        logger.error("Ingen text genererades")
        return
    
    # Steg 2: Konvertera till tal
    audio_path = text_to_speech(text)
    if not audio_path:
        logger.error("Kunde inte skapa ljudfil")
        return
    
    # Steg 3: Spela upp
    play_audio(audio_path)
    
    elapsed = time.time() - start_time
    logger.info(f"Total tid: {elapsed:.1f} sekunder")
    logger.info("=" * 50)

# ============================================================================
# GPIO OCH PIR-SENSOR
# ============================================================================

pir_sensor = None

def setup_gpio():
    """Initierar GPIO för PIR-sensor."""
    global pir_sensor
    if not PI_AVAILABLE:
        logger.warning("GPIO inte tillgangligt - testlage")
        return False
    
    pir_sensor = MotionSensor(PIR_PIN)
    logger.info(f"GPIO initierat, PIR pa pin {PIR_PIN}")
    return True

def cleanup_gpio():
    """Städar upp GPIO."""
    global pir_sensor
    if pir_sensor:
        pir_sensor.close()
        logger.info("GPIO stadat")

# ============================================================================
# HUVUDLOOP
# ============================================================================

def main():
    """Huvudprogram - lyssnar på PIR och triggar Nisse."""
    logger.info("=" * 50)
    logger.info("   AI-NISSE STARTAR!")
    logger.info("=" * 50)
    
    # Validera API-nycklar
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY saknas i .env!")
        return
    if not ELEVENLABS_API_KEY:
        logger.error("ELEVENLABS_API_KEY saknas i .env!")
        return
    
    logger.info("API-nycklar laddade")
    
    # Initiera GPIO
    gpio_ready = setup_gpio()
    
    last_trigger_time = 0
    
    try:
        logger.info("Lyssnar pa rorelse...")
        
        while True:
            motion_detected = False
            
            if gpio_ready and pir_sensor:
                # Läs PIR-sensor
                motion_detected = pir_sensor.motion_detected
            else:
                # Testläge - vänta på Enter
                try:
                    input("Tryck Enter for att simulera rorelse (Ctrl+C for att avsluta)...")
                    motion_detected = True
                except EOFError:
                    # Om vi kör som service utan terminal
                    time.sleep(1)
                    continue
            
            if motion_detected:
                current_time = time.time()
                time_since_last = current_time - last_trigger_time
                
                if time_since_last >= COOLDOWN_SECONDS:
                    logger.info("Rorelse detekterad!")
                    last_trigger_time = current_time
                    nisse_flow()
                else:
                    remaining = COOLDOWN_SECONDS - time_since_last
                    logger.debug(f"Cooldown aktiv, {remaining:.0f}s kvar")
            
            # Liten paus för att inte överbelasta CPU
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        logger.info("Avslutar Nisse...")
    finally:
        cleanup_gpio()
        logger.info("Nisse somnar... God jul!")

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    main()
