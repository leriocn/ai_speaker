# main.py
import threading
import json
from flask import Flask, render_template
from flask_sock import Sock

import config
from smart_speaker.smartspeaker import SmartSpeaker, SpeakerState
from smart_speaker.audio_handler import AudioHandler
from smart_speaker.flask_utils import clients, broadcast

# --- Web服务器和WebSocket设置 ---
app = Flask(__name__)
sock = Sock(app)

# --- Flask路由 ---
@app.route('/')
def index():
    return render_template('index.html')

@sock.route('/ws')
def ws(ws_client):
    clients.append(ws_client)
    print(f"新客户端连接，当前共 {len(clients)} 个连接。")
    if 'speaker' in globals() and speaker:
        # 发送初始状态
        ws_client.send(json.dumps({"type": "conversation_history", "history": speaker.conversation_history[1:]}))
        current_message = config.PROMPT_SLEEPING
        ws_client.send(json.dumps({"type": "status_update", "state": "idle", "message": current_message}))
    try:
        while True:
            # 保持连接，可以接收来自前端的消息（目前未使用）
            message = ws_client.receive(timeout=60)
    except Exception:
        print("客户端断开连接。")
    finally:
        if ws_client in clients:
            clients.remove(ws_client)

# --- 主程序入口 ---
if __name__ == '__main__':
    if config.check_env_vars():
        # 1. 创建业务逻辑实例
        speaker = SmartSpeaker()
        
        # 2. 创建并启动音频处理器，它会持有speaker的引用
        audio_handler = AudioHandler(speaker)
        audio_handler.start()
        
        # 3. 启动Web服务器 (在主线程中)
        print("Web服务器已在 http://0.0.0.0:5000 启动")
        try:
            # 使用werkzeug的开发服务器，它能很好地处理多线程和WebSocket
            app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
        except KeyboardInterrupt:
            print("\n正在关闭程序...")
        finally:
            # 确保所有后台进程都被清理
            audio_handler.stop()
            if speaker.music_player.is_active():
                speaker.music_player.stop()
            print("程序已完全退出。")
    else:
        print("\n请先完成 .env 文件的配置后再运行程序。")