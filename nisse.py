#!/usr/bin/env python3

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
    print("gpiozero inte tillgängligt - kör i testläge")

import openai
import requests

# KONFIGURATION
load_dotenv()

OPENAI_API_KEY = os.getenv("openai_api_key")
ELEVENLABS_API_KEY = os.getenv("elevenlabs_api_key")

PIR_PIN = 17  # GPIO17 (fysisk pin 11)

COOLDOWN_SECONDS = 25

ELEVENLABS_VOICE_ID = "DUnzBkwtjRWXPr6wRbmL"  # Mad Scientist
ELEVENLABS_MODEL = "eleven_multilingual_v2"
ELEVENLABS_SPEED = 0.85
ELEVENLABS_VOICE_SETTINGS = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": True
}

NISSE_PERSONALITY = """
Du är en tomtenisse som älskar julen.
Du pratar gammaldags och mysigt, som en riktig tomtenisse från svenska folksagorna.
Du använder uttryck som "ho ho", "nämen", "jösses".
Du är godhjärtad och älskar barn.
Du säger aldrig något läskigt.
"""

CURRENT_THEME = """
Det är adventstid och julen närmar sig!
Du kan prata om:
- Julklappar och julönskelistor
- Tomten som snart kommer
- Pepparkaksbak och julpynt
- Snälla barn och busiga barn
- Julstämning och magi
- Renar och slädar
- Snön och vintern
Välj ett av dessa ämnen och gör en kort, glad kommentar.
"""

# LOGGNING
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

# GPT - GENERERA NISSE-REPLIK
def generate_nisse_response() -> str:
    logger.info("Genererar nissreplik via GPT...")    
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    prompt = f"""
{NISSE_PERSONALITY}

Dagens tema: {CURRENT_THEME}

Generera EN kort replik (max 1-2 meningar) som nissen säger när ett barn går förbi.
Repliken ska vara:
- Handla om jul, julklappar, tomten, snön, eller något annat juligt
- Använd nisseuttryck som "ho ho", "nämen", "jösses"
- Barnvänlig och glad
- På svenska
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
        text = text.strip('"\'')
        logger.info(f"Nisse säger: {text}")
        return text
        
    except Exception as e:
        logger.error(f"GPT-fel: {e}")
        return None

# ELEVENLABS - TEXT TILL TAL
def text_to_speech(text: str) -> str:
    logger.info("Konverterar text till tal via ElevenLabs...")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }    
    data = {
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": ELEVENLABS_VOICE_SETTINGS,
        "speed": ELEVENLABS_SPEED
    }
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=30)
        response.raise_for_status()
        audio_path = tempfile.mktemp(suffix=".mp3", prefix="nisse_")
        with open(audio_path, "wb") as f:
            f.write(response.content)        
        logger.info(f"Ljud sparat: {audio_path}")
        return audio_path     
    except Exception as e:
        logger.error(f"ElevenLabs-fel: {e}")
        return None

# LJUDUPPSPELNING
def play_audio(audio_path: str) -> bool:
    if not audio_path or not os.path.exists(audio_path):
        logger.error("Ingen ljudfil att spela upp")
        return False    
    logger.info(f"Spelar upp: {audio_path}")      
    try:
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
        logger.error("mpg123 är inte installerat! Kör: sudo apt install mpg123")
        return False
    except subprocess.TimeoutExpired:
        logger.error("Uppspelning tog för lång tid")
        return False
    except Exception as e:
        logger.error(f"Uppspelningsfel: {e}")
        return False
    finally:
        try:
            os.remove(audio_path)
            logger.debug(f"Raderade: {audio_path}")
        except:
            pass
    
    return True

# NISSE-FLÖDE
def nisse_flow():
    logger.info("=" * 50)
    logger.info("NISSE AKTIVERAD!")
    logger.info("=" * 50)
    start_time = time.time()
    text = generate_nisse_response()
    if not text:
        logger.error("Ingen text genererades")
        return   
    audio_path = text_to_speech(text)
    if not audio_path:
        logger.error("Kunde inte skapa ljudfil")
        return
    
    play_audio(audio_path)
    
    elapsed = time.time() - start_time
    logger.info(f"Total tid: {elapsed:.1f} sekunder")
    logger.info("=" * 50)

# GPIO OCH PIR-SENSOR
pir_sensor = None
def setup_gpio():
    global pir_sensor
    if not PI_AVAILABLE:
        logger.warning("GPIO inte tillgängligt - testläge")
        return False
    
    pir_sensor = MotionSensor(PIR_PIN)
    logger.info(f"GPIO initierat, PIR på pin {PIR_PIN}")
    return True

def cleanup_gpio():
    global pir_sensor
    if pir_sensor:
        pir_sensor.close()
        logger.info("GPIO städat")

# HUVUDLOOP
def main():
    logger.info("=" * 50)
    logger.info("   AI-NISSE STARTAR!")
    logger.info("=" * 50)   
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY saknas i .env!")
        return
    if not ELEVENLABS_API_KEY:
        logger.error("ELEVENLABS_API_KEY saknas i .env!")
        return
    logger.info("API-nycklar laddade")
    gpio_ready = setup_gpio()
    last_trigger_time = 0
    try:
        logger.info("Lyssnar på rörelse...")
        
        while True:
            motion_detected = False
            
            if gpio_ready and pir_sensor:
                motion_detected = pir_sensor.motion_detected
            else:
                try:
                    input("Tryck Enter for att simulera rörelse (Ctrl+C for att avsluta)...")
                    motion_detected = True
                except EOFError:
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
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        logger.info("Avslutar Nisse...")
    finally:
        cleanup_gpio()
        logger.info("Nisse somnar... God jul!")

# ENTRY POINT
if __name__ == "__main__":
    main()
