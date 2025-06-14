# smart_speaker/audio_processing.py
import subprocess
import threading
import time
import os
import requests

import config

class MusicPlayer:
    """
    一个专门用于在后台播放音乐的类。
    它管理一个ffplay子进程，并可以从外部停止。
    """
    def __init__(self):
        self.process = None
        self.is_playing = False
        self.play_thread = None
        self.current_song_name = ""
        self.on_playback_finished_callback = None # 用于存放回调函数

    def _play_thread_target(self, url, song_name):
        """在后台线程中运行的播放任务"""
        print(f"[MusicPlayer] 准备播放音乐: {song_name}")
        command = [
            "ffplay",
            "-nodisp",              # 不显示图形窗口
            "-autoexit",            # 播放完毕自动退出
            "-loglevel", "error",   # 只打印错误信息
            url                     # 直接播放URL
        ]
        try:
            self.process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            self.is_playing = True
            self.current_song_name = song_name
            print(f"[MusicPlayer] ✅ 音乐《{song_name}》开始播放...")
            
            # 等待进程结束
            self.process.wait()
            
            # 进程结束后，检查是否有错误输出
            stderr_output = self.process.stderr.read().decode(errors='ignore').strip()
            # 只有在不是被我们主动停止时，才打印错误
            if self.is_playing and stderr_output: 
                print(f"[MusicPlayer] 播放出错或自然结束: {stderr_output}")

        except FileNotFoundError:
            print("❌ 错误: 'ffplay' 命令未找到。")
        except Exception as e:
            print(f"❌ 启动音乐播放器时出错: {e}")
        finally:
            self.is_playing = False
            self.process = None
            self.current_song_name = ""
            print(f"[MusicPlayer] 音乐《{song_name}》播放线程结束。")
            # 调用回调函数，通知上层播放已结束
            if self.on_playback_finished_callback:
                self.on_playback_finished_callback()

    def play(self, url, song_name, on_finished_callback=None):
        """开始播放一首音乐，并注册一个结束回调"""
        if self.is_playing:
            self.stop() # 如果正在播放，先停止上一首
        
        self.on_playback_finished_callback = on_finished_callback # 保存回调
        
        try:
            print(f"[MusicPlayer] 正在解析音乐真实地址: {url}")
            # requests库会自动处理302跳转
            response = requests.get(url, allow_redirects=True, stream=True, timeout=10)
            final_url = response.url
            print(f"[MusicPlayer] 解析到真实地址: {final_url}")
        except requests.RequestException as e:
            print(f"❌ 解析音乐URL失败: {e}")
            # 解析失败也要触发回调，让系统恢复
            if self.on_playback_finished_callback:
                self.on_playback_finished_callback()
            return

        self.play_thread = threading.Thread(target=self._play_thread_target, args=(final_url, song_name), daemon=True)
        self.play_thread.start()

    def stop(self):
        """停止当前正在播放的音乐"""
        if self.process and self.is_playing:
            print(f"[MusicPlayer] 正在停止音乐《{self.current_song_name}》...")
            self.is_playing = False # 主动设置标志，让_play_thread_target知道是主动停止
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
            except Exception as e:
                print(f"❌ 停止音乐播放时出错: {e}")
            self.process = None
            print("[MusicPlayer] ✅ 音乐已停止。")

    def is_active(self):
        """检查播放器是否正在播放"""
        return self.is_playing

# --- 以下是用于播放TTS短音频流的函数 ---

def _feed_audio_to_player(player_process, audio_stream_generator, save_path=None):
    """私有辅助函数：在后台线程中将音频块喂给播放器进程"""
    file_to_write = None
    try:
        if save_path:
            file_to_write = open(save_path, 'wb')
        for chunk in audio_stream_generator:
            if chunk:
                if player_process.stdin and not player_process.stdin.closed:
                    try:
                        player_process.stdin.write(chunk)
                    except (IOError, BrokenPipeError):
                        print("[TTS-Play] 播放管道在写入时关闭，正常现象。")
                        break
                else:
                    break
                if file_to_write:
                    file_to_write.write(chunk)
            else:
                break
    except Exception as e:
        print(f"❌ 喂给TTS播放器时出错: {e}")
    finally:
        if player_process.stdin and not player_process.stdin.closed:
            try:
                player_process.stdin.close()
            except (IOError, BrokenPipeError):
                pass
        if file_to_write:
            file_to_write.close()

def play_audio_stream(audio_stream_generator):
    """使用ffplay播放一个来自内存的音频流生成器（用于TTS）。"""
    if not audio_stream_generator:
        return
    
    print("[TTS-Play] 准备播放语音流...")
    command = ["ffplay", "-autoexit", "-nodisp", "-loglevel", "error", "-i", "-"]
    save_path = None
    if config.SAVE_TTS_AUDIO:
        timestamp = int(time.time())
        save_path = os.path.join(config.AUDIO_DIR, f"tts_output_{timestamp}.mp3")

    try:
        ffplay_process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        time.sleep(0.1)
        if ffplay_process.poll() is not None:
             stderr_output = ffplay_process.stderr.read().decode(errors='ignore')
             print(f"❌ ffplay(TTS) 启动失败! 错误: {stderr_output.strip()}"); return

        player_thread = threading.Thread(target=_feed_audio_to_player, args=(ffplay_process, audio_stream_generator, save_path))
        player_thread.start()
        player_thread.join()
        ffplay_process.wait()
    except Exception as e:
        print(f"❌ 启动TTS播放器时出错: {e}")