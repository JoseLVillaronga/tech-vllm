// Frontend Logic for Alignment and MEA Policies Manager

const CANONICAL_INVARIANTS_PROMPT = `🏛️ [DIRECTIVAS FUNDAMENTALES Y DEBER DE VERACIDAD (INVARIANTES NO NEGOCIABLES)]
1. PROHIBICIÓN ABSOLUTA DE ENLACES SIMULADOS O FICTICIOS:
   - Jamás inventes URLs, hipervínculos markdown manuales a dominios ficticios (como example.com, test.com) ni redactes mensajes de 'entorno simulado o representativo'.
   - Si el usuario solicita un archivo descargable, reporte formal o resumen en PDF, es MANDATORIO generar el archivo invocando la herramienta formal del sistema. Está estrictamente prohibido simular que el archivo fue creado sin haber emitido la llamada a la tool.
2. FIDELIDAD DOCUMENTAL Y EXHAUSTIVIDAD:
   - Al analizar, sintetizar o explicar documentos operativos, procedimientos técnicos o normativas, procesa la totalidad del contenido relevante.
   - Conserva con exactitud matemática y conceptual las tablas comparativas, las categorías operativas (ej: ASC, ASE, ASG), los tiempos límites y los protocolos de comunicación sin omitir detalles críticos ni aplicar atajos superficiales.
3. RIGOR TÉCNICO Y HONESTIDAD:
   - Si una información no está presente en el contexto o en las herramientas disponibles, decláralo con total transparencia en lugar de suponerla o inventarla.
4. PROTOCOLO ANTISESGO Y SECUENCIA DE NAVEGACIÓN EN EMBUDO (OBLIGATORIO):
   - Jamás asumas de memoria previa el contenido de leyes, vigencias, manuales o versiones documentales cuando tengas herramientas de consulta disponibles: consulta activamente las herramientas para contrastar el texto oficial.
   - En cualquier consulta de investigación en la biblioteca, aplica la búsqueda en la base documental:
     * Búsqueda Directa: buscar_en_base_de_conocimiento para ubicar artículos y conceptos puntuales.
     * Mapa Estructural: obtener_estructura_documento (en obras de más de 10.000 tokens para identificar los capítulos exactos).
     * Lectura Quirúrgica: leer_documento_completo (solicitando la sección o capítulo puntual).
   - Si existen versiones múltiples de un documento o reformas legislativas, identifica siempre la versión vigente más reciente.
5. DEBER DE VERIFICACIÓN ACTIVA, GROUNDING DOCUMENTAL Y PROHIBICIÓN DE SIMULACIÓN O ADIVINACIÓN:
   - Cuando el usuario consulte o pida mostrar/citar cualquier artículo, preámbulo, ley, código, norma o cláusula (ej: "mostrame el artículo X", "texto del preámbulo", "qué dice el artículo Y"), o cuando repregunte sobre el alcance de una norma o solicite fuentes exactas:
     ESTÁ ESTRICTAMENTE PROHIBIDO RESPONDER DE MEMORIA PARAMÉTRICA O INVENTAR EL CONTENIDO.
   - Es OBLIGATORIO EMITIR DE INMEDIATO UNA LLAMADA A 'buscar_en_base_de_conocimiento', 'obtener_estructura_documento' o 'leer_documento_completo' para contrastar contra el texto documental real antes de emitir cualquier respuesta.
   - QUEDA TERMINANTEMENTE PROHIBIDO SIMULAR EN TEXTO QUE ESTÁS RECUPERANDO INFORMACIÓN (ej. no escribas '[En proceso de recuperación...]', 'procederé a buscar...' ni narres procesos internos). La recuperación de información se realiza EXCLUSIVAMENTE ejecutando la herramienta formal.
   - Si la búsqueda rápida no devuelve el artículo exacto en los fragmentos iniciales, declara con honestidad y transparencia que no fue localizado en la búsqueda preliminar o ejecuta 'leer_documento_completo' solicitando la sección correspondiente, pero JAMÁS rellenes el vacío inventando texto normativo apócrifo.
   - Si la figura consultada no se encuentra en el documento que venías analizando, utiliza 'obtener_indice_biblioteca' para verificar si está regulada en una ley especial independiente (ej: Ley General de Sociedades 19.550, Ley de Contrato de Trabajo 20.744) en lugar de forzarla o inventarla dentro del código general.`;

async function loadAlignmentSettings() {
    try {
        const resp = await fetch('/api/alignment/settings');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        
        if (data && data.settings) {
            const s = data.settings;
            document.getElementById('align-enabled').checked = s.enabled !== false;
            document.getElementById('align-inject-temporal').checked = s.inject_temporal !== false;
            document.getElementById('align-inject-invariants').checked = s.inject_invariants !== false;
            document.getElementById('align-pdf-protocol').checked = s.pdf_protocol_enabled !== false;
            document.getElementById('align-doc-protocol').checked = s.doc_reader_protocol_enabled !== false;
            
            const capVal = s.max_response_tokens_cap || 8192;
            document.getElementById('align-max-tokens-cap').value = capVal;
            const capDisplay = document.getElementById('align-cap-display');
            if (capDisplay) capDisplay.innerText = capVal;

            document.getElementById('align-invariants-prompt').value = s.invariants_prompt || CANONICAL_INVARIANTS_PROMPT;
            document.getElementById('align-custom-prompt').value = s.custom_system_prompt || '';
        }
    } catch (err) {
        console.error('Error cargando configuración de alineación:', err);
    }
}

async function saveAlignmentSettings() {
    const btn = document.getElementById('btn-save-alignment');
    const origHtml = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<svg class="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg> Guardando...`;
    }

    try {
        const payload = {
            enabled: document.getElementById('align-enabled').checked,
            inject_temporal: document.getElementById('align-inject-temporal').checked,
            inject_invariants: document.getElementById('align-inject-invariants').checked,
            pdf_protocol_enabled: document.getElementById('align-pdf-protocol').checked,
            doc_reader_protocol_enabled: document.getElementById('align-doc-protocol').checked,
            max_response_tokens_cap: parseInt(document.getElementById('align-max-tokens-cap').value) || 8192,
            invariants_prompt: document.getElementById('align-invariants-prompt').value.trim(),
            custom_system_prompt: document.getElementById('align-custom-prompt').value.trim()
        };

        const resp = await fetch('/api/alignment/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const resData = await resp.json();
        if (resp.ok && resData.success) {
            showAlignmentToast('✅ ' + (resData.message || 'Políticas aplicadas exitosamente en caliente.'));
        } else {
            showAlignmentToast('⚠️ ' + (resData.message || 'Error al guardar configuración.'), true);
        }
    } catch (err) {
        console.error('Error guardando configuración de alineación:', err);
        showAlignmentToast('❌ Error de red al comunicarse con el servidor.', true);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = origHtml;
        }
    }
}

function restoreDefaultInvariantsPrompt() {
    const el = document.getElementById('align-invariants-prompt');
    if (el) {
        el.value = CANONICAL_INVARIANTS_PROMPT;
        showAlignmentToast('ℹ️ Invariantes MEA canónicos restaurados.');
    }
}

function showAlignmentToast(msg, isError = false) {
    const toast = document.getElementById('align-toast');
    const msgEl = document.getElementById('align-toast-msg');
    if (!toast || !msgEl) return;

    msgEl.innerText = msg;
    toast.className = `fixed bottom-6 right-6 ${isError ? 'bg-rose-600' : 'bg-emerald-600'} text-white text-xs font-bold px-4 py-3 rounded-xl shadow-2xl flex items-center gap-2.5 transition-all z-50`;
    toast.classList.remove('hidden');

    setTimeout(() => {
        toast.classList.add('hidden');
    }, 4000);
}

// Cargar al inicializar o al abrir la pestaña
document.addEventListener('DOMContentLoaded', () => {
    loadAlignmentSettings();

    const capInput = document.getElementById('align-max-tokens-cap');
    const capDisplay = document.getElementById('align-cap-display');
    if (capInput && capDisplay) {
        capInput.addEventListener('input', (e) => {
            capDisplay.innerText = e.target.value;
        });
    }
});
