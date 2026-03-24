import pyaudiowpatch as pyaudio
import speech_recognition as sr
import requests
import io
import wave

# ──────────────────────────────────────────────
# CONFIGURAÇÕES — preencha com seus dados
PUSHOVER_USER_KEY  = "SEU_USER_KEY_AQUI"
PUSHOVER_API_TOKEN = "SEU_API_TOKEN_AQUI"
PALAVRA_ALVO       = "chamada"   # palavra que dispara a notificação
# ──────────────────────────────────────────────

#Configuração Rápida do Pushover :
# 1 - Crie conta em pushover.net
# 2 - Instale o app Pushover no seu celular
# 3 - Copie o User Key da dashboard
# 4 - Crie um novo "Application" e copie o API Token
# 5 - Cole os dois valores no topo do script

SAMPLE_RATE  = 16000
CHUNK        = 1024
RECORD_SECS  = 4        # segundos de áudio capturado por ciclo

def enviar_notificacao():
    """Envia push notification via Pushover."""
    payload = {
        "token":   PUSHOVER_API_TOKEN,
        "user":    PUSHOVER_USER_KEY,
        "title":   "🔔 Palavra Detectada",
        "message": f'A palavra "{PALAVRA_ALVO}" foi identificada no áudio!',
    }
    resp = requests.post("https://api.pushover.net/1/messages.json", data=payload)
    if resp.status_code == 200:
        print("[✔] Notificação enviada ao celular.")
    else:
        print(f"[✘] Falha ao enviar notificação: {resp.text}")


def audio_para_wav_bytes(frames: list, channels: int, sampwidth: int, rate: int) -> bytes:
    """Converte frames de áudio bruto para bytes no formato WAV."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(rate)
        wf.writeframes(b"".join(frames))
    buf.seek(0)
    return buf.read()


def obter_dispositivo_loopback(pa_instance):
    """Retorna o dispositivo de loopback (saída do PC) via PyAudioWPatch."""
    try:
        # Busca o dispositivo padrão de saída com suporte a loopback
        wasapi_info = pa_instance.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_out_idx = wasapi_info["defaultOutputDevice"]
        default_out = pa_instance.get_device_info_by_index(default_out_idx)

        # Encontra o dispositivo loopback correspondente
        for i in range(pa_instance.get_device_count()):
            dev = pa_instance.get_device_info_by_index(i)
            if dev.get("isLoopbackDevice") and default_out["name"] in dev["name"]:
                return dev
    except Exception as e:
        print(f"[!] Erro ao buscar loopback: {e}")
    return None


def main():
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True

    print(f"[*] Monitorando áudio de saída... (palavra-alvo: '{PALAVRA_ALVO}')")
    print("[*] Pressione Ctrl+C para encerrar.\n")

    pa = pyaudio.PyAudio()

    dispositivo = obter_dispositivo_loopback(pa)
    if not dispositivo:
        print("[✘] Nenhum dispositivo de loopback encontrado.")
        print("    Certifique-se de estar no Windows com PyAudioWPatch instalado.")
        pa.terminate()
        return

    channels   = min(2, dispositivo["maxInputChannels"])
    rate       = int(dispositivo["defaultSampleRate"])
    dev_index  = dispositivo["index"]

    print(f"[✔] Dispositivo loopback: {dispositivo['name']}")
    print(f"    Canais: {channels} | Taxa: {rate} Hz\n")

    stream = pa.open(
        format=pyaudio.paInt16,
        channels=channels,
        rate=rate,
        input=True,
        input_device_index=dev_index,
        frames_per_buffer=CHUNK,
    )

    notificacao_enviada = False  # evita spam de notificações

    try:
        while True:
            frames = [stream.read(CHUNK, exception_on_overflow=False)
                      for _ in range(int(rate / CHUNK * RECORD_SECS))]

            wav_bytes = audio_para_wav_bytes(frames, channels, 2, rate)

            audio_data = sr.AudioData(wav_bytes, rate, 2)

            try:
                texto = recognizer.recognize_google(audio_data, language="pt-BR")
                print(f"[>] Transcrito: {texto}")

                if PALAVRA_ALVO.lower() in texto.lower():
                    print(f"[!] Palavra '{PALAVRA_ALVO}' detectada!")
                    if not notificacao_enviada:
                        enviar_notificacao()
                        notificacao_enviada = True
                else:
                    notificacao_enviada = False  # reset para próxima detecção

            except sr.UnknownValueError:
                pass  # silêncio ou áudio incompreensível
            except sr.RequestError as e:
                print(f"[!] Erro na API de reconhecimento: {e}")

    except KeyboardInterrupt:
        print("\n[*] Encerrando monitoramento.")
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


if __name__ == "__main__":
    main()