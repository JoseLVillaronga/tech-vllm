import torchaudio

def resample_audio_to_24k_mono(input_path: str, output_path: str) -> bool:
    """Helper para re-muestrear audio a 24kHz mono (formato esperado por F5-TTS)."""
    try:
        waveform, sample_rate = torchaudio.load(input_path)
        # Convertir a mono si es estéreo
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        # Re-muestrear a 24000 Hz si es diferente
        if sample_rate != 24000:
            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=24000)
            waveform = resampler(waveform)
        torchaudio.save(output_path, waveform, 24000)
        return True
    except Exception as e:
        print(f"Error re-muestreando audio {input_path} -> {output_path}: {e}")
        return False
