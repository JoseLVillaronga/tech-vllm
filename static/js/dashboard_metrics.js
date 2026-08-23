        // --- Historial de Telemetría (Chart.js) ---
        let chartProcessing = null;
        let chartMemory = null;
        let activeHours = 6;

        function initCharts() {
            const ctxProc = document.getElementById('chart-processing').getContext('2d');
            const ctxMem = document.getElementById('chart-memory').getContext('2d');
            
            const gradCpu = ctxProc.createLinearGradient(0, 0, 0, 200);
            gradCpu.addColorStop(0, 'rgba(99, 102, 241, 0.25)');
            gradCpu.addColorStop(1, 'rgba(99, 102, 241, 0.0)');
            
            const gradGpu = ctxProc.createLinearGradient(0, 0, 0, 200);
            gradGpu.addColorStop(0, 'rgba(16, 185, 129, 0.25)');
            gradGpu.addColorStop(1, 'rgba(16, 185, 129, 0.0)');
            
            const gradRam = ctxMem.createLinearGradient(0, 0, 0, 200);
            gradRam.addColorStop(0, 'rgba(6, 182, 212, 0.25)');
            gradRam.addColorStop(1, 'rgba(6, 182, 212, 0.0)');
            
            const gradVram = ctxMem.createLinearGradient(0, 0, 0, 200);
            gradVram.addColorStop(0, 'rgba(129, 140, 248, 0.25)');
            gradVram.addColorStop(1, 'rgba(129, 140, 248, 0.0)');

            const commonOptions = {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            color: '#94a3b8',
                            boxWidth: 12,
                            boxHeight: 12,
                            font: { size: 10, family: 'monospace' }
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: '#0f172a',
                        titleColor: '#f1f5f9',
                        bodyColor: '#cbd5e1',
                        borderColor: '#334155',
                        borderWidth: 1,
                        titleFont: { size: 10, family: 'monospace' },
                        bodyFont: { size: 10, family: 'monospace' }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(51, 65, 85, 0.08)' },
                        ticks: {
                            color: '#64748b',
                            font: { size: 9, family: 'monospace' },
                            maxTicksLimit: 10
                        }
                    },
                    y: {
                        min: 0,
                        max: 100,
                        grid: { color: 'rgba(51, 65, 85, 0.12)' },
                        ticks: {
                            color: '#64748b',
                            font: { size: 9, family: 'monospace' },
                            callback: value => value + '%'
                        }
                    }
                }
            };

            chartProcessing = new Chart(ctxProc, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'CPU (%)',
                            data: [],
                            borderColor: '#6366f1',
                            backgroundColor: gradCpu,
                            fill: true,
                            tension: 0.35,
                            borderWidth: 2,
                            pointRadius: 0,
                            pointHoverRadius: 4
                        },
                        {
                            label: 'GPU (%)',
                            data: [],
                            borderColor: '#10b981',
                            backgroundColor: gradGpu,
                            fill: true,
                            tension: 0.35,
                            borderWidth: 2,
                            pointRadius: 0,
                            pointHoverRadius: 4
                        }
                    ]
                },
                options: commonOptions
            });

            chartMemory = new Chart(ctxMem, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'RAM (%)',
                            data: [],
                            borderColor: '#06b6d4',
                            backgroundColor: gradRam,
                            fill: true,
                            tension: 0.35,
                            borderWidth: 2,
                            pointRadius: 0,
                            pointHoverRadius: 4
                        },
                        {
                            label: 'VRAM (%)',
                            data: [],
                            borderColor: '#818cf8',
                            backgroundColor: gradVram,
                            fill: true,
                            tension: 0.35,
                            borderWidth: 2,
                            pointRadius: 0,
                            pointHoverRadius: 4
                        }
                    ]
                },
                options: commonOptions
            });
        }

        async function loadTelemetryHistory() {
            if (!chartProcessing || !chartMemory) return;
            
            try {
                const res = await fetch(`/api/telemetry/history?hours=${activeHours}`);
                const data = await res.json();
                
                if (data.error) {
                    console.error("Error al obtener historial de telemetría:", data.error);
                    return;
                }
                
                const labels = [];
                const cpuData = [];
                const gpuData = [];
                const ramData = [];
                const vramPctData = [];
                
                data.forEach(r => {
                    const date = new Date(r.timestamp);
                    const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                    labels.push(timeStr);
                    
                    cpuData.push(r.cpu);
                    gpuData.push(r.gpu_util);
                    ramData.push(r.ram);
                    
                    const vramPct = r.vram_total > 0 ? (r.vram_used / r.vram_total) * 100 : 0;
                    vramPctData.push(Math.round(vramPct));
                });
                
                chartProcessing.data.labels = labels;
                chartProcessing.data.datasets[0].data = cpuData;
                chartProcessing.data.datasets[1].data = gpuData;
                chartProcessing.update('none');
                
                chartMemory.data.labels = labels;
                chartMemory.data.datasets[0].data = ramData;
                chartMemory.data.datasets[1].data = vramPctData;
                chartMemory.update('none');
            } catch (err) {
                console.error("Error al refrescar gráficos de telemetría:", err);
            }
        }

        function changeTimescale(hours) {
            activeHours = parseInt(hours);
            loadTelemetryHistory();
        }



        // --- Reportes Gráficos y Telemetría de Uso (Chart.js) ---
        let chartHistory = null;
        let chartShare = null;
        let currentShareType = 'models';
        let cachedSharesData = null;

        async function loadMetrics() {
            const days = document.getElementById('metrics-days').value;
            const service = document.getElementById('metrics-service').value;
            const apikey = document.getElementById('metrics-apikey').value;
            const model = document.getElementById('metrics-model').value;
            
            try {
                const url = `/api/metrics?days=${days}&service=${encodeURIComponent(service)}&api_key=${encodeURIComponent(apikey)}&model=${encodeURIComponent(model)}`;
                const res = await fetch(url);
                if (!res.ok) throw new Error("Error en respuesta de API");
                const data = await res.json();
                
                // 1. Rellenar KPIs
                document.getElementById('kpi-calls').textContent = data.summary.total_calls.toLocaleString();
                document.getElementById('kpi-tokens').textContent = (data.summary.total_prompt_tokens + data.summary.total_completion_tokens).toLocaleString();
                
                // Convertir segundos de audio a minutos:segundos legibles
                const audioMin = Math.floor(data.summary.total_audio_sec / 60);
                const audioSec = Math.floor(data.summary.total_audio_sec % 60);
                document.getElementById('kpi-audio').textContent = `${audioMin}m ${audioSec}s`;
                
                // Duración promedio de cómputo en segundos
                const totalCalls = data.summary.total_calls;
                const totalDuration = data.summary.total_prompt_tokens > 0 
                    ? data.summary.total_calls * 1.5 // Estimación razonable
                    : data.summary.total_audio_sec;
                document.getElementById('kpi-duration').textContent = totalCalls > 0 
                    ? `${(totalDuration / totalCalls).toFixed(2)}s prom`
                    : '0.00s';
                
                // 2. Poblar filtros dinámicos (solo la primera vez para no interrumpir la selección del usuario)
                const apikeySelect = document.getElementById('metrics-apikey');
                if (apikeySelect.options.length <= 1 && data.filters_data.api_keys) {
                    data.filters_data.api_keys.forEach(k => {
                        const opt = document.createElement('option');
                        opt.value = k;
                        opt.textContent = k;
                        apikeySelect.appendChild(opt);
                    });
                }
                
                const modelSelect = document.getElementById('metrics-model');
                if (modelSelect.options.length <= 1 && data.filters_data.models) {
                    data.filters_data.models.forEach(m => {
                        const opt = document.createElement('option');
                        opt.value = m;
                        opt.textContent = m;
                        modelSelect.appendChild(opt);
                    });
                }
                
                // 3. Renderizar Gráfico Histórico Lineal
                renderHistoryChart(data.time_series);
                
                // 4. Renderizar Gráfico de Reparto
                cachedSharesData = data.shares;
                renderShareChart();
                
            } catch (err) {
                console.error("Error cargando métricas:", err);
            }
        }

        function exportMetrics() {
            const days = document.getElementById('metrics-days').value;
            const service = document.getElementById('metrics-service').value;
            const apikey = document.getElementById('metrics-apikey').value;
            const model = document.getElementById('metrics-model').value;
            
            const url = `/api/metrics/export?days=${days}&service=${encodeURIComponent(service)}&api_key=${encodeURIComponent(apikey)}&model=${encodeURIComponent(model)}`;
            window.location.href = url;
        }

        function renderHistoryChart(timeSeries) {
            const ctx = document.getElementById('chart-history').getContext('2d');
            
            const labels = timeSeries.map(x => {
                const parts = x.date.split('-');
                if (parts.length === 3) {
                    const months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
                    return `${parseInt(parts[2])} ${months[parseInt(parts[1]) - 1]}`;
                }
                return x.date;
            });
            
            const promptTokens = timeSeries.map(x => x.prompt_tokens);
            const completionTokens = timeSeries.map(x => x.completion_tokens);
            const audioSec = timeSeries.map(x => x.audio_duration_sec);
            
            if (chartHistory) {
                chartHistory.destroy();
            }
            
            const gradPrompt = ctx.createLinearGradient(0, 0, 0, 200);
            gradPrompt.addColorStop(0, 'rgba(99, 102, 241, 0.25)');
            gradPrompt.addColorStop(1, 'rgba(99, 102, 241, 0.0)');
            
            const gradComp = ctx.createLinearGradient(0, 0, 0, 200);
            gradComp.addColorStop(0, 'rgba(168, 85, 247, 0.25)');
            gradComp.addColorStop(1, 'rgba(168, 85, 247, 0.0)');

            chartHistory = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Tokens de Entrada',
                            data: promptTokens,
                            borderColor: '#6366f1',
                            backgroundColor: gradPrompt,
                            fill: true,
                            tension: 0.3,
                            yAxisID: 'y'
                        },
                        {
                            label: 'Tokens de Salida',
                            data: completionTokens,
                            borderColor: '#a855f7',
                            backgroundColor: gradComp,
                            fill: true,
                            tension: 0.3,
                            yAxisID: 'y'
                        },
                        {
                            label: 'Audio Procesado (Seg)',
                            data: audioSec,
                            borderColor: '#10b981',
                            backgroundColor: 'transparent',
                            fill: false,
                            tension: 0.3,
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            labels: { color: '#94a3b8', font: { size: 10, family: 'monospace' } }
                        },
                        tooltip: {
                            backgroundColor: '#0f172a',
                            borderColor: '#334155',
                            borderWidth: 1,
                            titleColor: '#f1f5f9',
                            bodyColor: '#cbd5e1',
                            titleFont: { size: 10, family: 'monospace' },
                            bodyFont: { size: 10, family: 'monospace' }
                        }
                    },
                    scales: {
                        x: {
                            grid: { color: 'rgba(51, 65, 85, 0.15)' },
                            ticks: { color: '#94a3b8', font: { size: 9, family: 'monospace' } }
                        },
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            grid: { color: 'rgba(51, 65, 85, 0.15)' },
                            ticks: { color: '#6366f1', font: { size: 9, family: 'monospace' } },
                            title: { display: true, text: 'Tokens LLM', color: '#6366f1', font: { size: 10, family: 'monospace' } }
                        },
                        y1: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            grid: { drawOnChartArea: false },
                            ticks: { color: '#10b981', font: { size: 9, family: 'monospace' } },
                            title: { display: true, text: 'Segundos Audio', color: '#10b981', font: { size: 10, family: 'monospace' } }
                        }
                    }
                }
            });
        }

        function toggleShareChart(type) {
            currentShareType = type;
            document.getElementById('btn-share-models').className = type === 'models' 
                ? 'px-3 py-1 rounded font-medium transition-all bg-indigo-600 text-white font-semibold'
                : 'px-3 py-1 rounded font-medium transition-all text-slate-400 hover:text-slate-200';
            document.getElementById('btn-share-keys').className = type === 'keys' 
                ? 'px-3 py-1 rounded font-medium transition-all bg-indigo-600 text-white font-semibold'
                : 'px-3 py-1 rounded font-medium transition-all text-slate-400 hover:text-slate-200';
            renderShareChart();
        }

        function renderShareChart() {
            if (!cachedSharesData) return;
            const ctx = document.getElementById('chart-share').getContext('2d');
            
            const rawData = currentShareType === 'models' ? cachedSharesData.model : cachedSharesData.api_key;
            
            const labels = Object.keys(rawData);
            const values = Object.values(rawData);
            
            if (chartShare) {
                chartShare.destroy();
            }
            
            if (labels.length === 0) {
                // Sin datos en el filtro
                ctx.clearRect(0, 0, 200, 200);
                chartShare = null;
                return;
            }
            
            const colors = [
                '#6366f1', '#a855f7', '#10b981', '#06b6d4', 
                '#f59e0b', '#ec4899', '#3b82f6', '#84cc16'
            ];

            chartShare = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: colors.slice(0, labels.length),
                        borderWidth: 1,
                        borderColor: '#0f172a'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                color: '#94a3b8',
                                boxWidth: 10,
                                boxHeight: 10,
                                font: { size: 9, family: 'monospace' }
                            }
                        },
                        tooltip: {
                            backgroundColor: '#0f172a',
                            borderColor: '#334155',
                            borderWidth: 1,
                            titleColor: '#f1f5f9',
                            bodyColor: '#cbd5e1',
                            titleFont: { size: 10, family: 'monospace' },
                            bodyFont: { size: 10, family: 'monospace' }
                        }
                    },
                    cutout: '65%'
                }
            });
        }

        function shouldLazyRefreshKeys() {
            // 1. Debe estar activa la pestaña de Seguridad
            if (window.currentActiveTab !== 'tab-keys') return false;
            // 2. La pestaña del navegador debe estar visible / enfocada
            if (document.hidden) return false;
            // 3. No debe haber ningún modal de edición abierto
            const editModal = document.getElementById('edit-key-modal');
            if (editModal && !editModal.classList.contains('hidden')) return false;
            // 4. El contenedor de claves debe existir y estar en el viewport visible
            const container = document.getElementById('keys-list-container');
            if (!container) return false;
            const rect = container.getBoundingClientRect();
            return (
                rect.top < (window.innerHeight || document.documentElement.clientHeight) &&
                rect.bottom > 0
            );
        }

        // Loop de actualización
        initCharts();
        refreshData();
        loadConfig();
        loadTelemetryHistory();
        setInterval(refreshData, 5000); // Actualizar estado de servicios y métricas cada 5s
        setInterval(loadTelemetryHistory, 60000); // Actualizar gráficos cada 60s
        setInterval(() => {
            if (shouldLazyRefreshKeys()) {
                loadApiKeys(true); // Actualización lazy y silenciosa in-place sin parpadeo
            }
        }, 4000); // Polling suave de claves API cada 4s si están visibles
