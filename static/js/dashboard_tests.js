        // --- Playground Functions ---

        // Chat Test
        async function testChat() {
            const input = document.getElementById('chat-input');
            const output = document.getElementById('chat-output');
            const modelSelect = document.getElementById('chat-model-select');
            const text = input.value.trim ? input.value.trim() : input.value;
            if (!text) return;
            
            const selectedModel = modelSelect ? modelSelect.value : "";
            output.innerText = selectedModel ? `Procesando con ${selectedModel}...` : "Pensando...";
            input.value = "";
            
            try {
                const res = await fetch('/api/test/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        prompt: text,
                        model: selectedModel || undefined,
                        max_tokens: 500
                    })
                });
                const data = await res.json();
                if (data.choices && data.choices[0]) {
                    output.innerText = data.choices[0].message.content;
                } else if (data.error) {
                    output.innerText = `⚠️ ${data.error}`;
                } else {
                    output.innerText = JSON.stringify(data, null, 2);
                }
            } catch (err) {
                output.innerText = `Error: ${err.message}`;
            }
        }

        // TTS Speech Test
        async function testSpeech() {
            const text = document.getElementById('tts-input').value;
            const voice = document.getElementById('tts-voice').value;
            const player = document.getElementById('tts-player');
            
            if (!text) {
                alert("Por favor, escribe algún texto.");
                return;
            }
            
            player.classList.add('hidden');
            
            try {
                const res = await fetch('/api/test/speech', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: text, voice: voice })
                });
                if (res.status === 200) {
                    const blob = await res.blob();
                    const audioUrl = URL.createObjectURL(blob);
                    player.src = audioUrl;
                    player.classList.remove('hidden');
                    player.play();
                } else {
                    const errData = await res.json();
                    alert(`Error al generar voz: ${errData.error || 'Error del servidor'}`);
                }
            } catch (err) {
                alert(`Error: ${err.message}`);
            }
        }

        // ASR Transcribe Test
        function updateFileLabel(type) {
            const input = document.getElementById(`${type}-file`);
            const label = document.getElementById(`${type}-file-label`);
            if (input.files && input.files[0]) {
                label.innerText = input.files[0].name;
            }
        }

        async function testTranscribe() {
            const fileInput = document.getElementById('asr-file');
            const output = document.getElementById('asr-output');
            
            if (!fileInput.files || !fileInput.files[0]) {
                alert("Por favor, selecciona un archivo de audio.");
                return;
            }
            
            output.innerText = "Transcribiendo...";
            const formData = new FormData();
            formData.append("file", fileInput.files[0]);
            
            try {
                const res = await fetch('/api/test/transcribe', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                output.innerText = data.text || JSON.stringify(data, null, 2);
            } catch (err) {
                output.innerText = `Error: ${err.message}`;
            }
        }

        // Diarization Test
        async function testDiarize() {
            const fileInput = document.getElementById('diarize-file');
            const output = document.getElementById('diarize-output');
            
            if (!fileInput.files || !fileInput.files[0]) {
                alert("Por favor, selecciona un archivo de audio.");
                return;
            }
            
            output.innerText = "Calculando segmentos de habla...";
            const formData = new FormData();
            formData.append("file", fileInput.files[0]);
            
            try {
                const res = await fetch('/api/test/diarize', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                output.innerText = JSON.stringify(data, null, 2);
            } catch (err) {
                output.innerText = `Error: ${err.message}`;
            }
        }

        // Image Generation Test
        async function testImage() {
            const promptInput = document.getElementById('img-test-prompt');
            const sizeSelect = document.getElementById('img-test-size');
            const btn = document.getElementById('btn-test-image');
            const imgEl = document.getElementById('img-test-result');
            const placeholder = document.getElementById('img-test-placeholder');
            const infoEl = document.getElementById('img-test-info');
            
            const prompt = promptInput ? promptInput.value.trim() : "";
            if (!prompt) {
                alert("Por favor ingresa un prompt en texto para generar la imagen.");
                return;
            }
            
            const size = sizeSelect ? sizeSelect.value : "512x512";
            const originalHtml = btn ? btn.innerHTML : "";
            
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span>⏳</span> Renderizando imagen (~1.5s)...';
            }
            if (placeholder) {
                placeholder.classList.remove('hidden');
                placeholder.innerHTML = '<span class="animate-pulse text-pink-400 font-medium">✨ Renderizando imagen con difusión...</span>';
            }
            if (imgEl) imgEl.classList.add('hidden');
            if (infoEl) infoEl.classList.add('hidden');
            
            try {
                const t0 = performance.now();
                const res = await fetch('/api/test/image', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        prompt: prompt,
                        size: size
                    })
                });
                const data = await res.json();
                const elapsedSec = ((performance.now() - t0) / 1000).toFixed(2);
                
                if (data.data && data.data[0] && data.data[0].url) {
                    const imgUrl = data.data[0].url;
                    if (imgEl) {
                        imgEl.src = imgUrl;
                        imgEl.classList.remove('hidden');
                    }
                    if (placeholder) placeholder.classList.add('hidden');
                    if (infoEl) {
                        infoEl.innerHTML = `✅ Renderizada en <b>${elapsedSec}s</b> (${size}) | <a href="${imgUrl}" target="_blank" download class="text-pink-400 hover:underline font-bold">Descargar PNG</a>`;
                        infoEl.classList.remove('hidden');
                    }
                } else if (data.error) {
                    alert("Error en generación: " + data.error);
                    if (placeholder) {
                        placeholder.innerHTML = `<span class="text-rose-400">⚠️ ${data.error}</span>`;
                    }
                } else {
                    alert("Respuesta inesperada: " + JSON.stringify(data));
                }
            } catch (err) {
                alert("Error de conexión: " + err.message);
                if (placeholder) {
                    placeholder.innerHTML = `<span class="text-rose-400">⚠️ Error: ${err.message}</span>`;
                }
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;
                }
            }
        }

        // ==============================================================================
        // InfoLEG Normative Extractor (HTML to Hierarchical Markdown)
        // ==============================================================================
        let currentInfolegDoc = null;

        async function extractInfolegDoc() {
            const urlInput = document.getElementById('infoleg-url-input');
            const titleInput = document.getElementById('infoleg-title-input');
            const preferUpdated = document.getElementById('infoleg-prefer-updated')?.checked ?? true;
            const saveDisk = document.getElementById('infoleg-save-disk')?.checked ?? true;
            const btn = document.getElementById('btn-extract-infoleg');
            const iconEl = document.getElementById('icon-extract-infoleg');
            const textEl = document.getElementById('text-extract-infoleg');

            const rawUrl = urlInput ? urlInput.value.trim() : "";
            if (!rawUrl) {
                alert("Por favor, ingresa una URL o el ID numérico de la norma en InfoLEG (ej: 409377).");
                if (urlInput) urlInput.focus();
                return;
            }

            const docTitle = titleInput ? titleInput.value.trim() : "";

            // Estado de carga
            if (btn) btn.disabled = true;
            if (iconEl) iconEl.innerText = "⏳";
            if (textEl) textEl.innerText = "Consultando InfoLEG y convirtiendo a Markdown...";

            try {
                const res = await fetch('/api/test/infoleg', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        url: rawUrl,
                        title: docTitle,
                        prefer_updated: preferUpdated,
                        save_to_disk: saveDisk
                    })
                });

                const data = await res.json();
                if (!res.ok || !data.success) {
                    throw new Error(data.error || "Fallo en la extracción de la norma.");
                }

                currentInfolegDoc = data;

                // Renderizar Badges de Metadatos
                const badgesContainer = document.getElementById('infoleg-badges-container');
                if (badgesContainer) {
                    const meta = data.metadata || {};
                    const stats = data.stats || {};
                    let badgesHtml = '';

                    if (meta.tipo_numero) {
                        badgesHtml += `<span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-purple-950/80 text-purple-300 border border-purple-800/60 flex items-center gap-1.5">
                            <span>🏛️</span> ${meta.tipo_numero}
                        </span>`;
                    }
                    if (meta.fecha) {
                        badgesHtml += `<span class="px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-900 text-slate-300 border border-slate-800 flex items-center gap-1.5">
                            <span>📅</span> Sanción: ${meta.fecha}
                        </span>`;
                    }
                    if (meta.boletin_oficial) {
                        badgesHtml += `<span class="px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-900 text-slate-300 border border-slate-800 flex items-center gap-1.5">
                            <span>📜</span> ${meta.boletin_oficial}
                        </span>`;
                    }
                    badgesHtml += `<span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-indigo-950/80 text-indigo-300 border border-indigo-800/60 flex items-center gap-1.5">
                        <span>⚖️</span> ${stats.articles || 0} Artículos
                    </span>`;
                    badgesHtml += `<span class="px-2.5 py-1 rounded-lg text-xs font-mono bg-emerald-950/60 text-emerald-300 border border-emerald-800/50 flex items-center gap-1.5">
                        <span>📊</span> ${stats.size_kb || 0} KB (${stats.lines || 0} líneas)
                    </span>`;
                    if (meta.texto_url) {
                        badgesHtml += `<a href="${meta.texto_url}" target="_blank" rel="noopener noreferrer" class="px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-900/80 text-cyan-300 hover:text-cyan-200 border border-cyan-800/40 hover:border-cyan-500/60 transition-all flex items-center gap-1.5 ml-auto" title="Abrir fuente original en InfoLEG">
                            <span>🔗</span> Fuente Oficial
                        </a>`;
                    }

                    badgesContainer.innerHTML = badgesHtml;
                }

                // Cargar Contenido en el Visor Raw
                const rawViewer = document.getElementById('infoleg-raw-viewer');
                if (rawViewer) {
                    rawViewer.textContent = data.content;
                }

                // Actualizar botón de descarga con el nombre real
                const downloadText = document.getElementById('text-download-infoleg');
                if (downloadText && data.filename) {
                    downloadText.innerText = `Descargar ${data.filename}`;
                }

                // Mostrar el panel de resultados
                const resultsPanel = document.getElementById('infoleg-results-panel');
                if (resultsPanel) {
                    resultsPanel.classList.remove('hidden');
                }

                // Activar vista Raw por defecto
                toggleInfolegView('raw');

            } catch (err) {
                alert(`❌ Error al extraer de InfoLEG:\n${err.message}`);
            } finally {
                if (btn) btn.disabled = false;
                if (iconEl) iconEl.innerText = "🚀";
                if (textEl) textEl.innerText = "Extraer y Convertir a Markdown";
            }
        }

        function downloadInfolegMarkdown() {
            if (!currentInfolegDoc || !currentInfolegDoc.content) {
                alert("Primero debes extraer un documento de InfoLEG.");
                return;
            }

            const filename = currentInfolegDoc.filename || "documento_infoleg.md";
            const blob = new Blob([currentInfolegDoc.content], { type: 'text/markdown;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        async function copyInfolegToClipboard() {
            if (!currentInfolegDoc || !currentInfolegDoc.content) {
                alert("Primero debes extraer un documento de InfoLEG.");
                return;
            }

            try {
                await navigator.clipboard.writeText(currentInfolegDoc.content);
                const textEl = document.getElementById('text-copy-infoleg');
                if (textEl) {
                    const oldText = textEl.innerText;
                    textEl.innerText = "¡Copiado!";
                    setTimeout(() => { textEl.innerText = oldText; }, 2000);
                }
            } catch (err) {
                // Fallback clásico
                const textarea = document.createElement('textarea');
                textarea.value = currentInfolegDoc.content;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                const textEl = document.getElementById('text-copy-infoleg');
                if (textEl) {
                    const oldText = textEl.innerText;
                    textEl.innerText = "¡Copiado!";
                    setTimeout(() => { textEl.innerText = oldText; }, 2000);
                }
            }
        }

        function toggleInfolegView(mode) {
            const rawViewer = document.getElementById('infoleg-raw-viewer');
            const previewViewer = document.getElementById('infoleg-preview-viewer');
            const btnRaw = document.getElementById('btn-view-raw');
            const btnPreview = document.getElementById('btn-view-preview');

            if (mode === 'raw') {
                if (rawViewer) rawViewer.classList.remove('hidden');
                if (previewViewer) previewViewer.classList.add('hidden');
                if (btnRaw) {
                    btnRaw.className = "px-3 py-1 rounded-md text-xs font-semibold bg-purple-600/30 text-purple-300 transition-all";
                }
                if (btnPreview) {
                    btnPreview.className = "px-3 py-1 rounded-md text-xs font-semibold text-slate-400 hover:text-slate-200 transition-all";
                }
            } else {
                if (rawViewer) rawViewer.classList.add('hidden');
                if (previewViewer) {
                    previewViewer.classList.remove('hidden');
                    if (currentInfolegDoc && currentInfolegDoc.content) {
                        previewViewer.innerHTML = renderMarkdownToHtml(currentInfolegDoc.content);
                    }
                }
                if (btnPreview) {
                    btnPreview.className = "px-3 py-1 rounded-md text-xs font-semibold bg-purple-600/30 text-purple-300 transition-all";
                }
                if (btnRaw) {
                    btnRaw.className = "px-3 py-1 rounded-md text-xs font-semibold text-slate-400 hover:text-slate-200 transition-all";
                }
            }
        }

        // Renderizador simple y seguro de Markdown a HTML para previsualización
        function renderMarkdownToHtml(md) {
            if (!md) return "";
            const lines = md.split("\n");
            let html = [];
            let inTable = false;
            let tableRows = [];

            function flushTable() {
                if (!inTable || tableRows.length === 0) return;
                let tableHtml = '<div class="overflow-x-auto my-3"><table class="w-full text-xs text-slate-200 border border-slate-800 divide-y divide-slate-800 rounded-lg overflow-hidden">';
                tableRows.forEach((row, idx) => {
                    const cols = row.split('|').map(c => c.trim()).filter((_, i, arr) => i > 0 && i < arr.length - 1);
                    if (idx === 0) {
                        tableHtml += '<thead class="bg-slate-900/80 font-bold text-purple-300"><tr>' + cols.map(c => `<th class="px-3 py-2 text-left border-r border-slate-800 last:border-r-0">${c}</th>`).join('') + '</tr></thead><tbody class="divide-y divide-slate-800/50">';
                    } else if (idx === 1 && cols.some(c => c.includes('---'))) {
                        // Divisor de cabecera ignorado
                    } else {
                        tableHtml += '<tr class="hover:bg-slate-900/40">' + cols.map(c => `<td class="px-3 py-2 border-r border-slate-800/50 last:border-r-0">${c}</td>`).join('') + '</tr>';
                    }
                });
                tableHtml += '</tbody></table></div>';
                html.push(tableHtml);
                tableRows = [];
                inTable = false;
            }

            for (let i = 0; i < lines.length; i++) {
                let line = lines[i];

                // Tablas Markdown
                if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
                    inTable = true;
                    tableRows.push(line.trim());
                    continue;
                } else if (inTable) {
                    flushTable();
                }

                // Sanitizar HTML básico
                let safe = line
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;');

                // Encabezados
                if (safe.startsWith('# ')) {
                    html.push(`<h1 class="text-xl font-extrabold text-purple-300 border-b border-purple-500/30 pb-2 mb-3 mt-1">${safe.slice(2)}</h1>`);
                } else if (safe.startsWith('## ')) {
                    html.push(`<h2 class="text-lg font-bold text-indigo-300 mt-5 mb-2">${safe.slice(3)}</h2>`);
                } else if (safe.startsWith('### ')) {
                    html.push(`<h3 class="text-base font-semibold text-slate-100 mt-4 mb-2">${safe.slice(4)}</h3>`);
                } else if (safe.startsWith('#### ')) {
                    html.push(`<h4 class="text-sm font-semibold text-purple-200 mt-3 mb-1">${safe.slice(5)}</h4>`);
                } else if (safe.startsWith('##### ')) {
                    html.push(`<h5 class="text-xs font-semibold text-slate-300 uppercase tracking-wider mt-2 mb-1">${safe.slice(6)}</h5>`);
                } else if (safe.startsWith('&gt; ')) {
                    // Blockquotes (metadatos)
                    html.push(`<blockquote class="border-l-2 border-purple-500/50 pl-3 py-0.5 text-xs text-slate-300 italic bg-purple-950/20 rounded-r my-1">${safe.slice(5).replace(/\*\*([^*]+)\*\*/g, '<b class="text-purple-200 not-italic">$1</b>')}</blockquote>`);
                } else if (safe.trim() === '---') {
                    html.push('<hr class="border-slate-800 my-4">');
                } else if (safe.startsWith('* ')) {
                    // Viñetas o incisos
                    const item = safe.slice(2).replace(/\*\*([^*]+)\*\*/g, '<b class="text-purple-300">$1</b>');
                    html.push(`<div class="flex items-start gap-2 text-xs text-slate-300 ml-4 my-1"><span class="text-purple-400">•</span><div>${item}</div></div>`);
                } else if (safe.trim().length > 0) {
                    // Párrafos regulares con detección de artículos en negrita
                    const formatted = safe.replace(/\*\*([^*]+)\*\*/g, '<strong class="font-bold text-purple-300">$1</strong>');
                    html.push(`<p class="text-xs text-slate-200 leading-relaxed my-2">${formatted}</p>`);
                }
            }

            if (inTable) flushTable();
            return html.join('\n');
        }

