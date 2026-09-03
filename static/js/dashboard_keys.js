        // --- Gestión de Claves API Específicas (MongoDB) ---
        window.cachedCloudProviders = [];
        window.cachedProviderModels = {};

        async function getProviderModels(providerId) {
            if (window.cachedProviderModels[providerId]) {
                return window.cachedProviderModels[providerId];
            }
            try {
                const res = await fetch(`/api/cloud-providers/${providerId}/models`);
                const data = await res.json();
                if (res.ok && data.models) {
                    window.cachedProviderModels[providerId] = data.models;
                    return data.models;
                }
            } catch (err) {
                console.error(`Error cargando modelos para proveedor ${providerId}:`, err);
            }
            return [];
        }

        async function handleProviderCheckboxChange(context, providerId, preselectedModels = []) {
            const cb = document.getElementById(`${context}-prov-cb-${providerId}`);
            const panel = document.getElementById(`${context}-prov-models-panel-${providerId}`);
            if (!cb || !panel) return;

            if (cb.checked) {
                panel.classList.remove('hidden');
                const listContainer = document.getElementById(`${context}-prov-models-list-${providerId}`);
                if (listContainer && listContainer.getAttribute('data-loaded') !== 'true') {
                    listContainer.innerHTML = '<span class="text-[10px] text-indigo-400 animate-pulse">Consultando modelos del proveedor...</span>';
                    const models = await getProviderModels(providerId);
                    const existingModelIds = new Set(models.map(m => m.id));
                    const customPreselected = (preselectedModels || []).filter(mId => mId !== '*' && !existingModelIds.has(mId));

                    if (models.length === 0 && customPreselected.length === 0) {
                        listContainer.innerHTML = '<span class="text-[10px] text-slate-500">No se encontraron modelos automáticos. Puedes declarar modelos manualmente abajo.</span>';
                    } else {
                        listContainer.setAttribute('data-loaded', 'true');
                        let htmlItems = '';

                        // Renderizar modelos preseleccionados personalizados / manuales
                        customPreselected.forEach(mId => {
                            htmlItems += `
                                <label data-model-item class="flex items-center gap-2 text-[11px] text-cyan-300 hover:text-white cursor-pointer py-0.5 px-1 rounded bg-cyan-950/20 border border-cyan-500/20 hover:bg-cyan-900/30 transition-all">
                                    <input type="checkbox" data-context="${context}" data-provider-id="${providerId}" value="${escapeHtml(mId)}" checked onchange="updateProviderModelCountBadge('${context}', '${providerId}')" class="rounded border-slate-700 text-cyan-500 focus:ring-cyan-500 bg-slate-950">
                                    <span class="font-mono text-cyan-200 truncate flex-1" title="${escapeHtml(mId)}">✨ ${escapeHtml(mId)} <span class="text-[9px] text-cyan-400 font-sans font-semibold">(Manual)</span></span>
                                    <button type="button" onclick="this.closest('label').remove(); updateProviderModelCountBadge('${context}', '${providerId}')" class="text-slate-500 hover:text-rose-400 text-[10px] px-1" title="Eliminar">✕</button>
                                </label>
                            `;
                        });

                        // Renderizar modelos descubiertos del proveedor
                        models.forEach(m => {
                            const isChecked = preselectedModels.includes(m.id) || preselectedModels.includes(m.prefixed_id) || preselectedModels.includes('*');
                            htmlItems += `
                                <label data-model-item class="flex items-center gap-2 text-[11px] text-slate-300 hover:text-white cursor-pointer py-0.5 px-1 rounded hover:bg-slate-800/50 transition-all">
                                    <input type="checkbox" data-context="${context}" data-provider-id="${providerId}" value="${escapeHtml(m.id)}" ${isChecked ? 'checked' : ''} onchange="updateProviderModelCountBadge('${context}', '${providerId}')" class="rounded border-slate-700 text-cyan-500 focus:ring-cyan-500 bg-slate-950">
                                    <span class="font-mono text-slate-200 truncate" title="${escapeHtml(m.id)}">${escapeHtml(m.id)}</span>
                                </label>
                            `;
                        });

                        listContainer.innerHTML = htmlItems;
                    }
                    updateProviderModelCountBadge(context, providerId);
                }
            } else {
                panel.classList.add('hidden');
            }
        }

        function addCustomProviderModel(context, providerId) {
            const input = document.getElementById(`${context}-custom-model-${providerId}`);
            if (!input) return;
            const modelId = input.value.trim();
            if (!modelId) return;

            const listContainer = document.getElementById(`${context}-prov-models-list-${providerId}`);
            if (!listContainer) return;

            // Si la lista contenía el mensaje de estado vacío o de carga, limpiarlo
            if (listContainer.querySelector('span.text-slate-500, span.text-indigo-400')) {
                listContainer.innerHTML = '';
            }

            // Evitar duplicados
            const existingCb = Array.from(listContainer.querySelectorAll(`input[data-context="${context}"][data-provider-id="${providerId}"]`)).find(cb => cb.value === modelId);
            if (existingCb) {
                existingCb.checked = true;
                input.value = '';
                updateProviderModelCountBadge(context, providerId);
                return;
            }

            const newLabel = document.createElement('label');
            newLabel.setAttribute('data-model-item', '');
            newLabel.className = 'flex items-center gap-2 text-[11px] text-cyan-300 hover:text-white cursor-pointer py-0.5 px-1 rounded bg-cyan-950/20 border border-cyan-500/20 hover:bg-cyan-900/30 transition-all';
            newLabel.innerHTML = `
                <input type="checkbox" data-context="${context}" data-provider-id="${providerId}" value="${escapeHtml(modelId)}" checked onchange="updateProviderModelCountBadge('${context}', '${providerId}')" class="rounded border-slate-700 text-cyan-500 focus:ring-cyan-500 bg-slate-950">
                <span class="font-mono text-cyan-200 truncate flex-1" title="${escapeHtml(modelId)}">✨ ${escapeHtml(modelId)} <span class="text-[9px] text-cyan-400 font-sans font-semibold">(Manual)</span></span>
                <button type="button" onclick="this.closest('label').remove(); updateProviderModelCountBadge('${context}', '${providerId}')" class="text-slate-500 hover:text-rose-400 text-[10px] px-1" title="Eliminar">✕</button>
            `;
            listContainer.prepend(newLabel);
            input.value = '';
            updateProviderModelCountBadge(context, providerId);
        }

        function filterProviderModels(context, providerId, query) {
            const listContainer = document.getElementById(`${context}-prov-models-list-${providerId}`);
            if (!listContainer) return;
            const q = (query || '').toLowerCase().trim();
            const items = listContainer.querySelectorAll('[data-model-item]');
            items.forEach(item => {
                const text = item.textContent.toLowerCase();
                if (!q || text.includes(q)) {
                    item.classList.remove('hidden');
                } else {
                    item.classList.add('hidden');
                }
            });
        }

        function selectAllProviderModels(context, providerId, selectAll) {
            const listContainer = document.getElementById(`${context}-prov-models-list-${providerId}`);
            if (!listContainer) return;
            const checkboxes = listContainer.querySelectorAll(`input[data-context="${context}"][data-provider-id="${providerId}"]`);
            checkboxes.forEach(cb => {
                const item = cb.closest('[data-model-item]');
                if (!item || !item.classList.contains('hidden')) {
                    cb.checked = selectAll;
                }
            });
            updateProviderModelCountBadge(context, providerId);
        }

        function updateProviderModelCountBadge(context, providerId) {
            const badge = document.getElementById(`${context}-prov-count-${providerId}`);
            if (!badge) return;
            const checkedCount = document.querySelectorAll(`input[data-context="${context}"][data-provider-id="${providerId}"]:checked`).length;
            const totalCount = document.querySelectorAll(`input[data-context="${context}"][data-provider-id="${providerId}"]`).length;
            badge.textContent = `${checkedCount} / ${totalCount} modelos`;
            if (checkedCount > 0) {
                badge.className = "text-[9px] px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-semibold border border-indigo-500/30";
            } else {
                badge.className = "text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-semibold";
            }
        }

        function renderCloudProviderCheckboxes() {
            const createContainer = document.getElementById('key-cloud-providers-container');
            if (!createContainer) return;

            if (!window.cachedCloudProviders || window.cachedCloudProviders.length === 0) {
                createContainer.innerHTML = '<span class="text-[10px] text-slate-500">No hay proveedores en la nube registrados.</span>';
                return;
            }

            createContainer.innerHTML = window.cachedCloudProviders.map(p => `
                <div class="flex flex-col gap-1.5 p-2 rounded-lg bg-slate-950/40 border border-slate-800/80">
                    <label class="flex items-center justify-between gap-2 text-xs text-slate-300 cursor-pointer select-none">
                        <div class="flex items-center gap-2">
                            <input id="create-prov-cb-${p.id}" type="checkbox" name="key-providers" value="${p.id}" onchange="handleProviderCheckboxChange('create', '${p.id}')" class="rounded border-slate-800 text-indigo-500 focus:ring-indigo-500 bg-slate-950">
                            <span class="font-semibold text-slate-200">☁️ ${escapeHtml(p.name)}</span>
                        </div>
                        <span id="create-prov-count-${p.id}" class="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-semibold">0 modelos</span>
                    </label>
                    <div id="create-prov-models-panel-${p.id}" class="hidden flex flex-col gap-1.5 mt-1 pt-1.5 border-t border-slate-800/60 pl-2">
                        <div class="flex items-center gap-1.5">
                            <input type="text" placeholder="Filtrar modelos (ej: sonnet, gpt-4)..." oninput="filterProviderModels('create', '${p.id}', this.value)" class="flex-1 bg-slate-900 border border-slate-800 rounded px-2 py-0.5 text-[10px] text-slate-200 focus:outline-none focus:border-indigo-500">
                            <button type="button" onclick="selectAllProviderModels('create', '${p.id}', true)" class="text-[9px] px-1.5 py-0.5 bg-slate-800 hover:bg-slate-700 text-indigo-300 rounded font-medium">Todos</button>
                            <button type="button" onclick="selectAllProviderModels('create', '${p.id}', false)" class="text-[9px] px-1.5 py-0.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded font-medium">Ninguno</button>
                        </div>
                        <div id="create-prov-models-list-${p.id}" class="flex flex-col gap-0.5 max-h-32 overflow-y-auto pr-1">
                            <span class="text-[10px] text-slate-500">Cargando modelos...</span>
                        </div>
                        <div class="flex items-center gap-1 mt-1 pt-1 border-t border-slate-850">
                            <input type="text" id="create-custom-model-${p.id}" placeholder="ID de modelo manual / no listado (ej: gemma4:31b)..." onkeydown="if(event.key==='Enter'){event.preventDefault(); addCustomProviderModel('create', '${p.id}');}" class="flex-1 bg-slate-900 border border-slate-800 rounded px-2 py-0.5 text-[10px] text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 font-mono">
                            <button type="button" onclick="addCustomProviderModel('create', '${p.id}')" class="text-[9px] px-2 py-0.5 bg-cyan-950/60 hover:bg-cyan-900/80 text-cyan-300 border border-cyan-500/30 rounded font-medium flex items-center gap-1 transition-colors">
                                <span>➕ Agregar</span>
                            </button>
                        </div>
                    </div>
                </div>
            `).join('');
        }

        async function renderEditCloudProviderCheckboxes(allowedProviders, keyModelsByProvider = {}) {
            const editContainer = document.getElementById('edit-key-cloud-providers-container');
            if (!editContainer) return;

            if (!window.cachedCloudProviders || window.cachedCloudProviders.length === 0) {
                editContainer.innerHTML = '<span class="text-[10px] text-slate-500">No hay proveedores en la nube registrados.</span>';
                return;
            }

            editContainer.innerHTML = window.cachedCloudProviders.map(p => {
                const isChecked = (allowedProviders || []).includes(p.id) || (allowedProviders || []).includes(p.name) || (allowedProviders || []).includes('*');
                return `
                    <div class="flex flex-col gap-1.5 p-2 rounded-lg bg-slate-950/40 border border-slate-800/80">
                        <label class="flex items-center justify-between gap-2 text-xs text-slate-300 cursor-pointer select-none">
                            <div class="flex items-center gap-2">
                                <input id="edit-prov-cb-${p.id}" type="checkbox" name="edit-key-providers" value="${p.id}" ${isChecked ? 'checked' : ''} onchange="handleProviderCheckboxChange('edit', '${p.id}')" class="rounded border-slate-800 text-indigo-500 focus:ring-indigo-500 bg-slate-950">
                                <span class="font-semibold text-slate-200">☁️ ${escapeHtml(p.name)}</span>
                            </div>
                            <span id="edit-prov-count-${p.id}" class="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-semibold">0 modelos</span>
                        </label>
                        <div id="edit-prov-models-panel-${p.id}" class="${isChecked ? '' : 'hidden'} flex flex-col gap-1.5 mt-1 pt-1.5 border-t border-slate-800/60 pl-2">
                            <div class="flex items-center gap-1.5">
                                <input type="text" placeholder="Filtrar modelos (ej: sonnet, gpt-4)..." oninput="filterProviderModels('edit', '${p.id}', this.value)" class="flex-1 bg-slate-900 border border-slate-800 rounded px-2 py-0.5 text-[10px] text-slate-200 focus:outline-none focus:border-indigo-500">
                                <button type="button" onclick="selectAllProviderModels('edit', '${p.id}', true)" class="text-[9px] px-1.5 py-0.5 bg-slate-800 hover:bg-slate-700 text-indigo-300 rounded font-medium">Todos</button>
                                <button type="button" onclick="selectAllProviderModels('edit', '${p.id}', false)" class="text-[9px] px-1.5 py-0.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded font-medium">Ninguno</button>
                            </div>
                            <div id="edit-prov-models-list-${p.id}" class="flex flex-col gap-0.5 max-h-32 overflow-y-auto pr-1">
                                <span class="text-[10px] text-slate-500">Cargando modelos...</span>
                            </div>
                            <div class="flex items-center gap-1 mt-1 pt-1 border-t border-slate-850">
                                <input type="text" id="edit-custom-model-${p.id}" placeholder="ID de modelo manual / no listado (ej: gemma4:31b)..." onkeydown="if(event.key==='Enter'){event.preventDefault(); addCustomProviderModel('edit', '${p.id}');}" class="flex-1 bg-slate-900 border border-slate-800 rounded px-2 py-0.5 text-[10px] text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 font-mono">
                                <button type="button" onclick="addCustomProviderModel('edit', '${p.id}')" class="text-[9px] px-2 py-0.5 bg-cyan-950/60 hover:bg-cyan-900/80 text-cyan-300 border border-cyan-500/30 rounded font-medium flex items-center gap-1 transition-colors">
                                    <span>➕ Agregar</span>
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');

            // Para los proveedores ya marcados, cargar sus modelos e inicializar la selección
            for (const p of window.cachedCloudProviders) {
                const isChecked = (allowedProviders || []).includes(p.id) || (allowedProviders || []).includes(p.name) || (allowedProviders || []).includes('*');
                if (isChecked) {
                    const preselected = keyModelsByProvider[p.id] || [];
                    await handleProviderCheckboxChange('edit', p.id, preselected);
                }
            }
        }

        async function loadApiKeys(isSilent = false) {
            const container = document.getElementById('keys-list-container');
            if (!container) return;
            
            if (!isSilent && container.children.length === 0) {
                container.innerHTML = '<div class="text-center py-8 text-xs text-slate-500">Cargando claves...</div>';
            }
            
            try {
                // Asegurar que los proveedores estén en caché para resolver nombres
                if (!window.cachedCloudProviders || window.cachedCloudProviders.length === 0) {
                    try {
                        const pRes = await fetch('/api/cloud-providers');
                        window.cachedCloudProviders = await pRes.json();
                        renderCloudProviderCheckboxes();
                    } catch(e) {}
                }

                const res = await fetch('/api/keys');
                const keys = await res.json();
                
                if (keys.length === 0) {
                    container.innerHTML = `
                        <div class="border border-dashed border-slate-850 rounded-xl p-8 text-center flex flex-col items-center justify-center gap-2 bg-slate-900/10">
                            <span class="text-xs text-slate-400 font-semibold">No hay claves API secundarias creadas.</span>
                            <span class="text-[10px] text-slate-500">Solo está activa la clave maestra ('API_KEY') de tu archivo .env.</span>
                        </div>
                    `;
                    return;
                }
                
                // Comprobamos si la estructura de IDs ha cambiado
                const currentIds = keys.map(k => k.id).join(',');
                const existingCards = container.querySelectorAll('[data-key-card-id]');
                const existingIds = Array.from(existingCards).map(c => c.getAttribute('data-key-card-id')).join(',');
                
                // Si las tarjetas ya existen y la lista es idéntica, actualizamos valores in-place de forma suave
                if (existingIds === currentIds && isSilent) {
                    keys.forEach(k => {
                        const usedTokens = Number(k.used_tokens) || 0;
                        const maxTokens = Number(k.max_tokens) || 0;
                        
                        if (maxTokens > 0) {
                            const pct = Math.min(100, Math.round((usedTokens / maxTokens) * 1000) / 10);
                            let barColor = 'bg-cyan-500';
                            let textColor = 'text-cyan-400 font-semibold';
                            if (pct >= 90) {
                                barColor = 'bg-rose-500';
                                textColor = 'text-rose-400 font-bold';
                            } else if (pct >= 75) {
                                barColor = 'bg-amber-500';
                                textColor = 'text-amber-400 font-semibold';
                            }
                            
                            const textEl = document.getElementById(`key-quota-used-text-${k.id}`);
                            if (textEl) {
                                textEl.className = textColor;
                                textEl.textContent = `${usedTokens.toLocaleString()} / ${maxTokens.toLocaleString()}`;
                            }
                            const pctEl = document.getElementById(`key-quota-pct-${k.id}`);
                            if (pctEl) {
                                pctEl.className = textColor;
                                pctEl.textContent = `${pct}%`;
                            }
                            const barEl = document.getElementById(`key-quota-bar-${k.id}`);
                            if (barEl) {
                                barEl.className = `${barColor} h-1.5 rounded-full transition-all duration-500`;
                                barEl.style.width = `${pct}%`;
                            }
                        } else {
                            const unlEl = document.getElementById(`key-unlimited-used-text-${k.id}`);
                            if (unlEl) {
                                unlEl.textContent = usedTokens.toLocaleString();
                            }
                        }
                    });
                    return;
                }
                
                let html = '';
                keys.forEach(k => {
                    const activeClass = k.is_active 
                        ? 'border-emerald-500/30 bg-emerald-950/5' 
                        : 'border-red-950/30 bg-red-950/5 opacity-60';
                    const activePill = k.is_active
                        ? '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 uppercase">Activa</span>'
                        : '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-red-500/20 text-red-400 uppercase">Suspendida</span>';
                        
                    let expiryHtml = '<span class="text-[10px] text-slate-500">Nunca expira</span>';
                    if (k.expires_at) {
                        const date = new Date(k.expires_at);
                        const expired = date < new Date();
                        const color = expired ? 'text-red-400 font-bold' : 'text-slate-400';
                        expiryHtml = `<span class="text-[10px] ${color}">Vence: ${date.toLocaleDateString()}</span>`;
                    }
                    
                    let servicesHtml = '';
                    const svcMap = {
                        'gemma': { name: 'LLM MEA (8000)', color: 'bg-indigo-500/10 text-indigo-400' },
                        'gemma_raw': { name: 'LLM RAW (8010)', color: 'bg-amber-500/10 text-amber-400' },
                        'whisper': { name: 'STT', color: 'bg-cyan-500/10 text-cyan-400' },
                        'tts': { name: 'TTS', color: 'bg-emerald-500/10 text-emerald-400' },
                        'diarization': { name: 'DIAR', color: 'bg-amber-500/10 text-amber-400' },
                        'embeddings': { name: 'EMBEDDINGS', color: 'bg-purple-500/10 text-purple-400' },
                        'image': { name: 'IMAGEN', color: 'bg-pink-500/10 text-pink-400' },
                        'docling': { name: 'DOCLING / OCR', color: 'bg-teal-500/10 text-teal-400' }
                    };
                    (k.services || []).forEach(s => {
                        const info = svcMap[s] || { name: s, color: 'bg-slate-500/10 text-slate-400' };
                        servicesHtml += `<span class="px-2 py-0.5 rounded text-[9px] font-bold ${info.color} uppercase text-center">${info.name}</span>`;
                    });

                    let providersHtml = '';
                    (k.allowed_providers || []).forEach(pId => {
                        const prov = (window.cachedCloudProviders || []).find(p => p.id === pId || p.name === pId);
                        const pName = prov ? prov.name : (pId === '*' ? 'Todos los Proveedores' : pId);
                        const modelCount = (k.models_by_provider && k.models_by_provider[pId]) ? k.models_by_provider[pId].length : 0;
                        const countBadge = modelCount > 0 ? `<span class="bg-indigo-900/80 text-indigo-200 text-[8px] px-1.5 py-0.2 rounded-full font-mono font-normal">(${modelCount} mod)</span>` : '';
                        providersHtml += `<span class="px-2 py-0.5 rounded text-[9px] font-bold bg-indigo-500/20 text-indigo-300 uppercase text-center flex items-center gap-1">☁️ ${escapeHtml(pName)} ${countBadge}</span>`;
                    });

                    // Barra de progreso de cupo de tokens
                    const usedTokens = Number(k.used_tokens) || 0;
                    const maxTokens = Number(k.max_tokens) || 0;
                    const quotaReset = k.quota_reset || 'none';
                    let resetBadge = '';
                    if (quotaReset === 'daily') {
                        resetBadge = '<span class="text-[9px] px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-300 font-semibold border border-indigo-500/30">📅 Diario</span>';
                    } else if (quotaReset === 'monthly') {
                        resetBadge = '<span class="text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-300 font-semibold border border-cyan-500/30">🗓️ Mensual</span>';
                    } else if (maxTokens > 0) {
                        resetBadge = '<span class="text-[9px] px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-400 font-semibold border border-slate-700/50">Manual</span>';
                    }

                    let quotaHtml = '';
                    if (maxTokens > 0) {
                        const pct = Math.min(100, Math.round((usedTokens / maxTokens) * 1000) / 10);
                        let barColor = 'bg-cyan-500';
                        let textColor = 'text-cyan-400 font-semibold';
                        if (pct >= 90) {
                            barColor = 'bg-rose-500';
                            textColor = 'text-rose-400 font-bold';
                        } else if (pct >= 75) {
                            barColor = 'bg-amber-500';
                            textColor = 'text-amber-400 font-semibold';
                        }
                        quotaHtml = `
                            <div class="mt-2 flex flex-col gap-1 w-full max-w-sm">
                                <div class="flex justify-between items-center text-[10px]">
                                    <span class="text-slate-400 flex items-center gap-1.5">Cupo de Tokens: <span id="key-quota-used-text-${k.id}" class="${textColor}">${usedTokens.toLocaleString()} / ${maxTokens.toLocaleString()}</span> ${resetBadge}</span>
                                    <span id="key-quota-pct-${k.id}" class="${textColor}">${pct}%</span>
                                </div>
                                <div class="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden border border-slate-800">
                                    <div id="key-quota-bar-${k.id}" class="${barColor} h-1.5 rounded-full transition-all duration-500" style="width: ${pct}%"></div>
                                </div>
                            </div>
                        `;
                    } else {
                        quotaHtml = `
                            <div class="mt-1 text-[10px] text-slate-400 flex items-center gap-1.5">
                                <span>Tokens consumidos: <span id="key-unlimited-used-text-${k.id}" class="font-mono text-slate-300 font-semibold">${usedTokens.toLocaleString()}</span> <span class="text-slate-500 font-mono">(Ilimitado)</span></span>
                                ${resetBadge}
                            </div>
                        `;
                    }

                    const escName = k.name.replace(/'/g, "\\'").replace(/"/g, '&quot;');
                    const escDesc = (k.description || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
                    const svcJson = JSON.stringify(k.services || []).replace(/"/g, '&quot;');
                    const provJson = JSON.stringify(k.allowed_providers || []).replace(/"/g, '&quot;');

                    html += `
                        <div data-key-card-id="${k.id}" class="glass-panel p-4 rounded-xl border flex flex-col md:flex-row justify-between items-start md:items-center gap-4 transition-all ${activeClass}">
                            <div class="flex-1 flex flex-col gap-1 min-w-[200px]">
                                <div class="flex items-center gap-2">
                                    <span class="text-xs font-bold text-slate-200">${escapeHtml(k.name)}</span>
                                    ${activePill}
                                </div>
                                <span class="text-[10px] text-slate-400 font-medium">${escapeHtml(k.description || 'Sin descripción')}</span>
                                <div class="flex flex-wrap items-center gap-2 mt-1.5">
                                    ${servicesHtml}
                                    ${providersHtml}
                                    <span class="text-slate-600">|</span>
                                    ${expiryHtml}
                                </div>
                                ${quotaHtml}
                            </div>
                            <div class="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full md:w-auto">
                                <div class="flex items-center bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 font-mono text-[10px] select-all relative group max-w-xs overflow-hidden text-ellipsis whitespace-nowrap">
                                    <span id="key-text-${k.id}" class="text-slate-400 select-all">${k.key}</span>
                                </div>
                                <div class="flex gap-2 justify-end">
                                    <button onclick="resetKeyQuota('${k.id}', '${escName}')" class="px-2 py-1 bg-cyan-950/40 hover:bg-cyan-900/50 text-cyan-400 hover:text-cyan-300 rounded text-[10px] font-semibold border border-cyan-800/40 transition-all" title="Reiniciar contador de tokens a cero">Reiniciar Cupo</button>
                                    <button onclick="openEditKeyModal('${k.id}', '${escName}', '${escDesc}', '${svcJson}', '${provJson}', ${maxTokens}, '${quotaReset}', '${k.expires_at || ''}', ${k.is_active})" class="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded text-[10px] font-semibold border border-slate-700 transition-all">Editar</button>
                                    <button onclick="deleteApiKey('${k.id}')" class="px-2 py-1 bg-red-950/50 hover:bg-red-900/50 text-red-400 hover:text-red-300 rounded text-[10px] font-semibold border border-red-900/30 transition-all">Borrar</button>
                                </div>
                            </div>
                        </div>
                    `;
                });
                container.innerHTML = html;
            } catch (err) {
                if (!isSilent) {
                    container.innerHTML = `<div class="text-center py-8 text-xs text-red-400">Error al cargar claves: ${err.message}</div>`;
                }
            }
        }

        async function createApiKey() {
            const name = document.getElementById('key-name').value.trim();
            const desc = document.getElementById('key-desc').value.trim();
            const maxTokens = parseInt(document.getElementById('key-max-tokens').value) || 0;
            const quotaReset = document.getElementById('key-quota-reset').value;
            const expiry = document.getElementById('key-expiry').value;
            
            const services = [];
            document.querySelectorAll('input[name="key-services"]:checked').forEach(cb => {
                services.push(cb.value);
            });

            const allowed_providers = [];
            const allowed_models = {};
            document.querySelectorAll('input[name="key-providers"]:checked').forEach(cb => {
                const pId = cb.value;
                allowed_providers.push(pId);
                const modelCbs = document.querySelectorAll(`input[data-context="create"][data-provider-id="${pId}"]:checked`);
                allowed_models[pId] = Array.from(modelCbs).map(mCb => mCb.value);
            });

            if (!name) {
                alert("El nombre de la clave es obligatorio.");
                return;
            }

            if (services.length === 0 && allowed_providers.length === 0) {
                alert("Debes seleccionar al menos un servicio local o un proveedor en la nube.");
                return;
            }

            try {
                const res = await fetch('/api/keys', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: name,
                        description: desc,
                        services: services,
                        allowed_providers: allowed_providers,
                        allowed_models: allowed_models,
                        max_tokens: maxTokens,
                        quota_reset: quotaReset,
                        expires_at: expiry
                    })
                });
                
                const data = await res.json();
                if (res.ok) {
                    document.getElementById('key-name').value = '';
                    document.getElementById('key-desc').value = '';
                    document.getElementById('key-max-tokens').value = '';
                    document.getElementById('key-quota-reset').value = 'none';
                    document.getElementById('key-expiry').value = '';
                    document.querySelectorAll('input[name="key-services"]').forEach(cb => cb.checked = false);
                    document.querySelectorAll('input[name="key-providers"]').forEach(cb => cb.checked = false);
                    renderCloudProviderCheckboxes();
                    
                    loadApiKeys();
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (err) {
                alert(`Error al guardar clave: ${err.message}`);
            }
        }

        async function resetKeyQuota(keyId, keyName) {
            if (!confirm(`¿Estás seguro de reiniciar el contador de tokens a cero para la clave '${keyName}'?`)) {
                return;
            }
            try {
                const res = await fetch(`/api/keys/${keyId}/reset-quota`, { method: 'POST' });
                const data = await res.json();
                if (res.ok) {
                    loadApiKeys();
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (err) {
                alert(`Error al reiniciar cupo: ${err.message}`);
            }
        }

        async function deleteApiKey(keyId) {
            if (!confirm("¿Estás seguro de que deseas eliminar esta clave API? Cualquier servicio que la use perderá el acceso inmediatamente.")) {
                return;
            }
            
            try {
                const res = await fetch(`/api/keys/${keyId}`, { method: 'DELETE' });
                const data = await res.json();
                if (res.ok) {
                    loadApiKeys();
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (err) {
                alert(`Error al borrar clave: ${err.message}`);
            }
        }

        async function openEditKeyModal(id, name, desc, servicesJson, providersJson, maxTokens, quotaReset, expiry, isActive) {
            const services = typeof servicesJson === 'string' ? JSON.parse(servicesJson) : (servicesJson || []);
            const providers = typeof providersJson === 'string' ? JSON.parse(providersJson) : (providersJson || []);
            
            document.getElementById('edit-key-id').value = id;
            document.getElementById('edit-key-name').value = name;
            document.getElementById('edit-key-desc').value = desc;
            document.getElementById('edit-key-max-tokens').value = maxTokens || '';
            document.getElementById('edit-key-quota-reset').value = quotaReset || 'none';
            document.getElementById('edit-key-expiry').value = expiry ? expiry.split('T')[0] : '';
            document.getElementById('edit-key-active').value = String(isActive);
            
            document.getElementById('edit-key-service-gemma').checked = services.includes('gemma');
            const gemmaRawEl = document.getElementById('edit-key-service-gemma_raw');
            if (gemmaRawEl) gemmaRawEl.checked = services.includes('gemma_raw');
            document.getElementById('edit-key-service-whisper').checked = services.includes('whisper');
            document.getElementById('edit-key-service-tts').checked = services.includes('tts');
            document.getElementById('edit-key-service-diarization').checked = services.includes('diarization');
            document.getElementById('edit-key-service-embeddings').checked = services.includes('embeddings');
            document.getElementById('edit-key-service-image').checked = services.includes('image');
            const doclingEl = document.getElementById('edit-key-service-docling');
            if (doclingEl) doclingEl.checked = services.includes('docling');
            
            // Consultar modelos existentes asignados a esta clave API
            let keyModelsByProv = {};
            try {
                const kmRes = await fetch(`/api/keys/${id}/models`);
                if (kmRes.ok) {
                    const kmList = await kmRes.json();
                    kmList.forEach(km => {
                        const pId = km.provider_id;
                        if (!keyModelsByProv[pId]) keyModelsByProv[pId] = [];
                        keyModelsByProv[pId].push(km.model_id);
                    });
                }
            } catch(e) {
                console.error("Error obteniendo modelos de la clave:", e);
            }
            
            await renderEditCloudProviderCheckboxes(providers, keyModelsByProv);
            
            document.getElementById('edit-key-modal').classList.remove('hidden');
        }

        function closeEditKeyModal() {
            document.getElementById('edit-key-modal').classList.add('hidden');
        }

        async function updateApiKey() {
            const id = document.getElementById('edit-key-id').value;
            const name = document.getElementById('edit-key-name').value.trim();
            const desc = document.getElementById('edit-key-desc').value.trim();
            const maxTokens = parseInt(document.getElementById('edit-key-max-tokens').value) || 0;
            const quotaReset = document.getElementById('edit-key-quota-reset').value;
            const expiry = document.getElementById('edit-key-expiry').value;
            const isActive = document.getElementById('edit-key-active').value === 'true';
            
            const services = [];
            if (document.getElementById('edit-key-service-gemma').checked) services.push('gemma');
            const gemmaRawElUpdate = document.getElementById('edit-key-service-gemma_raw');
            if (gemmaRawElUpdate && gemmaRawElUpdate.checked) services.push('gemma_raw');
            if (document.getElementById('edit-key-service-whisper').checked) services.push('whisper');
            if (document.getElementById('edit-key-service-tts').checked) services.push('tts');
            if (document.getElementById('edit-key-service-diarization').checked) services.push('diarization');
            if (document.getElementById('edit-key-service-embeddings').checked) services.push('embeddings');
            if (document.getElementById('edit-key-service-image').checked) services.push('image');
            const doclingElUpdate = document.getElementById('edit-key-service-docling');
            if (doclingElUpdate && doclingElUpdate.checked) services.push('docling');

            const allowed_providers = [];
            const allowed_models = {};
            document.querySelectorAll('input[name="edit-key-providers"]:checked').forEach(cb => {
                const pId = cb.value;
                allowed_providers.push(pId);
                const modelCbs = document.querySelectorAll(`input[data-context="edit"][data-provider-id="${pId}"]:checked`);
                allowed_models[pId] = Array.from(modelCbs).map(mCb => mCb.value);
            });

            if (!name) {
                alert("El nombre de la clave es obligatorio.");
                return;
            }

            if (services.length === 0 && allowed_providers.length === 0) {
                alert("Debes seleccionar al menos un servicio local o un proveedor en la nube.");
                return;
            }

            try {
                const res = await fetch(`/api/keys/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: name,
                        description: desc,
                        services: services,
                        allowed_providers: allowed_providers,
                        allowed_models: allowed_models,
                        max_tokens: maxTokens,
                        quota_reset: quotaReset,
                        expires_at: expiry,
                        is_active: isActive
                    })
                });
                
                const data = await res.json();
                if (res.ok) {
                    closeEditKeyModal();
                    loadApiKeys();
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (err) {
                alert(`Error al actualizar clave: ${err.message}`);
            }
        }



        // --- Gestión de Reglas de IP (MongoDB) ---
        async function loadIpRules() {
            try {
                const res = await fetch('/api/ip-rules');
                const rules = await res.json();
                
                const container = document.getElementById('ip-rules-list');
                if (rules.length === 0) {
                    container.innerHTML = `
                        <tr>
                            <td colspan="5" class="text-center py-8 text-slate-500">
                                No hay reglas de IP configuradas. El Gateway permite acceso libre desde cualquier IP (validando la API Key).
                            </td>
                        </tr>
                    `;
                    return;
                }
                
                container.innerHTML = rules.map(r => {
                    const badgeAction = r.action === 'whitelist' 
                        ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-600/10 text-emerald-400 border border-emerald-500/20 font-mono">LISTA BLANCA</span>' 
                        : '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-600/10 text-rose-400 border border-rose-500/20 font-mono">LISTA NEGRA</span>';
                        
                    const badgeActive = r.is_active 
                        ? '<span class="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-650/10 text-emerald-400 border border-emerald-500/20">ACTIVA</span>' 
                        : '<span class="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-slate-800 text-slate-500 border border-slate-700/20">INACTIVA</span>';
                        
                    return `
                        <tr class="hover:bg-slate-900/40 transition-colors">
                            <td class="py-3 px-3 font-semibold text-slate-200">${escapeHtml(r.name)}</td>
                            <td class="py-3 px-3 font-mono text-xs text-indigo-300">${escapeHtml(r.network)}</td>
                            <td class="py-3 px-3">${badgeAction}</td>
                            <td class="py-3 px-3">${badgeActive}</td>
                            <td class="py-3 px-3 text-right">
                                <div class="flex gap-2 justify-end">
                                    <button onclick="openEditIpModal('${r.id}', '${escapeJs(r.name)}', '${escapeJs(r.network)}', '${r.action}', ${r.is_active})" class="p-1 hover:text-emerald-400 text-slate-400 transition-colors" title="Editar">
                                        <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                                            <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                        </svg>
                                    </button>
                                    <button onclick="deleteIpRule('${r.id}')" class="p-1 hover:text-rose-400 text-slate-400 transition-colors" title="Eliminar">
                                        <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                                            <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                        </svg>
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `;
                }).join('');
            } catch (err) {
                console.error("Error al cargar reglas de IP:", err);
            }
        }

        // --- Gestión de Proveedores de IA en la Nube ---
        async function loadCloudProviders() {
            try {
                const res = await fetch('/api/cloud-providers');
                const providers = await res.json();
                window.cachedCloudProviders = providers;
                
                renderCloudProviderCheckboxes();

                const container = document.getElementById('cloud-providers-list');
                if (container) {
                    if (providers.length === 0) {
                        container.innerHTML = `
                            <tr>
                                <td colspan="5" class="text-center py-8 text-slate-500 font-medium">
                                    No hay proveedores de IA en la nube configurados. La suite solo procesará modelos locales.
                                </td>
                            </tr>
                        `;
                    } else {
                        container.innerHTML = providers.map(p => {
                            const badgeActive = p.is_active 
                                ? '<span class="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-cyan-950/15 text-cyan-400 border border-cyan-500/20">ACTIVO</span>' 
                                : '<span class="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-slate-800 text-slate-500 border border-slate-700/20">INACTIVO</span>';
                                
                            return `
                                <tr class="hover:bg-slate-900/40 transition-colors">
                                    <td class="py-3 px-3 font-semibold text-slate-200">${escapeHtml(p.name)}</td>
                                    <td class="py-3 px-3 font-mono text-xs text-indigo-300">${escapeHtml(p.base_url)}</td>
                                    <td class="py-3 px-3 font-mono text-xs text-slate-450">${escapeHtml(p.api_key)}</td>
                                    <td class="py-3 px-3">${badgeActive}</td>
                                    <td class="py-3 px-3 text-right">
                                        <div class="flex gap-2 justify-end">
                                            <button onclick="editCloudProvider('${p.id}', '${escapeJs(p.name)}', '${escapeJs(p.base_url)}', '${escapeJs(p.api_key)}', ${p.is_active})" class="p-1 hover:text-cyan-400 text-slate-400 transition-colors" title="Editar">
                                                <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                                                    <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                                </svg>
                                            </button>
                                            <button onclick="deleteCloudProvider('${p.id}')" class="p-1 hover:text-rose-400 text-slate-400 transition-colors" title="Eliminar">
                                                <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                                                    <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                </svg>
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            `;
                        }).join('');
                    }
                }
            } catch (err) {
                console.error("Error al cargar proveedores en la nube:", err);
            }
        }

        async function saveCloudProvider() {
            const id = document.getElementById('cloud-provider-id').value;
            const name = document.getElementById('cloud-provider-name').value.trim();
            const url = document.getElementById('cloud-provider-url').value.trim();
            const key = document.getElementById('cloud-provider-key').value.trim();
            const isActive = document.getElementById('cloud-provider-active').checked;
            
            if (!name || !url || !key) {
                alert("Por favor completa todos los campos.");
                return;
            }
            
            const payload = {
                name: name,
                base_url: url,
                api_key: key,
                is_active: isActive
            };
            
            const method = id ? 'PUT' : 'POST';
            const urlEndpoint = id ? `/api/cloud-providers/${id}` : '/api/cloud-providers';
            
            try {
                const res = await fetch(urlEndpoint, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                
                const data = await res.json();
                if (data.error) {
                    alert(data.error);
                } else {
                    cancelCloudEdit();
                    await loadCloudProviders();
                    loadApiKeys();
                }
            } catch (err) {
                console.error("Error al guardar proveedor:", err);
                alert("Error al guardar proveedor.");
            }
        }

        async function deleteCloudProvider(id) {
            if (!confirm("¿Estás seguro de eliminar este proveedor? Esto removerá de inmediato el acceso a todos sus modelos.")) {
                return;
            }
            
            try {
                const res = await fetch(`/api/cloud-providers/${id}`, { method: 'DELETE' });
                const data = await res.json();
                if (data.error) {
                    alert(data.error);
                } else {
                    await loadCloudProviders();
                    loadApiKeys();
                }
            } catch (err) {
                console.error("Error al eliminar proveedor:", err);
            }
        }

        function editCloudProvider(id, name, url, key, isActive) {
            document.getElementById('cloud-provider-id').value = id;
            document.getElementById('cloud-provider-name').value = name;
            document.getElementById('cloud-provider-url').value = url;
            document.getElementById('cloud-provider-key').value = key;
            document.getElementById('cloud-provider-active').checked = isActive;
            
            document.getElementById('cloud-form-title').textContent = "Editar Proveedor en la Nube";
            document.getElementById('btn-save-cloud-text').textContent = "Guardar Cambios";
            document.getElementById('btn-cancel-cloud-edit').classList.remove('hidden');
        }

        function cancelCloudEdit() {
            document.getElementById('cloud-provider-id').value = "";
            document.getElementById('cloud-provider-name').value = "";
            document.getElementById('cloud-provider-url').value = "";
            document.getElementById('cloud-provider-key').value = "";
            document.getElementById('cloud-provider-active').checked = true;
            
            document.getElementById('cloud-form-title').textContent = "Registrar Proveedor en la Nube";
            document.getElementById('btn-save-cloud-text').textContent = "Añadir Proveedor";
            document.getElementById('btn-cancel-cloud-edit').classList.add('hidden');
        }

        let currentSecPage = 1;
        
        async function loadBlockedRequests(page = 1) {
            currentSecPage = page;
            const startDate = document.getElementById('sec-filter-start').value;
            const endDate = document.getElementById('sec-filter-end').value;
            const ip = document.getElementById('sec-filter-ip').value.trim();
            const service = document.getElementById('sec-filter-service').value;
            const endpoint = document.getElementById('sec-filter-endpoint').value.trim();
            const reason = document.getElementById('sec-filter-reason').value;
            
            // Construir query string
            let query = `page=${page}&limit=10`;
            if (startDate) query += `&start_date=${encodeURIComponent(startDate)}`;
            if (endDate) query += `&end_date=${encodeURIComponent(endDate)}`;
            if (ip) query += `&ip=${encodeURIComponent(ip)}`;
            if (service) query += `&service=${encodeURIComponent(service)}`;
            if (endpoint) query += `&endpoint=${encodeURIComponent(endpoint)}`;
            if (reason) query += `&reason=${encodeURIComponent(reason)}`;
            
            try {
                const res = await fetch(`/api/blocked-requests?${query}`);
                const data = await res.json();
                
                const container = document.getElementById('blocked-requests-list');
                const infoContainer = document.getElementById('blocked-pagination-info');
                const buttonsContainer = document.getElementById('blocked-pagination-buttons');
                
                if (!data.logs || data.logs.length === 0) {
                    container.innerHTML = `
                        <tr>
                            <td colspan="5" class="text-center py-6 text-slate-500 font-medium">
                                No se encontraron intentos bloqueados con los filtros seleccionados.
                            </td>
                        </tr>
                    `;
                    infoContainer.textContent = "Mostrando 0-0 de 0 registros";
                    buttonsContainer.innerHTML = "";
                    return;
                }
                
                // 1. Pintar Filas de la Tabla
                container.innerHTML = data.logs.map(l => {
                    let badgeReason = "";
                    if (l.reason === 'whitelist') {
                        badgeReason = '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-600/10 text-amber-400 border border-amber-500/20 font-mono">LISTA BLANCA</span>';
                    } else if (l.reason === 'api_key') {
                        badgeReason = '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-cyan-650/10 text-cyan-400 border border-cyan-500/20 font-mono">CLAVE API ERROR</span>';
                    } else {
                        badgeReason = '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-600/10 text-rose-400 border border-rose-500/20 font-mono">LISTA NEGRA</span>';
                    }
                        
                    const date = new Date(l.timestamp);
                    const localTime = date.toLocaleString();
                    
                    return `
                        <tr class="hover:bg-slate-900/40 transition-colors">
                            <td class="py-2.5 px-3 font-mono text-xs text-slate-405">${localTime}</td>
                            <td class="py-2.5 px-3 font-mono font-semibold text-rose-405">${escapeHtml(l.ip)}</td>
                            <td class="py-2.5 px-3 font-mono text-slate-205">${escapeHtml(l.service)}</td>
                            <td class="py-2.5 px-3 font-mono text-indigo-305 text-xs">${escapeHtml(l.endpoint)}</td>
                            <td class="py-2.5 px-3">${badgeReason}</td>
                        </tr>
                    `;
                }).join('');
                
                // 2. Pintar Info de Paginación
                const startIdx = (data.current_page - 1) * data.limit + 1;
                const endIdx = Math.min(data.current_page * data.limit, data.total_records);
                infoContainer.textContent = `Mostrando ${startIdx}-${endIdx} de ${data.total_records} registros`;
                
                // 3. Pintar Botones de Paginación
                let paginationHtml = "";
                
                // Botón Anterior
                const prevDisabled = data.current_page === 1 ? 'disabled' : '';
                paginationHtml += `
                    <button onclick="loadBlockedRequests(${data.current_page - 1})" ${prevDisabled} class="px-2.5 py-1 bg-slate-900 border border-slate-800 rounded-lg text-xs font-semibold text-slate-400 hover:bg-slate-800/80 hover:text-slate-200 transition-all disabled:opacity-30 disabled:pointer-events-none">
                        Anterior
                    </button>
                `;
                
                // Números de Páginas
                const startPage = Math.max(1, data.current_page - 2);
                const endPage = Math.min(data.total_pages, data.current_page + 2);
                
                if (startPage > 1) {
                    paginationHtml += `<button onclick="loadBlockedRequests(1)" class="px-2.5 py-1 bg-slate-900 border border-slate-800 rounded-lg text-xs font-semibold text-slate-400 hover:text-slate-200">1</button>`;
                    if (startPage > 2) paginationHtml += `<span class="text-slate-600 px-1 font-mono">...</span>`;
                }
                
                for (let i = startPage; i <= endPage; i++) {
                    const activeClass = i === data.current_page 
                        ? 'bg-indigo-650 text-white border-indigo-600' 
                        : 'bg-slate-900 text-slate-400 border-slate-800 hover:bg-slate-800/80 hover:text-slate-200';
                    paginationHtml += `
                        <button onclick="loadBlockedRequests(${i})" class="px-2.5 py-1 border rounded-lg text-xs font-semibold transition-all ${activeClass}">
                            ${i}
                        </button>
                    `;
                }
                
                if (endPage < data.total_pages) {
                    if (endPage < data.total_pages - 1) paginationHtml += `<span class="text-slate-600 px-1 font-mono">...</span>`;
                    paginationHtml += `<button onclick="loadBlockedRequests(${data.total_pages})" class="px-2.5 py-1 bg-slate-900 border border-slate-800 rounded-lg text-xs font-semibold text-slate-400 hover:text-slate-200">${data.total_pages}</button>`;
                }
                
                // Botón Siguiente
                const nextDisabled = data.current_page === data.total_pages ? 'disabled' : '';
                paginationHtml += `
                    <button onclick="loadBlockedRequests(${data.current_page + 1})" ${nextDisabled} class="px-2.5 py-1 bg-slate-900 border border-slate-800 rounded-lg text-xs font-semibold text-slate-400 hover:bg-slate-800/80 hover:text-slate-200 transition-all disabled:opacity-30 disabled:pointer-events-none">
                        Siguiente
                    </button>
                `;
                
                buttonsContainer.innerHTML = paginationHtml;
                
            } catch (err) {
                console.error("Error al cargar telemetría de bloqueos:", err);
            }
        }

        function exportBlockedRequests() {
            const startDate = document.getElementById('sec-filter-start').value;
            const endDate = document.getElementById('sec-filter-end').value;
            const ip = document.getElementById('sec-filter-ip').value.trim();
            const service = document.getElementById('sec-filter-service').value;
            const endpoint = document.getElementById('sec-filter-endpoint').value.trim();
            const reason = document.getElementById('sec-filter-reason').value;
            
            let query = "";
            if (startDate) query += `&start_date=${encodeURIComponent(startDate)}`;
            if (endDate) query += `&end_date=${encodeURIComponent(endDate)}`;
            if (ip) query += `&ip=${encodeURIComponent(ip)}`;
            if (service) query += `&service=${encodeURIComponent(service)}`;
            if (endpoint) query += `&endpoint=${encodeURIComponent(endpoint)}`;
            if (reason) query += `&reason=${encodeURIComponent(reason)}`;
            
            if (query.startsWith("&")) query = query.substring(1);
            
            window.location.href = `/api/blocked-requests/export?${query}`;
        }

        function clearBlockedFilters() {
            document.getElementById('sec-filter-start').value = "";
            document.getElementById('sec-filter-end').value = "";
            document.getElementById('sec-filter-ip').value = "";
            document.getElementById('sec-filter-service').value = "";
            document.getElementById('sec-filter-endpoint').value = "";
            document.getElementById('sec-filter-reason').value = "";
            loadBlockedRequests(1);
        }

        async function createIpRule() {
            const name = document.getElementById('ip-rule-name').value.trim();
            const network = document.getElementById('ip-rule-network').value.trim();
            const action = document.getElementById('ip-rule-action').value;
            const isActive = document.getElementById('ip-rule-active').checked;
            
            if (!name || !network) {
                alert("Completa todos los campos antes de guardar.");
                return;
            }
            
            try {
                const res = await fetch('/api/ip-rules', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: name,
                        network: network,
                        action: action,
                        is_active: isActive
                    })
                });
                
                const data = await res.json();
                if (res.ok) {
                    document.getElementById('ip-rule-name').value = '';
                    document.getElementById('ip-rule-network').value = '';
                    loadIpRules();
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (err) {
                alert(`Error al conectar con la API: ${err.message}`);
            }
        }

        function openEditIpModal(id, name, network, action, isActive) {
            document.getElementById('edit-ip-id').value = id;
            document.getElementById('edit-ip-name').value = name;
            document.getElementById('edit-ip-network').value = network;
            document.getElementById('edit-ip-action').value = action;
            document.getElementById('edit-ip-active').value = String(isActive);
            document.getElementById('edit-ip-modal').classList.remove('hidden');
        }

        function closeEditIpModal() {
            document.getElementById('edit-ip-modal').classList.add('hidden');
        }

        async function updateIpRule() {
            const id = document.getElementById('edit-ip-id').value;
            const name = document.getElementById('edit-ip-name').value.trim();
            const network = document.getElementById('edit-ip-network').value.trim();
            const action = document.getElementById('edit-ip-action').value;
            const isActive = document.getElementById('edit-ip-active').value === 'true';
            
            if (!name || !network) {
                alert("Completa todos los campos.");
                return;
            }
            
            try {
                const res = await fetch(`/api/ip-rules/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: name,
                        network: network,
                        action: action,
                        is_active: isActive
                    })
                });
                
                const data = await res.json();
                if (res.ok) {
                    closeEditIpModal();
                    loadIpRules();
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (err) {
                alert(`Error al actualizar la regla: ${err.message}`);
            }
        }

        async function deleteIpRule(id) {
            if (!confirm("¿Estás seguro de que quieres eliminar esta regla de IP?")) return;
            
            try {
                const res = await fetch(`/api/ip-rules/${id}`, {
                    method: 'DELETE'
                });
                if (res.ok) {
                    loadIpRules();
                } else {
                    const data = await res.json();
                    alert(`Error: ${data.error}`);
                }
            } catch (err) {
                alert(`Error al eliminar regla: ${err.message}`);
            }
        }

