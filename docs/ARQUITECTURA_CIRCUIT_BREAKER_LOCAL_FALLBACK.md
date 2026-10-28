# 🛡️ Arquitectura Circuit Breaker: Fallback de Alta Disponibilidad a la Nube para Inferencia Local

**Proyecto:** vLLM Suite / Tech Support Argentina  
**Autor y Supervisor:** José Luis Villaronga  
**Fecha:** 28 de octubre de 2026  
**Subsistema:** Gateway de Seguridad y Reverse Proxy (`gateway/`)  
**Estándar Operativo:** Resiliencia Operativa ASD-STE100 (Ley 5) | Modularización Estricta (Ley 1) | Integridad RAG (Ley 4)  

---

## 🏛️ 1. Resumen Ejecutivo y Propósito

En entornos de inferencia local de alto rendimiento (vLLM y llama.cpp sobre GPU de 24 GB VRAM), existen escenarios críticos donde el motor local puede quedar fuera de servicio:
1. Reinicio o mantenimiento programado del host de cómputo.
2. Desbordamiento no advertido de memoria gráfica (*CUDA Out Of Memory - OOM*).
3. Parada o cambio de modelo entre `vllm.service` y `vllm-llama.service`.

En arquitecturas tradicionales, este incidente devuelve errores inmediatos `502 Bad Gateway`, `Connection Refused` o desconexión en clientes externos como **Open WebUI**, interrumpiendo el flujo operativo de los usuarios y agentes de IA.

El subsistema **Circuit Breaker con Fallback a la Nube** actúa como una red de seguridad elástica:
* **Conmutación transparente e instantánea:** Detecta la caída del motor local y enruta las solicitudes a un proveedor en la nube configurado (OpenRouter, DeepSeek, Groq, etc.).
* **Transparencia absoluta de contrato:** El modelo mantiene inalterado su identificador (`local/CorpAI-Gen`) y su nombre descriptivo (`local/CorpAI-Gen | Legal & Compliance`) tanto en el catálogo `/v1/models` como en cada chunk de streaming emitido.
* **Retorno autónomo (Auto-Recovery):** Un monitor en segundo plano desacoplado verifica el estado del puerto local y restaura el tráfico a la GPU en cuanto el motor vuelve a estar operativo, sin latencia añadida en las consultas de los usuarios.

---

## 🔬 2. Principios de Ingeniería Aplicados

### A. Latencia Cero en la Petición ($0\text{ ms}$ overhead - Ley 3)
La decisión de ruta se toma leyendo directamente una variable booleana atómica en memoria (`_local_engine_healthy`). No se realizan pings bloqueantes, handshakes de red ni consultas HTTP en el camino crítico de la petición del usuario.

### B. Fast Failover Reactivo ($1\text{ ms}$ TCP RST)
* Cuando el proceso local muere o el servicio se detiene, el kernel de Linux responde de forma inmediata con un paquete `TCP RST` (*Connection Refused*).
* La excepción en el Gateway (`httpx.ConnectError`) ocurre en menos de $2\text{ ms}$.
* La petición en curso captura el fallo, marca el disyuntor en `False` en memoria, reconstruye el payload hacia el proveedor cloud y entrega la respuesta al usuario en esa misma llamada.
* A partir de ese milisegundo, las siguientes peticiones detectan el disyuntor en `False` y viajan directamente a la nube sin tocar el puerto local.

### C. Connect Timeout Quirúrgico para Procesos Congelados
* Si el proceso del motor no murió pero la GPU quedó en *deadlock* o congelada sin responder a nivel de socket:
  * Se aplica una regla estricta de tiempo de conexión (`LOCAL_FALLBACK_CONNECT_TIMEOUT`, predeterminado en `1.0s`).
  * En conexiones sobre `127.0.0.1`, un handshake TCP toma $<0.5\text{ ms}$. Si en 1 segundo no conecta, se declara caído, salta el disyuntor y se conmuta a la nube.

### D. Integridad RAG y Grounding MEA (Ley 4)
* El enriquecimiento de contexto documental en LanceDB, la búsqueda web periférica y la inyección de directivas deontológicas MEA se ejecutan en el Gateway **antes** del despacho de la inferencia.
* En consecuencia, el modelo sustituto en la nube opera exactamente con el mismo contexto corporativo y base de conocimiento que el motor local.

---

## 📐 3. Diagrama de Estados del Disyuntor

```mermaid
stateDiagram-v2
    [*] --> Local_Operativo: Inicio del Gateway
    
    state Local_Operativo {
        [*] --> Trafico_GPU: _local_engine_healthy = True
        Trafico_GPU --> Trafico_GPU: Inferencia en :18100 (0ms overhead)
    }

    Local_Operativo --> Fallback_Cloud_Activo: TCP RST (1ms) o Connect Timeout (1s)
    note on link
      Disyuntor Reactivo:
      1. mark_local_engine_down()
      2. Conmutación a Proveedor Cloud
      3. Enmascarar modelo a local/CorpAI-Gen
    end note

    state Fallback_Cloud_Activo {
        [*] --> Bypass_Directo: _local_engine_healthy = False
        Bypass_Directo --> Bypass_Directo: Tráfico directo a Cloud (0ms espera)
    }

    Fallback_Cloud_Activo --> Local_Operativo: Sonda de fondo recibe HTTP 200 OK (:18100/health)
    note on link
      Auto-Recovery Desacoplado:
      1. Intervalo programado (60s)
      2. mark_local_engine_up()
      3. Retorno instantáneo a GPU
    end note
```

---

## ⚙️ 4. Variables de Entorno (`.env`)

Las siguientes variables gobiernan el comportamiento del Circuit Breaker y se configuran al inicio del archivo de entorno:

| Variable | Tipo | Predeterminado | Descripción |
| :--- | :---: | :---: | :--- |
| `LOCAL_FALLBACK_ENABLED` | Booleano | `false` | Conmutador maestro para activar o desactivar el fallback a la nube. |
| `LOCAL_FALLBACK_PROVIDER_ID` | String | `""` | ID del proveedor cloud en MongoDB (OpenRouter, DeepSeek, Groq, etc.). Si está vacío, usa el primer proveedor activo. |
| `LOCAL_FALLBACK_MODEL` | String | `""` | Identificador del modelo en el proveedor destino (ej: `meta-llama/llama-3.3-70b-instruct`). |
| `LOCAL_FALLBACK_CHECK_INTERVAL`| Número | `60` | Frecuencia en segundos de la tarea asíncrona de fondo que sondea el estado del motor local. |
| `LOCAL_FALLBACK_CONNECT_TIMEOUT`| Número | `1.0` | Timeout máximo en segundos para establecer la conexión TCP con `127.0.0.1:18100`. |

---

## 🧩 5. Módulos y Arquitectura de Código

El subsistema se divide en componentes modulares con responsabilidades atómicas (Ley 1):

```
vllm-suite/
├── gateway/
│   ├── cloud/
│   │   ├── local_fallback.py      # Estado en memoria, disyuntor y lazo de sondeo en segundo plano
│   │   └── cloud_router.py        # Inyección virtual de local/CorpAI-Gen en /v1/models ante caída
│   ├── proxy/
│   │   └── proxy_factory.py       # Intercepción reactiva, despacho cloud y enmascaramiento de streaming
│   └── server.py                  # Orquestación concurrente con local_fallback_monitor_loop()
├── dashboard/
│   └── core/
│       └── env_manager.py         # Lectura y persistencia de variables preservando estructura
├── templates/
│   └── tabs/
│       └── tab_config.html        # Panel visual superior en la pestaña Variables (.env)
└── static/
    └── js/
        └── dashboard_core.js      # Inicialización dinámica, selectores de proveedores/modelos y badges
```

### Funciones Clave del Módulo `local_fallback.py`
* `is_local_engine_healthy() -> bool`: Lectura atómica de memoria para resolución inmediata de rutas.
* `mark_local_engine_down()`: Transición a estado caído; emite aviso formal en consola.
* `mark_local_engine_up()`: Transición a estado recuperado; restablece la prioridad de la GPU.
* `get_local_fallback_target() -> (prov_dict, model_str)`: Resuelve la clave API, URL base y modelo destino desde MongoDB o configuración.
* `local_fallback_monitor_loop()`: Bucle asíncrono desacoplado (`asyncio.create_task`) que ejecuta la sonda `GET /health` cada $N$ segundos.

---

## 📋 6. Runbook Operativo a las 3 AM (Estándar ASD-STE100)

### Escenario 1: El motor local se detiene inesperadamente
1. **Comportamiento Automático:**
   * El Gateway captura la caída en $<2\text{ ms}$.
   * El disyuntor se activa: `⚠️ [Circuit Breaker] Motor local declarado NO DISPONIBLE. Activando conmutación a Fallback Cloud.`
   * Open WebUI continúa respondiendo con el modelo en la nube configurado.
   * La telemetría registra las peticiones con el ID `local/CorpAI-Gen`.
2. **Acción del Operador:**
   * Ninguna acción urgente requerida para restaurar el servicio de los usuarios.
   * Diagnosticar el motivo del apagón local en los logs del servicio:
     ```bash
     journalctl -u vllm-llama.service -n 100 --no-pager
     # o bien
     journalctl -u vllm.service -n 100 --no-pager
     ```
   * Reiniciar el servicio local cuando corresponda:
     ```bash
     sudo systemctl start vllm-llama.service
     ```
3. **Recuperación Automática:**
   * En cuanto el motor cargue los pesos y responda `200 OK`, el monitor emite:
     `✅ [Circuit Breaker] Motor local (:18100) recuperado y operativo. Restableciendo tráfico a la GPU local.`
   * El tráfico vuelve a la GPU local de forma inmediata.

### Escenario 2: Cambiar el modelo o proveedor de respaldo desde la GUI
1. Ingresar al Dashboard web en la pestaña **Variables (.env)**.
2. En el panel superior **Alta Disponibilidad & Fallback Nube**:
   * Cambiar el selector **Proveedor Cloud de Respaldo** al proveedor deseado.
   * Seleccionar el **Modelo Cloud Sustituto** de la lista desplegable actualizada automáticamente.
   * (Opcional) Ajustar el **Sondeo de Recuperación** o el **Connect Timeout**.
3. Hacer clic en **Guardar y Aplicar**.
4. Los cambios se persisten de inmediato en `.env` sin necesidad de reiniciar servicios.

### Escenario 3: Desactivar por completo el Fallback a la Nube
1. En la pestaña **Variables (.env)**, cambiar **Fallback Activo** a `false (Desactivado)`.
2. Hacer clic en **Guardar y Aplicar**.
3. El Gateway volverá al comportamiento tradicional (si el motor local cae, responderá con error estándar sin consultar proveedores externos).
