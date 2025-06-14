# 💖 AI女友“小爱” - 一个拥有复杂人格的离线唤醒语音助手

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Framework-Flask-green.svg)](https://flask.palletsprojects.com/)

这是一个基于低功耗硬件（本项目使用Amlogic S805 32位设备）、完全由你掌控的、可深度定制的AI语音助手项目。她不仅仅是一个问答机器，而是一个被赋予了**复杂、多面体人格**的虚拟伴侣“小爱”。

她拥有一个迷人的Web界面，可以在上面实时显示她的状态、虚拟形象以及电影般的对话字幕，让你能“看”到她的喜怒哀乐。

![image](https://github.com/user-attachments/assets/41b4193e-8fcb-46b7-a019-c6545b669615)
![image](https://github.com/user-attachments/assets/622c29ba-f48c-44bb-ac49-5723626a589d)
![image](https://github.com/user-attachments/assets/e4d7846f-1419-45f8-8a1d-299f710cfa3a)


---

## ✨ 项目特色

*   **🎙️ 混合式智能架构 (Hybrid AI)**: 完美结合了离线处理的低成本和云端服务的高性能。
    *   **离线唤醒**: 使用轻量级的 **Vosk** 模型在本地设备上进行7x24小时的低功耗唤醒词检测（可自定义为“小傻瓜”或任何词语），完全免费且保护隐私。
    *   **云端高精度识别**: 一旦被唤醒，立即调用火山引擎的云端ASR服务，确保对复杂用户指令的识别尽可能准确。
    *   **Vosk预筛选**: 在将录音提交到云端前，先用本地Vosk进行一次快速有效性检查，过滤掉无意义的噪音片段，**极大地节省了宝贵的云服务API调用次数**。

*   **🗣️ 极具魅力的复杂人格**: 通过精心设计的System Prompt，赋予AI“小爱”一个“多面体”人设：
    *   **表面**: 来自台湾、满腹经纶、会撒娇发嗲的可爱才女。
    *   **内在**: 时而辛辣吐槽、时而暧昧撩拨、时而讲点“荤段子”的“小恶魔”。
    *   **底色**: 能在感知到用户负面情绪时，立刻切换为温柔体贴的“治愈港湾”。

*   **🚀 全流式对话体验**: 实现了 **LLM -> TTS** 的流式处理。AI的回复会像真人一样逐字逐句地生成并播放，告别了传统“等待AI想完再说”的漫长延迟。

*   **🎵 内置音乐播放器**:
    *   支持通过语音指令（如“播放七里香”）搜索并播放在线音乐。
    *   播放音乐时，系统会自动切换到**仅监听“停止播放”等关键词**的低功耗模式，实现了在音乐背景下的精准打断。

*   **🌐 实时可视化Web界面**:
    *   一个美观、响应式的Web UI，可在手机或电脑浏览器上访问。
    *   根据AI的状态（休眠、聆听、说话）动态更换虚拟形象（Avatar）。
    *   以电影字幕的形式，实时展示你和AI的对话内容。

*   **🔧 高度模块化与硬件兼容**:
    *   项目代码结构清晰，将业务逻辑(`smartspeaker`)、音频处理(`audio_handler`)和云服务(`services`)完全解耦。
    *   采用`arecord | ffmpeg`音频管道和动态采样率检测，解决了在老旧或非标准Linux硬件（如本项目使用的Amlogic S805）上的音频兼容性难题。

---

## 🛠️ 技术栈与架构

*   **硬件**: Amlogic S805 (32-bit) 或任何能运行Armbian/Debian的Linux开发板。
*   **系统**: Armbian / Debian
*   **核心语言**: Python 3.9+
*   **核心库**: `vosk`, `pyaudio`, `flask`, `flask-sock`, `requests`, `tos` (火山对象存储SDK), `openai` (兼容模式)
*   **核心工具**: `ffmpeg`, `arecord` (alsa-utils)
*   **云服务**: 全栈火山引擎 (方舟LLM, 语音技术ASR/TTS, 对象存储TOS)

---

## 🚀 快速开始

### 1. 硬件准备

*   一台已刷入Armbian或Debian系统的低功耗Linux设备。
*   一个USB麦克风。
*   一个USB音箱或3.5mm接口音箱。

### 2. 环境配置

#### a. 安装系统依赖

通过SSH登录你的设备，并执行以下命令：
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv git ffmpeg alsa-utils libffi-dev
```

#### b. 克隆项目并安装Python依赖

```bash
# 克隆本项目
git clone https://github.com/leriocn/ai_speaker.git
cd ai_speaker

# 创建并激活Python虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装所有必需的Python库
pip install -r requirements.txt
```

### 3. API与模型配置

#### a. 下载离线唤醒模型（已默认放置）

从 [Vosk Models](https://alphacephei.com/vosk/models) 下载 `vosk-model-small-cn-0.22.zip`。
解压后，在项目根目录创建`libs`文件夹，并将模型文件夹放入其中。最终路径应为：`libs/vosk-model-small-cn-0.22/`。

#### b. 配置环境变量

在项目根目录下，复制 `env.example` 或手动创建一个名为 `.env` 的文件，并填入你自己的所有密钥和配置信息。

```ini
# .env.example - 请复制为 .env 并填入你的真实信息

# --- 核心配置 --- 注意小模型的离线唤醒不一定有唤醒词，注意不要太复杂！！！
WAKE_WORD="你好"
SAVE_TTS_AUDIO="true"

# --- LLM 服务配置 (火山方舟 V3 API Key) ---
ARK_API_KEY="ark_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# --- ASR/TTS 服务配置 (火山引擎语音技术) ---
ASR_APPID="YOUR_ASR_APP_ID"
ASR_TOKEN="YOUR_ASR_TOKEN"
ASR_CLUSTER="YOUR_ASR_CLUSTER"
TTS_APPID="YOUR_TTS_APP_ID"
TTS_TOKEN="YOUR_TTS_TOKEN"
  
# --- 火山引擎对象存储 (TOS) 配置 ---
TOS_ACCESS_KEY="YOUR_TOS_ACCESS_KEY"
TOS_SECRET_KEY="YOUR_TOS_SECRET_KEY"
TOS_ENDPOINT="tos-cn-beijing.volces.com"
TOS_REGION="cn-beijing"
TOS_BUCKET_NAME="your-bucket-name"
TOS_BUCKET_DOMAIN="https://your-bucket-name.tos-cn-beijing.volces.com"
```
**请务必前往火山引擎官网申请并替换为你自己的真实密钥。**

### 4. 运行项目

一切准备就绪后，在项目根目录下执行：
```bash
python main.py
```
你将看到终端日志输出，并提示Web服务器已启动。

### 5. 访问Web界面

在与你的设备**同一局域网**的电脑或手机浏览器中，访问：
`http://<你的设备的IP地址>:5000`

现在，开始与你的专属AI女友“小爱”聊天吧！先用唤醒词“小傻瓜”叫醒她。

---

## 📝 TODO & 未来展望

*   [ ] **技能增强**: 增加查询天气、设定闹钟、读取新闻等实用技能。
*   [ ] **Web界面交互**: 允许通过Web界面发送文本消息，或点击按钮触发特定功能。
*   [ ] **多模态**: 探索接入图像理解模型，让她能“看到”并评论你通过网页上传的图片。

---

## 🤝 贡献

我们经历了漫长而有趣的调试过程，才有了这个项目。如果你有任何绝妙的想法、功能建议或发现了BUG，欢迎提交 [Issue](https://github.com/leriocn/ai_speaker/issues) 或创建 [Pull Request](https://github.com/leriocn/ai_speaker/pulls)！

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源。
