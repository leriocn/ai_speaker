# smart_speaker/audio_handler.py
import subprocess
import threading
import time
import collections
import audioop
import pyaudio

import config
from .services.wake_word_service import VoskWakeWordDetector
from .flask_utils import broadcast
from .smartspeaker import SpeakerState

class AudioHandler:
    def __init__(self, speaker):
        self.speaker = speaker
        # 创建两个不同的Vosk识别器实例
        self.wake_word_detector = VoskWakeWordDetector(keywords=[config.WAKE_WORD])
        self.stop_music_detector = VoskWakeWordDetector(keywords=config.MUSIC_STOP_WORDS)
        
        self.is_running = False
        self.pipeline_process = None
        self.thread = None
        self.p_audio = pyaudio.PyAudio()

    def _find_best_input_device_index(self):
        """在PyAudio中查找最佳输入设备"""
        print(f"[Audio] 正在自动查找输入设备 (关键词: {config.INPUT_DEVICE_KEYWORDS})...")
        for i in range(self.p_audio.get_device_count()):
            dev_info = self.p_audio.get_device_info_by_index(i)
            if dev_info.get('maxInputChannels') > 0:
                dev_name = dev_info.get('name', '').lower()
                if any(keyword.lower() in dev_name for keyword in config.INPUT_DEVICE_KEYWORDS):
                    print(f"[Audio] ✅ 找到输入设备: ID {i} - '{dev_info.get('name')}'")
                    return i
        print("[Audio] ⚠️ 警告: 未找到匹配的USB输入设备，将使用系统默认设备。")
        try:
            return self.p_audio.get_default_input_device_info().get('index')
        except IOError:
            print("[Audio-Error] 无法获取默认输入设备。")
            return None

    def _start_pipeline(self):
        """动态获取原生采样率，并启动 arecord | ffmpeg 管道。"""
        device_index = self._find_best_input_device_index()
        if device_index is None:
            print("[Audio-Error] 找不到任何可用的输入设备，无法启动管道。")
            return None
            
        try:
            dev_info = self.p_audio.get_device_info_by_index(device_index)
            native_rate = int(dev_info['defaultSampleRate'])
            print(f"[Audio] 检测到设备原生采样率: {native_rate}Hz")
        except Exception as e:
            native_rate = 48000
            print(f"❌ 获取设备原生采样率失败: {e}。将使用默认值: {native_rate}Hz")

        arecord_cmd = ["arecord", "-D", config.ARECORD_DEVICE, "-f", "S16_LE", "-r", str(native_rate), "-c", "1", "-t", "raw"]
        ffmpeg_cmd = ["ffmpeg", "-f", "s16le", "-ar", str(native_rate), "-ac", "1", "-i", "-", "-ar", str(config.TARGET_RATE), "-ac", "1", "-f", "s16le", "-"]
        
        print("[Audio] 准备启动实时重采样管道...")
        try:
            arecord_p = subprocess.Popen(arecord_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            ffmpeg_p = subprocess.Popen(ffmpeg_cmd, stdin=arecord_p.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.pipeline_process = (arecord_p, ffmpeg_p)
            print("[Audio] ✅ 统一音频捕获管道已启动。")
            return ffmpeg_p.stdout
        except Exception as e:
            print(f"❌ 启动音频管道失败: {e}"); return None

    def _is_pipeline_healthy(self):
        """检查音频管道中的进程是否都还存活"""
        if not self.pipeline_process: return False
        arecord_p, ffmpeg_p = self.pipeline_process
        if arecord_p.poll() is not None or ffmpeg_p.poll() is not None:
            print("[Audio-Health] 检测到音频管道进程已意外退出。")
            return False
        return True

    def start(self):
        self.is_running = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False
        if self.thread: self.thread.join(timeout=2)
        if self.pipeline_process:
            try:
                self.pipeline_process[0].kill(); self.pipeline_process[1].kill()
            except Exception as e:
                print(f"[Audio] 清理管道进程时出错: {e}")
        self.p_audio.terminate()
        print("[Audio] 音频处理器已停止。")

    def run(self):
        """主运行循环，根据speaker的状态分发音频流"""
        while self.is_running:
            if not self._is_pipeline_healthy():
                print("[Audio-Health] 音频管道不健康，正在尝试重启...")
                if self.pipeline_process:
                    try: self.pipeline_process[0].kill(); self.pipeline_process[1].kill()
                    except: pass
                
                audio_stream = self._start_pipeline()
                if not audio_stream:
                    print("[Audio-Error] 管道重启失败，将在5秒后重试。"); time.sleep(5); continue
            else:
                audio_stream = self.pipeline_process[1].stdout

            rolling_buffer = collections.deque(maxlen=int(config.PRE_BUFFER_DURATION_S * config.TARGET_RATE / config.CHUNK_SIZE))
            recorded_frames = []
            is_recording = False
            last_speech_time = 0
            
            print(f"\n[State-Loop] 进入新一轮监听循环，当前状态: {self.speaker.state.name}")
            while self.is_running and self._is_pipeline_healthy():
                # 播放TTS或音乐时，不处理麦克风输入，避免回声
                if self.speaker.is_speaking or self.speaker.music_player.is_active():
                    time.sleep(0.1); continue

                try:
                    chunk = audio_stream.read(config.CHUNK_SIZE)
                    if not chunk: print("[Audio-Warn] 从管道读取到空数据..."); break
                except (IOError, ValueError): break

                # --- 核心状态分发逻辑 ---
                current_state = self.speaker.state

                if current_state == SpeakerState.SLEEPING:
                    if self.wake_word_detector.process(chunk):
                        self.speaker.wake_up()
                
                elif current_state == SpeakerState.PLAYING_MUSIC:
                    if self.stop_music_detector.process(chunk):
                        self.speaker.handle_stop_music()
                
                elif current_state == SpeakerState.AWAKE:
                    is_speech = self.speaker._is_speech(chunk)
                    if not is_recording:
                        rolling_buffer.append(chunk)
                        if is_speech:
                            is_recording = True
                            recorded_frames.extend(list(rolling_buffer))
                            last_speech_time = time.time()
                            broadcast({"type": "status_update", "state": "listening", "message": ""})
                    else:
                        recorded_frames.append(chunk)
                        if is_speech: last_speech_time = time.time()
                        if time.time() - last_speech_time > config.SILENCE_DURATION_S:
                            print("[VAD] 检测到静音，录音结束，开始处理...")
                            self.speaker.process_command(list(recorded_frames))
                            is_recording = False; recorded_frames.clear(); rolling_buffer.clear()
        
        print("[Audio] 音频处理线程已停止。")