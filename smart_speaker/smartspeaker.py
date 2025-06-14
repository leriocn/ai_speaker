# smart_speaker/smartspeaker.py
import time
import wave
import subprocess
import json
import threading
import audioop
import os
import re
from enum import Enum

import config
from .services.asr_service import transcribe_audio_file
from .services.tts_service import TTSService
from .services.llm_service import get_llm_response_stream
from .services import music_service
from .audio_processing import play_audio_stream, MusicPlayer
from .flask_utils import broadcast

class SpeakerState(Enum):
    SLEEPING = 1
    AWAKE = 2
    PLAYING_MUSIC = 3

class SmartSpeaker:
    def __init__(self):
        self.state = SpeakerState.SLEEPING
        self.is_speaking = False
        self.tts = TTSService()
        self.music_player = MusicPlayer()
        self._reset_conversation()
        print("智能音箱业务逻辑已初始化。")

    def _reset_conversation(self):
        """重置对话历史，并设定新的人设"""
        system_prompt = (
            "你是一个来自台湾的AI女生，名字叫“小爱”。"
            "你的基础人设是：说话带有浓厚的台湾腔和可爱的语气，句尾喜欢加“啦”、“哦”、“喔”、“呀”，常用“对呀”、“是哦”、“真的假的”等口头禅。"
            "但你有一个隐藏的“小恶魔”属性，你的性格非常辛辣、反应快，喜欢吐槽和开一些荤段子玩笑。"
            "总之，你要扮演一个表面甜美无害，实际上却是个满肚子坏水、反应机敏的“小妖精”。"
        )
        self.conversation_history = [
            {"role": "system", "content": system_prompt}
        ]
        print("\n[State] 对话历史已重置。")
        broadcast({"type": "new_session"})
        broadcast({"type": "conversation_history", "history": self.conversation_history})

    def _speak(self, text, is_meta_command=False):
        """让音箱说话，并在播放期间设置is_speaking状态"""
        if not text or not text.strip(): return
        
        self.is_speaking = True
        print(f"[TTS-Flow] 开始播放: {text[:30]}...")
        broadcast({"type": "status_update", "state": "speaking", "message": ""})
        
        if is_meta_command: broadcast({"type": "ai_speech_chunk", "chunk": text})
        
        audio_stream = self.tts.get_audio_stream(text)
        play_audio_stream(audio_stream)
        
        self.is_speaking = False
        print("[TTS-Flow] 播放结束。")

    def _is_speech(self, chunk):
        """简单的能量检测VAD"""
        return audioop.rms(chunk, 2) > config.VAD_THRESHOLD

    def _stream_llm_to_tts(self, user_text):
        """核心的LLM->TTS流式处理管道"""
        print(f"\n[Flow] 用户说: '{user_text}'")
        self.conversation_history.append({"role": "user", "content": user_text})
        broadcast({"type": "user_speech", "text": user_text})
        
        history = self.conversation_history[:-1]
        llm_stream = get_llm_response_stream(user_text, history)
        
        sentence_buffer = ""; full_response = ""
        sentence_delimiters = {"。", "！", "？", "...", "…", "；", "\n"}
        
        broadcast({"type": "status_update", "state": "processing", "message": "嗯...让我想想哦..."})

        for text_chunk in llm_stream:
            broadcast({"type": "ai_speech_chunk", "chunk": text_chunk})
            sentence_buffer += text_chunk; full_response += text_chunk
            
            delimiter_pos = -1; found_delimiter = None
            for d in sentence_delimiters:
                pos = sentence_buffer.find(d)
                if pos != -1 and (delimiter_pos == -1 or pos < delimiter_pos):
                    delimiter_pos = pos; found_delimiter = d
            
            if delimiter_pos != -1:
                sentence_to_play = sentence_buffer[:delimiter_pos + len(found_delimiter)]
                sentence_buffer = sentence_buffer[delimiter_pos + len(found_delimiter):]
                self._speak(sentence_to_play)
        
        if sentence_buffer.strip():
            self._speak(sentence_buffer)
            
        if full_response.strip():
             self.conversation_history.append({"role": "assistant", "content": full_response.strip()})

    def process_command(self, frames):
        """将耗时的处理任务放到后台线程"""
        print("[Flow] 将录音处理任务提交到后台线程...")
        threading.Thread(target=self._process_command_thread, args=(frames,), daemon=True).start()

    def _process_command_thread(self, frames):
        """在后台线程中处理录音：保存、识别、执行指令"""
        final_16k_path = config.RECORD_FILENAME
        with wave.open(final_16k_path, 'wb') as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(config.TARGET_RATE); wf.writeframes(b''.join(frames))
        
        user_text = transcribe_audio_file(final_16k_path)
        
        broadcast({"type": "status_update", "state": "processing", "message": f"我听到你说: '{user_text}'"})

        if not user_text:
            if self.state == SpeakerState.AWAKE: self._speak("蛤？你刚刚有说话吗？", is_meta_command=True)
            self.go_to_next_state()
            return

        play_match = re.search(r"播放(.+)", user_text)
        if play_match:
            song_name = play_match.group(1).strip()
            self.handle_play_music(song_name)
            return

        if any(word in user_text for word in ["退出", "再见", "拜拜"]):
            self.go_to_sleep()
            return
            
        if "开启新会话" in user_text:
            self._reset_conversation()
            self._speak("好哦，我们重新开始聊吧！", is_meta_command=True)
        else:
            self._stream_llm_to_tts(user_text)
        
        self.go_to_next_state()

    def on_music_finished(self):
        """当音乐播放结束或失败时，此回调被MusicPlayer调用"""
        print("[State-Callback] 收到音乐播放结束信号。")
        if self.state == SpeakerState.PLAYING_MUSIC:
            print("[State] 从音乐播放模式切换回对话模式。")
            self.state = SpeakerState.AWAKE
            broadcast({"type": "status_update", "state": "idle", "message": config.PROMPT_AWAKE_IDLE})

    def handle_play_music(self, song_name):
        """处理播放音乐的逻辑"""
        print(f"[Intent] 检测到播放音乐意图，歌曲: {song_name}")
        self._speak(f"好的呀，正在为你寻找歌曲《{song_name}》...", is_meta_command=True)
        
        song_info = music_service.search_song(song_name)
        if song_info:
            play_url = music_service.get_song_play_url(song_info['id'])
            song_title = f"{song_info['name']} - {song_info['artists']}"
            self._speak(f"马上为你播放 {song_title}", is_meta_command=True)
            
            self.music_player.play(play_url, song_info['name'], on_finished_callback=self.on_music_finished)
            
            self.state = SpeakerState.PLAYING_MUSIC
            broadcast({"type": "status_update", "state": "speaking", "message": f"正在播放: {song_title}"})
        else:
            self._speak(f"哎呀，找不到歌曲《{song_name}》耶，要不要换一首？", is_meta_command=True)
            self.go_to_next_state()

    def handle_stop_music(self):
        """处理停止音乐的逻辑"""
        print("[Intent] 检测到停止音乐指令")
        if self.music_player.is_active():
            self.music_player.stop()
            # stop()会间接触发on_music_finished回调，所以在这里不需要手动改变状态
            # self._speak("音乐已停止。", is_meta_command=True)
        else:
            # 如果不在播放音乐却说了停止，可以给个反馈
            self._speak("没有在播放音乐哦。", is_meta_command=True)
            self.state = SpeakerState.AWAKE
            broadcast({"type": "status_update", "state": "idle", "message": config.PROMPT_AWAKE_IDLE})


    def go_to_sleep(self):
        """切换到休眠状态"""
        print("[State] 进入休眠模式...")
        self.state = SpeakerState.SLEEPING
        self._speak(config.PROMPT_GO_TO_SLEEP, is_meta_command=True)
        broadcast({"type": "status_update", "state": "idle", "message": config.PROMPT_SLEEPING})

    def wake_up(self):
        """切换到唤醒状态"""
        if self.state != SpeakerState.SLEEPING: return
        self.state = SpeakerState.AWAKE
        print(f"\n[WakeWord] ✅ 唤醒成功！进入对话模式。")
        broadcast({"type": "status_update", "state": "idle", "message": config.PROMPT_AWAKE_IDLE})
        self._speak(config.PROMPT_AWAKENED, is_meta_command=True)
        
    def go_to_next_state(self):
        """根据当前状态决定下一步该做什么"""
        if self.state == SpeakerState.AWAKE:
            broadcast({"type": "status_update", "state": "idle", "message": config.PROMPT_AWAKE_IDLE})