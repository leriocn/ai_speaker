# smart_speaker/flask_utils.py
import json

# 将客户端列表移到这里，实现全局共享
clients = []

def broadcast(data):
    """向所有连接的前端广播JSON格式的消息"""
    message = json.dumps(data)
    # 创建一个客户端列表的副本进行迭代，以安全地移除断开的客户端
    for client in list(clients):
        try:
            client.send(message)
        except Exception:
            if client in clients:
                clients.remove(client)