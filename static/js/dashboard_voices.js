        // --- Gestión de Voces Clonadas (MongoDB & MediaRecorder) ---
        let mediaRecorder;
        let audioChunks = [];
        let recordedBlob = null;
        let recordingTimer;
        let recordDuration = 0;
        let selectedInputMode = 'record'; // 'record' o 'file'

        function toggleAudioInput(mode) {
            selectedInputMode = mode;
            const btnRecord = document.getElementById('btn-input-record');
            const btnFile = document.getElementById('btn-input-file');
            const boxRecord = document.getElementById('box-record');
            const boxFile = document.getElementById('box-file');

            if (mode === 'record') {
                btnRecord.className = "py-1.5 rounded-lg text-xs font-semibold bg-cyan-600/30 text-cyan-400 border border-cyan-500/30";
                btnFile.className = "py-1.5 rounded-lg text-xs font-semibold bg-slate-900 text-slate-400 border border-slate-800 hover:bg-slate-800";
                boxRecord.classList.remove('hidden');
                boxFile.classList.add('hidden');
            } else {
                btnFile.className = "py-1.5 rounded-lg text-xs font-semibold bg-cyan-600/30 text-cyan-400 border border-cyan-500/30";
                btnRecord.className = "py-1.5 rounded-lg text-xs font-semibold bg-slate-900 text-slate-400 border border-slate-800 hover:bg-slate-800";
                boxFile.classList.remove('hidden');
                boxRecord.classList.add('hidden');
            }
        }

        function handleVoiceFileChange() {
            const input = document.getElementById('voice-file-input');
            const label = document.getElementById('voice-file-label');
            if (input.files && input.files[0]) {
                label.innerText = `Seleccionado: ${input.files[0].name} (${(input.files[0].size/1024/1024).toFixed(2)} MB)`;
            } else {
                label.innerText = "Haz clic para subir WAV o MP3";
            }
        }

        async function startRecording() {
            audioChunks = [];
            recordedBlob = null;
            document.getElementById('record-preview-box').classList.add('hidden');

            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                
                mediaRecorder.ondataavailable = e => {
                    if (e.data.size > 0) {
                        audioChunks.push(e.data);
                    }
                };

                mediaRecorder.onstop = () => {
                    recordedBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    const audioUrl = URL.createObjectURL(recordedBlob);
                    const player = document.getElementById('record-audio-player');
                    player.src = audioUrl;
                    document.getElementById('record-preview-box').classList.remove('hidden');
                    
                    stream.getTracks().forEach(track => track.stop());
                };

                mediaRecorder.start();
                
                document.getElementById('record-indicator').classList.remove('bg-slate-500');
                document.getElementById('record-indicator').classList.add('bg-red-500', 'animate-pulse');
                document.getElementById('btn-start-record').disabled = true;
                document.getElementById('btn-start-record').classList.add('opacity-50', 'cursor-not-allowed');
                document.getElementById('btn-stop-record').disabled = false;
                document.getElementById('btn-stop-record').classList.remove('bg-slate-800', 'text-slate-500', 'cursor-not-allowed');
                document.getElementById('btn-stop-record').classList.add('bg-red-600', 'text-white', 'hover:bg-red-500');

                recordDuration = 0;
                document.getElementById('record-timer').innerText = "00:00";
                recordingTimer = setInterval(() => {
                    recordDuration++;
                    const mins = String(Math.floor(recordDuration / 60)).padStart(2, '0');
                    const secs = String(recordDuration % 60).padStart(2, '0');
                    document.getElementById('record-timer').innerText = `${mins}:${secs}`;
                }, 1000);

            } catch (err) {
                alert(`Error al acceder al micrófono: ${err.message}`);
            }
        }

        function stopRecording() {
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
            }
            
            clearInterval(recordingTimer);
            
            document.getElementById('record-indicator').classList.remove('bg-red-500', 'animate-pulse');
            document.getElementById('record-indicator').classList.add('bg-slate-500');
            document.getElementById('btn-start-record').disabled = false;
            document.getElementById('btn-start-record').classList.remove('opacity-50', 'cursor-not-allowed');
            document.getElementById('btn-stop-record').disabled = true;
            document.getElementById('btn-stop-record').className = "h-10 w-10 rounded-full bg-slate-800 text-slate-500 flex items-center justify-center transition-all cursor-not-allowed";
        }

        async function loadVoices() {
            const container = document.getElementById('voices-list-container');
            container.innerHTML = '<div class="text-center py-8 text-xs text-slate-500">Cargando perfiles...</div>';
            
            try {
                const res = await fetch('/api/voices');
                const voices = await res.json();
                
                if (voices.length === 0) {
                    container.innerHTML = `
                        <div class="border border-dashed border-slate-850 rounded-xl p-8 text-center flex flex-col items-center justify-center gap-2">
                            <span class="text-xs text-slate-400 font-semibold">No tienes ningún perfil de voz personalizado creado.</span>
                            <span class="text-[10px] text-slate-500">El sistema está utilizando el fallback local ('mi_voz_24k_mono.wav') de forma predeterminada.</span>
                        </div>
                    `;
                    return;
                }
                
                container.innerHTML = '';
                voices.forEach(voice => {
                    const activeClass = voice.is_active 
                        ? 'border-cyan-500/50 bg-cyan-950/10' 
                        : 'border-slate-800/80 bg-slate-900/20';
                    const activePill = voice.is_active
                        ? '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/20 text-cyan-400 uppercase">Activo</span>'
                        : '<button onclick="activateVoice(\''+voice.id+'\')" class="px-2.5 py-1 bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white rounded border border-slate-800 text-[10px] font-semibold transition-all">Activar</button>';
                        
                    // Escapar comillas simples para los argumentos onclick
                    const escName = voice.name.replace(/'/g, "\\'").replace(/"/g, '&quot;');
                    const escDesc = voice.description.replace(/'/g, "\\'").replace(/"/g, '&quot;');
                    const escText = voice.text.replace(/'/g, "\\'").replace(/"/g, '&quot;');

                    container.innerHTML += `
                        <div class="glass-panel p-4 rounded-xl border flex flex-col md:flex-row justify-between items-start md:items-center gap-4 transition-all ${activeClass}">
                            <div class="flex-1 flex flex-col gap-1 min-w-[200px]">
                                <div class="flex items-center gap-2">
                                    <span class="text-xs font-bold text-slate-200">${voice.name}</span>
                                    ${activePill}
                                </div>
                                <span class="text-[10px] text-slate-400 font-medium">${voice.description || 'Sin descripción'}</span>
                                <div class="mt-2 bg-slate-950/80 border border-slate-800/60 rounded p-2.5 max-h-16 overflow-y-auto">
                                    <p class="text-[10px] font-mono text-slate-300 select-all">${voice.text}</p>
                                </div>
                            </div>
                            <div class="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full md:w-auto">
                                <audio src="${voice.audio_url}" class="h-7 w-48" controls></audio>
                                <div class="flex gap-2 justify-end">
                                    <button onclick="openEditModal('${voice.id}', '${escName}', '${escDesc}', '${escText}')" class="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded text-[10px] font-semibold border border-slate-700 transition-all">Editar</button>
                                    <button onclick="deleteVoice('${voice.id}')" class="px-2 py-1 bg-red-950/50 hover:bg-red-900/50 text-red-400 hover:text-red-300 rounded text-[10px] font-semibold border border-red-900/30 transition-all">Borrar</button>
                                </div>
                            </div>
                        </div>
                    `;
                });
            } catch (err) {
                container.innerHTML = `<div class="text-center py-8 text-xs text-red-400">Error al cargar voces: ${err.message}</div>`;
            }
        }

        async function activateVoice(voiceId) {
            try {
                const res = await fetch(`/api/voices/${voiceId}/activate`, { method: 'POST' });
                const data = await res.json();
                if (res.ok) {
                    loadVoices();
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (err) {
                alert(`Error al activar: ${err.message}`);
            }
        }

        async function deleteVoice(voiceId) {
            if (!confirm("¿Estás seguro de que deseas eliminar este perfil de voz? Se borrará permanentemente de la base de datos y del disco.")) {
                return;
            }
            
            try {
                const res = await fetch(`/api/voices/${voiceId}`, { method: 'DELETE' });
                const data = await res.json();
                if (res.ok) {
                    loadVoices();
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (err) {
                alert(`Error al borrar: ${err.message}`);
            }
        }

        function openEditModal(id, name, desc, text) {
            document.getElementById('edit-voice-id').value = id;
            document.getElementById('edit-voice-name').value = name;
            document.getElementById('edit-voice-desc').value = desc;
            document.getElementById('edit-voice-text').value = text;
            document.getElementById('edit-voice-modal').classList.remove('hidden');
        }

        function closeEditModal() {
            document.getElementById('edit-voice-modal').classList.add('hidden');
        }

        async function updateVoiceProfile() {
            const id = document.getElementById('edit-voice-id').value;
            const name = document.getElementById('edit-voice-name').value.trim();
            const desc = document.getElementById('edit-voice-desc').value.trim();
            const text = document.getElementById('edit-voice-text').value.trim();

            if (!name || !text) {
                alert("El nombre y el texto de referencia son obligatorios.");
                return;
            }

            try {
                const res = await fetch(`/api/voices/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name, description: desc, text: text })
                });
                const data = await res.json();
                if (res.ok) {
                    closeEditModal();
                    loadVoices();
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (err) {
                alert(`Error al actualizar: ${err.message}`);
            }
        }

        async function saveVoiceProfile() {
            const name = document.getElementById('voice-name').value.trim();
            const desc = document.getElementById('voice-desc').value.trim();
            const text = document.getElementById('voice-text').value.trim();

            if (!name || !text) {
                alert("Por favor, introduce el nombre del perfil y el texto pronunciado.");
                return;
            }

            const formData = new FormData();
            formData.append("name", name);
            formData.append("description", desc);
            formData.append("text", text);

            if (selectedInputMode === 'record') {
                if (!recordedBlob) {
                    alert("Por favor, realiza una grabación primero.");
                    return;
                }
                formData.append("file", recordedBlob, "recording.wav");
            } else {
                const fileInput = document.getElementById('voice-file-input');
                if (!fileInput.files || !fileInput.files[0]) {
                    alert("Por favor, selecciona un archivo de audio para subir.");
                    return;
                }
                formData.append("file", fileInput.files[0]);
            }

            try {
                const res = await fetch('/api/voices', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                
                if (res.ok) {
                    document.getElementById('voice-name').value = '';
                    document.getElementById('voice-desc').value = '';
                    document.getElementById('voice-text').value = '';
                    recordedBlob = null;
                    document.getElementById('record-preview-box').classList.add('hidden');
                    document.getElementById('voice-file-input').value = '';
                    document.getElementById('voice-file-label').innerText = "Haz clic para subir WAV o MP3";
                    
                    loadVoices();
                } else {
                    alert(`Error al guardar: ${data.error}`);
                }
            } catch (err) {
                alert(`Error al conectar con el servidor: ${err.message}`);
            }
        }

