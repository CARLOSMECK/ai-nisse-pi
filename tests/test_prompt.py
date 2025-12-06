#!/usr/bin/env python3
import random
import sys
from datetime import datetime
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    NISSE_PERSONALITY, GENERAL_THEME, BARN,
    REPLIK_STILAR, REPLIK_LÄNGDER
)

def get_todays_theme():
    if random.random() < 0.5:
        return GENERAL_THEME    
    brevfil = Path(__file__).parent.parent / "nissebrev.json"  
    if not brevfil.exists():
        return GENERAL_THEME   
    try:
        with open(brevfil, 'r', encoding='utf-8') as f:
            brev = json.load(f)       
        today = datetime.now().strftime("%Y-%m-%d")       
        for entry in brev:
            if entry.get("date") == today:
                return f'Idag lämnade du detta brev:\n"{entry["message"][:100]}..."'
        return GENERAL_THEME
    except:
        return GENERAL_THEME

def simulate_prompt():
    current_theme = get_todays_theme()    
    namn_text = ""
    if BARN and random.random() < 0.3: 
        namn_text = f"\n- Nämn barnen {' och '.join(BARN)} vid namn"  
    replik_stil = random.choice(REPLIK_STILAR)
    längd = random.choice(REPLIK_LÄNGDER)  
    prompt = f"""
{NISSE_PERSONALITY}

Dagens tema: {current_theme}
Generera en replik ({längd}).
Stil: {replik_stil}{namn_text}
"""
    return prompt, replik_stil, längd, bool(namn_text)

if __name__ == "__main__":
    print("Simulerar prompt till GPT")
    
    for i in range(5):
        prompt, stil, längd, namn = simulate_prompt()
        print(f"\n--- Prompt #{i+1} ---")
        print(f"Längd: {längd}")
        print(f"Stil: {stil}")
        print(f"Namn: {'Ja (' + ' & '.join(BARN) + ')' if namn else 'Nej'}")
        print("-" * 40)
        print(prompt)
        print("=" * 60)

