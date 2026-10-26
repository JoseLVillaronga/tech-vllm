#!/usr/bin/env python3
"""
lab_linear_evaluator/bench_rwkv_evaluator.py
Prueba de clasificación de suficiencia RAG con RWKV-6 Finch 3B Q8_0 en modo booleano ultra-rápido.
"""

import urllib.request
import json
import time

URL = "http://127.0.0.1:18305/completion"

TEST_CASES = [
    {
        "name": "Caso 1: Definición Legal Literal (Positivo)",
        "query": "Concepto de contrato de trabajo",
        "context": "Habrá contrato de trabajo, cualquiera sea su forma o denominación, siempre que una persona física se obligue a realizar actos, ejecutar obras o prestar servicios en favor de la otra y bajo la dependencia de ésta, durante un período determinado o indeterminado de tiempo, mediante el pago de una remuneración.",
        "expected": True
    },
    {
        "name": "Caso 2: Artículo de Prescripción Literal (Positivo)",
        "query": "¿Cuál es el plazo de prescripción para reclamo de daños derivados de la responsabilidad civil?",
        "context": "Artículo 2561. Plazos especiales. El reclamo de la indemnización de daños derivados de la responsabilidad civil prescribe a los tres años. Las acciones civiles derivadas de delitos de lesa humanidad son imprescriptibles.",
        "expected": True
    },
    {
        "name": "Caso 3: Título/Catálogo sin articulado (Negativo / Trampa)",
        "query": "¿Cuáles son las penas para el delito de peculado en el Código Penal?",
        "context": "Índice General de la Biblioteca: Código Civil y Comercial de la Nación. Ley 26.994. Sección V: Contratos de locación urbana y comercial.",
        "expected": False
    },
    {
        "name": "Caso 4: Mención Tangencial sin Datos (Negativo)",
        "query": "¿Cómo ratificó Argentina el tratado de no proliferación de armas nucleares?",
        "context": "Tratado de no proliferación nuclear firmado en Ginebra en 1968 por diversos países miembros.",
        "expected": False
    },
    {
        "name": "Caso 5: Procedimiento Técnico Incompleto (Negativo)",
        "query": "¿Cómo se configura el puerto serial RS-485 en el controlador Teccam v2?",
        "context": "Manual de Producto Teccam: Introducción general, especificaciones de alimentación 220V AC y dimensiones del gabinete.",
        "expected": False
    }
]

def format_prompt(query, context):
    return (
        f"User: Evalúa si el siguiente texto contiene la información exacta y suficiente para responder la pregunta del usuario.\n"
        f"Si la información responde la pregunta, responde estrictamente 'SI'.\n"
        f"Si la información no responde la pregunta o falta información, responde estrictamente 'NO'.\n\n"
        f"Pregunta: {query}\n"
        f"Texto: {context}\n\n"
        f"Respuesta (SI o NO):\n\n"
        f"Assistant:"
    )

def run_evaluation(test_case):
    prompt = format_prompt(test_case["query"], test_case["context"])
    payload = {
        "prompt": prompt,
        "n_predict": 5,
        "temperature": 0.0,
        "stop": ["\n", "User:"]
    }
    
    start_t = time.perf_counter()
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    
    latency_ms = (time.perf_counter() - start_t) * 1000
    choice = res.get("content", "").strip().upper()
    timings = res.get("timings", {})
    
    # Mapeo booleano
    is_sufficient = "SI" in choice or "YES" in choice
    is_correct = (is_sufficient == test_case["expected"])
    
    return {
        "choice": choice,
        "is_sufficient": is_sufficient,
        "is_correct": is_correct,
        "latency_ms": latency_ms,
        "prompt_ms": timings.get("prompt_ms", 0),
        "pred_ms": timings.get("predicted_ms", 0)
    }

def main():
    print("=" * 70)
    print("🧪 Benchmark de Evaluación Booleana CRAG con RWKV-6 Finch 3B Q8_0")
    print("=" * 70)
    
    correct_count = 0
    total_time_ms = 0
    
    for tc in TEST_CASES:
        res = run_evaluation(tc)
        status = "✅ CORRECTO" if res["is_correct"] else "❌ INCORRECTO"
        if res["is_correct"]:
            correct_count += 1
        total_time_ms += res["latency_ms"]
        
        print(f"\n📋 {tc['name']}")
        print(f"   Esperado: {'SUFICIENTE (SI)' if tc['expected'] else 'INSUFICIENTE (NO)'}")
        print(f"   Obtenido: '{res['choice']}' -> {'SUFICIENTE' if res['is_sufficient'] else 'INSUFICIENTE'} [{status}]")
        print(f"   ⏱️ Latencia: {res['latency_ms']:.2f} ms (Prompt: {res['prompt_ms']:.2f} ms | Decode: {res['pred_ms']:.2f} ms)")
        
    avg_latency = total_time_ms / len(TEST_CASES)
    accuracy = (correct_count / len(TEST_CASES)) * 100
    
    print("\n" + "=" * 70)
    print(f"🎯 Precisión: {accuracy:.1f}% ({correct_count}/{len(TEST_CASES)})")
    print(f"⚡ Latencia Promedio: {avg_latency:.2f} ms por dictamen")
    print("=" * 70)

if __name__ == "__main__":
    main()
