# smart_speaker/services/wake_word_service.py
import json
from vosk import Model, KaldiRecognizer
import config

class VoskWakeWordDetector:
    """
    一个通用的、基于Vosk的关键词检测服务。
    """
    def __init__(self, keywords: list):
        """
        初始化检测器。

        Args:
            keywords (list): 一个包含要监听的关键词的字符串列表。
        """
        self.recognizer = None
        self.keywords = [kw for kw in keywords if kw] # 过滤掉空字符串
        
        if not self.keywords:
            print("[Vosk-Detector] 错误：未提供任何有效的关键词。")
            return

        try:
            # 模型是共享的，所以我们只加载一次
            # 为了避免重复加载，可以考虑在更高层级管理模型实例
            # 但在这里，为保持模块独立性，我们每次都加载
            print(f"[Vosk-Detector] 正在从 '{config.VOSK_MODEL_PATH}' 加载模型...")
            model = Model(config.VOSK_MODEL_PATH)
            
            # 根据传入的关键词列表，动态创建Vosk语法
            grammar = json.dumps(self.keywords + ["[unk]"], ensure_ascii=False)
            self.recognizer = KaldiRecognizer(model, config.TARGET_RATE, grammar)
            print(f"[Vosk-Detector] ✅ 识别器已准备就绪，监听: {self.keywords}")

        except Exception as e:
            print(f"❌ Vosk模型加载或识别器创建失败: {e}")

    def process(self, chunk: bytes) -> bool:
        """
        处理一小块音频，如果检测到任何一个设定的关键词，则返回True。

        Args:
            chunk (bytes): 16kHz, 16-bit, 单声道的PCM音频块。

        Returns:
            bool: True表示检测到关键词，False则没有。
        """
        if not self.recognizer:
            return False
        
        if self.recognizer.AcceptWaveform(chunk):
            result = json.loads(self.recognizer.Result())
            text = result.get('text', '').replace(" ", "")
            
            # 检查识别出的文本是否包含任何一个关键词
            if any(keyword in text for keyword in self.keywords):
                print(f"[Vosk-Detector] ✅ 检测到关键词: '{text}' (匹配列表: {self.keywords})")
                return True
                
        return False