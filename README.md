Se trata de un extractor de momentos destacados de directos en crudo.

## Como funciona:
1. Coloca el script en el mismo directorio de tus VOD (mov,mp4,mkv).
2. Ejecuta el script **python3 script.py video.mp4**
3. El script hará la transcripcion inicial usando Whisper con el modelo "medium".
4. Se fragmenta el SRT en bloques de 15 minutos para evitar alucinaciones de Gemma4.
5. Se usa Ollama para pasar la peticion a Gemma4.
6. Se analiza el archivo SRT en busca de los momentos destacados de menos de 1 minuto.
7. Ffmpeg extrae los clips seleccionados.
8. Se realiza la transcripcion de los clips usando Whisper con el modelo "large"
9. Se pasa a Gemma4 los SRT de los clips para acortar las frases a palabras clave, y convertir a mayuscula.
10. Ffmpeg incrusta con estilo los nuevos SRT y genera los clips finales

## Requisitos:
- Python3
- Ffmpeg: **sudo apt update && sudo apt install ffmpeg**
- Whisper: **pip install git+https://github.com/openai/whisper.git**
- Gemma4: **https://ollama.com/download/windows**

Y dale Like y suscríbete! ;)
