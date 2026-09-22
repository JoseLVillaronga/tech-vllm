"""
rag.evaluator - Evaluador Desacoplado de Suficiencia Documental (CRAG).
Implementa Ley 1 (Modularización Estricta), Ley 2 (Causa Raíz), Ley 3 (Mínimo Cambio)
y Ley 4 (Integridad en Cascada RAG).

Utiliza un SLM especializado en lógica formal y razonamiento (twil-lm3-q4_k_m.gguf)
en el puerto 18300, complementado con fast-pass heurístico de latencia cero para
casos concluyentes de alta fidelidad.
"""

import os
import sys
import re
import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Union, Optional
from .config import EVALUATOR_BACKEND_PORT, MASTER_KEY


def _extract_clean_json(text: str) -> Optional[Dict[str, Any]]:
    """Extrae y decodifica un objeto JSON de una cadena de texto, manejando bloques de código markdown."""
    if not text or not isinstance(text, str):
        return None
    cleaned = text.strip()
    # Si viene envuelto en markdown ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(1).strip()
    else:
        # Buscar el primer { y el último }
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start:end + 1]

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def evaluate_context_sufficiency(
    query: str,
    context: Union[str, List[Dict[str, Any]]],
    fast_pass_threshold: float = 0.85,
    timeout: float = 3.5
) -> Dict[str, Any]:
    """
    Evalúa si la evidencia documental recuperada es lógica y deductivamente suficiente
    para contestar la consulta sin recurrir a memoria paramétrica ni alucinaciones.

    Retorna un diccionario con:
    - suficiente (bool): True si los datos alcanzan para responder con certeza.
    - motivo (str): Explicación concisa.
    - faltantes (list): Lista de elementos ausentes si no es suficiente.
    - evaluador (str): 'fast_pass' | 'twil-lm3' | 'fallback_heuristico' | 'vacio'
    """
    query_str = (query or "").strip()
    if not query_str:
        return {
            "suficiente": False,
            "motivo": "Consulta vacía.",
            "faltantes": ["consulta"],
            "evaluador": "vacio"
        }

    # Normalizar contexto a texto plano y extraer similitud máxima preliminar
    context_text = ""
    top_similarity = 0.0

    if isinstance(context, list):
        if not context:
            return {
                "suficiente": False,
                "motivo": "No se encontraron fragmentos relevantes en la base documental.",
                "faltantes": ["información documental"],
                "evaluador": "vacio"
            }
        # Extraer similitud máxima del primer resultado
        first_item = context[0]
        if isinstance(first_item, dict):
            top_similarity = float(first_item.get("similarity", 0.0))
        
        # Unir contenidos
        text_snippets = []
        for idx, item in enumerate(context, 1):
            if isinstance(item, dict):
                title = item.get("doc_title") or item.get("title") or f"Doc {idx}"
                sec = item.get("section_path") or ""
                cnt = item.get("content") or item.get("texto") or ""
                text_snippets.append(f"[{title} - {sec}]:\n{cnt}".strip())
            elif isinstance(item, str):
                text_snippets.append(item.strip())
        context_text = "\n\n".join(text_snippets)
    elif isinstance(context, str):
        context_text = context.strip()
        if not context_text or "No se encontraron fragmentos" in context_text:
            return {
                "suficiente": False,
                "motivo": "No se encontraron fragmentos relevantes en la base documental.",
                "faltantes": ["información documental"],
                "evaluador": "vacio"
            }
        # Intentar extraer porcentaje de coincidencia si el texto proviene de format_rag_context_for_llm
        sim_match = re.search(r"Coincidencia:\s*(\d+)%", context_text)
        if sim_match:
            top_similarity = float(sim_match.group(1)) / 100.0
    else:
        return {
            "suficiente": False,
            "motivo": "Contexto no válido.",
            "faltantes": ["contexto"],
            "evaluador": "vacio"
        }

    # 1. Filtro Heurístico de Pase Rápido (Latencia Cero - 0ms CPU)
    # Si la coincidencia es concluyente (>= 85%), el fragmento termina en punto/cierre y no es consulta de catálogo extenso
    is_deep_catalog = bool(re.search(r"\b(?:lista|todos|todas|tratados|convenios|cat[aá]logo|exhaustiv[ao])\b", query_str, re.IGNORECASE))
    ends_cleanly = bool(re.search(r"[.!?\"'»]\s*$", context_text))

    if top_similarity >= fast_pass_threshold and ends_cleanly and not is_deep_catalog:
        print(f"⚡ [RAG Evaluator] Fast-Pass activado: suficiente=True ({int(top_similarity * 100)}% de coincidencia semántica)", file=sys.stderr, flush=True)
        return {
            "suficiente": True,
            "motivo": f"Evidencia directa y concluyente ({int(top_similarity * 100)}% de coincidencia semántica).",
            "faltantes": [],
            "evaluador": "fast_pass"
        }

    # 2. Evaluación con twil-lm3 (SmolLM3 3.1B Logic / Reasoning) en puerto 18300
    backend_port = EVALUATOR_BACKEND_PORT or int(os.getenv("EVALUATOR_BACKEND_PORT", "18300"))
    url = f"http://127.0.0.1:{backend_port}/v1/chat/completions"

    system_prompt = (
        "Eres un evaluador de suficiencia lógica y factual (CRAG). Tu tarea es determinar con rigor deductivo "
        "si el contexto documental provisto contiene suficiente información para responder a la consulta del usuario "
        "de manera concluyente y verídica, sin necesidad de inferir o adivinar datos ausentes.\n\n"
        "Responde ÚNICAMENTE un objeto JSON válido con este esquema exacto:\n"
        "{\n"
        '  "suficiente": true o false,\n'
        '  "motivo": "Explicación concisa en una frase",\n'
        '  "faltantes": ["aspecto específico ausente si no es suficiente"]\n'
        "}"
    )

    truncated_context = context_text[:5000]
    user_prompt = f"CONSULTA DEL USUARIO:\n{query_str}\n\nCONTEXTO DOCUMENTAL RECUPERADO:\n{truncated_context}"

    payload = {
        "model": os.getenv("EVALUATOR_ALIAS", "twil-lm3-q4_k_m"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.0,
        "max_tokens": 350,
        "response_format": {"type": "json_object"}
    }

    req_data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json"
    }
    if MASTER_KEY:
        headers["Authorization"] = f"Bearer {MASTER_KEY}"

    req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                resp_bytes = response.read()
                resp_json = json.loads(resp_bytes.decode("utf-8"))
                choices = resp_json.get("choices", [])
                if choices:
                    raw_msg = choices[0].get("message", {})
                    raw_content = raw_msg.get("content", "")
                    parsed = _extract_clean_json(raw_content)
                    # Rescate desde reasoning_content si llama-server aisló el bloque de pensamiento
                    if not parsed or "suficiente" not in parsed:
                        reasoning_txt = raw_msg.get("reasoning_content", "")
                        parsed = _extract_clean_json(reasoning_txt)

                    if parsed and "suficiente" in parsed:
                        is_suf = bool(parsed.get("suficiente"))
                        reason = str(parsed.get("motivo", "")).strip() or ("Datos suficientes" if is_suf else "Datos insuficientes")
                        missing = parsed.get("faltantes")
                        if not isinstance(missing, list):
                            missing = []
                        print(f"⚖️ [RAG Evaluator] twil-lm3 (:18300) dictamen: suficiente={is_suf} | Motivo: {reason}", file=sys.stderr, flush=True)
                        return {
                            "suficiente": is_suf,
                            "motivo": reason,
                            "faltantes": missing,
                            "evaluador": "twil-lm3"
                        }
    except Exception as exc:
        # Fallback silencioso y resiliente ante indisponibilidad del servicio local
        print(f"ℹ️ [RAG Evaluator] Fallback heurístico activado (puerto {backend_port} no disponible o timeout: {exc})", file=sys.stderr, flush=True)

    # 3. Fallback Heurístico (Resiliencia ante fallo del backend 18300)
    if (top_similarity >= 0.70 and len(context_text) > 400) or len(context_text) >= 20000:
        fb_res = {
            "suficiente": True,
            "motivo": f"Evaluación heurística de respaldo por volumen documental sustancial ({len(context_text):,} caracteres)." if len(context_text) >= 20000 else f"Evaluación heurística de respaldo por coincidencia semántica aceptable ({int(top_similarity * 100)}%).",
            "faltantes": [],
            "evaluador": "fallback_heuristico"
        }
    else:
        fb_res = {
            "suficiente": False,
            "motivo": "La evidencia documental preliminar es parcial o insuficiente para responder con certeza jurídica o técnica.",
            "faltantes": ["evidencia complementaria"],
            "evaluador": "fallback_heuristico"
        }

    print(f"ℹ️ [RAG Evaluator] Fallback heurístico dictamen: suficiente={fb_res['suficiente']} | Motivo: {fb_res['motivo']}", file=sys.stderr, flush=True)
    return fb_res


__all__ = [
    "evaluate_context_sufficiency"
]
