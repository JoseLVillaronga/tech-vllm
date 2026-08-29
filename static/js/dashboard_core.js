        // Funciones auxiliares para prevenir XSS e inyección de JS
        function escapeHtml(str) {
            if (!str) return '';
            return String(str)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        function escapeJs(str) {
            if (!str) return '';
            return String(str)
                .replace(/\\/g, "\\\\")
                .replace(/'/g, "\\'")
                .replace(/"/g, '\\"')
                .replace(/\n/g, "\\n")
                .replace(/\r/g, "\\r");
        }

        function handleLoraChange(loraValue) {
            const modelInput = document.getElementById('model-input');
            if (modelInput && modelInput.value === 'google/gemma-4-E4B-it') {
                const gpuInput = document.querySelector('input[name="GPU_MEMORY_UTILIZATION"]');
                if (gpuInput) {
                    gpuInput.value = loraValue === 'False' ? '0.51' : '0.55';
                }
            }
        }

        function selectQuickModel(modelName, gpuMem = '', maxLen = '', quantization = '', loraVal = null, swapSpace = null) {
            const input = document.getElementById('model-input');
            if (input) {
                input.value = modelName;
            }
            const loraSelect = document.querySelector('select[name="LORA"]');
            if (loraSelect && loraVal !== null && loraVal !== undefined) {
                loraSelect.value = loraVal;
            }
            let targetGpuMem = gpuMem;
            if (modelName === 'google/gemma-4-E4B-it') {
                if (loraSelect) {
                    if (loraSelect.value === 'False') {
                        targetGpuMem = '0.51';
                    } else {
                        targetGpuMem = '0.55';
                    }
                }
            }
            const gpuInput = document.querySelector('input[name="GPU_MEMORY_UTILIZATION"]');
            if (gpuInput && targetGpuMem !== undefined && targetGpuMem !== null) {
                gpuInput.value = targetGpuMem;
            }
            const lenInput = document.querySelector('input[name="MAX_MODEL_LEN"]');
            if (lenInput && maxLen !== undefined && maxLen !== null) {
                lenInput.value = maxLen;
            }
            const quantInput = document.querySelector('input[name="QUANTIZATION"]');
            if (quantInput && quantization !== undefined && quantization !== null) {
                quantInput.value = quantization;
            }
            const swapInput = document.querySelector('input[name="SWAP_SPACE"]');
            if (swapInput && swapSpace !== null && swapSpace !== undefined) {
                swapInput.value = swapSpace;
            }
        }

        window.currentActiveTab = 'tab-monitor';

        // Cambiar pestañas
        function showTab(tabId) {
            window.currentActiveTab = tabId;
            document.querySelectorAll('.tab-content').forEach(content => content.classList.add('hidden'));
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('active', 'bg-slate-800/80', 'text-cyan-400', 'border-cyan-500/30');
                btn.classList.add('text-slate-300', 'border-transparent');
            });
            
            const activeBtn = document.querySelector(`[onclick="showTab('${tabId}')"]`);
            if (activeBtn) {
                activeBtn.classList.add('bg-slate-800/80', 'text-cyan-400', 'border-cyan-500/30');
                activeBtn.classList.remove('text-slate-300', 'border-transparent');
            }
            
            document.getElementById(tabId).classList.remove('hidden');
            
            if (tabId === 'tab-voices') {
                loadVoices();
            }
            if (tabId === 'tab-keys') {
                loadApiKeys();
                loadIpRules();
                loadCloudProviders();
                loadBlockedRequests();
            }
            if (tabId === 'tab-monitor') {
                loadTelemetryHistory();
            }
            if (tabId === 'tab-metrics') {
                loadMetrics();
            }
            if (tabId === 'tab-rag') {
                loadRagStats();
            }
        }

        // Obtener estado y métricas
        async function refreshData() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                
                // Actualizar métricas del sistema
                document.getElementById('metric-cpu').innerText = `${data.system.cpu}%`;
                const cpuTempEl = document.getElementById('metric-cpu-temp');
                if (cpuTempEl && data.system.cpu_temp !== undefined && data.system.cpu_temp !== null) {
                    cpuTempEl.innerText = `${data.system.cpu_temp}°C`;
                }
                document.getElementById('progress-cpu').style.width = `${data.system.cpu}%`;
                
                document.getElementById('metric-ram').innerText = `${data.system.ram}%`;
                document.getElementById('progress-ram').style.width = `${data.system.ram}%`;
                
                document.getElementById('metric-gpu-load').innerText = `${data.system.gpu_util}%`;
                document.getElementById('metric-gpu-temp').innerText = `${data.system.gpu_temp}°C`;
                document.getElementById('progress-gpu-load').style.width = `${data.system.gpu_util}%`;
                
                const totalGb = (data.system.vram_total / 1024).toFixed(1);
                const usedGb = (data.system.vram_used / 1024).toFixed(1);
                document.getElementById('metric-vram-text').innerText = `${usedGb} / ${totalGb} GB`;
                document.getElementById('metric-vram-pct').innerText = `${data.system.vram_percent}%`;
                document.getElementById('progress-vram').style.width = `${data.system.vram_percent}%`;
                
                // Actualizar estado de servicios
                updateServiceBadge('status-gemma', data.services?.gemma?.status || 'inactive');
                updateServiceBadge('status-whisper', data.services?.whisper?.status || 'inactive');
                updateServiceBadge('status-fallback_stt', data.services?.fallback_stt?.status || 'inactive');
                updateServiceBadge('status-tts', data.services?.tts?.status || 'inactive');
                updateServiceBadge('status-fallback_tts', data.services?.fallback_tts?.status || 'inactive');
                updateServiceBadge('status-diarization', data.services?.diarization?.status || 'inactive');
                updateServiceBadge('status-embeddings', data.services?.embeddings?.status || 'inactive');
                updateServiceBadge('status-image', data.services?.image?.status || 'inactive');
                updateServiceBadge('status-rag_sync', data.services?.rag_sync?.status || 'inactive');
                updateServiceBadge('status-docling', data.services?.docling?.status || 'inactive');
                updateServiceBadge('status-gateway', data.services?.gateway?.status || 'inactive');
                
                // Hora de actualización
                const now = new Date();
                document.getElementById('last-update').innerText = `Act: ${now.toLocaleTimeString()}`;
            } catch (err) {
                console.error("Error al actualizar estado:", err);
            }
        }

        function updateServiceBadge(elementId, status) {
            const badge = document.getElementById(elementId);
            if (!badge) return;
            badge.innerText = status;
            badge.className = "px-2 py-0.5 rounded text-xs font-mono font-bold uppercase ";
            if (status === 'active') {
                badge.className += "bg-emerald-500/20 text-emerald-400";
            } else if (status === 'failed') {
                badge.className += "bg-rose-500/20 text-rose-400";
            } else {
                badge.className += "bg-slate-800 text-slate-400";
            }
        }

        // Controlar servicios
        async function controlService(serviceKey, action) {
            const badge = document.getElementById(`status-${serviceKey}`);
            badge.innerText = "...";
            try {
                const res = await fetch(`/api/service/${serviceKey}/${action}`, { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    refreshData();
                } else {
                    alert(`Error al ejecutar acción: ${data.error || 'Desconocido'}`);
                    refreshData();
                }
            } catch (err) {
                alert(`Error de red: ${err.message}`);
                refreshData();
            }
        }

        // Cargar variables de entorno en el formulario
        async function loadConfig() {
            try {
                const res = await fetch('/api/config');
                const config = await res.json();
                const form = document.getElementById('config-form');
                
                for (const key in config) {
                    const input = form.elements[key];
                    if (input) {
                        input.value = config[key];
                    }
                }
            } catch (err) {
                console.error("Error al cargar config:", err);
            }
        }

        // Guardar configuración
        async function saveConfig() {
            const form = document.getElementById('config-form');
            const data = {};
            // Recoger los valores del formulario
            for (let i = 0; i < form.elements.length; i++) {
                const input = form.elements[i];
                if (input.name) {
                    data[input.name] = input.value;
                }
            }
            
            try {
                const res = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                const resData = await res.json();
                if (resData.success) {
                    alert("¡Configuración .env guardada correctamente!");
                    loadConfig();
                } else {
                    alert(`Error al guardar: ${resData.error}`);
                }
            } catch (err) {
                alert(`Error de red: ${err.message}`);
            }
        }

        function selectQuickEmbeddingsMode(device, threads, batchSize) {
            const form = document.getElementById('config-form');
            if (form) {
                if (form.elements['EMBEDDINGS_DEVICE']) form.elements['EMBEDDINGS_DEVICE'].value = device;
                if (form.elements['EMBEDDINGS_CPU_THREADS']) form.elements['EMBEDDINGS_CPU_THREADS'].value = threads;
                if (form.elements['EMBEDDINGS_BATCH_SIZE']) form.elements['EMBEDDINGS_BATCH_SIZE'].value = batchSize;
            }
            const sel = document.getElementById('embeddings-device-select');
            const thr = document.getElementById('embeddings-cpu-threads-input');
            const bat = document.getElementById('embeddings-batch-size-input');
            if (sel) sel.value = device;
            if (thr) thr.value = threads;
            if (bat) bat.value = batchSize;
        }

        function handleEmbeddingsDeviceChange(device) {
            const isCuda = (device === 'cuda');
            const threads = isCuda ? 6 : 8;
            const batchSize = isCuda ? 64 : 16;
            selectQuickEmbeddingsMode(device, threads, batchSize);
        }

        async function restartEmbeddingsService() {
            const btn = document.getElementById('btn-restart-embeddings');
            const originalHtml = btn ? btn.innerHTML : '';
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span>⏳</span> Reiniciando...';
            }
            try {
                const res = await fetch('/api/service/embeddings/restart', { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    if (btn) btn.innerHTML = '<span>✅</span> ¡Reiniciado!';
                    setTimeout(() => {
                        if (btn) {
                            btn.disabled = false;
                            btn.innerHTML = originalHtml;
                        }
                    }, 2000);
                } else {
                    alert("Error al reiniciar embeddings: " + (data.error || "Desconocido"));
                    if (btn) {
                        btn.disabled = false;
                        btn.innerHTML = originalHtml;
                    }
                }
            } catch (err) {
                alert("Error de conexión: " + err.message);
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;
                }
            }
        }

