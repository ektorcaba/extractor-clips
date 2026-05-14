import os
import subprocess
import json
import re
import argparse
from ollama import Client
import random
import unicodedata

# Configuración del Cliente
client = Client(host='http://127.0.0.1:11434') #Host WSL Example IP: http://172.29.96.1:11434

# --- CONFIGURACIÓN FIJA ---
MODEL_NAME = "gemma4"  
OUTPUT_BASE = "GENERADOS"
INTERVALO_MINUTOS = 15

def srt_a_segundos(tiempo_str):
    try:
        tiempo_str = tiempo_str.strip().replace(',', '.')
        partes = tiempo_str.split(':')
        if len(partes) == 3: h, m, s = partes
        elif len(partes) == 2: h, m, s = 0, partes[0], partes[1]
        else: return 0
        return int(h) * 3600 + int(m) * 60 + float(s)
    except:
        return 0

def limpiar_y_fragmentar_srt(ruta_srt, intervalo_min=15):
    if not os.path.exists(ruta_srt):
        return []
    with open(ruta_srt, 'r', encoding='utf-8') as f:
        lineas = f.readlines()
    
    bloques = []
    intervalo_segundos = intervalo_min * 60
    patron_tiempo = re.compile(r'(\d{1,2}:\d{1,2}:\d{1,2})')
    
    for l in lineas:
        if "-->" in l:
            match = patron_tiempo.search(l)
            if match:
                segundos = srt_a_segundos(match.group(1))
                indice = int(segundos // intervalo_segundos)
                while len(bloques) <= indice:
                    bloques.append("")
                bloques[indice] += f"\n[{match.group(1)}] "
        elif l.strip() and not l.strip().isdigit() and "-->" not in l:
            if bloques:
                bloques[-1] += l.strip() + " "
    return [b for b in bloques if len(b.strip()) > 5]

def extraer_json(texto):
    try:
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        if match: return json.loads(match.group(0))
    except:
        return None

def obtener_clips_ia(frag, nombre, idx):
    system = "Eres un extractor de datos. Respeta un margen tiempo de inicio y fin de 5 segundos extra. Responde SOLO JSON plano: {\"clips\": [{\"inicio\": \"HH:MM:SS\", \"fin\": \"HH:MM:SS\", \"motivo\": \"...\"}]}"
    user = f"Busca 1 momento clave en este texto del video {nombre} (Bloque {idx}):\n{frag}"
    
    try:
        response = client.chat(
            model=MODEL_NAME,
            messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            format='json',
            options={'temperature': 0.1, 'seed' : random.randint(1, 1000000), 'num_ctx': 16000}
        )
        return extraer_json(response['message']['content'])
    except:
        return None

def limpiar_nombre_archivo(nombre):
    nombre = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('ascii')
    nombre = nombre.replace(" ", "_")
    nombre = re.sub(r'[^a-zA-Z0-9_-]', '', nombre)
    return nombre[:50]

def simplificar_srt_para_vertical(ruta_srt, model_name="gemma4"):
    if not os.path.exists(ruta_srt):
        return None

    with open(ruta_srt, 'r', encoding='utf-8') as f:
        contenido_srt = f.read()

    system_prompt = (
        "Eres un editor de subtítulos dinámicos para TikTok. Tu objetivo es fragmentar el texto "
        "para que sea extremadamente fluido. "
        "REGLAS CRÍTICAS:\n"
        "1. BREVEDAD EXTREMA: Muestra solo de 1 a 3 palabras por cada marca de tiempo.\n"
        "2. REDISTRIBUCIÓN: Si un bloque original tiene mucho texto, divídelo en varios bloques "
        "ajustando los tiempos de inicio y fin proporcionalmente para que no se pierda la sincronía.\n"
        "3. MAYÚSCULAS: Todo el texto debe estar en MAYÚSCULAS.\n"
        "4. LENGUAJE: Elimina muletillas y simplifica el mensaje para que sea directo.\n"
        "5. FORMATO: Devuelve solo el código SRT limpio, sin texto adicional ni bloques de Markdown."
    )

    user_prompt = f"Convierte este SRT a formato dinámico (1-3 palabras por línea) en MAYÚSCULAS:\n\n{contenido_srt}"

    try:
        response = client.chat(
            model=model_name,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            options={'temperature': 0.1, 'num_ctx': 24000}
        )

        resultado = response['message']['content']
        resultado = re.sub(r'```[a-z]*\n', '', resultado)
        resultado = resultado.replace('```', '').strip()

        ruta_salida = ruta_srt.replace(".srt", "_Dinamico.srt")
        with open(ruta_salida, 'w', encoding='utf-8') as f:
            f.write(resultado)

        return ruta_salida
    except Exception as e:
        print(f"⚠️ Error en la simplificación dinámica: {e}")
        return None

def extraer_y_unir(video_input, clips, destino):
    if not os.path.exists(destino): os.makedirs(destino, exist_ok=True)
    rutas = []
    
    for i, c in enumerate(clips):
        start = c['inicio'].replace(',', '.')
        end = c['fin'].replace(',', '.')
        out_name = f"clip_{i+1}.mp4"
        out = os.path.join(destino, out_name)

        print(f"  -> {i+1}/{len(clips)} Extrayendo: {start} a {end}")
        cmd = ['ffmpeg', '-y', '-ss', start, '-to', end, '-i', video_input, 
               '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '22', 
               '-c:a', 'aac', '-loglevel', 'error', out]
        subprocess.run(cmd)

        # Transcripción pro del clip seleccionado
        cmd_whisper = ['whisper', out, '--language', 'Spanish', '--model', 'large-v3', '--model_dir', 'models', '--output_format', 'srt', '--output_dir', destino, '--verbose', 'False']
        subprocess.run(cmd_whisper)

        out_textos = os.path.join(destino, f"clip_{i+1}_final.mp4")
        out_textos_srt = os.path.join(destino, f"clip_{i+1}.srt")

        sub_mod_path = simplificar_srt_para_vertical(out_textos_srt)

        if sub_mod_path:
            estilo = (
                "subtitles={}:force_style="
                "'FontName=Oswald,FontSize=16,"
                "PrimaryColour=&H0000D2FF,OutlineColour=&H00000000,"
                "BorderStyle=2,Outline=1,Shadow=0,"
                "Alignment=6,MarginV=110,MarginL=60,MarginR=60'"
            ).format(sub_mod_path)

            cmd_textos = ['ffmpeg', '-y', '-i', out, '-vf', estilo, '-c:a', 'copy', '-loglevel', 'error', out_textos]
            subprocess.run(cmd_textos)
        
        rutas.append(out)

    if rutas:
        list_path = os.path.join(destino, "lista.txt")
        with open(list_path, 'w') as f:
            for r in rutas: f.write(f"file '{os.path.basename(r)}'\n")
        
        resumen = os.path.join(destino, "RESUMEN_TOTAL.mp4")
        subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_path, '-c:v', 'copy', '-c:a', 'copy', '-loglevel', 'error', resumen])
        os.remove(list_path)
        print(f"  ✨ Resumen total generado: {resumen}")

def procesar_video(video_file):
    srt_file = os.path.splitext(video_file)[0] + ".srt"

    # Si no existe el SRT, lo generamos con Medium antes de analizar
    if not os.path.exists(srt_file):
        print(f"🔍 No se encontró SRT para {video_file}. Generando transcripción base (Medium)...")
        cmd_whisper_base = [
            'whisper', video_file, 
            '--language', 'Spanish', 
            '--model', 'medium', 
            '--model_dir', 'models', 
            '--output_format', 'srt', 
            '--verbose', 'False'
        ]
        subprocess.run(cmd_whisper_base)

    if not os.path.exists(srt_file):
        print(f"❌ Error crítico: No se pudo generar el SRT para {video_file}.")
        return

    print(f"\n🎬 Iniciando análisis de: {video_file}")
    frags = limpiar_y_fragmentar_srt(srt_file, INTERVALO_MINUTOS)
    
    if not frags:
        print(f"  ❌ No se pudieron generar bloques del SRT para {video_file}.")
        return

    print(f"  📦 Vídeo dividido en {len(frags)} bloques.")
    
    total_clips = []
    for idx, frag in enumerate(frags, 1):
        print(f"  🧠 Analizando bloque {idx}/{len(frags)}...")
        res = obtener_clips_ia(frag, video_file, idx)
        if res and 'clips' in res:
            total_clips.extend([c for c in res['clips'] if 'inicio' in c and 'fin' in c])

    if total_clips:
        print(f"  ✅ Clips encontrados: {len(total_clips)}")
        video_name = os.path.splitext(os.path.basename(video_file))[0]
        ext_dir = os.path.join(OUTPUT_BASE, video_name)
        extraer_y_unir(video_file, total_clips, ext_dir)
    else:
        print(f"  ❌ No se encontraron clips destacados en {video_file}.")

def main():
    parser = argparse.ArgumentParser(description="Procesado de vídeos y clips con IA.")
    parser.add_argument("video", nargs='?', help="Nombre del vídeo. Si se omite, procesa todo el directorio.")
    args = parser.parse_args()

    if args.video:
        procesar_video(args.video)
    else:
        formatos_video = ('.mp4', '.mkv', '.mov', '.avi')
        videos = [f for f in os.listdir('.') if f.lower().endswith(formatos_video)]
        
        if not videos:
            print("No hay vídeos para procesar.")
            return
            
        for vid in videos:
            procesar_video(vid)

if __name__ == "__main__":
    main()
