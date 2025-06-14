# services/asr_service.py
import time
import requests
import tos

# 从我们的配置模块导入所需内容
from config import (
    ASR_APPID, ASR_TOKEN, ASR_CLUSTER, ASR_SERVICE_URL,
    TOS_ACCESS_KEY, TOS_SECRET_KEY, TOS_ENDPOINT, TOS_REGION,
    TOS_BUCKET_NAME, TOS_BUCKET_DOMAIN
)

# --- 文件识别部分 (使用TOS) ---
http_session = requests.Session()

# 初始化TOS客户端
if all([TOS_ACCESS_KEY, TOS_SECRET_KEY, TOS_ENDPOINT, TOS_REGION]):
    try:
        tos_client = tos.TosClientV2(
            ak=TOS_ACCESS_KEY,
            sk=TOS_SECRET_KEY,
            endpoint=TOS_ENDPOINT,
            region=TOS_REGION
        )
    except Exception as e:
        tos_client = None
        print(f"[TOS-Error] 初始化TOS客户端失败: {e}")
else:
    tos_client = None
    print("[TOS-Warn] TOS配置不完整，对象存储功能将不可用。")

def _upload_to_tos(file_path):
    """上传文件到火山TOS并返回公网URL和使用的Key"""
    if not tos_client: 
        print("❌ TOS客户端未初始化，上传中断。")
        return None, None
    
    key = f"temp/{int(time.time())}_{file_path.split('/')[-1]}"
    print(f"[TOS] 准备上传 {file_path} 到 bucket '{TOS_BUCKET_NAME}' (Key: {key})...")
    
    try:
        # 使用最简单的上传调用，不指定任何acl或headers
        tos_client.put_object_from_file(
            bucket=TOS_BUCKET_NAME,
            key=key,
            file_path=file_path
        )
        
        domain = TOS_BUCKET_DOMAIN.rstrip('/')
        public_url = f"{domain}/{key}"
        print(f"[TOS] ✅ 上传成功。公网URL: {public_url}")
        return public_url, key
        
    except tos.exceptions.TosClientError as e:
        print(f'❌ TOS上传客户端异常: message:{e.message}, cause: {e.cause}')
    except tos.exceptions.TosServerError as e:
        print(f'❌ TOS上传服务端异常, code: {e.code}, request_id: {e.request_id}, message: {e.message}')
    except Exception as e:
        print(f'❌ TOS上传未知错误: {e}')
        
    return None, None

def _delete_from_tos(key):
    """从火山TOS删除文件"""
    if not tos_client: return
    
    print(f"[TOS] 正在删除文件: {key}...")
    try:
        tos_client.delete_object(TOS_BUCKET_NAME, key)
        print(f"[TOS] ✅ 文件删除成功。")
    except Exception as e:
        print(f"❌ TOS文件删除失败: {e}")

def transcribe_audio_file(file_path):
    """将本地音频文件上传到TOS并进行识别"""
    if not tos_client:
        print("❌ ASR 服务错误: TOS客户端未配置或初始化失败。")
        return None

    public_audio_url, uploaded_key = None, None
    try:
        public_audio_url, uploaded_key = _upload_to_tos(file_path)
        if not public_audio_url: return None

        print("[ASR-File] 正在使用公网URL进行语音识别...")
        headers = {'Authorization': f'Bearer; {ASR_TOKEN}'}
        submit_req_body = {
            "app": {"appid": ASR_APPID, "token": ASR_TOKEN, "cluster": ASR_CLUSTER},
            "user": {"uid": "s805_command_recognizer"},
            "audio": {"format": "wav", "url": public_audio_url}
        }
        
        r = requests.post(ASR_SERVICE_URL + '/submit', json=submit_req_body, headers=headers, timeout=10)
        
        if r.status_code != 200:
            print(f"❌ ASR文件任务提交请求失败，状态码: {r.status_code}, 内容: {r.text}"); return None
        resp_dic = r.json()
        if resp_dic.get('resp', {}).get('code') != 1000:
            print(f"❌ ASR文件任务提交失败 (API): {r.text}"); return None
        task_id = resp_dic['resp']['id']
        print(f"[ASR-File] 任务提交成功, Task ID: {task_id}")

        query_req_body = {"appid": ASR_APPID, "token": ASR_TOKEN, "cluster": ASR_CLUSTER, "id": task_id}
        start_time = time.time()
        while time.time() - start_time < 60:
            time.sleep(1.5)
            q_r = requests.post(ASR_SERVICE_URL + '/query', json=query_req_body, headers=headers, timeout=10)
            if q_r.status_code != 200: continue
            q_resp_dic = q_r.json()
            code = q_resp_dic.get('resp', {}).get('code')
            if code == 1000:
                text = q_resp_dic['resp'].get('text', '')
                print(f"[ASR-File] 识别结果: '{text}'")
                return text.strip() or "（未识别到有效内容）"
            elif code is not None and code < 2000:
                print(f"❌ ASR文件任务处理失败: {q_r.text}"); return None
        print("❌ ASR文件任务查询超时。")
    finally:
        if uploaded_key:
            _delete_from_tos(uploaded_key)
            
    return None