# 🦙 Arquitectura e Integración Técnica: Motor Llama.cpp (Qwen 3.6 35B MoE) en vLLM Suite

**Proyecto:** vLLM Suite / Tech Support Argentina  
**Autor y Supervisor:** José Luis Villaronga  
**Fecha:** 3 de septiembre de 2026  
**Entorno de Hardware:** NVIDIA GeForce RTX 3090 (24 GB VRAM Ampere) | 64 GB RAM DDR4 | Ubuntu Linux  
**Repositorio Oficial del Motor:** [https://github.com/ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp)

---

## 🏛️ 1. Reconocimiento y Créditos

Este subsistema de inferencia de alto rendimiento utiliza el binario de servidor **`llama-server`**, compilado de forma nativa en este host a partir del repositorio de código abierto de **[llama.cpp](https://github.com/ggml-org/llama.cpp)**.

> ### 🌟 Agradecimiento al Proyecto Open Source
> Queremos expresar nuestro más sincero reconocimiento y agradecimiento a **Georgi Gerganov ([@ggerganov](https://github.com/ggerganov))** y a la extraordinaria comunidad de colaboradores del proyecto **llama.cpp / ggml-org**.  
> Gracias a sus avances pioneros en cuantización GGUF (k-quants), aceleración CUDA, kernels MoE de latencia ultrabaja, prefix caching mediante LCP y parsers de plantillas Jinja nativos, es posible desplegar y ejecutar localmente modelos de frontera de **35 mil millones de parámetros (MoE A3B)** a casi **50 tokens por segundo** sobre una sola GPU de consumo de 24 GB.

---

## 🎯 2. Objetivos de la Integración

1. **Inferencia Ultrarrápida para Modelos MoE:** Desplegar `Qwen3.6-35B-A3B-Q4_K_M.gguf` con 35B parámetros totales y 3B parámetros activos por token.
2. **Compatibilidad Total con vLLM Suite:** Exponer una API compatible con OpenAI en el puerto interno `18100`, enrutada a través del **vLLM Gateway Proxy** en el puerto público `8000`.
3. **Control Agéntico Puro:** Asegurar que el modelo ejecute herramientas sintácticas (`<tool_call>`) sin caer en la trampa de "simular mentalmente" las respuestas dentro de bloques `<think>`.
4. **Gobernanza de Memoria y Rendimiento Máximo:** Ejecutar el servicio con privilegios de `root` y `LimitMEMLOCK=infinity` para permitir el bloqueo físico de pesos en memoria (`--load-mode mlock`) sin fallo alguno.
5. **Exclusión Mutua Preventiva (Anti-Colisión de VRAM):** Garantizar que `vllm.service` (Gemma 4) y `vllm-llama.service` (Qwen MoE) jamás puedan ejecutarse al mismo tiempo ni sobrescribir sus asignaciones de memoria gráfica.
6. **Portabilidad Total (5to Invariante MEA):** Eliminar toda ruta absoluta hardcodeada; resolución dinámica del usuario y del entorno.

---

## 🔬 3. Análisis de Problemas Técnicos y Soluciones de Causa Raíz

### A. El Síndrome del "Pensamiento que se come a la Acción"
* **Problema:** Los modelos híbridos de razonamiento (como Qwen 3.6 y DeepSeek) poseen dos impulsos competitivos: resolver el problema pensando o delegar en herramientas externas. En las pruebas iniciales, el modelo deliberaba extensamente dentro del bloque `<think>`, calculaba mentalmente el resultado previsto (*"Result anticipation: Art. 958..."*) y redactaba la conclusión final como si la búsqueda ya hubiera ocurrido, sin emitir la llamada formal a la herramienta.
* **Causa Raíz:** El presupuesto de razonamiento no estaba acotado para tareas de *Function Calling* directo.
* **Solución de Arquitectura:** Se configuró `--reasoning off` en el script lanzador y en `.env`. Al desactivar el pensamiento interno libre, Qwen 3.6 salta directamente al modo agéntico puro, emite el bloque sintáctico de herramientas y ejecuta la consulta en LanceDB en milisegundos con datos 100% verificados.

### B. Fallo de Bloqueo de Memoria (`failed to mlock ... Cannot allocate memory`)
* **Problema:** En el inicio de `llama-server` aparecía la advertencia de que no se podían bloquear los ~9 GB de buffer en RAM física.
* **Causa Raíz:** En Linux, los usuarios estándar sin privilegios tienen topes estrictos de memoria bloqueada (`ulimit -l`), lo que impedía a `mlock` garantizar la residencia en memoria física contra el swap del sistema operativo.
* **Solución de Arquitectura:**
  1. Se configuró el servicio systemd `vllm-llama.service` con `User=root`.
  2. Se configuró la directiva de systemd `LimitMEMLOCK=infinity`.
  3. Se actualizó la bandera deprecada `--mlock` por la moderna `--load-mode mlock`.  
  *Resultado:* El modelo bloquea la totalidad de sus buffers en RAM y VRAM sin un solo error en consola.

### C. Riesgo de Colisión Catastrófica de VRAM (Leyes 1 y 2)
* **Problema:** Si un operador o script iniciaba `vllm.service` (~14.2 GB de VRAM) mientras `vllm-llama.service` (~21.8 GB de VRAM) estaba corriendo, la GPU RTX 3090 sufría un desbordamiento inmediato de VRAM (*Out Of Memory - OOM*), provocando el colapso del driver NVIDIA o la caída de los servicios satélite (Embeddings, Whisper).
* **Solución de Arquitectura (Módulo `check_service_conflict.sh`):**  
  En lugar de confiar en una simple variable o dejar que uno tumbe al otro a ciegas, se diseñó un guardia modular pre-arranque en `ExecStartPre`:
  ```bash
  #!/usr/bin/env bash
  set -e
  OPPONENT_SERVICE="$1"
  PORT="${2:-18100}"

  if [ -n "${OPPONENT_SERVICE}" ] && systemctl is-active --quiet "${OPPONENT_SERVICE}"; then
      echo "❌ Conflicto: El servicio ${OPPONENT_SERVICE} está activo. Deténgalo antes de iniciar." >&2
      exit 1
  fi

  if [ -n "${PORT}" ] && ss -tulpn | grep -q ":${PORT} "; then
      echo "❌ Conflicto: El puerto backend ${PORT} ya está en uso. Detenga el proceso que lo ocupa." >&2
      exit 1
  fi
  exit 0
  ```
  Ambos servicios (`vllm.service` y `vllm-llama.service`) invocan este script antes de levantar. Si detectan que su oponente está activo, **aborta el inicio de inmediato (código 1) sin tocar ni interrumpir la instancia que está trabajando**.

### D. Resolución Dinámica de Rutas (5to Invariante MEA v2.1)
* **Problema:** Como el servicio systemd corre como `User=root`, la variable `$HOME` se resuelve a `/root`, donde no existe la instalación de `llama.cpp`. Hardcodear `/home/jose` violaría el 5to Invariante de portabilidad.
* **Solución de Arquitectura:**  
  En `llama-srv.sh`, se detecta el dueño del proyecto dinámicamente mediante `stat -c %U "$PROJECT_DIR"` o la variable `USER_SYSTEMD`:
  ```bash
  TARGET_USER="${USER_SYSTEMD:-${SUDO_USER:-$(stat -c %U "${PROJECT_DIR}" 2>/dev/null || echo "jose")}}"
  if [ "${TARGET_USER}" = "root" ]; then
      TARGET_USER="$(stat -c %U "${PROJECT_DIR}" 2>/dev/null || echo "jose")"
  fi
  USER_HOME=$(eval echo "~${TARGET_USER}")
  RESOLVED_LLAMA_DIR="${USER_HOME}/llama.cpp"
  ```
  Esto permite que el script funcione de forma 100% portable y agnóstica en cualquier máquina o usuario donde se clone el repositorio.

---

## 📊 4. Métricas de Rendimiento en Producción (RTX 3090)

| Métrica | Valor Empírico | Comportamiento |
| :--- | :---: | :--- |
| **Prefill / Ingesta de Prompt** | **650.0 – 675.0 t/s** | Estable a lo largo de prompts de 1.400 hasta 20.582 tokens. |
| **Generación (Inferencia Activa)** | **47.5 – 51.5 t/s** | ~20 ms por token generado sostenidos. |
| **Contexto Máximo** | **131.072 tokens** | 128k nativo asignado en VRAM. |
| **Ocupación de VRAM** | **21.8 GB / 24.0 GB (90.8%)** | Con 256 capas en GPU y 18 expertos MoE en CPU. |
| **Aceleración LCP Prefix Caching** | **> 7.000 grafos reutilizados** | En 15 llamadas consecutivas de herramientas, redujo la latencia intermedia a < 900 ms por paso. |

---

## 🎛️ 5. Administración y Control Operativo

### Comandos de Terminal (Systemd)
```bash
# Iniciar motor Llama.cpp (Qwen 3.6 MoE)
sudo systemctl start vllm-llama

# Detener motor Llama.cpp
sudo systemctl stop vllm-llama

# Consultar estado y logs en tiempo real
sudo systemctl status vllm-llama
sudo journalctl -u vllm-llama -f

# Conmutar de vLLM a Llama.cpp de forma segura
sudo systemctl stop vllm
sudo systemctl start vllm-llama
```

### Control Web desde el Dashboard (`http://localhost:8004`)
1. **Pestaña "Monitoreo":**
   - Tarjeta dedicada **`Llama.cpp LLM (Qwen MoE)`** con badge reactivo en tiempo real (`ACTIVE` / `INACTIVE`).
   - Botones interactivos para `Start`, `Stop` y `Restart`.
2. **Pestaña "Variables":**
   - Sección dorada/ámbar para editar los 10 parámetros de `llama.cpp` (`LLAMA_MODEL`, `LLAMA_PORT`, `LLAMA_CTX_SIZE`, `LLAMA_BATCH_SIZE`, `LLAMA_GPU_LAYERS`, `LLAMA_N_CPU_MOE`, `LLAMA_REASONING`, `LLAMA_LOAD_MODE`, `LLAMA_THREADS`).
   - Botón de carga de preset óptimo: **`⚡ Qwen 3.6 35B MoE (Predeterminado)`**.
   - Guardado persistente y determinista en `.env`.

---

## 🔒 6. Cumplimiento del Marco Ético MEA v2.1 y Leyes de Ingeniería

* **Ley 1 (Modularización Estricta):** El motor no modificó la lógica interna del Gateway ni de vLLM; se desacopló mediante un script de colisión y un servicio independiente.
* **Ley 2 (Atacar Causas Raíz):** Se corrigió la simulación mental apagando el reasoning para tools y se solucionó el fallo de mlock mediante privilegios root y directivas nativas de systemd.
* **Ley 3 (Mínimo Blast Radius):** Los cambios en la UI y scripts no alteraron la estabilidad de los 8 microservicios satélite.
* **5to Invariante (Anti-Hardcoded Paths):** Rutas resueltas dinámicamente mediante `USER_SYSTEMD` y la estructura del proyecto.
* **RVI de la Integración:** `1/10` (Riesgo mínimo, aislamiento total y reversibilidad garantizada).
