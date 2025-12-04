#!/usr/bin/env python3

import os
import time
import json
import random
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
from config import (
    NISSE_PERSONALITY, GENERAL_THEME, BARN, 
    AKTIV_START, AKTIV_SLUT, VOLYM, AUDIO_DEVICE
)

# KONFIGURATION
load_dotenv()

OPENAI_API_KEY = os.getenv("openai_api_key")
ELEVENLABS_API_KEY = os.getenv("elevenlabs_api_key")

PIR_PIN = 17

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

def get_todays_theme() -> str: 
    if random.random() < 0.5:
        return GENERAL_THEME    
    brevfil = Path(__file__).parent / "nissebrev.json"  
    if not brevfil.exists():
        return GENERAL_THEME   
    try:
        with open(brevfil, 'r', encoding='utf-8') as f:
            brev = json.load(f)       
        today = datetime.now().strftime("%Y-%m-%d")       
        for entry in brev:
            if entry.get("date") == today:
                return f"""
Idag lämnade du detta brev till barnen:
"{entry['message']}"

Prata om något som anknyter till dagens brev, kanske det bus du gjorde i natt,
eller fråga om de hittade det du gömde. Var lekfull och nyfiken!
"""
        
        return GENERAL_THEME
        
    except Exception:
        return GENERAL_THEME

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
    
    current_theme = get_todays_theme()
    
    namn_text = ""
    if BARN and random.random() < 0.3: 
        namn_text = f"\n- Nämn barnen {' och '.join(BARN)} vid namn"
    
    prompt = f"""
{NISSE_PERSONALITY}

Dagens tema: {current_theme}

Generera EN kort replik (max 1-2 meningar) som nissen säger när ett barn går förbi.
Repliken ska vara:
- Anknyta till dagens tema/brev om möjligt
- Använd nisseuttryck som "ho ho", "nämen", "jösses"
- Barnvänlig och glad
- På svenska{namn_text}
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
def set_volume():
    try:
        subprocess.run(
            ["amixer", "-c", "2", "set", "PCM", f"{VOLYM}%"],
            capture_output=True
        )
        logger.info(f"Volym satt till {VOLYM}%")
    except Exception as e:
        logger.warning(f"Kunde inte sätta volym: {e}")

def play_audio(audio_path: str) -> bool:
    if not audio_path or not os.path.exists(audio_path):
        logger.error("Ingen ljudfil att spela upp")
        return False    
    logger.info(f"Spelar upp: {audio_path}")      
    try:
        result = subprocess.run(
            ["mpg123", "-q", "-a", AUDIO_DEVICE, audio_path],
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
def is_active_hours() -> bool:
    hour = datetime.now().hour
    return AKTIV_START <= hour < AKTIV_SLUT

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
    logger.info(f"Aktiv mellan kl {AKTIV_START}:00 - {AKTIV_SLUT}:00")
    logger.info(f"Barn: {', '.join(BARN)}")
    
    set_volume()
    gpio_ready = setup_gpio()
    last_trigger_time = 0
    try:
        logger.info("Lyssnar på rörelse...")
        
        while True:
            motion_detected = False
            
            if gpio_ready and pir_sensor:
                try:
                    motion_detected = pir_sensor.motion_detected
                except RuntimeError:
                    time.sleep(0.1)
                    continue
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
                    if not is_active_hours():
                        logger.info(f"Rörelse men utanför aktiva tider (kl {AKTIV_START}-{AKTIV_SLUT})")
                        last_trigger_time = current_time
                        continue
                    logger.info("Rörelse detekterad!")
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
