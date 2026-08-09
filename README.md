# 🚀 vLLM Local Server: Gemma 4 26B (Multimodal & Reasoning)

Servidor de Inferencia de Modelos de Lenguaje (LLM) de alto rendimiento basado en **vLLM**, configurado para desplegar el modelo **NVIDIA Gemma 4 26B-A4B-NVFP4** con soporte **Multimodal (Visión/OCR)**, **Razonamiento** y **Llamadas a Herramientas (*Tool Choice*)**, totalmente integrado con clientes como **Open-WebUI**.

---

## 🛠️ Especificaciones del Entorno

* **Sistema Operativo:** Ubuntu Linux
* **GPU:** NVIDIA GeForce RTX 3090 (24 GB VRAM, Compute Capability 8.6 - Ampere)
* **Memoria RAM:** 64 GB DDR4/DDR5
* **Entorno Python:** Virtualenv (`venv`) con Python 3.13
* **Motor de Inferencia:** vLLM v0.26.0 (Engine V1)

---

## 🌟 Características Principales

1. **Cuatro Servidores API locales (Gemma 4 en 8000, Whisper en 8001, F5-TTS en 8002, PyAnnote en 8003)**: Coexistencia de cuatro instancias locales de API en segundo plano que implementan chat, transcripción, generación de voz y separación de interlocutores de forma unificada.
2. **Despliegue Multimodal de Audio y Visión**: Soporte nativo para procesar imágenes y voz directamente.
3. **Gestión Coordinada de VRAM**: Asignación estricta de memoria (Gemma 4 al 50%, Whisper al 10%, F5-TTS al 10% y PyAnnote a GPU con ~400MB), manteniendo la suite completa siempre cargada en caliente sin colisiones.
4. **Instalación como Servicios del Sistema (`systemd`)**: Autoinstaladores integrados (`install_service.sh`, `install_whisper_service.sh`, `install_tts_service.sh` y `install_diarization_service.sh`) con autorreinicio.
5. **Scripts de Integración de Audio**: Scripts para re-muestrear ondas a la frecuencia nativa esperada (16kHz para Whisper/Gemma y 24kHz para F5-TTS).
6. **Exposición Swagger UI (`/docs`)**: Documentación interactiva completa autogenerada en el puerto de cada servicio de forma nativa.

---

## 🚀 Guía de Instalación y Despliegue

### 1. Clonar el repositorio y crear el entorno virtual

```bash
git clone <URL_DEL_REPOSITORIO>
cd vllm
python -m venv venv
source venv/bin/activate
```

### 2. Instalar dependencias del sistema y Python

Primero, instala las herramientas del sistema necesarias (el compilador CUDA `nvcc` para vLLM y `libportaudio2` para capturar audio desde el micrófono):

```bash
sudo apt update && sudo apt install -y nvidia-cuda-toolkit libportaudio2
```

Luego, instala vLLM junto con los paquetes necesarios para la diarización, el procesamiento de audio y las peticiones de red:

```bash
pip install vllm python-dotenv pyannote.audio faster-whisper sounddevice numpy scipy requests
```

> **Nota:** El paquete `nvidia-cuda-toolkit` provee el compilador `nvcc`, requerido por el backend FlashInfer de vLLM para la compilación en tiempo de ejecución (JIT).

### 3. Configurar las variables de entorno (`.env`)

Copia la plantilla `.env.example` para crear tu propio `.env`:

```bash
cp .env.example .env
```

Edita tu archivo `.env` configurando tu token de Hugging Face y clave API:

```env
HF_TOKEN=tu_token_huggingface_aqui
API_KEY=token-abc123

HOST=0.0.0.0
PORT=8000
MODEL=nvidia/Gemma-4-26B-A4B-NVFP4

GPU_MEMORY_UTILIZATION=0.90
MAX_MODEL_LEN=16384
MAX_NUM_SEQS=64
KV_CACHE_DTYPE=bfloat16
SWAP_SPACE=0
```

---

## ⚙️ Modos de Ejecución

### Opción A: Ejecución Manual

```bash
python app.py
```

### Opción B: Instalación como Servicio Systemd (Recomendado)

Ejecuta el script instalador para registrar e iniciar el servidor como un servicio del sistema Linux:

```bash
./install_service.sh
```

#### Comandos de administración de systemd:

* **Ver estado:** `sudo systemctl status vllm`
* **Ver logs en tiempo real:** `sudo journalctl -u vllm -f`
* **Detener servicio:** `sudo systemctl stop vllm`
* **Reiniciar servicio:** `sudo systemctl restart vllm`

---

## 🎙️ Servidor de Transcripción Persistente: vLLM-Whisper

Para evitar tiempos de carga en frío de Whisper, el proyecto incluye un servidor de transcripción permanente e independiente corriendo en vLLM bajo el puerto **`8001`**.

El servidor levanta el modelo `openai/whisper-large-v3-turbo` reservando únicamente el **10% de la VRAM** (~2.8 GB), permitiendo que coexista con el LLM principal.

### 1. Instalación del servicio systemd:
```bash
./install_whisper_service.sh
```

### 2. Comandos de administración:
* **Ver logs en tiempo real:** `sudo journalctl -u vllm-whisper -f`
* **Ver estado:** `sudo systemctl status vllm-whisper`
* **Detener servicio:** `sudo systemctl stop vllm-whisper`
* **Reiniciar servicio:** `sudo systemctl restart vllm-whisper`

### 3. Probar transcripción vía API (`POST /v1/audio/transcriptions`):
Ejecuta el cliente de prueba para mandar un archivo local:
```bash
python test_whisper_api.py
```

### 4. Integración con Open-WebUI (Voz a Texto / STT):
Para habilitar la transcripción por voz local en la interfaz de Open-WebUI, ve a **Ajustes de Administrador > Audio** y configura la sección **Voz a Texto (STT)** con los siguientes valores:

* **Motor Voz a Texto (STT):** `OpenAI`
* **URL Base API:** `http://localhost:8001/v1` *(Si corres Open-WebUI en Docker, usa `http://host.docker.internal:8001/v1`)*
* **Clave API:** `token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939` *(o la clave configurada en tu `.env`)*
* **Request Format:** `Multipart Upload`
* **Modelo STT:** `openai/whisper-large-v3-turbo`

---

## 🗣️ Servidor de Texto a Voz: vLLM-TTS

Para tener generación de voz con clonación zero-shot en caliente y sin retrasos de carga, el proyecto incluye un servidor de Texto a Voz (TTS) multilingüe basado en FastAPI y F5-TTS que corre en el puerto **`8002`**.

El servidor administra dinámicamente múltiples acentos intercambiando el modelo activo en la GPU en milisegundos y manteniendo los inactivos en la RAM del sistema, consumiendo apenas **~1.2 GB de VRAM fija**. Expone la API compatible con OpenAI `/v1/audio/speech`.

### 1. Instalación del servicio systemd:
```bash
./install_tts_service.sh
```

### 2. Comandos de administración:
* **Ver logs en tiempo real:** `sudo journalctl -u vllm-tts -f`
* **Ver estado:** `sudo systemctl status vllm-tts`
* **Detener servicio:** `sudo systemctl stop vllm-tts`
* **Reiniciar servicio:** `sudo systemctl restart vllm-tts`

### 3. Documentación interactiva (Swagger UI):
Accede desde tu navegador para probar y documentar los endpoints:
`http://localhost:8002/docs`

> **🔒 Autenticación en Swagger:** Haz clic en el botón **"Authorize"** en la parte superior derecha e introduce tu API key (`token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939`) para desbloquear las pruebas.

### 4. Integración con Open-WebUI (Texto a Voz / TTS):
Para escuchar las respuestas con tu voz clonada y el acento correcto según el idioma en Open-WebUI, ve a **Ajustes de Administrador > Audio** y configura la sección **Texto a Voz (TTS)** con los siguientes valores:

* **Motor Texto a Voz (TTS):** `OpenAI`
* **URL Base API:** `http://localhost:8002/v1` *(Si corres Open-WebUI en Docker, usa `http://host.docker.internal:8002/v1`)*
* **Clave API:** `token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939`
* **Modelo TTS:** `tts-1`
* **Voz TTS / Mapeo de Acentos:**
  Selecciona o escribe el identificador de voz correspondiente al acento nativo deseado:
  
  | Identificador de Voz (API / WebUI) | Idioma / Acento Nativo | Modelo Asociado |
  | :--- | :--- | :--- |
  | `jose`, `jose-es` o **`alloy`** | 🇪🇸 **Español** | `jpgallegoar/F5-Spanish` |
  | `jose-en` o **`echo`** | 🇺🇸 **Inglés** | `SWivid/F5-TTS` (Base Oficial) |
  | `jose-fr` o **`fable`** | 🇫🇷 **Francés** | `RASPIAUDIO/F5-French` |
  | `jose-de` o **`onyx`** | 🇩🇪 **Alemán** | `aihpi/F5-TTS-German` |
  | `jose-ru` o **`nova`** | 🇷🇺 **Ruso** | `hotstone228/F5-TTS-Russian` |
  | `jose-ja` o **`shimmer`** | 🇯🇵 **Japonés** | `Jmica/F5TTS` |

*(Nota: Todas las opciones clonan tu timbre de voz nativo en base a `mi_voz_24k_mono.wav`, pero con la pronunciación del acento seleccionado).*

---

## 👥 Servidor de Diarización de Voz: vLLM-Diarization

Para identificar "quién habla en cada momento" (separación de voces) en grabaciones de múltiples personas, el proyecto incluye un servidor de diarización basado en FastAPI y **PyAnnote 3.1** que corre en el puerto **`8003`**.

El servidor se ejecuta en la **GPU (CUDA)** para obtener la máxima velocidad de procesamiento, permaneciendo precargado con un consumo extremadamente ligero de apenas **~300 MB a 500 MB** de VRAM.

### 1. Requisito previo (Aceptar términos de uso en Hugging Face):
Los modelos de PyAnnote son de acceso restringido (*gated*). Antes de iniciar el servicio, debes ingresar con tu usuario a Hugging Face y aceptar las condiciones haciendo clic en:
1. [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
2. [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
3. [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)

*(El token configurado en `HF_TOKEN` en tu `.env` se usará automáticamente para descargar los pesos).*

### 2. Instalación del servicio systemd:
```bash
./install_diarization_service.sh
```

### 3. Comandos de administración:
* **Ver logs en tiempo real:** `sudo journalctl -u vllm-diarization -f`
* **Ver estado:** `sudo systemctl status vllm-diarization`
* **Detener servicio:** `sudo systemctl stop vllm-diarization`
* **Reiniciar servicio:** `sudo systemctl restart vllm-diarization`

### 4. Probar Diarización mediante Swagger UI:
Accede al panel interactivo y haz clic en **"Authorize"** con tu API key:
`http://localhost:8003/docs`

### 5. Ejemplo de prueba vía `curl`:
```bash
curl -X POST http://localhost:8003/v1/audio/diarize \
  -H "Authorization: Bearer token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939" \
  -F "file=@mi_voz_24k_mono.wav"
```

---

## 🧪 Pruebas con `curl`

### 1. Probar el Chat (Gemma 4 en Puerto 8000)

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939" \
  -d '{
    "model": "nvidia/Gemma-4-26B-A4B-NVFP4",
    "messages": [
      {"role": "user", "content": "¡Hola! ¿Puedes presentarte?"}
    ],
    "max_tokens": 150
  }'
```

### 2. Probar Texto a Voz con Clonación (F5-TTS en Puerto 8002)

Usa los siguientes comandos `curl` para generar audios en diferentes idiomas con pronunciación nativa manteniendo tu clon de voz:

#### 🇪🇸 Español (Voz `alloy` o `jose`)
```bash
curl -X POST http://localhost:8002/v1/audio/speech \
  -H "Authorization: Bearer token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939" \
  -H "Content-Type: application/json" \
  -d '\''{
    "model": "tts-1",
    "input": "Hola. Este es un mensaje de prueba generado en español usando mi propia voz clonada de forma local en mi computadora.",
    "voice": "alloy",
    "response_format": "mp3"
  }'\'' \
  -o espanol_clonado.mp3
```

#### 🇺🇸 Inglés (Voz `echo` o `jose-en`)
```bash
curl -X POST http://localhost:8002/v1/audio/speech \
  -H "Authorization: Bearer token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939" \
  -H "Content-Type: application/json" \
  -d '\''{
    "model": "tts-1",
    "input": "Hello! This is a test of my cloned voice speaking in English. It runs completely locally on my machine.",
    "voice": "echo",
    "response_format": "mp3"
  }'\'' \
  -o ingles_clonado.mp3
```

#### 🇫🇷 Francés (Voz `fable` o `jose-fr`)
```bash
curl -X POST http://localhost:8002/v1/audio/speech \
  -H "Authorization: Bearer token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939" \
  -H "Content-Type: application/json" \
  -d '\''{
    "model": "tts-1",
    "input": "Bonjour! C’est un test de ma voix clonée en français. Le rendu est généré instantanément.",
    "voice": "fable",
    "response_format": "mp3"
  }'\'' \
  -o frances_clonado.mp3
```

#### 🇩🇪 Alemán (Voz `onyx` o `jose-de`)
```bash
curl -X POST http://localhost:8002/v1/audio/speech \
  -H "Authorization: Bearer token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939" \
  -H "Content-Type: application/json" \
  -d '\''{
    "model": "tts-1",
    "input": "Guten Tag! Ich spreche Deutsch mit meiner eigenen geklonten Stimme auf meiner RTX dreißig-neunzig.",
    "voice": "onyx",
    "response_format": "mp3"
  }'\'' \
  -o aleman_clonado.mp3
```

#### 🇯🇵 Japonés (Voz `shimmer` o `jose-ja`)
```bash
curl -X POST http://localhost:8002/v1/audio/speech \
  -H "Authorization: Bearer token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939" \
  -H "Content-Type: application/json" \
  -d '\''{
    "model": "tts-1",
    "input": "こんにちは！これは私のクローン音声の日本語のテストです。完全にローカルで動作しています。",
    "voice": "shimmer",
    "response_format": "mp3"
  }'\'' \
  -o japones_clonado.mp3
```

#### 🇨🇳 Chino (Voz `echo` o `jose-en`)
```bash
curl -X POST http://localhost:8002/v1/audio/speech \
  -H "Authorization: Bearer token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939" \
  -H "Content-Type: application/json" \
  -d '\''{
    "model": "tts-1",
    "input": "你好！这是我本地克隆声音的中文测试。运行速度非常快。",
    "voice": "echo",
    "response_format": "mp3"
  }'\'' \
  -o chino_clonado.mp3
```

### 3. Probar Transcripción y Diarización en Vivo (Micrófono)

El proyecto incluye el cliente interactivo [live_transcribe.py](file:///home/jose/vllm/live_transcribe.py) para demostrar cómo capturar audio desde el micrófono en vivo, detectar actividad de voz (VAD) para dividir la frase al detectar silencios, y llamar en paralelo a la API de Diarización (puerto 8003) y la API de Whisper (puerto 8001) para transcribir con distinción de interlocutor en tiempo real.

#### Requisitos de grabación:
```bash
sudo apt update && sudo apt install -y libportaudio2
pip install sounddevice numpy scipy requests
```

#### Ejecución:
```bash
python live_transcribe.py
```

---

## 📚 Aprendizajes Técnicos y Optimizaciones

Durante el proceso de configuración y depuración de este proyecto se identificaron y resolvieron diversos aspectos clave sobre la arquitectura de vLLM y el hardware Ampere (RTX 3090):

### 1. Requerimiento del Compilador CUDA (`nvcc`)
* **Problema:** Error `RuntimeError: Could not find nvcc`.
* **Causa:** `FlashInfer` (utilizado por vLLM para el muestreo de tokens) requiere compilar kernels C++/CUDA JIT.
* **Solución:** Instalar `nvidia-cuda-toolkit` en el sistema Linux.

### 2. Tipo de Datos para Caché KV en GPUs SM86 (RTX 3090)
* **Problema:** Error `ValueError: FP8 KV cache is not supported by Triton attention backend on RTX 3090 (compute capability 8.6)`.
* **Causa:** El soporte nativo para FP8 en caché KV requiere GPUs de arquitectura Ada Lovelace/Hopper (SM89+).
* **Solución:** Configurar explícitamente `KV_CACHE_DTYPE=bfloat16`.

### 3. Ajuste de Muestreo por Tamaño de Vocabulario (Sampler Warmup OOM)
* **Problema:** `CUDA out of memory` durante la fase de *warmup* del sampler.
* **Causa:** Gemma 4 posee un vocabulario muy amplio (~256.000 tokens). Al realizar el *warmup* con 256 secuencias simultáneas por defecto, la asignación del mapa de probabilidades colapsaba la VRAM restante.
* **Solución:** Limitar `--max-num-seqs 64`, garantizando un consumo controlado durante el arranque.

### 4. Rendimiento de GPU Pura vs. CPU Offload (`SWAP_SPACE`)
* **Demostración Empírica:**
  * **GPU Pura (`SWAP_SPACE=0`):** Inferencia ultrarrápida de **~70-80 tokens/segundo** en generación y **~128+ tokens/segundo** en prompt throughput al ejecutarse 100% en la VRAM GDDR6X (~936 GB/s).
  * **CPU Offload (`SWAP_SPACE>0`):** La transferencia continua por el bus PCIe (~32 GB/s) genera un cuello de botella que reduce la tasa de generación a **~4 tokens/segundo**.
* **Conclusión:** Se configuró `app.py` para omitir automáticamente la bandera `--cpu-offload-gb` cuando `SWAP_SPACE=0`, obteniendo el máximo rendimiento nativo de la GPU.

### 5. Coexistencia Eficiente de VRAM (Gemma + Whisper)
* **Descubrimiento:** El motor vLLM pre-aloca estáticamente la VRAM al arrancar (default 90% por servidor). Correr dos instancias por defecto colapsaría la GPU (43.2 GB necesarios).
* **Solución:** 
  * Limitamos a Gemma 4 en `.env` con `GPU_MEMORY_UTILIZATION=0.50` (ocupa ~13 GB). Su arquitectura híbrida sliding-window reduce el peso de la caché KV para 128K tokens a solo ~3.6 GB.
  * Limitamos a Whisper en `app_whisper.py` con `--gpu-memory-utilization 0.10` (ocupa ~2.8 GB).
  * **Resultado:** Ambos servicios corren permanentemente en GPU consumiendo juntos ~15.8 GB, dejando más de 8 GB libres para el uso intermitente de F5-TTS.

### 6. Muestreo Frecuencial de Audio para Modelos de Voz
* **Problema:** Enviar audios convertidos para F5-TTS (24 kHz) a modelos de procesamiento conversacional (como Whisper o Gemma 4) producía transcripciones incomprensibles y bucles infinitos en alemán (*"die neunzehntausend..."*).
* **Causa:** Los modelos de reconocimiento de voz esperan ondas remuestreadas estrictamente a la frecuencia estándar de **16.000 Hz (16 kHz)**.
* **Solución:** Implementar re-muestreo dinámico a 16kHz mono mediante `torchaudio` antes del envío (ver [test_transcription.py](file:///home/jose/vllm/test_transcription.py) y [test_whisper_api.py](file:///home/jose/vllm/test_whisper_api.py)).

### 7. Sintaxis de Prompts Multimodales de Audio
* **Descubrimiento:** vLLM recibe el audio serializado en Base64 mediante el esquema `data:audio/wav;base64,...` en el tipo `audio_url`.
* **Ubicación:** Para el modelo Gemma 4, el audio debe ir colocado *después* del texto. Además, el texto del prompt debe incluir la etiqueta de marcador de posición **`<|audio|>`** para indicarle al modelo dónde inyectar los embeddings de audio:
  `"Transcribe este audio de voz: <|audio|>"`
  Sin la etiqueta en el prompt, el modelo ignora el archivo de audio o responde: *"No se proporcionó ningún audio para transcribir."*

### 8. CPU-GPU Offloading Dinámico para Multilingüismo
* **Problema:** Cargar en paralelo 6 modelos de voz distintos (uno por cada idioma) colapsaría la GPU (~7.2 GB de VRAM requeridos solo para TTS).
* **Solución:** Implementar administración perezosa (*lazy loading*) en [app_tts.py](file:///home/jose/vllm/app_tts.py). Los modelos inactivos se instancian en la RAM del sistema (CPU) y se transfieren a la GPU (CUDA) sobre el bus PCIe bajo demanda en menos de 0.2 segundos.
* **Resultado:** Soporte completo de 6 idiomas nativos con un consumo constante y controlado de **~1.2 GB de VRAM**.

---

## 🎙️ Clonación de Voz con F5-TTS (Zero-Shot TTS)

El proyecto incluye el script [test_f5.py](file:///home/jose/vllm/test_f5.py) para realizar pruebas de clonación de voz (*Zero-Shot Voice Cloning*) utilizando la arquitectura **F5-TTS**.

### 🌍 Repositorios y Checkpoints por Idioma en Hugging Face

En F5-TTS, el idioma se define descargando e instanciando el *checkpoint* específico para ese idioma mediante `hf_hub_download`:

| Idioma | Repositorio (`repo_id`) | Archivo (`filename`) | Arquitectura | Notas |
| :--- | :--- | :--- | :--- | :--- |
| 🇪🇸 **Español** | `jpgallegoar/F5-Spanish` | `model_1200000.safetensors` | `F5TTS_Base` | 218h audio (AR, CL, ES, PE, VE). |
| 🇺🇸 / 🇨🇳 **Inglés y Chino** | `SWivid/F5-TTS` | *(descarga automática)* | `F5TTS_v1_Base` | Modelo base oficial de SWivid. |
| 🇫🇷 **Francés** | `RASPIAUDIO/F5-French-MixedSpeakers-reduced` | `model_last_reduced.pt` | `F5TTS_Base` | LibriVox FR, múltiples hablantes. |
| 🇩🇪 **Alemán** | `aihpi/F5-TTS-German` | `F5TTS_Base/model_420000.safetensors` | `F5TTS_Base` | HPI, Common Voice + Emilia_DE. |
| 🇷🇺 **Ruso** | `hotstone228/F5-TTS-Russian` | `model_last.safetensors` | `F5TTS_Base` | Afinado en ruso. |
| 🇯🇵 **Japonés** | `Jmica/F5TTS` | `JA_21999120/model_21999120.pt` | `F5TTS_Base` | Requiere `vocab_japanese.txt`. |

> **⚠️ IMPORTANTE:** Los modelos comunitarios (ES, FR, DE, RU, JA) fueron entrenados sobre `F5TTS_Base` (con `text_mask_padding: False`). El modelo base oficial (EN/ZH) usa `F5TTS_v1_Base`. Usar la arquitectura incorrecta produce audio incomprensible.

#### Ejemplo de uso en Python (`test_f5-es.py`):

```python
from huggingface_hub import hf_hub_download
from f5_tts.api import F5TTS

# Cargar checkpoint específico para Español
ckpt_path = hf_hub_download(repo_id="jpgallegoar/F5-Spanish", filename="model_1200000.safetensors")
vocab_path = hf_hub_download(repo_id="jpgallegoar/F5-Spanish", filename="vocab.txt")

# IMPORTANTE: especificar model="F5TTS_Base" para modelos comunitarios
f5tts = F5TTS(model="F5TTS_Base", ckpt_file=ckpt_path, vocab_file=vocab_path)

f5tts.infer(
    ref_file="mi_voz_24k_mono.wav",
    ref_text="Texto correspondiente a tu muestra de audio",
    gen_text="Texto en español que quieres que diga tu voz clonada",
    speed=1.0,
    file_wave="resultado_clonado.wav"
)
```

---

## 📄 Licencia

Este proyecto está distribuido bajo la [Licencia MIT](LICENSE).
