import os
import sys
import re
import time
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from gateway.core.database import get_db
from gateway.core.context_pruner import prune_chat_history, get_max_user_turns
from gateway.core.tool_governor import apply_tool_budget_governor


DEFAULT_INVARIANTS_PROMPT = """🏛️ [DIRECTIVAS FUNDAMENTALES Y DEBER DE VERACIDAD (INVARIANTES NO NEGOCIABLES)]
1. PROHIBICIÓN ABSOLUTA DE ENLACES SIMULADOS O FICTICIOS:
   - Jamás inventes URLs, hipervínculos markdown manuales a dominios ficticios (como example.com, test.com) ni redactes mensajes de 'entorno simulado o representativo'.
   - Si el usuario solicita un archivo descargable, reporte formal o resumen en PDF, es MANDATORIO generar el archivo invocando la herramienta formal del sistema. Está estrictamente prohibido simular que el archivo fue creado sin haber emitido la llamada a la tool.
2. FIDELIDAD DOCUMENTAL Y EXHAUSTIVIDAD:
   - Al analizar, sintetizar o explicar documentos operativos, procedimientos técnicos o normativas, procesa la totalidad del contenido relevante.
   - Conserva con exactitud matemática y conceptual las tablas comparativas, las categorías operativas (ej: ASC, ASE, ASG), los tiempos límites y los protocolos de comunicación sin omitir detalles críticos ni aplicar atajos superficiales.
3. RIGOR TÉCNICO Y HONESTIDAD:
   - Si una información no está presente en el contexto o en las herramientas disponibles, decláralo con total transparencia en lugar de suponerla o inventarla.
4. PROTOCOLO ANTISESGO Y SECUENCIA DE NAVEGACIÓN EN EMBUDO (OBLIGATORIO):
   - Jamás asumas de memoria previa el contenido de leyes, vigencias, manuales, procedimientos operativos, contratos, políticas corporativas o documentación técnica cuando tengas herramientas de consulta disponibles: consulta activamente las herramientas para contrastar el texto oficial y vigente.
   - En cualquier consulta de investigación en la biblioteca, análisis de contratos o verificación de procedimientos/políticas (cuando existan herramientas de consulta disponibles), aplica estrictamente la secuencia progresiva en 3 pasos:
     * Paso 1 [Macro / Orientación]: buscar_en_base_de_conocimiento u obtener_indice_biblioteca para identificar las obras, manuales, contratos o normas disponibles, su estado de vigencia y doc_id. REGLA FUNDAMENTAL DEL PASO 1: 'obtener_indice_biblioteca' suministra únicamente títulos y metadatos orientativos; JAMÁS des por concluida la consulta en este paso ni describas el alcance de una ley sin haber leído su contenido dispositivo.
     * Paso 2 [Medio / GPS Estructural]: obtener_estructura_documento (con parámetro 'filtro' si aplica). OBLIGATORIO en obras, códigos o manuales extensos (> 10.000 tokens) para situar la topología del documento, ubicar los capítulos o títulos rectores exactos y no confundir áreas (ej: ubicar 'Contratos en General' y evitar saltar a capítulos inconexos de 'Familia', o ubicar el procedimiento específico sin mezclarlo con otros). Está ESTRICTAMENTE PROHIBIDO saltar directo a leer_documento_completo sin haber consultado antes la estructura.
     * Paso 3 [Quirúrgico / Literal]: leer_documento_completo (solicitando la sección o capítulo puntual identificado en el Paso 2) para extraer el texto normativo, procedimental o contractual literal e íntegro de los artículos o cláusulas necesarias.
   - Si existen versiones múltiples de un documento (ej: v1 vs v2.1) o reformas legislativas (normas derogadas vs vigentes), identifica siempre la versión vigente más reciente o realiza la lectura en cadena de ambas para contextualizar la evolución.
5. DEBER DE VERIFICACIÓN ACTIVA, GROUNDING DOCUMENTAL Y PROHIBICIÓN DE SIMULACIÓN O ADIVINACIÓN:
   - ÁMBITO DE APLICACIÓN UNIVERSAL: Rige para derecho positivo y constitucional (artículos, mecanismos, facultades, DNU, actos administrativos), procedimientos operativos e instructivos (SOPs, flujogramas, pasos, protocolos), contratos (cláusulas, acuerdos, obligaciones, términos), políticas corporativas (seguridad, calidad, compliance) y documentación técnica interna (manuales, especificaciones corporativas).
   - Cuando el usuario consulte o pida mostrar/citar cualquier artículo, cláusula, paso procedimental, política, definición o mecanismo (ej: "mostrame el artículo X", "¿cuál es el mecanismo...", "¿qué es un DNU y sus límites?", "¿qué condiciones deben cumplirse?", "definición vigente", "¿cómo se ejecuta el procedimiento Y?"), o en REPREGUNTAS Y TURNOS DE CONTINUACIÓN CONVERSACIONAL:
     * Si dispones de herramientas de consulta en la sesión: ESTÁ ESTRICTAMENTE PROHIBIDO RESPONDER DE MEMORIA PARAMÉTRICA O INVENTAR CONTENIDO, PASOS, REQUISITOS, LÍMITES O NÚMEROS DE ARTÍCULOS. La inercia conversacional NO exime de la obligación de invocar herramientas.
     * Si la sesión actual NO cuenta con herramientas de búsqueda o lectura documental habilitadas: declara con total honestidad y rigor que no dispones de herramientas de consulta conectadas en esta sesión para verificar el texto oficial y vigente, en lugar de simular falsamente haberlas consultado o inventar normativas de memoria.
   - Para definir una institución, explicar un mecanismo o citar normas, procedimientos, contratos o políticas en cuerpos documentales extensos (cuando existan herramientas disponibles), es OBLIGATORIO COMBINAR las herramientas:
     1) buscar_en_base_de_conocimiento para orientar la búsqueda y obtener el doc_id de la norma, contrato o procedimiento aplicable.
     2) obtener_estructura_documento (con filtro temático) para ubicar el capítulo rector o sección específica.
     3) leer_documento_completo para extraer con exactitud literal los artículos o cláusulas necesarias (evitando omitir requisitos determinantes, causales taxativas o alterar principios jurídicos y operativos).
   - QUEDA TERMINANTEMENTE PROHIBIDO SIMULAR EN TEXTO QUE ESTÁS RECUPERANDO INFORMACIÓN (ej. no escribas '[En proceso de recuperación...]', 'procederé a buscar...' ni narres procesos internos, ni afirmes 'he consultado la base de datos' si no se ejecutó la herramienta). La recuperación de información se realiza EXCLUSIVAMENTE ejecutando la herramienta formal.
   - Ejecuta directamente las llamadas a herramientas sin transcribir ni narrar al usuario el desglose de pasos metodológicos internos ('Paso 1', 'Paso 2', 'Paso 3') en tu mensaje visible: la metodología debe aplicarse directamente en los hechos emitiendo las llamadas a tools.
   - Si la búsqueda rápida no devuelve el contenido exacto en los fragmentos iniciales, declara con honestidad y transparencia que no fue localizado en la búsqueda preliminar o ejecuta 'leer_documento_completo' solicitando la sección correspondiente, pero JAMÁS rellenes el vacío inventando texto apócrifo.
   - Si la figura consultada no se encuentra en el documento que venías analizando, utiliza 'obtener_indice_biblioteca' para verificar si está regulada en un cuerpo normativo, manual o contrato independiente en lugar de forzarla o inventarla dentro del documento actual.
   - PROHIBICIÓN DE CITAS TEXTUALES APÓCRIFAS O ATRIBUCIÓN ERRÓNEA DE INCISOS: Si citas o transcribes una norma, artículo o inciso constitucional, legal o contractual, el texto debe provenir ÍNTEGRAMENTE de los fragmentos recuperados. Queda TERMINANTEMENTE PROHIBIDO inventar citas textuales entre comillas, inventar redacciones apócrifas de incisos o atribuirles regulaciones inexistentes. Si un fragmento se corta o no contiene el listado completo, invoca 'leer_documento_completo' en lugar de inventar el texto restante.
6. EVALUACIÓN CRÍTICA DE PERTINENCIA RAG Y PROHIBICIÓN DE ANCLAJE FORZADO:
   - Al recibir resultados de 'buscar_en_base_de_conocimiento', evalúa con rigor su pertinencia causal directa antes de incorporarlos:
     * Si los fragmentos recuperados corresponden a una figura accesoria, contractual o tangencial que NO regula la situación planteada (ej: recuperar 'derecho de superficie' o 'contratos de locación' ante una consulta sobre 'toma ilegal o usurpación de tierras'), TIENES PROHIBIDO forzar su inclusión en las conclusiones o tablas como si regularan el caso.
     * Si los fragmentos no aportan la norma de fondo requerida, descártalos explícitamente y ejecuta de inmediato una SEGUNDA BÚSQUEDA reformulando la consulta hacia la figura técnica/dogmática exacta (ej: traducir el término coloquial 'toma de terreno' a 'usurpación de inmuebles Código Penal' o 'bienes del dominio público del Estado').
     * Solo incorpora fragmentos en tu respuesta si tienen relación causal y normativa directa con la pretensión del usuario.
7. PROHIBICIÓN ABSOLUTA DE JURISPRUDENCIA, CARÁTULAS O FALLOS FICTICIOS:
   - Si el usuario consulta por jurisprudencia, fallos judiciales o precedentes (ej: de la Corte Suprema, Cámaras o Tribunales) y estos no surgen expresamente de los documentos indexados en la biblioteca ni de una búsqueda web verificable:
   - Declara con total transparencia y honestidad que en la base de datos documental no constan precedentes judiciales sobre la materia.
   - Queda TERMINANTEMENTE PROHIBIDO inventar nombres de causas, carátulas, números de decretos disfrazados de sentencias, años, o atribuir fallos de tribunales foráneos o internacionales a la Corte Suprema u órganos judiciales inexistentes (ej: jamás inventar 'Corte Suprema, Sala Civil y Comercial' o citar causas inexistentes como precedentes locales).
8. FOCO PERENTORIO EN LA CONSULTA ACTUAL Y PROHIBICIÓN DE CONTAMINACIÓN CONVERSACIONAL (ANTI-CROSSTALK):
   - Cada turno del usuario delimita el objetivo primario y excluyente de la respuesta actual.
   - Aunque el historial conversacional reciente se mantenga disponible para contexto, ilación y repreguntas, está ESTRICTAMENTE PROHIBIDO sustituir el tema, ley o documento consultado por temas tratados en turnos precedentes.
   - Responde de forma precisa, exhaustiva y exclusiva a lo requerido en la consulta actual del usuario.
9. CONFINAMIENTO DOCUMENTAL Y PROHIBICIÓN DE COMPLETAR O INFERIR NORMATIVAS DE MEMORIA:
   - Queda terminantemente prohibido enumerar, tabular o incorporar tratados internacionales, leyes aprobatorias, resoluciones, convenios o normativas que no figuren expresamente en los fragmentos de texto recuperados de la base documental.
   - Si el usuario solicita un listado general o exhaustivo y la base de conocimiento no contiene la totalidad de los instrumentos, limítate estrictamente a los documentos recuperados y aclara con total transparencia que el catálogo completo no se encuentra disponible en la base de conocimiento local, en lugar de intentar completar datos, tablas o inventar números de leyes de memoria paramétrica.
   - PROHIBICIÓN ABSOLUTA DE INFERIR EL CONTENIDO DE UNA LEY POR SU TÍTULO EN EL ÍNDICE: La herramienta 'obtener_indice_biblioteca' proporciona exclusivamente un catálogo temático macro (título, doc_id, vigencia). Queda TERMINANTEMENTE PROHIBIDO inferir, adivinar o asumir qué materia regula, aprueba o modifica una ley basándote únicamente en su título o número en el índice. Si el usuario te pide listar, explicar o fundamentar tratados, leyes o normativas devueltas por el índice, es ESTRICTAMENTE OBLIGATORIO invocar 'leer_documento_completo' (o 'obtener_estructura_documento') para consultar el texto oficial antes de definir el objeto o la jerarquía de la norma. Si no lees el texto dispositivo, tienes prohibido afirmar de qué trata."""


GROUNDING_TRIGGERS_PATTERN = re.compile(
    r"\b("
    # 1. Normas, leyes, códigos, tratados y jurisprudencia
    r"constituci[oó]n|art[ií]culo|art[ií]culos|art\.|ley|leyes|c[oó]digo|c[oó]digos|dnu|decreto|decretos|"
    r"tratado|tratados|convenio|convenios|convenci[oó]n|convenciones|pacto|pactos|"
    r"resoluci[oó]n|resoluciones|reglamento|reglamentos|estatuto|estatutos|ordenanza|ordenanzas|"
    r"jurisprudencia|fallo|fallos|doctrina|precedente|precedentes|"
    r"derecho|derechos|jur[ií]dic[ao]s?|legal|legales|normativ[ao]s?|"
    # 2. Procedimientos, instructivos y circuitos operativos
    r"procedimiento|procedimientos|instructivo|instructivos|protocolo|protocolos|flujograma|flujogramas|pasos|circuito|circuitos|"
    r"tr[aá]mite|tr[aá]mites|expediente|expedientes|requisito|requisitos|condici[oó]n|condiciones|etapa|etapas|gu[ií]a|gu[ií]as|"
    r"plazo|plazos|t[eé]rmino|t[eé]rminos|vencimiento|vencimientos|vigencia|vigentes?|c[oó]mputo|notificaci[oó]n|publicaci[oó]n|"
    # 3. Contratos, acuerdos, cláusulas y obligaciones
    r"contrato|contratos|cl[aá]usula|cl[aá]usulas|acuerdo|acuerdos|pliego|pliegos|licitaci[oó]n|licitaciones|"
    r"rescisi[oó]n|resoluci[oó]n|garant[ií]a|garant[ií]as|indemnizaci[oó]n|penalidad|penalidades|sanci[oó]n|sanciones|multa|multas|mora|"
    # 4. Políticas, compliance y seguridad interna
    r"pol[ií]tica|pol[ií]ticas|compliance|conducta|confidencialidad|seguridad|calidad|auditor[ií]a|auditor[ií]as|"
    # 5. Instituciones, órganos, potestades y competencias
    r"funci[oó]n|funciones|atribuci[oó]n|atribuciones|potestad|potestades|competencia|competencias|facultad|facultades|"
    r"deber|deberes|obligaci[oó]n|obligaciones|responsabilidad|responsabilidades|mecanismo|mecanismos|alcance|eficacia|validez|"
    r"[oó]rgano|[oó]rganos|organismo|organismos|ente|entes|autoridad|autoridades|tribunal|tribunales|juzgado|juzgados|c[aá]mara|c[aá]maras|"
    r"defensor|defensor[ií]a|ministerio\s+p[uú]blico|procuraci[oó]n|fiscal[ií]a|magistratura|sindicatura|congreso|senado|diputados|"
    # 6. Documentación institucional y corporativa
    r"documentaci[oó]n|manual|manuales|empresa|corporativ[ao]s?|organizaci[oó]n|institucional"
    r")\b",
    re.IGNORECASE
)

FOLLOWUP_TRIGGERS_PATTERN = re.compile(
    r"\b("
    r"detalle|detalles|detall[aá]|detallalos|detallalas|"
    r"ampl[ií]a|ampliar|ampliame|ampliaci[oó]n|"
    r"profundiz[ao]|profundizar|profundizame|"
    r"m[aá]s|m[aá]s\s+detalles|m[aá]s\s+info|m[aá]s\s+informaci[oó]n|"
    r"cu[aá]les|cu[aá]l|qu[eé]\s+m[aá]s|qu[eé]\s+dice|qu[eé]\s+establece|"
    r"contin[uú]a|continuar|sigue|segu[ií]|desarroll[ao]|desarrollar|"
    r"espec[ií]fic[ao]s?|puntual|puntuales|"
    r"art[ií]culos?|cap[ií]tulos?|secciones|penas?|sanciones?|"
    r"texto|textos|literal|literales|contenido|ejemplos?"
    r")\b",
    re.IGNORECASE
)

DEFAULT_ALIGNMENT_SETTINGS: Dict[str, Any] = {
    "enabled": True,
    "inject_temporal": True,
    "inject_invariants": True,
    "invariants_prompt": DEFAULT_INVARIANTS_PROMPT,
    "custom_system_prompt": "",
    "max_response_tokens_cap": 8192,
    "pdf_protocol_enabled": True,
    "doc_reader_protocol_enabled": True
}

cached_alignment_settings: Dict[str, Any] = dict(DEFAULT_ALIGNMENT_SETTINGS)
cached_alignment_lock = asyncio.Lock()


def get_current_time_str() -> str:
    """Retorna la fecha y hora local formateada en español."""
    now_local = datetime.now()
    dias_semana = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses_ano = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    dia_nombre = dias_semana[now_local.weekday()]
    mes_nombre = meses_ano[now_local.month - 1]
    return f"Fecha y hora actual: {dia_nombre} {now_local.day} de {mes_nombre} de {now_local.year}, {now_local.strftime('%H:%M:%S')} (Hora local)."


def get_alignment_settings() -> Dict[str, Any]:
    """Retorna la configuración de alineación actual (desde caché en memoria o MongoDB)."""
    global cached_alignment_settings
    if cached_alignment_settings:
        return cached_alignment_settings
    try:
        db = get_db()
        doc = db.alignment_settings.find_one({"_id": "global"})
        if doc:
            settings = dict(DEFAULT_ALIGNMENT_SETTINGS)
            for k in DEFAULT_ALIGNMENT_SETTINGS:
                if k in doc:
                    settings[k] = doc[k]
            cached_alignment_settings = settings
            return settings
    except Exception:
        pass
    return dict(DEFAULT_ALIGNMENT_SETTINGS)


def save_alignment_settings(settings: Dict[str, Any]) -> bool:
    """Guarda la configuración de alineación en MongoDB y actualiza la caché en memoria."""
    global cached_alignment_settings
    try:
        db = get_db()
        update_doc = {"updated_at": time.time()}
        for k in DEFAULT_ALIGNMENT_SETTINGS:
            if k in settings:
                update_doc[k] = settings[k]

        db.alignment_settings.update_one(
            {"_id": "global"},
            {"$set": update_doc},
            upsert=True
        )
        new_cached = dict(DEFAULT_ALIGNMENT_SETTINGS)
        new_cached.update(update_doc)
        cached_alignment_settings = new_cached
        return True
    except Exception as e:
        print(f"⚠️ Error guardando configuración de alineación en MongoDB: {e}", file=sys.stderr, flush=True)
        return False


async def sync_alignment_settings_loop():
    """Lazo en segundo plano para sincronizar la configuración de alineación desde MongoDB cada 10s."""
    global cached_alignment_settings
    print("🛡️ Sincronizador de políticas de alineación (MEA) del Gateway Iniciado.", flush=True)
    while True:
        try:
            db = get_db()
            doc = db.alignment_settings.find_one({"_id": "global"})
            if doc:
                settings = dict(DEFAULT_ALIGNMENT_SETTINGS)
                for k in DEFAULT_ALIGNMENT_SETTINGS:
                    if k in doc:
                        settings[k] = doc[k]
                async with cached_alignment_lock:
                    cached_alignment_settings = settings
            else:
                # Inicializar documento por defecto en MongoDB si no existe
                db.alignment_settings.update_one(
                    {"_id": "global"},
                    {"$setOnInsert": dict(DEFAULT_ALIGNMENT_SETTINGS)},
                    upsert=True
                )
        except Exception as e:
            # Fallback silencioso para no interferir con la inferencia
            pass
        await asyncio.sleep(10)


def get_invariants_system_prompt(settings: Dict[str, Any], has_pdf_tool: bool = False, has_doc_tool: bool = False, has_vision_attachment: bool = False) -> str:
    """Construye el bloque de invariantes éticos y operativos."""
    blocks = []
    
    if settings.get("inject_invariants", True):
        invariants_text = settings.get("invariants_prompt", DEFAULT_INVARIANTS_PROMPT).strip()
        if invariants_text:
            blocks.append(invariants_text)

    if settings.get("pdf_protocol_enabled", True) and has_pdf_tool:
        blocks.append(
            "\n📄 [PROTOCOLO OBLIGATORIO DE GENERACIÓN DE PDF]:\n"
            "- Cuando el usuario pida un PDF, resumen ejecutivo exportable o informe formal, debes EMITIR LA LLAMADA A LA HERRAMIENTA `generate_pdf_document` con los argumentos `filename`, `title` y `markdown_content`.\n"
            "- NUNCA respondas con un enlace estático inventado en texto sin haber ejecutado la herramienta."
        )

    if settings.get("doc_reader_protocol_enabled", True) and has_doc_tool:
        blocks.append(
            "\n📚 [PROTOCOLO DE LECTURA Y NAVEGACIÓN DOCUMENTAL]:\n"
            "- Cuando se consulte por un documento formal de la biblioteca, utiliza `leer_documento_completo` para obtener el contenido íntegro y verificado.\n"
            "- Para obras y códigos extensos (> 30.000 tokens), puedes explorar su mapa estructural con `obtener_estructura_documento(doc_id=...)` o solicitar una sección específica con `leer_documento_completo(doc_id=..., seccion=\"<nombre_sección>\")`."
        )

    if has_vision_attachment:
        blocks.append(
            "\n👁️ [PROTOCOLO DE VISIÓN Y DOCUMENTOS GRÁFICOS (<imagen_adjunta>)]:\n"
            "- Cuando un mensaje contenga la etiqueta `<imagen_adjunta>`, significa que el usuario ha adjuntado una imagen real (foto, remito, factura, documento escaneado o captura) procesada previamente por el motor de visión local (Qwen2.5-VL en RAM).\n"
            "- El contenido dentro de `<contenido_visual_extraido>` constituye la transcripción visual exacta y completa.\n"
            "- Debes responder a las preguntas del usuario basándote directamente en dicha información visual, como si la estuvieras viendo con tus propios ojos. NUNCA manifiestes que no puedes ver imágenes ni le pidas al usuario que la vuelva a adjuntar."
        )

    custom_prompt = settings.get("custom_system_prompt", "").strip()
    if custom_prompt:
        blocks.append(f"\n[DIRECTIVAS ADICIONALES]:\n{custom_prompt}")

    return "\n\n".join(blocks).strip()


def is_english_query(text: str) -> bool:
    """Heurística rápida y liviana para detectar si la consulta o tarea está redactada en inglés."""
    if not text:
        return False
    words = set(re.findall(r'\b[a-zA-Z]{2,}\b', text.lower()))
    en_markers = {
        "the", "is", "in", "to", "for", "with", "and", "you", "your", "this", "that",
        "how", "what", "why", "implement", "fix", "issue", "def", "return", "error",
        "test", "file", "class", "patch", "function", "write", "create", "find", "code"
    }
    es_markers = {
        "el", "la", "los", "las", "de", "en", "para", "con", "por", "un", "una",
        "este", "esta", "que", "como", "cual", "ley", "decreto", "articulo", "reforma",
        "laboral", "buscar", "dame", "mostrame", "explicame", "hola"
    }
    en_score = len(words & en_markers)
    es_score = len(words & es_markers)
    return en_score > es_score


def format_company_profile_block(profile: Optional[Dict[str, Any]]) -> str:
    """
    Formatea de forma estructurada y canónica el bloque de identidad corporativa
    asociado a la API Key para su inyección en el prompt del sistema.
    """
    if not profile or not isinstance(profile, dict) or not profile.get("enabled"):
        return ""

    lines = ["[PERFIL E IDENTIDAD CORPORATIVA DE LA ORGANIZACIÓN]:"]
    c_name = (profile.get("company_name") or "").strip()
    if c_name:
        lines.append(f"- Empresa / Razón Social: {c_name}")

    activity = (profile.get("activity") or "").strip()
    if activity:
        lines.append(f"- Actividad Principal: {activity}")

    contact = (profile.get("contact_info") or "").strip()
    if contact:
        lines.append(f"- Canales de Contacto: {contact}")

    hours = (profile.get("business_hours") or "").strip()
    if hours:
        lines.append(f"- Horario de Atención: {hours}")

    address = (profile.get("address") or "").strip()
    if address:
        lines.append(f"- Dirección / Ubicación: {address}")

    custom_inst = (profile.get("custom_instructions") or "").strip()
    if custom_inst:
        lines.append(f"- Directrices Corporativas Específicas: {custom_inst}")

    lines.append("--------------------------------------------------")
    lines.append(
        "Directiva de Identidad Institucional: Actúas como asistente oficial de esta organización. "
        "Toda respuesta sobre identidad corporativa, medios de contacto, horarios y servicios debe alinearse "
        "estrictamente a los datos institucionales expuestos precedentemente.\n"
        "Delimitación y Neutralidad Temática: Si la consulta del usuario versa sobre temas generales "
        "(legislación nacional o internacional general, ciencia, código, historia o cultura) no vinculados "
        "específicamente a la operativa, contratación o servicios internos de esta organización, responde con "
        "estricta neutralidad, objetividad y universalidad técnica, sin forzar menciones a la empresa, su actividad comercial "
        "ni encuadres corporativos innecesarios."
    )

    return "\n".join(lines)


async def enrich_chat_payload(
    data: Dict[str, Any],
    actual_model: str,
    is_cloud_request: bool = False,
    apply_rag_injection: bool = False,
    include_alignment: bool = True,
    alignment_mode: Optional[str] = None,
    company_profile: Optional[Dict[str, Any]] = None,
    rag_table: Optional[str] = None
) -> Dict[str, Any]:
    """
    Enriquece el payload de chat completions según el modo de alineación:
    - 'full': Invariantes MEA, directivas de control y grounding, foco activo en tools, poda de contexto (Puerto 8000).
    - 'agentic': System prompt virgen, sin directivas doctrinales, pero con foco activo en tools (anti-decay/crosstalk),
      poda de contexto y KV slot flusher para benchmarks y agentes como Deepseek Harness (Puerto 8010).
    - 'off': Pass-through sin enriquecimiento.
    """
    if "messages" not in data or not isinstance(data["messages"], list):
        return data

    if alignment_mode:
        mode = alignment_mode.lower().strip()
    else:
        mode = "full" if include_alignment else "agentic"

    if mode == "off":
        return data

    settings = get_alignment_settings()
    if not settings.get("enabled", True):
        return data

    # 0. Poda de contexto selectiva (Ventana Deslizante Canónica: 10 Turnos de Usuario o 32k Tokens)
    pruned_msgs, dropped_turns = prune_chat_history(data["messages"])
    if dropped_turns > 0:
        data["messages"] = pruned_msgs
        max_u_turns = get_max_user_turns()
        print(
            f"🧹 [Context Pruner] Conversación acotada: descartados {dropped_turns} turnos de usuario antiguos "
            f"(retenidos los últimos {max_u_turns} turnos atómicos).",
            file=sys.stderr,
            flush=True
        )
        # Nivel 1: Forzar reevaluación limpia en llama-server (ignorar prefijo sucio del KV cache)
        if not is_cloud_request:
            data["cache_prompt"] = False
            print(
                f"🧹 [Context Pruner] Inyectado 'cache_prompt: false' para forzar reevaluación limpia del KV cache en backend local.",
                file=sys.stderr,
                flush=True
            )

    # 0.1 Gobernador de Presupuesto y Suficiencia RAG (Techo 50k, Semáforo 4 llamadas / 5k, Discrecional 5k-10k)
    try:
        data, _gov_stats = apply_tool_budget_governor(data)
    except Exception as gov_err:
        print(f"⚠️ Error en Gobernador de Tools: {gov_err}", file=sys.stderr, flush=True)

    messages: List[Dict[str, Any]] = data["messages"]
    tools: List[Dict[str, Any]] = data.get("tools", [])
    tool_names = []
    for t in tools:
        if isinstance(t, dict):
            fn = t.get("function", {})
            if isinstance(fn, dict) and "name" in fn:
                tool_names.append(fn["name"])

    has_pdf_tool = "generate_pdf_document" in tool_names or "generate_pdf" in tool_names
    has_doc_tool = "leer_documento_completo" in tool_names or "read_document" in tool_names
    has_vision_attachment = any("<imagen_adjunta>" in str(m.get("content", "")) for m in messages)

    # 1. Construir bloques del sistema (Fecha/Hora siempre presente si inject_temporal=True)
    system_parts = []
    if settings.get("inject_temporal", True):
        system_parts.append(get_current_time_str())

    # Inyección de Perfil Corporativo (si está configurado y habilitado en la API Key)
    if company_profile:
        corp_block = format_company_profile_block(company_profile)
        if corp_block:
            system_parts.append(corp_block)

    # Bloque de invariantes éticos, protocolos y guías (sólo en modo 'full')
    if mode == "full":
        invariants_block = get_invariants_system_prompt(settings, has_pdf_tool=has_pdf_tool, has_doc_tool=has_doc_tool, has_vision_attachment=has_vision_attachment)
        if invariants_block:
            system_parts.append(invariants_block)

    full_system_header = "\n\n".join(system_parts).strip()

    if full_system_header:
        system_msg = next((m for m in messages if m.get("role") == "system"), None)
        if system_msg:
            orig_content = system_msg.get("content", "")
            needed_parts = []
            if settings.get("inject_temporal", True) and "Fecha y hora actual:" not in orig_content:
                needed_parts.append(get_current_time_str())
            if company_profile:
                corp_block = format_company_profile_block(company_profile)
                if corp_block and "[PERFIL E IDENTIDAD CORPORATIVA" not in orig_content:
                    needed_parts.append(corp_block)
            if mode == "full":
                invariants_block = get_invariants_system_prompt(settings, has_pdf_tool=has_pdf_tool, has_doc_tool=has_doc_tool, has_vision_attachment=has_vision_attachment)
                if invariants_block and "[DIRECTIVAS FUNDAMENTALES" not in orig_content:
                    needed_parts.append(invariants_block)

            if needed_parts:
                header_to_add = "\n\n".join(needed_parts).strip()
                system_msg["content"] = f"{header_to_add}\n\n{orig_content}".strip()
        else:
            messages.insert(0, {"role": "system", "content": full_system_header})

    # Extraer última consulta del usuario para contextualización y anclaje
    last_user_msg = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    user_query = ""
    if last_user_msg:
        content_val = last_user_msg.get("content", "")
        if isinstance(content_val, str):
            user_query = content_val
        elif isinstance(content_val, list):
            text_parts = [p.get("text", "") for p in content_val if isinstance(p, dict) and p.get("type") == "text"]
            user_query = " ".join(text_parts)

        # Anclaje explícito del target actual para prevenir atención errática / crosstalk hacia turnos anteriores (sólo en 'full')
        if mode == "full":
            if isinstance(content_val, str):
                if not content_val.startswith("[CONSULTA ACTUAL DEL USUARIO]:"):
                    last_user_msg["content"] = f"[CONSULTA ACTUAL DEL USUARIO]:\n{content_val}"
            elif isinstance(content_val, list) and content_val:
                first_part = content_val[0]
                if isinstance(first_part, dict) and first_part.get("type") == "text":
                    txt = first_part.get("text", "")
                    if not txt.startswith("[CONSULTA ACTUAL DEL USUARIO]:"):
                        first_part["text"] = f"[CONSULTA ACTUAL DEL USUARIO]:\n{txt}"

    # 2. Refuerzo Dinámico de Grounding Anti-Decay (MEA) en Consultas Sensibles y Repreguntas Contextuales (sólo en 'full')
    has_rag_tools = any(t in tool_names for t in ["buscar_en_base_de_conocimiento", "obtener_estructura_documento", "leer_documento_completo", "rag_search"])
    if mode == "full" and has_rag_tools and user_query and last_user_msg:
        is_direct_grounding = bool(GROUNDING_TRIGGERS_PATTERN.search(user_query))
        
        is_followup_candidate = (
            bool(FOLLOWUP_TRIGGERS_PATTERN.search(user_query)) or 
            len(user_query.strip().split()) <= 15
        )
        has_prior_grounding = False
        if not is_direct_grounding and is_followup_candidate:
            for m in messages:
                if m is last_user_msg:
                    continue
                m_role = m.get("role")
                if m_role == "tool":
                    has_prior_grounding = True
                    break
                if m_role == "assistant":
                    if m.get("tool_calls"):
                        has_prior_grounding = True
                        break
                    m_content = str(m.get("content", ""))
                    if any(kw in m_content for kw in ["doc_id:", "base_de_conocimiento", "obtener_estructura_documento", "leer_documento_completo"]):
                        has_prior_grounding = True
                        break
                elif m_role == "user":
                    u_txt = str(m.get("content", ""))
                    if GROUNDING_TRIGGERS_PATTERN.search(u_txt):
                        has_prior_grounding = True
                        break

        should_inject = is_direct_grounding or has_prior_grounding
        if should_inject:
            if is_direct_grounding:
                reminder_text = (
                    "\n\n[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO (MEA)]:\n"
                    "Esta consulta involucra normativa, procedimientos, contratos, políticas o documentación interna. "
                    "Conforme a las Directivas Fundamentales, tienes ESTRICTAMENTE PROHIBIDO responder de memoria paramétrica, deducir o suponer el contenido. "
                    "Es OBLIGATORIO emitir de inmediato una llamada a tus herramientas ('buscar_en_base_de_conocimiento', 'obtener_estructura_documento' o 'leer_documento_completo') "
                    "para contrastar los textos oficiales y vigentes antes de emitir tu respuesta. "
                    "Si se solicita jurisprudencia y no consta en las fuentes recuperadas, declara con honestidad su ausencia sin inventar fallos, carátulas ni salas."
                )
            else:
                reminder_text = (
                    "\n\n[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO (SEGUIMIENTO - MEA)]:\n"
                    "Esta consulta es una repregunta o solicitud de detalles sobre la normativa, procedimiento, contrato o documentación técnica abordada previamente. "
                    "Conforme a las Directivas Fundamentales, tienes ESTRICTAMENTE PROHIBIDO responder de memoria paramétrica, inventar o suponer artículos o clasificaciones. "
                    "Es OBLIGATORIO emitir de inmediato una llamada a tus herramientas ('obtener_estructura_documento', 'leer_documento_completo' o 'buscar_en_base_de_conocimiento') "
                    "para recuperar los textos oficiales, capítulos exactos y artículos literales antes de responder. "
                    "Si se solicita jurisprudencia y no consta en las fuentes recuperadas, declara con honestidad su ausencia sin inventar fallos, carátulas ni salas."
                )

            content_val = last_user_msg.get("content")
            if isinstance(content_val, str):
                if "[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO" not in content_val:
                    last_user_msg["content"] = f"{content_val}{reminder_text}"
            elif isinstance(content_val, list):
                if not any("[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO" in str(p.get("text", "")) for p in content_val if isinstance(p, dict)):
                    content_val.append({"type": "text", "text": reminder_text})

    # 2.1 Refuerzo de Foco Activo en Salidas de Herramientas (Anti-Attention Decay & Anti-Crosstalk)
    # Activo en 'full' y 'agentic': si el último mensaje es un resultado de herramienta ('tool'),
    # inyectamos un pie de anclaje perentorio que recuerda el objetivo excluyente de la consulta actual.
    if mode in ["full", "agentic"] and messages and messages[-1].get("role") == "tool" and last_user_msg:
        clean_query = user_query
        if "[DIRECTIVA DE CONTROL" in clean_query:
            clean_query = clean_query.split("[DIRECTIVA DE CONTROL")[0]
        if "[CONSULTA ACTUAL DEL USUARIO]:" in clean_query:
            clean_query = clean_query.replace("[CONSULTA ACTUAL DEL USUARIO]:", "")
        clean_query = clean_query.strip()

        if clean_query:
            last_tool_msg = messages[-1]
            t_content = last_tool_msg.get("content")
            is_en = is_english_query(clean_query)
            footer_tag = (
                "[ACTIVE TASK FOCUS & RELEVANCE REMINDER (ANTI-CROSSTALK)]"
                if is_en else
                "[RECORDATORIO DE FOCO ACTIVO Y REGLA DE PERTINENCIA (ANTI-CROSSTALK)]"
            )
            if isinstance(t_content, str) and footer_tag not in t_content and "[RECORDATORIO DE FOCO ACTIVO" not in t_content:
                if is_en:
                    focus_reminder = (
                        f"\n\n📌 {footer_tag}:\n"
                        f"You are executing tools to solve EXCLUSIVELY the current user task:\n"
                        f"\"{clean_query}\"\n"
                        f"1. Evaluate this tool output critically: use only information directly relevant to the task above and discard extraneous or accidental details.\n"
                        f"2. Está ESTRICTAMENTE PROHIBIDO desviar tu respuesta o tus próximas herramientas hacia temas de turnos anteriores / It is strictly prohibited to drift.\n"
                        f"3. Maintain strict, persistent focus on completing: \"{clean_query}\"."
                    )
                else:
                    focus_reminder = (
                        f"\n\n📌 {footer_tag}:\n"
                        f"Estás ejecutando herramientas para responder EXCLUSIVAMENTE a la consulta actual del usuario:\n"
                        f"\"{clean_query}\"\n"
                        f"1. Evalúa críticamente esta salida de herramienta: utiliza únicamente la información directamente relevante y descarta datos accidentales o tangenciales.\n"
                        f"2. Está ESTRICTAMENTE PROHIBIDO desviar tu respuesta o tus próximas herramientas hacia temas de turnos anteriores.\n"
                        f"3. Mantén el foco perentorio en resolver: \"{clean_query}\"."
                    )
                last_tool_msg["content"] = f"{t_content}{focus_reminder}"

    # 3. Inyección de Búsqueda Web (si es modelo web - sólo en 'full')
    if mode == "full" and not is_cloud_request and actual_model == "gemma-4-web" and user_query:
        try:
            from gateway.tools.web_search import perform_ollama_web_search
            max_res = int(os.getenv("OLLAMA_SEARCH_MAX_RESULTS", "3"))
            web_results = await perform_ollama_web_search(user_query, max_results=max_res)
            if web_results:
                snippets = []
                for idx, r in enumerate(web_results, 1):
                    snippets.append(f"[{idx}] {r['title']}\nURL: {r['url']}\nContenido: {r['content']}")
                web_context = "\n\n".join(snippets)
                search_prompt = (
                    f"\n\n[INFORMACIÓN DE BÚSQUEDA WEB EN TIEMPO REAL (VÍA OLLAMA)]:\n"
                    f"{web_context}\n"
                    f"--------------------------------------------------\n"
                    f"Instrucciones: Utiliza la información web anterior para responder de forma precisa, "
                    f"actualizada y cita las fuentes o enlaces si es relevante."
                )
                system_msg = next((m for m in messages if m.get("role") == "system"), None)
                if system_msg:
                    system_msg["content"] = f"{system_msg.get('content', '')}{search_prompt}".strip()
        except Exception as we:
            print(f"⚠️ Error en búsqueda web Gateway: {we}", file=sys.stderr, flush=True)

    # 3. Inyección RAG Documental (LanceDB - Teccam o Multi-Tenant - sólo en 'full')
    if mode == "full" and (apply_rag_injection or actual_model == "gemma-4-rag") and user_query:
        try:
            from rag_engine import (
                search_knowledge_base,
                format_rag_context_for_llm,
                get_rag_settings,
                find_documents_by_fuzzy_title,
                get_document_full_content
            )
            rag_sett = get_rag_settings()
            if rag_sett.get("enabled", True):
                target_table = rag_table
                if not target_table and company_profile and isinstance(company_profile, dict):
                    target_table = company_profile.get("rag_table")

                rag_context_str = ""
                matched_docs = find_documents_by_fuzzy_title(user_query, table_name=target_table)

                # Si la consulta menciona un documento específico
                if matched_docs and matched_docs[0].get("score", 0) >= 0.5:
                    top_doc = matched_docs[0]
                    full_res = get_document_full_content(top_doc["doc_id"], token_threshold=30000, table_name=target_table)
                    total_tokens = full_res.get("total_doc_tokens", 0)

                    if total_tokens <= 30000 and full_res.get("content"):
                        rag_context_str = (
                            f"--- DOCUMENTO COMPLETO OFICIAL DE LA BIBLIOTECA (Fidelidad 100%): \"{top_doc['title']}\" ---\n"
                            f"(Tema: {top_doc.get('topic', 'General')} | Autor: {top_doc.get('author', 'Desconocido')})\n\n"
                            f"{full_res.get('content')}\n\n"
                            f"--- FIN DEL DOCUMENTO OFICIAL ---"
                        )
                    else:
                        rag_results = search_knowledge_base(
                            query=user_query,
                            temas=[top_doc.get("topic")] if top_doc.get("topic") else None,
                            top_k=8,
                            table_name=target_table
                        )
                        if rag_results:
                            rag_context_str = format_rag_context_for_llm(rag_results)

                if not rag_context_str:
                    rag_results = search_knowledge_base(query=user_query, top_k=8, table_name=target_table)
                    if rag_results:
                        rag_context_str = format_rag_context_for_llm(rag_results)

                if rag_context_str:
                    table_label = f"LANCEDB - {target_table.upper()}" if target_table else "LANCEDB - KNOWLEDGE BASE"
                    rag_prompt = (
                        f"\n\n[CONTEXTO DE LA BASE DE CONOCIMIENTO DOCUMENTAL ({table_label})]:\n"
                        f"{rag_context_str}\n"
                        f"--------------------------------------------------\n"
                        f"Instrucciones de Grounding y Pertinencia: Evalúa críticamente la aplicabilidad causal directa de las fuentes anteriores. "
                        f"Utiliza y cita de forma prioritaria ÚNICAMENTE aquellos fragmentos que regulen directamente la situación consultada. "
                        f"Si algún fragmento trata sobre una figura accesoria, contractual o tangencial que no aplica al caso, no fuerces su inclusión; descártalo o contrástalo explícitamente."
                    )
                    system_msg = next((m for m in messages if m.get("role") == "system"), None)
                    if system_msg:
                        system_msg["content"] = f"{system_msg.get('content', '')}{rag_prompt}".strip()
        except Exception as re_err:
            print(f"⚠️ Error en contextualización RAG: {re_err}", file=sys.stderr, flush=True)

    # 4. Tool Choice Enforcement Inteligente
    if has_pdf_tool and user_query:
        pdf_triggers = [r"\bpdf\b", r"\bdescargar\b", r"\bexportar\b", r"\bgenerar\s+pdf\b", r"\bpasamelo\s+en\s+pdf\b", r"\bformato\s+pdf\b"]
        if any(re.search(pat, user_query, re.IGNORECASE) for pat in pdf_triggers):
            if data.get("tool_choice") == "none":
                data["tool_choice"] = "auto"

    # 5. Clamping inteligente de max_tokens para evitar el bug de desborde de OpenWebUI
    if "max_tokens" in data and isinstance(data["max_tokens"], int):
        max_output_cap = int(settings.get("max_response_tokens_cap", 8192))
        if data["max_tokens"] > max_output_cap:
            data["max_tokens"] = max_output_cap

    return data
