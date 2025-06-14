# smart_speaker/services/music_service.py
import requests
import urllib.parse
from typing import Optional, Dict, Any

# 网易云音乐API的基地址
SEARCH_API_URL = "https://music.163.com/api/search/get/web"
SONG_URL_TEMPLATE = "https://music.163.com/song/media/outer/url?id={}.mp3"

# 创建一个持久化的HTTP会话，可以复用连接
http_session = requests.Session()
# 设置一个浏览器User-Agent，避免被API拒绝
http_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
})

def search_song(song_name: str) -> Optional[Dict[str, Any]]:
    """
    根据歌曲名称搜索歌曲，并返回最匹配的一首歌曲信息。

    Args:
        song_name (str): 歌曲名称。

    Returns:
        Optional[Dict[str, Any]]: 包含歌曲信息的字典 (id, name, artists)，如果找不到则返回None。
    """
    if not song_name:
        return None

    # 对歌曲名称进行URL编码
    encoded_song_name = urllib.parse.quote(song_name)
    full_url = f"{SEARCH_API_URL}?s={encoded_song_name}&type=1"
    
    print(f"[MusicService] 正在搜索歌曲: '{song_name}' (URL: {full_url})")
    
    try:
        response = http_session.get(full_url, timeout=10)
        response.raise_for_status() # 检查HTTP错误
        
        data = response.json()
        
        if data.get('code') == 200 and data.get('result', {}).get('songs'):
            songs = data['result']['songs']
            # 策略：选择第一个非VIP（fee!=1）或非付费专辑（fee!=4）的歌曲
            # 如果都是付费的，就返回第一个
            best_song = None
            for song in songs:
                # fee=0或8是免费的，fee=4是付费单曲，fee=1是VIP
                if song.get('fee') in [0, 8]:
                    best_song = song
                    break
            
            if not best_song and songs:
                best_song = songs[0] # 回退到第一个结果

            if best_song:
                artist_names = ", ".join([artist['name'] for artist in best_song.get('artists', [])])
                print(f"[MusicService] ✅ 找到最匹配歌曲: '{best_song['name']}' - {artist_names} (ID: {best_song['id']})")
                
                return {
                    "id": best_song['id'],
                    "name": best_song['name'],
                    "artists": artist_names
                }
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 音乐搜索网络请求失败: {e}")
    except (KeyError, IndexError, TypeError) as e:
        print(f"❌ 解析音乐搜索结果失败: {e}")
        
    return None

def get_song_play_url(song_id: int) -> str:
    """
    根据歌曲ID构建播放URL。

    Args:
        song_id (int): 歌曲ID。

    Returns:
        str: 最终的播放URL。
    """
    return SONG_URL_TEMPLATE.format(song_id)

if __name__ == '__main__':
    # 这是一个用于独立测试本模块功能的示例
    print("--- 音乐服务模块独立测试 ---")
    test_song_name = "七里香"
    song_info = search_song(test_song_name)
    if song_info:
        play_url = get_song_play_url(song_info['id'])
        print(f"歌曲: {song_info['name']}")
        print(f"歌手: {song_info['artists']}")
        print(f"播放URL: {play_url}")
    else:
        print(f"未能找到歌曲 '{test_song_name}'")