# services/tts_service.py
import json, uuid, struct, threading, websocket
from queue import Queue, Empty
from config import TTS_APPID, TTS_TOKEN, TTS_CLUSTER, TTS_VOICE_TYPE, TTS_WS_URL

class TTSService:
    # ... (__init__, _construct_request_data 不变) ...
    def __init__(self):
        self.ws = None; self.ws_thread = None; self.audio_queue = Queue(); self.is_finished = threading.Event()

    def _construct_request_data(self, text):
        req_id = str(uuid.uuid4())
        payload_dict = {
            "app": {"appid": TTS_APPID, "token": TTS_TOKEN, "cluster": TTS_CLUSTER},
            "user": {"uid": "s805_smart_speaker_user"},
            "audio": {"voice_type": TTS_VOICE_TYPE, "encoding": "mp3", "rate": 16000},
            "request": {"reqid": req_id, "text": text, "operation": "submit"}
        }
        payload_json = json.dumps(payload_dict).encode('utf-8')
        header_int = (1 << 28) | (1 << 24) | (1 << 20) | (0 << 16) | (1 << 12) | (0 << 8) | 0
        header_bytes = struct.pack('>I', header_int)
        size_bytes = struct.pack('>I', len(payload_json))
        return header_bytes + size_bytes + payload_json

    def _on_message(self, ws, message):
        """[修正版] 增加对消息长度的严格检查"""
        if not isinstance(message, bytes): return
        
        # 打印收到的原始消息，用于调试
        # print(f"[TTS-Debug] 收到原始二进制消息 (长度: {len(message)}): {message[:60]}...")

        try:
            # 至少需要4字节的Header
            if len(message) < 4: return
            header_int = struct.unpack('>I', message[:4])[0]
            msg_type = (header_int >> 20) & 0xF
            flags = (header_int >> 16) & 0xF

            if msg_type == 0b1011: # Audio-only server response
                # 必须至少有 Header(4) + Seq(4) + Size(4) = 12 字节
                if len(message) < 12:
                    print(f"[TTS-Warn] 收到一个不完整的音频响应包 (长度: {len(message)})")
                    return
                
                payload_size = struct.unpack('>I', message[8:12])[0]
                # 确认包的剩余长度足够
                if len(message) < 12 + payload_size:
                    print(f"[TTS-Warn] 音频包数据不完整，期望 {payload_size} 字节，实际 {len(message)-12} 字节。")
                    return

                audio_data = message[12 : 12 + payload_size]
                self.audio_queue.put(audio_data)
                
                if flags in (0b0010, 0b0011): # Last message
                    self.audio_queue.put(None)
                    self.is_finished.set()

            elif msg_type == 0b1111: # Error message
                # 错误包也需要有最小长度
                if len(message) < 12:
                    print(f"[TTS-Warn] 收到一个不完整的错误响应包 (长度: {len(message)})")
                    return
                # 根据文档，错误包格式为 Header(4) + Code(4) + Size(4) + Message
                error_code = struct.unpack('>I', message[4:8])[0]
                error_msg_size = struct.unpack('>I', message[8:12])[0]
                error_msg = message[12 : 12 + error_msg_size].decode('utf-8')
                print(f"❌ TTS 服务器返回错误: Code={error_code}, Message='{error_msg}'")
                self.audio_queue.put(None)
                self.is_finished.set()
            else:
                print(f"[TTS-Warn] 收到未知类型的消息: Type={msg_type}")

        except Exception as e:
            print(f"❌ 处理TTS消息时发生异常: {e}")
            self.audio_queue.put(None)
            self.is_finished.set()

    # ... (_on_error, _on_close, _on_open, get_audio_stream 方法保持不变) ...
    def _on_error(self, ws, error):
        print(f"❌ TTS WebSocket 错误: {error}"); self.audio_queue.put(None); self.is_finished.set()
    def _on_close(self, ws, _, __):
        print("[TTS] WebSocket 连接已关闭。"); self.is_finished.set(); self.audio_queue.put(None)
    def _on_open(self, ws):
        print("[TTS] WebSocket 已连接，正在发送合成请求..."); ws.send(ws.request_data, opcode=websocket.ABNF.OPCODE_BINARY)

    def get_audio_stream(self, text):
        if not text.strip(): return iter([])
        if not all([TTS_APPID, TTS_TOKEN]): print("❌ TTS 服务错误: AppID 或 Token 未配置。"); return iter([])
        self.is_finished.clear()
        while not self.audio_queue.empty():
            try: self.audio_queue.get_nowait()
            except Empty: break
        request_data = self._construct_request_data(text)
        headers = {"Authorization": f"Bearer; {TTS_TOKEN}"}
        self.ws = websocket.WebSocketApp(TTS_WS_URL, header=headers, on_open=self._on_open, on_message=self._on_message, on_error=self._on_error, on_close=self._on_close)
        self.ws.request_data = request_data
        self.ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self.ws_thread.start()
        while True:
            chunk = self.audio_queue.get()
            if chunk is None: break
            yield chunk
        print("[TTS] 音频流已全部生成。")