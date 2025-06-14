# services/llm_service.py
import os
from openai import OpenAI

# 从我们的配置模块导入所需内容
from config import ARK_API_KEY, LLM_MODEL_ID, LLM_BASE_URL

# 创建一个全局的、可复用的OpenAI客户端实例
# 它将被配置为指向火山方舟的服务器
llm_client = OpenAI(
    base_url=LLM_BASE_URL,
    api_key=ARK_API_KEY  # 在初始化时传递API Key
)

def get_llm_response_stream(prompt, history=[]):
    """
    调用兼容OpenAI协议的火山方舟大模型API，以流式方式获取回复。

    Args:
        prompt (str): 当前用户的提问。
        history (list): 对话历史，格式为 [{"role": "user/assistant", "content": "..."}, ...]。

    Yields:
        str: LLM生成的一个个文本块。
    """
    # 检查配置
    if not ARK_API_KEY:
        print("❌ LLM 服务错误: ARK_API_KEY 未在 config.py 中配置。")
        yield "抱歉，我的大脑连接密钥丢失了。"
        return

    # 构造符合API要求的messages列表
    messages = history + [{"role": "user", "content": prompt}]
    
    print(f"[LLM] 正在向大模型发送请求 (via OpenAI SDK): '{prompt[:30]}...'")
    
    try:
        # 发起流式请求，代码和调用OpenAI完全一样
        stream = llm_client.chat.completions.create(
            model=LLM_MODEL_ID,
            messages=messages,
            stream=True
        )
        
        print("[LLM] 已连接，开始接收流式回复...")
        
        first_chunk = True
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                content_piece = chunk.choices[0].delta.content
                if first_chunk:
                    content_piece = content_piece.lstrip()
                    if not content_piece: continue
                    first_chunk = False
                
                yield content_piece
                
    except Exception as e:
        error_message = f"❌ LLM API 调用出错: {e}"
        print(error_message)
        yield f"抱歉，我的思维模块好像出了一点问题。"
    
    print("[LLM] 流式回复接收完毕。")