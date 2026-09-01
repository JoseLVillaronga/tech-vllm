        // ==============================================================================
        // Funciones de Base de Conocimiento RAG & LanceDB (Teccam PDF)
        // ==============================================================================
        let availableRagTopics = [];
        let selectedRagTopics = []; // Vacío significa TODOS los temas activos
        let isRagGloballyEnabled = true;

        async function loadRagStats() {
            try {
                const res = await fetch('/api/rag/stats');
                const data = await res.json();
                
                const docsEl = document.getElementById('rag-stat-docs');
                const chunksEl = document.getElementById('rag-stat-chunks');
                const topicsEl = document.getElementById('rag-stat-topics');
                
                if (docsEl) docsEl.innerText = data.total_documents || 0;
                if (chunksEl) chunksEl.innerText = (data.total_chunks || 0).toLocaleString();
                if (topicsEl) topicsEl.innerText = (data.topics ? data.topics.length : 0);
                
                const lastSyncEl = document.getElementById('rag-stat-last-sync');
                const lastDurEl = document.getElementById('rag-stat-last-duration');
                
                if (data.last_sync && data.last_sync.timestamp) {
                    const d = new Date(data.last_sync.timestamp);
                    if (lastSyncEl) lastSyncEl.innerText = d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    if (lastDurEl) lastDurEl.innerText = `Duración: ${data.last_sync.duration_sec}s (${data.last_sync.status})`;
                } else {
                    if (lastSyncEl) lastSyncEl.innerText = 'LanceDB Activo';
                    if (lastDurEl) lastDurEl.innerText = 'Sincronizado';
                }
                
                // Actualizar estado de encendido/apagado global del RAG
                isRagGloballyEnabled = (data.enabled !== false);
                const btnPower = document.getElementById('btn-toggle-rag-power');
                const badgePower = document.getElementById('badge-rag-power');
                const textPower = document.getElementById('text-rag-power');
                const bannerDisabled = document.getElementById('rag-disabled-banner');
                
                if (btnPower && badgePower && textPower) {
                    if (isRagGloballyEnabled) {
                        btnPower.className = "flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all border bg-emerald-950/60 border-emerald-500/40 text-emerald-300 hover:bg-emerald-900/60 cursor-pointer";
                        badgePower.className = "w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse";
                        textPower.innerText = "Servicio RAG: ACTIVO";
                        if (bannerDisabled) bannerDisabled.classList.add('hidden');
                    } else {
                        btnPower.className = "flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all border bg-rose-950/70 border-rose-500/50 text-rose-300 hover:bg-rose-900/70 cursor-pointer";
                        badgePower.className = "w-2.5 h-2.5 rounded-full bg-rose-500";
                        textPower.innerText = "Servicio RAG: INACTIVO";
                        if (bannerDisabled) bannerDisabled.classList.remove('hidden');
                    }
                }
                
                // Actualizar temas disponibles
                availableRagTopics = data.topics || [];
                
                // Si la base de datos tenía temas activos predeterminados guardados, cargarlos
                if (data.active_topics && Array.isArray(data.active_topics) && data.active_topics.length > 0) {
                    selectedRagTopics = [...data.active_topics];
                }
                
                renderRagTopicChips();
                
                // Cargar configuración de modelo Cloud RAG
                loadCloudRagSettings();
                
                // Actualizar tabla de documentos
                const tbody = document.getElementById('rag-docs-table-body');
                if (tbody) {
                    if (!data.documents || data.documents.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-6 text-center text-slate-500">No hay documentos indexados. Haz clic en "Sincronizar Base RAG Ahora".</td></tr>';
                    } else {
                        tbody.innerHTML = data.documents.map(doc => {
                            const escapedTitle = escapeHtml(doc.title);
                            const safeJsTitle = doc.title.replace(/'/g, "\\'").replace(/"/g, '&quot;');
                            return `
                            <tr class="hover:bg-slate-900/40 transition-all">
                                <td class="px-4 py-3 font-medium text-slate-200">${escapedTitle}</td>
                                <td class="px-4 py-3">
                                    <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
                                        ${escapeHtml(doc.topic)}
                                    </span>
                                </td>
                                <td class="px-4 py-3 text-center font-mono font-bold text-slate-300">${doc.chunks_count}</td>
                                <td class="px-4 py-3 text-center">
                                    <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Indexado
                                    </span>
                                </td>
                                <td class="px-4 py-3 text-right flex items-center justify-end gap-2">
                                    <button onclick="viewDocumentStructure('${escapeHtml(doc.id)}', '${safeJsTitle}')" class="px-2.5 py-1 rounded-lg bg-purple-500/10 hover:bg-purple-600 text-purple-300 hover:text-white border border-purple-500/20 text-xs font-medium transition-all inline-flex items-center gap-1" title="Ver estructura de secciones y GPS Documental">
                                        <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                                            <path stroke-linecap="round" stroke-linejoin="round" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                                        </svg>
                                        GPS
                                    </button>
                                    <button onclick="deleteRagDocument('${escapeHtml(doc.id)}', '${safeJsTitle}')" class="px-2.5 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-600 text-rose-400 hover:text-white border border-rose-500/20 text-xs font-medium transition-all inline-flex items-center gap-1" title="Eliminar este libro de la base vectorial">
                                        <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                                            <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                        </svg>
                                        Borrar
                                    </button>
                                </td>
                            </tr>
                        `;
                        }).join('');
                    }
                }
            } catch (err) {
                console.error("Error cargando estadísticas RAG:", err);
            }
        }

        function renderRagTopicChips() {
            const container = document.getElementById('rag-topics-chips-container');
            const summaryEl = document.getElementById('rag-active-filter-summary');
            const btnAll = document.getElementById('btn-toggle-all-topics');
            
            if (!container) return;
            
            if (!availableRagTopics || availableRagTopics.length === 0) {
                container.innerHTML = '<span class="text-xs text-slate-500">No hay temas registrados aún.</span>';
                if (summaryEl) summaryEl.innerText = "Sin dominios";
                return;
            }
            
            const isAllSelected = (selectedRagTopics.length === 0 || selectedRagTopics.length === availableRagTopics.length);
            
            if (btnAll) {
                if (isAllSelected) {
                    btnAll.className = "px-3 py-1.5 rounded-xl bg-purple-600 text-xs font-bold text-white shadow-sm transition-all";
                } else {
                    btnAll.className = "px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 transition-all";
                }
            }
            
            container.innerHTML = availableRagTopics.map(t => {
                const isSelected = isAllSelected || selectedRagTopics.includes(t.name);
                const safeName = escapeHtml(t.name);
                const safeJsName = t.name.replace(/'/g, "\\'");
                
                let icon = "📚";
                if (t.name.toLowerCase().includes("derecho")) icon = "⚖️";
                else if (t.name.toLowerCase().includes("procedimiento") || t.name.toLowerCase().includes("teccam")) icon = "🛠️";
                else if (t.name.toLowerCase().includes("estrategia")) icon = "📈";
                else if (t.name.toLowerCase().includes("filosof")) icon = "💡";
                
                let chipClass = isSelected 
                    ? "bg-purple-950/80 border-purple-500 text-purple-200 shadow-sm shadow-purple-950 font-semibold"
                    : "bg-slate-900/60 border-slate-800 text-slate-400 opacity-60 hover:opacity-100 hover:border-slate-700";
                    
                let checkBadge = isSelected
                    ? `<span class="w-2 h-2 rounded-full bg-emerald-400 inline-block"></span>`
                    : `<span class="w-2 h-2 rounded-full bg-slate-600 inline-block"></span>`;
                
                return `
                    <button type="button" onclick="toggleRagTopic('${safeJsName}')" class="flex items-center gap-2 px-3.5 py-2 rounded-xl border text-xs transition-all cursor-pointer ${chipClass}">
                        ${checkBadge}
                        <span>${icon} ${safeName}</span>
                        <span class="font-mono text-[10px] px-1.5 py-0.5 rounded-md bg-slate-950/60 text-purple-300 font-bold">${t.chunks_count}</span>
                    </button>
                `;
            }).join('');
            
            if (summaryEl) {
                if (isAllSelected) {
                    summaryEl.innerText = "✨ Todos los dominios (" + availableRagTopics.length + ")";
                } else {
                    summaryEl.innerText = "🎯 " + selectedRagTopics.join(', ');
                }
            }
        }

        function toggleRagTopic(topicName) {
            const isAllSelected = (selectedRagTopics.length === 0 || selectedRagTopics.length === availableRagTopics.length);
            
            if (isAllSelected) {
                // Si estaban todos seleccionados y hace clic en uno, aislar ese tema
                selectedRagTopics = [topicName];
            } else {
                if (selectedRagTopics.includes(topicName)) {
                    selectedRagTopics = selectedRagTopics.filter(t => t !== topicName);
                    // Si desmarca todos, vuelve a considerar "Todos"
                    if (selectedRagTopics.length === 0) {
                        selectedRagTopics = [];
                    }
                } else {
                    selectedRagTopics.push(topicName);
                    // Si seleccionó todos individualmente, resetear a vacío (todos)
                    if (selectedRagTopics.length === availableRagTopics.length) {
                        selectedRagTopics = [];
                    }
                }
            }
            renderRagTopicChips();
        }

        function toggleAllRagTopics() {
            selectedRagTopics = [];
            renderRagTopicChips();
        }

        async function toggleRagMasterPower(targetState = null) {
            const newState = (targetState !== null) ? Boolean(targetState) : !isRagGloballyEnabled;
            const btnPower = document.getElementById('btn-toggle-rag-power');
            if (btnPower) btnPower.style.opacity = '0.6';
            
            try {
                const res = await fetch('/api/rag/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: newState })
                });
                const data = await res.json();
                if (data.success) {
                    await loadRagStats();
                } else {
                    alert("Error cambiando estado del RAG: " + (data.error || "Desconocido"));
                }
            } catch (err) {
                alert("Error de conexión: " + err.message);
            } finally {
                if (btnPower) btnPower.style.opacity = '1';
            }
        }

        async function saveGlobalRagTopics() {
            const btn = document.getElementById('btn-save-topics');
            const originalHtml = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span>⏳</span> Guardando...';
            
            try {
                const res = await fetch('/api/rag/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ active_topics: selectedRagTopics })
                });
                const data = await res.json();
                if (data.success) {
                    btn.innerHTML = '<span>✅</span> ¡Guardado!';
                    setTimeout(() => {
                        btn.disabled = false;
                        btn.innerHTML = originalHtml;
                    }, 2000);
                } else {
                    alert("Error guardando configuración RAG: " + (data.error || "Desconocido"));
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;
                }
            } catch (err) {
                alert("Error de conexión: " + err.message);
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            }
        }

        async function deleteRagDocument(docId, docTitle) {
            if (!confirm(`¿Estás seguro de que deseas eliminar "${docTitle}" de la base vectorial LanceDB?`)) {
                return;
            }
            try {
                const res = await fetch(`/api/rag/documents/${encodeURIComponent(docId)}`, {
                    method: 'DELETE'
                });
                const data = await res.json();
                if (data.success) {
                    await loadRagStats();
                } else {
                    alert("Error eliminando documento: " + (data.error || "Desconocido"));
                }
            } catch (err) {
                alert("Error de conexión: " + err.message);
            }
        }

        async function triggerRagSync(force = false) {
            const confirmMsg = force 
                ? "⚠️ Aviso de Memoria GPU (Re-indexación Completa):\n\nPara garantizar máxima aceleración CUDA y proteger la VRAM, el servicio del LLM se pausará temporalmente durante la sincronización (~1-2 min) y se reactivará automáticamente al finalizar.\n\n¿Deseas iniciar la re-indexación forzada ahora?"
                : "⚠️ Aviso de Memoria GPU:\n\nPara sincronizar con máxima aceleración CUDA y proteger la VRAM, el servicio del LLM se pausará brevemente durante la sincronización (~15-45s) y se reactivará automáticamente al terminar.\n\n¿Deseas iniciar la sincronización ahora?";
                
            if (!confirm(confirmMsg)) {
                return;
            }

            const btn = document.getElementById('btn-sync-rag');
            const icon = document.getElementById('icon-sync-rag');
            const text = document.getElementById('text-sync-rag');
            
            btn.disabled = true;
            if (icon) icon.classList.add('animate-spin');
            if (text) text.innerText = "Sincronizando (LLM pausado temporalmente)...";
            
            try {
                const res = await fetch('/api/rag/sync', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ force: force })
                });
                const data = await res.json();
                
                // Polling cada 3 segundos hasta que termine
                let attempts = 0;
                const interval = setInterval(async () => {
                    attempts++;
                    await loadRagStats();
                    if (attempts >= 15) {
                        clearInterval(interval);
                        btn.disabled = false;
                        if (icon) icon.classList.remove('animate-spin');
                        if (text) text.innerText = "Sincronizar Base RAG Ahora";
                    }
                }, 3000);
                
            } catch (err) {
                alert("Error al iniciar sincronización: " + err.message);
                btn.disabled = false;
                if (icon) icon.classList.remove('animate-spin');
                if (text) text.innerText = "Sincronizar Base RAG Ahora";
            }
        }

        async function searchRagPlayground() {
            const input = document.getElementById('rag-query-input');
            const btn = document.getElementById('btn-search-rag');
            const container = document.getElementById('rag-results-container');
            const resultsList = document.getElementById('rag-results-list');
            const latencyHeader = document.getElementById('rag-latency-header');
            
            const query = input.value.trim();
            if (!query) {
                alert("Por favor escribe una consulta o pregunta.");
                return;
            }
            
            btn.disabled = true;
            btn.innerText = "Buscando...";
            container.classList.remove('hidden');
            resultsList.innerHTML = '<div class="p-4 text-center text-xs text-slate-500 animate-pulse font-mono">Buscando vectores más cercanos en LanceDB...</div>';
            
            try {
                const filterTemas = (selectedRagTopics && selectedRagTopics.length > 0) ? selectedRagTopics : null;
                const res = await fetch('/api/rag/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: query,
                        temas: filterTemas,
                        top_k: 4
                    })
                });
                const data = await res.json();
                
                if (latencyHeader) latencyHeader.innerText = `Latencia LanceDB: ${data.latency_ms} ms`;
                
                if (!data.results || data.results.length === 0) {
                    resultsList.innerHTML = '<div class="p-4 bg-slate-900/60 rounded-xl text-center text-xs text-slate-400">No se encontraron fragmentos relevantes para los dominios seleccionados.</div>';
                } else {
                    resultsList.innerHTML = data.results.map((r, idx) => {
                        const simPct = Math.round(r.similarity * 100);
                        let badgeColor = "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
                        if (simPct < 75) badgeColor = "bg-amber-500/10 text-amber-400 border-amber-500/30";
                        
                        return `
                            <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-4 flex flex-col gap-2 hover:border-purple-500/40 transition-all">
                                <div class="flex items-center justify-between gap-2 flex-wrap">
                                    <div class="flex items-center gap-2">
                                        <span class="text-xs font-mono font-bold text-purple-400">#${idx + 1}</span>
                                        <span class="text-xs font-bold text-slate-200">${escapeHtml(r.doc_title)}</span>
                                        <span class="text-xs font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-400">${escapeHtml(r.doc_topic)}</span>
                                    </div>
                                    <span class="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold border ${badgeColor}">
                                        ${simPct}% Coincidencia
                                    </span>
                                </div>
                                <div class="text-xs font-mono text-purple-300/80 flex items-center gap-1">
                                    <svg class="h-3.5 w-3.5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                                        <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
                                    </svg>
                                    ${escapeHtml(r.section_path || 'Sección Principal')}
                                </div>
                                <div class="text-xs text-slate-300 font-sans whitespace-pre-wrap bg-slate-950/60 p-3 rounded-lg border border-slate-800/60 mt-1 max-h-40 overflow-y-auto leading-relaxed">
                                    ${escapeHtml(r.content)}
                                </div>
                            </div>
                        `;
                    }).join('');
                }
            } catch (err) {
                resultsList.innerHTML = `<div class="p-4 bg-rose-950/20 border border-rose-800/40 rounded-xl text-center text-xs text-rose-300">Error: ${escapeHtml(err.message)}</div>`;
            } finally {
                btn.disabled = false;
                btn.innerText = "Buscar";
            }
        }

        // ==============================================================================
        // Configuración de Modelo Cloud para RAG (Alias: cloud-rag)
        // ==============================================================================
        let activeCloudProvidersList = [];
        let currentCloudRagProviderId = "";
        let currentCloudRagModelId = "";

        async function loadCloudRagSettings() {
            const provSelect = document.getElementById('cloud-rag-provider-select');
            const modelSelect = document.getElementById('cloud-rag-model-select');
            const badgeEl = document.getElementById('cloud-rag-current-badge');
            if (!provSelect || !modelSelect) return;

            try {
                // 1. Obtener configuración actual de RAG
                const ragRes = await fetch('/api/rag/settings');
                const ragData = await ragRes.json();
                currentCloudRagProviderId = ragData.cloud_rag_provider_id || "";
                currentCloudRagModelId = ragData.cloud_rag_model_id || "";
                const currentProvName = ragData.cloud_rag_provider_name || "";

                // 2. Obtener lista de proveedores cloud
                const provRes = await fetch('/api/cloud-providers');
                const provData = await provRes.json();
                activeCloudProvidersList = (Array.isArray(provData) ? provData : []).filter(p => p.is_active);

                if (activeCloudProvidersList.length === 0) {
                    provSelect.innerHTML = '<option value="">No hay proveedores en la nube activos</option>';
                    modelSelect.innerHTML = '<option value="">Sin modelos disponibles</option>';
                    if (badgeEl) badgeEl.innerText = 'Sin proveedor configurado';
                    return;
                }

                // Poblar select de proveedores
                provSelect.innerHTML = activeCloudProvidersList.map(p => {
                    const isSel = (p.id === currentCloudRagProviderId) ? 'selected' : '';
                    return `<option value="${p.id}" ${isSel}>${escapeHtml(p.name)} (${escapeHtml(p.base_url)})</option>`;
                }).join('');

                // Si no había proveedor guardado, seleccionar el primero
                if (!currentCloudRagProviderId && activeCloudProvidersList.length > 0) {
                    currentCloudRagProviderId = activeCloudProvidersList[0].id;
                }

                // Cargar modelos del proveedor seleccionado
                await populateCloudRagModels(currentCloudRagProviderId, currentCloudRagModelId);

                // Actualizar badge
                if (badgeEl) {
                    if (currentCloudRagProviderId && currentCloudRagModelId) {
                        const pFound = activeCloudProvidersList.find(p => p.id === currentCloudRagProviderId);
                        const pName = pFound ? pFound.name : currentProvName || 'Cloud';
                        badgeEl.innerText = `${pName} ➔ ${currentCloudRagModelId}`;
                        badgeEl.className = "font-mono text-xs text-emerald-400 bg-emerald-950/40 border border-emerald-500/30 px-2.5 py-0.5 rounded-lg";
                    } else {
                        badgeEl.innerText = 'No configurado (se usará el primer proveedor activo)';
                        badgeEl.className = "font-mono text-xs text-amber-400 bg-amber-950/40 border border-amber-500/30 px-2.5 py-0.5 rounded-lg";
                    }
                }
            } catch (err) {
                console.error("Error cargando configuración de Cloud RAG:", err);
            }
        }

        async function populateCloudRagModels(providerId, targetModelId = "") {
            const modelSelect = document.getElementById('cloud-rag-model-select');
            if (!modelSelect || !providerId) return;

            modelSelect.innerHTML = '<option value="">Cargando modelos del proveedor...</option>';
            try {
                const res = await fetch(`/api/cloud-providers/${providerId}/models`);
                const data = await res.json();
                const models = data.models || [];

                const found = models.some(m => m.id === targetModelId || m.prefixed_id === targetModelId);
                let optionsHtml = models.map(m => {
                    const isSel = (m.id === targetModelId || m.prefixed_id === targetModelId) ? 'selected' : '';
                    return `<option value="${m.id}" ${isSel}>${escapeHtml(m.name || m.id)}</option>`;
                }).join('');

                if (targetModelId && !found) {
                    optionsHtml = `<option value="${targetModelId}" selected>✨ ${escapeHtml(targetModelId)} (Manual)</option>` + optionsHtml;
                }

                modelSelect.innerHTML = optionsHtml;
            } catch (err) {
                modelSelect.innerHTML = `<option value="">Error cargando modelos: ${escapeHtml(err.message)}</option>`;
            }
        }

        async function onCloudRagProviderChange() {
            const provSelect = document.getElementById('cloud-rag-provider-select');
            if (!provSelect) return;
            const selectedProvId = provSelect.value;
            await populateCloudRagModels(selectedProvId, "");
        }

        async function saveCloudRagModelSelection() {
            const provSelect = document.getElementById('cloud-rag-provider-select');
            const modelSelect = document.getElementById('cloud-rag-model-select');
            const btn = document.getElementById('btn-save-cloud-rag');
            const badgeEl = document.getElementById('cloud-rag-current-badge');
            if (!provSelect || !modelSelect || !btn) return;

            const provId = provSelect.value;
            const modelId = modelSelect.value;

            if (!provId || !modelId) {
                alert("Debes seleccionar un proveedor y un modelo destino válido.");
                return;
            }

            const pFound = activeCloudProvidersList.find(p => p.id === provId);
            const provName = pFound ? pFound.name : "";

            const origHtml = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span>⏳</span> Guardando...';

            try {
                const res = await fetch('/api/rag/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        cloud_rag_provider_id: provId,
                        cloud_rag_provider_name: provName,
                        cloud_rag_model_id: modelId
                    })
                });
                const data = await res.json();
                if (data.success) {
                    currentCloudRagProviderId = provId;
                    currentCloudRagModelId = modelId;
                    btn.innerHTML = '<span>✅</span> ¡Guardado!';
                    if (badgeEl) {
                        badgeEl.innerText = `${provName} ➔ ${modelId}`;
                        badgeEl.className = "font-mono text-xs text-emerald-400 bg-emerald-950/40 border border-emerald-500/30 px-2.5 py-0.5 rounded-lg";
                    }
                    setTimeout(() => {
                        btn.disabled = false;
                        btn.innerHTML = origHtml;
                    }, 2000);
                } else {
                    alert("Error guardando modelo Cloud RAG: " + (data.error || "Desconocido"));
                    btn.disabled = false;
                    btn.innerHTML = origHtml;
                }
            } catch (err) {
                alert("Error de conexión: " + err.message);
                btn.disabled = false;
                btn.innerHTML = origHtml;
            }
        }

        async function viewDocumentStructure(docId, title) {
            const modal = document.getElementById('modal-rag-structure');
            const subtitle = document.getElementById('modal-structure-subtitle');
            const body = document.getElementById('modal-structure-body');

            if (!modal || !body) return;

            if (subtitle) subtitle.innerText = `Documento: "${title}" [ID: ${docId}]`;
            body.innerHTML = `
                <div class="py-12 flex flex-col items-center justify-center gap-3 text-purple-400">
                    <svg class="animate-spin h-6 w-6 text-purple-400" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                    </svg>
                    <span class="text-xs text-slate-400 font-mono">Analizando árbol de secciones en LanceDB...</span>
                </div>
            `;
            modal.classList.remove('hidden');

            try {
                const res = await fetch(`/api/rag/structure/${encodeURIComponent(docId)}`);
                const data = await res.json();

                if (!res.ok || !data.success) {
                    body.innerHTML = `<div class="p-4 bg-rose-950/40 border border-rose-500/40 text-rose-300 rounded-xl">Error: ${escapeHtml(data.error || 'No se pudo obtener la estructura.')}</div>`;
                    return;
                }

                if (subtitle) {
                    subtitle.innerText = `"${data.titulo}" — Total: ~${(data.total_doc_tokens || 0).toLocaleString()} tokens (${data.total_chunks || 0} chunks, ${data.sections_count || 0} secciones)`;
                }

                if (!data.sections || data.sections.length === 0) {
                    body.innerHTML = `<div class="text-slate-400 py-6 text-center">Este documento no tiene subdivisiones jerárquicas registradas.</div>`;
                    return;
                }

                let rowsHtml = data.sections.map(s => {
                    const cleanParam = s.section.split('>').pop().trim().replace(/"/g, '');
                    return `
                    <tr class="hover:bg-slate-900/60 transition-all border-b border-slate-800/40">
                        <td class="px-3 py-2 font-mono text-purple-400 text-center">${String(s.index).padStart(2, '0')}</td>
                        <td class="px-3 py-2 font-semibold text-slate-200">${escapeHtml(s.section)}</td>
                        <td class="px-3 py-2 text-center font-mono text-slate-300">${s.chunks_count}</td>
                        <td class="px-3 py-2 text-right font-mono text-emerald-400">~${(s.estimated_tokens || 0).toLocaleString()}</td>
                        <td class="px-3 py-2 text-right">
                            <span class="text-[11px] font-mono text-slate-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                                seccion="${escapeHtml(cleanParam)}"
                            </span>
                        </td>
                    </tr>
                    `;
                }).join('');

                body.innerHTML = `
                    <div class="flex flex-col gap-3">
                        <div class="flex items-center justify-between bg-slate-900/80 p-3 rounded-xl border border-slate-800 text-xs">
                            <div><span class="text-slate-400">Tema:</span> <span class="text-purple-300 font-semibold">${escapeHtml(data.tema || 'General')}</span></div>
                            <div><span class="text-slate-400">Autor:</span> <span class="text-slate-200">${escapeHtml(data.autor || 'Desconocido')}</span></div>
                            <div><span class="text-slate-400">Total Tokens:</span> <span class="text-emerald-400 font-bold font-mono">~${(data.total_doc_tokens || 0).toLocaleString()}</span></div>
                        </div>

                        <div class="overflow-x-auto rounded-xl border border-slate-800">
                            <table class="w-full text-left text-xs">
                                <thead class="bg-slate-900 text-slate-400 font-bold uppercase tracking-wider border-b border-slate-800">
                                    <tr>
                                        <th class="px-3 py-2 text-center">#</th>
                                        <th class="px-3 py-2">Sección / Capítulo</th>
                                        <th class="px-3 py-2 text-center">Chunks</th>
                                        <th class="px-3 py-2 text-right">Tokens</th>
                                        <th class="px-3 py-2 text-right">Parámetro de Tool</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${rowsHtml}
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;
            } catch (err) {
                body.innerHTML = `<div class="p-4 bg-rose-950/40 border border-rose-500/40 text-rose-300 rounded-xl">Error de red: ${escapeHtml(err.message)}</div>`;
            }
        }

        function closeRagStructureModal() {
            const modal = document.getElementById('modal-rag-structure');
            if (modal) modal.classList.add('hidden');
        }

