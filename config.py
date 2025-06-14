# config.py
import os
from pathlib import Path # 引入pathlib库
from dotenv import load_dotenv

# 在模块加载时，自动加载 .env 文件中的环境变量
load_dotenv()

# --- 核心路径配置 ---
# 获取config.py文件所在的目录，也就是项目的根目录
# Path(__file__) -> 获取当前文件的路径
# .parent -> 获取其父目录
# str() -> 转换为字符串
ROOT_DIR = str(Path(__file__).parent)
# [修改] 创建并使用audio子目录
AUDIO_DIR = os.path.join(ROOT_DIR, "audio")
if not os.path.exists(AUDIO_DIR):
    os.makedirs(AUDIO_DIR)

# --- 核心配置 ---
WAKE_WORD = os.getenv('WAKE_WORD', "你好")
MUSIC_STOP_WORDS = ["停止播放", "不想听了", "关掉音乐", "暂停"] 

# 使用os.path.join来构建一个跨平台兼容的绝对路径
VOSK_MODEL_PATH = os.path.join(ROOT_DIR, "libs", "vosk-model-small-cn-0.22")

# --- [新增] TTS调试配置 ---
SAVE_TTS_AUDIO = os.getenv('SAVE_TTS_AUDIO', 'false').lower() == 'true'

# --- UI提示语模板 ---
PROMPT_SLEEPING = f"人家在打盹哦，叫“{WAKE_WORD}”就能叫醒我啦~"
PROMPT_AWAKENED = "终于等到你了啦，我们聊聊天吧！"
PROMPT_AWAKE_IDLE = "想聊点什么呀？"
PROMPT_GO_TO_SLEEP = f"好的啦，那我先去休息哦。需要我的时候，再叫“{WAKE_WORD}”哦！"

# --- VAD & 录音配置 ---
VAD_THRESHOLD = 500             # VAD能量阈值，需要根据麦克风和环境微调
PRE_BUFFER_DURATION_S = 1.0       # 预录制时长（秒），即保留说话前多久的音频
SILENCE_DURATION_S = 2.0        # 检测到超过2秒的静音则认为说话结束
MAX_RECORDING_S = 15            # 安全措施：一次录音最长不超过15秒

# --- 音频管道配置 ---
ARECORD_DEVICE = "plughw:1,0"   # 通过 `arecord -l` 确认
TARGET_RATE = 16000             # Vosk 和其他服务需要的目标采样率
CHUNK_SIZE = 3200               # 16kHz, 16bit, 100ms * 2 bytes = 3200

# --- 全局音频配置 ---
INPUT_DEVICE_KEYWORDS = ["USB", "Audio", "Mic"] 
# [修改] 将录音文件路径指向audio目录
RECORD_FILENAME = os.path.join(AUDIO_DIR, "user_audio_16k.wav")

# --- LLM 服务配置 (OpenAI SDK 兼容模式) ---
ARK_API_KEY = os.getenv('ARK_API_KEY')
LLM_MODEL_ID = "doubao-pro-32k-241215"
LLM_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

# --- ASR 服务配置 (录音文件极速版) ---
ASR_APPID = os.getenv('ASR_APPID')
ASR_TOKEN = os.getenv('ASR_TOKEN')
ASR_CLUSTER = os.getenv('ASR_CLUSTER')
ASR_SERVICE_URL = 'https://openspeech.bytedance.com/api/v1/auc'

# --- TTS 服务配置 (大模型WebSocket) ---
TTS_APPID = os.getenv('TTS_APPID')
TTS_TOKEN = os.getenv('TTS_TOKEN')
TTS_CLUSTER = os.getenv('TTS_CLUSTER', 'volcano_tts')
TTS_VOICE_TYPE = "zh_female_wanwanxiaohe_moon_bigtts"
TTS_WS_URL = "wss://openspeech.bytedance.com/api/v1/tts/ws_binary"

# --- 火山引擎对象存储 (TOS) 配置 ---
TOS_ACCESS_KEY = os.getenv('TOS_ACCESS_KEY')
TOS_SECRET_KEY = os.getenv('TOS_SECRET_KEY')
TOS_ENDPOINT = os.getenv('TOS_ENDPOINT')
TOS_REGION = os.getenv('TOS_REGION')
TOS_BUCKET_NAME = os.getenv('TOS_BUCKET_NAME')
TOS_BUCKET_DOMAIN = os.getenv('TOS_BUCKET_DOMAIN')

# --- 检查配置完整性 ---
def check_env_vars():
    """检查所有需要的环境变量是否已配置"""
    required_vars = [
        'WAKE_WORD', # 增加了对唤醒词的检查
        'ARK_API_KEY', 
        'ASR_APPID', 'ASR_TOKEN', 'ASR_CLUSTER', 
        'TTS_APPID', 'TTS_TOKEN',
        'TOS_ACCESS_KEY', 'TOS_SECRET_KEY', 'TOS_ENDPOINT', 'TOS_REGION', 
        'TOS_BUCKET_NAME', 'TOS_BUCKET_DOMAIN'
    ]
    missing_vars = [var for var in required_vars if not globals().get(var)]
    if missing_vars:
        print(f"❌ 错误：请在 .env 文件中配置以下缺失的环境变量: {', '.join(missing_vars)}")
        return False
    print("✅ 所有环境变量配置加载成功。")
    return True