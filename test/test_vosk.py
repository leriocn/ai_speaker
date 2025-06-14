# test_vosk.py
import subprocess
import json
import threading
import time
from queue import Queue
from vosk import Model, KaldiRecognizer

# --- 配置 ---
MODEL_PATH = "libs/vosk-model-small-cn-0.22"
TARGET_RATE = 16000
ARECORD_DEVICE = "plughw:1,0"
NATIVE_RATE = 48000
CHUNK_SIZE = 3200

class VoskPipelineTester:
    def __init__(self):
        self.audio_queue = Queue()
        self.result_queue = Queue()
        self.is_running = threading.Event()
        self.vosk_model = None

    def _init_vosk(self):
        try:
            print("[Vosk] 正在加载模型...")
            self.vosk_model = Model(MODEL_PATH)
            print("[Vosk] ✅ 模型加载成功。")
            return True
        except Exception as e:
            print(f"❌ Vosk模型加载失败: {e}"); return False

    def _audio_capture_thread(self):
        """线程1：生产者 - 从管道捕获音频并放入audio_queue"""
        arecord_cmd = ["arecord", "-D", ARECORD_DEVICE, "-f", "S16_LE", "-r", str(NATIVE_RATE), "-c", "1", "-t", "raw"]
        ffmpeg_cmd = ["ffmpeg", "-f", "s16le", "-ar", str(NATIVE_RATE), "-ac", "1", "-i", "-", "-ar", str(TARGET_RATE), "-ac", "1", "-f", "s16le", "-"]
        
        arecord_p = subprocess.Popen(arecord_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ffmpeg_p = subprocess.Popen(ffmpeg_cmd, stdin=arecord_p.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 启动日志线程
        threading.Thread(target=self._log_stderr, args=(arecord_p, "arecord"), daemon=True).start()
        threading.Thread(target=self._log_stderr, args=(ffmpeg_p, "ffmpeg"), daemon=True).start()

        print("[Audio] ✅ 音频捕获管道已启动。")
        while self.is_running.is_set():
            audio_chunk = ffmpeg_p.stdout.read(CHUNK_SIZE)
            if not audio_chunk:
                break
            self.audio_queue.put(audio_chunk)
        
        print("[Audio] 音频捕获线程正在停止...")
        arecord_p.terminate(); ffmpeg_p.terminate()

    def _vosk_recognize_thread(self):
        """线程2：消费者/生产者 - 从audio_queue获取音频，识别后将结果放入result_queue"""
        if not self.vosk_model: return
        
        rec = KaldiRecognizer(self.vosk_model, TARGET_RATE)
        rec.SetWords(True)
        print("[Vosk] ✅ 识别线程已启动。")

        while self.is_running.is_set():
            try:
                # 设置超时，避免在停止时无限期阻塞
                audio_chunk = self.audio_queue.get(timeout=1)
                if rec.AcceptWaveform(audio_chunk):
                    result = json.loads(rec.Result())
                    text = result.get('text', '').replace(" ", "")
                    if text:
                        self.result_queue.put(f"[Result] {text}")
                else:
                    partial_result = json.loads(rec.PartialResult())
                    if partial_result.get('partial'):
                         self.result_queue.put(f"[Partial]... {partial_result['partial']}")
            except: # 捕获队列超时等异常，在停止时是正常的
                if not self.is_running.is_set():
                    break
        
        # 处理最后的结果
        result = json.loads(rec.FinalResult())
        text = result.get('text', '').replace(" ", "")
        if text:
            self.result_queue.put(f"[Final] {text}")
        
        self.result_queue.put(None) # 发送结束信号
        print("[Vosk] 识别线程已停止。")

    def _log_stderr(self, process, name):
        """后台线程，用于读取子进程的错误输出"""
        for line in iter(process.stderr.readline, b''):
            print(f"[{name}-stderr] {line.decode(errors='ignore').strip()}")

    def run_test(self):
        if not self._init_vosk(): return
        
        self.is_running.set()
        
        # 启动两个核心后台线程
        capture_thread = threading.Thread(target=self._audio_capture_thread, daemon=True)
        recognize_thread = threading.Thread(target=self._vosk_recognize_thread, daemon=True)
        
        capture_thread.start()
        recognize_thread.start()

        print("\n>>> 系统已启动，请开始说话 (按 Ctrl+C 停止)...")
        
        try:
            while True:
                # 主线程只做一件事：从result_queue获取并打印结果
                result = self.result_queue.get()
                if result is None: # 收到结束信号
                    break
                
                if "[Partial]" in result:
                    print(f"\r{result}", end="")
                else:
                    print(f"\n{result}\n")
        except KeyboardInterrupt:
            print("\n用户中断测试...")
        
        finally:
            self.stop()
            # 等待线程结束
            capture_thread.join(timeout=2)
            recognize_thread.join(timeout=2)
            print("-" * 30)
            print("测试结束。")

    def stop(self):
        print("\n[Info] 正在停止所有线程...")
        self.is_running.clear() # 清除运行标志，所有线程的循环都会退出

if __name__ == '__main__':
    tester = VoskPipelineTester()
    tester.run_test()