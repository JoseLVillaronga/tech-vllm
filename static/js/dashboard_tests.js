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

