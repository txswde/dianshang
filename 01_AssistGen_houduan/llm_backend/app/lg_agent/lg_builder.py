from app.lg_agent.lg_states import AgentState, Router
from app.lg_agent.lg_prompts import (
    ROUTER_SYSTEM_PROMPT,
    GET_ADDITIONAL_SYSTEM_PROMPT,
    GENERAL_QUERY_SYSTEM_PROMPT,
    GET_IMAGE_SYSTEM_PROMPT,
    GUARDRAILS_SYSTEM_PROMPT,
    RAGSEARCH_SYSTEM_PROMPT,
    CHECK_HALLUCINATIONS,
    GENERATE_QUERIES_SYSTEM_PROMPT
)
from langchain_core.runnables import RunnableConfig
from langchain_deepseek import ChatDeepSeek
from langchain_ollama import ChatOllama
from app.core.config import settings, ServiceType
from app.core.logger import get_logger
from typing import cast, Literal, TypedDict, List, Dict, Any
from langchain_core.messages import BaseMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from app.lg_agent.lg_states import AgentState, InputState, Router, GradeHallucinations
from app.lg_agent.kg_sub_graph.agentic_rag_agents.retrievers.cypher_examples.northwind_retriever import NorthwindCypherRetriever
from app.lg_agent.kg_sub_graph.agentic_rag_agents.components.planner.node import create_planner_node
from app.lg_agent.kg_sub_graph.agentic_rag_agents.workflows.multi_agent.multi_tool import create_multi_tool_workflow
from app.lg_agent.kg_sub_graph.kg_neo4j_conn import get_neo4j_graph
from pydantic import BaseModel
from typing import Dict, List
from langchain_core.messages import AIMessage
from langchain_core.runnables.base import Runnable
from app.lg_agent.kg_sub_graph.agentic_rag_agents.components.utils.utils import retrieve_and_parse_schema_from_graph_for_prompts
from langchain_core.prompts import ChatPromptTemplate
import base64
import os
import aiohttp
import asyncio
import json
import time
from pathlib import Path


from typing import Literal
from pydantic import BaseModel, Field


class AdditionalGuardrailsOutput(BaseModel):
    """
    格式化输出，用于判断用户的问题是否与图谱内容相关
    """
    decision: Literal["end", "continue"] = Field(
        description="Decision on whether the question is related to the graph contents."
    )


# 构建日志记录器
logger = get_logger(service="lg_builder")

async def analyze_and_route_query(
    state: AgentState, *, config: RunnableConfig
) -> dict[str, Router]:
    """Analyze the user's query and determine the appropriate routing.

    This function uses a language model to classify the user's query and decide how to route it
    within the conversation flow.

    Args:
        state (AgentState): The current state of the agent, including conversation history.
        config (RunnableConfig): Configuration with the model used for query analysis.

    Returns:
        dict[str, Router]: A dictionary containing the 'router' key with the classification result (classification type and logic).
    """
    # 选择模型实例，通过.env文件中的AGENT_SERVICE参数选择
    if settings.AGENT_SERVICE == ServiceType.DEEPSEEK:
        model = ChatDeepSeek(api_key=settings.DEEPSEEK_API_KEY, model_name=settings.DEEPSEEK_MODEL, temperature=0.1, tags=["router"])
        logger.info(f"Using DeepSeek model: {settings.DEEPSEEK_MODEL}")
    else:
        model = ChatOllama(model=settings.OLLAMA_AGENT_MODEL, base_url=settings.OLLAMA_BASE_URL, temperature=0.1, tags=["router"])
        logger.info(f"Using Ollama model: {settings.OLLAMA_AGENT_MODEL}")

    # 拼接提示模版 + 用户的实时问题（包含历史上下文对话） 
    messages = [
        {"role": "system", "content": ROUTER_SYSTEM_PROMPT}
    ] + state.messages
    logger.info("-----Analyze user query type-----")
    logger.info(f"History messages: {state.messages}")
    
    # 使用结构化输出，输出问题类型
    response = cast(
        Router, await model.with_structured_output(Router).ainvoke(messages)
    )
    logger.info(f"Analyze user query type completed, result: {response}")
    return {"router": response}

def route_query(
    state: AgentState,
) -> Literal["respond_to_general_query", "get_additional_info", "create_research_plan", "create_image_query", "create_file_query"]:
    """根据查询分类确定下一步操作。

    Args:
        state (AgentState): 当前代理状态，包括路由器的分类。

    Returns:
        Literal["respond_to_general_query", "get_additional_info", "create_research_plan", "create_image_query", "create_file_query"]: 下一步操作。
    """
    _type = state.router["type"]
    
    # 检查配置中是否有图片路径，如果有，优先处理为图片查询
    if hasattr(state, "config") and state.config and state.config.get("configurable", {}).get("image_path"):
        logger.info("检测到图片路径，转为图片查询处理")
        return "create_image_query"

    if _type == "general-query":
        return "respond_to_general_query"
    elif _type == "additional-query":
        return "get_additional_info"
    elif _type == "graphrag-query":
        return "create_research_plan"
    elif _type == "image-query":
        return "create_image_query"
    elif _type == "file-query":
        return "create_file_query"
    else:
        raise ValueError(f"Unknown router type {_type}")
    
async def respond_to_general_query(
    state: AgentState, *, config: RunnableConfig
) -> Dict[str, List[BaseMessage]]:
    """生成对一般查询的响应，完全基于大模型，不会触发任何外部服务的调用，包括自定义工具、知识库查询等。

    当路由器将查询分类为一般问题时，将调用此节点。

    Args:
        state (AgentState): 当前代理状态，包括对话历史和路由逻辑。
        config (RunnableConfig): 用于配置响应生成的模型。

    Returns:
        Dict[str, List[BaseMessage]]: 包含'messages'键的字典，其中包含生成的响应。
    """
    logger.info("-----generate general-query response-----")
    
    # 使用大模型生成回复
    if settings.AGENT_SERVICE == ServiceType.DEEPSEEK:
        model = ChatDeepSeek(api_key=settings.DEEPSEEK_API_KEY, model_name=settings.DEEPSEEK_MODEL, temperature=0.7, tags=["general_query"])
    else:
        model = ChatOllama(model=settings.OLLAMA_AGENT_MODEL, base_url=settings.OLLAMA_BASE_URL, temperature=0.7, tags=["general_query"])
    
    system_prompt = GENERAL_QUERY_SYSTEM_PROMPT.format(
        logic=state.router["logic"]
    )
    
    messages = [{"role": "system", "content": system_prompt}] + state.messages
    response = await model.ainvoke(messages)
    return {"messages": [response]}

async def get_additional_info(
    state: AgentState, *, config: RunnableConfig
) -> Dict[str, List[BaseMessage]]:
    """生成一个响应，要求用户提供更多信息。

    当路由确定需要从用户那里获取更多信息时，将调用此函数。

    Args:
        state (AgentState): 当前代理状态，包括对话历史和路由逻辑。
        config (RunnableConfig): 用于配置响应生成的模型。

    Returns:
        Dict[str, List[BaseMessage]]: 包含'messages'键的字典，其中包含生成的响应。
    """
    logger.info("------continue to get additional info------")
    
    # 使用大模型生成回复
    if settings.AGENT_SERVICE == ServiceType.DEEPSEEK:
        model = ChatDeepSeek(api_key=settings.DEEPSEEK_API_KEY, model_name=settings.DEEPSEEK_MODEL, temperature=0.7, tags=["additional_info"])
    else:
        model = ChatOllama(model=settings.OLLAMA_AGENT_MODEL, base_url=settings.OLLAMA_BASE_URL, temperature=0.7, tags=["additional_info"])

    # 如果用户的问题是电商相关，但与自己的业务无关，则需要返回"无关问题"

    # 首先连接 Neo4j 图数据库
    neo4j_graph = None
    try:
        neo4j_graph = get_neo4j_graph()
        logger.info("success to get Neo4j graph database connection")
    except Exception as e:
        logger.error(f"failed to get Neo4j graph database connection: {e}")

    # 定义电商经营范围
    scope_description = """
    个人电商经营范围：智能家居产品，包括但不限于：
    - 智能照明（灯泡、灯带、开关）
    - 智能安防（摄像头、门锁、传感器）
    - 智能控制（温控器、遥控器、集线器）
    - 智能音箱（语音助手、音响）
    - 智能厨电（电饭煲、冰箱、洗碗机）
    - 智能清洁（扫地机器人、洗衣机）
    - 智能空气净化器
    - 智能净水器
    - 智能窗帘
    - 智能电视
    - 智能加湿器
    - 智能开关
    - 智能空调
    - 智能马桶
    - 智能门铃
    - 智能门锁
    - 智能摄像头
    - 智能手环
    - 智能体重秤
    - 智能洗衣机

    不包含：服装、鞋类、体育用品、化妆品、食品等非智能家居产品。
    """

    scope_context = (
        f"参考此范围描述来决策:\n{scope_description}"
        if scope_description is not None
        else ""
    )

    # 动态从 Neo4j 图表中获取图表结构
    graph_context = (
        f"\n参考图表结构来回答:\n{retrieve_and_parse_schema_from_graph_for_prompts(neo4j_graph)}"
        if neo4j_graph is not None
        else ""
    )

    message = scope_context + graph_context + "\nQuestion: {question}"

    # 拼接提示模版
    full_system_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                GUARDRAILS_SYSTEM_PROMPT,
            ),
            (
                "human",
                (message),
            ),
        ]
    )

    # 构建格式化输出的 Chain， 如果匹配，返回 continue，否则返回 end
    guardrails_chain = full_system_prompt | model.with_structured_output(AdditionalGuardrailsOutput)
    guardrails_output = await guardrails_chain.ainvoke(
            {"question": state.messages[-1].content if state.messages else ""}
        )

    # 根据格式化输出的结果，返回不同的响应
    if guardrails_output.decision == "end":
        logger.info("-----Fail to pass guardrails check-----")
        return {"messages": [AIMessage(content="抱歉，我家暂时没有这方面的商品，可以在别家看看哦~")]}
    else:
        logger.info("-----Pass guardrails check-----")
        system_prompt = GET_ADDITIONAL_SYSTEM_PROMPT.format(
            logic=state.router["logic"]
        )
        messages = [{"role": "system", "content": system_prompt}] + state.messages
        response = await model.ainvoke(messages)
        return {"messages": [response]}

async def create_image_query(
    state: AgentState, *, config: RunnableConfig
) -> Dict[str, List[BaseMessage]]:
    """处理图片查询并生成描述回复
    
    Args:
        state (AgentState): 当前代理状态，包括对话历史
        config (RunnableConfig): 配置参数，包含线程ID等配置信息
        
    Returns:
        Dict[str, List[BaseMessage]]: 包含'messages'键的字典，其中包含生成的响应
    """
    logger.info("-----Found User Upload Image-----")    
    image_path = config.get("configurable", {}).get("image_path", None)

    if not image_path or not Path(image_path).exists():
        logger.warning(f"User Upload Image Not Found: {image_path}")
        return {"messages": [AIMessage(content="抱歉，我无法查看这张图片，请重新上传。")]}
    
    # 获取视觉模型配置
    api_key = settings.VISION_API_KEY
    base_url = settings.VISION_BASE_URL
    vision_model = settings.VISION_MODEL
    
    if not api_key or not base_url or not vision_model:
        logger.error("Vision Model Configuration Not Complete")
        return {"messages": [AIMessage(content="抱歉，我无法查看这张图片，请重新上传。")]}
    
    logger.info(f"Using Vision Model: {vision_model} to process image: {image_path}")
    
    try:
        # 导入图片处理库
        from PIL import Image
        import io
        
        # 读取并压缩图片
        with Image.open(image_path) as img:
            # 设置最大尺寸
            max_size = 1024
            # 计算缩放比例
            width, height = img.size
            ratio = min(max_size / width, max_size / height)
            
            # 如果图片尺寸已经小于最大尺寸，不需要缩放
            if width <= max_size and height <= max_size:
                resized_img = img
            else:
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                resized_img = img.resize((new_width, new_height), Image.LANCZOS)
            
            # 转换为JPEG格式，并调整质量
            img_byte_arr = io.BytesIO()
            if resized_img.mode != 'RGB':
                resized_img = resized_img.convert('RGB')
            resized_img.save(img_byte_arr, format='JPEG', quality=85)
            img_byte_arr.seek(0)
            
            # 转换为base64
            image_data = base64.b64encode(img_byte_arr.read()).decode('utf-8')
            
            logger.info(f"Image Compressed, Original Size: {width}x{height}, New Size: {resized_img.width}x{resized_img.height}")
        
        # 构建API请求
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "model": vision_model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的图像分析助手。请详细分析图片中的内容，特别关注产品细节、品牌、型号等信息。"
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 4000,
            "temperature": 0.7
        }
        
        # 发送API请求
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60  # 增加超时时间
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    image_description = result["choices"][0]["message"]["content"]
                    logger.info(f"Successfully processed image and generated description")
                    # 使用图片描述和用户问题生成最终回复
                    # 从lg_prompts导入电商客服模板
                    
                    # 构建回复请求
                    if settings.AGENT_SERVICE == ServiceType.DEEPSEEK:
                        model = ChatDeepSeek(api_key=settings.DEEPSEEK_API_KEY, model_name=settings.DEEPSEEK_MODEL, temperature=0.7, tags=["image_query"])
                    else:
                        model = ChatOllama(model=settings.OLLAMA_AGENT_MODEL, base_url=settings.OLLAMA_BASE_URL, temperature=0.7, tags=["image_query"])
                    # 使用专门的图片查询提示模板
                    system_prompt = GET_IMAGE_SYSTEM_PROMPT.format(
                        image_description=image_description
                    )
                    messages = [{"role": "system", "content": system_prompt}] + state.messages
                    response = await model.ainvoke(messages)
                    return {"messages": [response]}    
        
                else:
                    error_text = await response.text()
                    logger.error(f"Vision API Request Failed: {response.status} - {error_text}")
                    return {"messages": [AIMessage(content=f"抱歉，我无法查看这张图片，请重新上传。")]}





    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        return {"messages": [AIMessage(content=f"抱歉，我无法查看这张图片，请重新上传。")]}

async def create_file_query(
    state: AgentState, *, config: RunnableConfig
) -> Dict[str, List[BaseMessage]]:
    """处理文件上传查询，支持图片、文本、PDF 等文件类型。

    Args:
        state: 当前代理状态
        config: 配置参数，包含 file_path 等

    Returns:
        包含处理结果的 messages
    """
    import aiohttp
    from pathlib import Path

    logger.info("-----Start File Query Processing-----")

    file_path = config.get("configurable", {}).get("file_path", None)

    if not file_path or not Path(file_path).exists():
        logger.warning(f"File Not Found: {file_path}")
        return {"messages": [AIMessage(content="抱歉，我无法读取您上传的文件，请重新上传。")]}

    file_ext = Path(file_path).suffix.lower()
    logger.info(f"Processing file: {file_path}, type: {file_ext}")

    try:
        # ========== 图片文件 ==========
        if file_ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]:
            return await _process_image_file(file_path, state, config)

        # ========== 文本/文档文件 ==========
        elif file_ext in [".txt", ".md", ".pdf", ".csv", ".json", ".xml"]:
            return await _process_document_file(file_path, state, config)

        # ========== 不支持的文件类型 ==========
        else:
            logger.warning(f"Unsupported file type: {file_ext}")
            return {"messages": [AIMessage(
                content=f"抱歉，暂时不支持 .{file_ext} 格式的文件呢。支持的文件格式包括：图片（jpg/png）、文本（txt/md）、PDF、CSV。请问您可以换个格式重新上传吗？"
            )]}

    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        return {"messages": [AIMessage(content="抱歉，文件处理过程中出了点问题，请稍后再试。")]}


async def _process_image_file(
    file_path: str,
    state: AgentState,
    config: RunnableConfig
) -> Dict[str, List[BaseMessage]]:
    """处理图片文件：复用 Vision API 提取描述，再生成回复"""
    from PIL import Image
    import io

    image_path = file_path

    if not Path(image_path).exists():
        return {"messages": [AIMessage(content="抱歉，我无法查看这张图片，请重新上传。")]}

    api_key = settings.VISION_API_KEY
    base_url = settings.VISION_BASE_URL
    vision_model = settings.VISION_MODEL

    if not api_key or not base_url or not vision_model:
        logger.error("Vision Model Configuration Not Complete")
        return {"messages": [AIMessage(content="抱歉，图片分析服务未配置，请联系管理员。")]}

    logger.info(f"Using Vision Model: {vision_model} to process image: {image_path}")

    try:
        # 读取并压缩图片
        with Image.open(image_path) as img:
            max_size = 1024
            width, height = img.size
            ratio = min(max_size / width, max_size / height)

            if width <= max_size and height <= max_size:
                resized_img = img
            else:
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                resized_img = img.resize((new_width, new_height), Image.LANCZOS)

            img_byte_arr = io.BytesIO()
            if resized_img.mode != 'RGB':
                resized_img = resized_img.convert('RGB')
            resized_img.save(img_byte_arr, format='JPEG', quality=85)
            img_byte_arr.seek(0)
            image_data = base64.b64encode(img_byte_arr.read()).decode('utf-8')

        # 调用 Vision API
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        payload = {
            "model": vision_model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的电商图像分析助手。请详细分析图片中的内容，特别关注产品细节、品牌、型号等信息，并以结构化方式描述。"
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                        }
                    ]
                }
            ],
            "max_tokens": 4000,
            "temperature": 0.7
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    image_description = result["choices"][0]["message"]["content"]
                    logger.info("Image description extracted successfully")

                    # 用描述结果生成回复
                    if settings.AGENT_SERVICE == ServiceType.DEEPSEEK:
                        model = ChatDeepSeek(
                            api_key=settings.DEEPSEEK_API_KEY,
                            model_name=settings.DEEPSEEK_MODEL,
                            temperature=0.7,
                            tags=["file_image"]
                        )
                    else:
                        model = ChatOllama(
                            model=settings.OLLAMA_AGENT_MODEL,
                            base_url=settings.OLLAMA_BASE_URL,
                            temperature=0.7,
                            tags=["file_image"]
                        )

                    system_prompt = GET_IMAGE_SYSTEM_PROMPT.format(
                        image_description=image_description
                    )
                    messages = [{"role": "system", "content": system_prompt}] + state.messages
                    response = await model.ainvoke(messages)
                    return {"messages": [response]}
                else:
                    error_text = await resp.text()
                    logger.error(f"Vision API Error: {resp.status} - {error_text}")
                    return {"messages": [AIMessage(content="抱歉，图片分析失败了，请稍后再试。")]}

    except Exception as e:
        logger.error(f"Image processing error: {str(e)}")
        return {"messages": [AIMessage(content="抱歉，图片处理失败了。")]}


async def _process_document_file(
    file_path: str,
    state: AgentState,
    config: RunnableConfig
) -> Dict[str, List[BaseMessage]]:
    """处理文档文件：提取文本内容后作为上下文查询知识库"""
    import aiohttp
    from pathlib import Path

    file_ext = Path(file_path).suffix.lower()
    extracted_text = ""

    try:
        # 读取文本文件
        if file_ext in [".txt", ".md"]:
            with open(file_path, "r", encoding="utf-8") as f:
                extracted_text = f.read()

        # 读取 JSON 文件
        elif file_ext == ".json":
            import json
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 把 JSON 展平成文本描述
            extracted_text = _flatten_json(data)

        # CSV 文件：提取表头和部分行
        elif file_ext == ".csv":
            import csv
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)
                if rows:
                    headers = rows[0]
                    sample_rows = rows[1:min(6, len(rows)+1)]
                    extracted_text = f"CSV 文件，包含列：{', '.join(headers)}\n前5行数据：\n"
                    for row in sample_rows:
                        extracted_text += f"  {', '.join(row)}\n"

        # PDF 文件（简单文本提取）
        elif file_ext == ".pdf":
            try:
                import PyPDF2
                with open(file_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    text_parts = []
                    for page in reader.pages[:5]:  # 只取前5页
                        text = page.extract_text()
                        if text:
                            text_parts.append(text)
                    extracted_text = "\n".join(text_parts)
            except ImportError:
                logger.warning("PyPDF2 not installed, skipping PDF text extraction")
                return {"messages": [AIMessage(
                    content="抱歉，系统暂不支持 PDF 文件的文本提取。可以将内容复制成 txt 格式重新上传哦～"
                )]}

        else:
            return {"messages": [AIMessage(content=f"暂不支持 .{file_ext} 格式的文件。")]}

        # 截断过长的文本
        if len(extracted_text) > 3000:
            extracted_text = extracted_text[:3000] + f"\n...[文件过长，已截断前3000字符，共{len(extracted_text)}字符]"

        logger.info(f"File text extracted, length: {len(extracted_text)} chars")

        # 用提取的文本作为上下文，结合用户问题生成回复
        if settings.AGENT_SERVICE == ServiceType.DEEPSEEK:
            model = ChatDeepSeek(
                api_key=settings.DEEPSEEK_API_KEY,
                model_name=settings.DEEPSEEK_MODEL,
                temperature=0.7,
                tags=["file_doc"]
            )
        else:
            model = ChatOllama(
                model=settings.OLLAMA_AGENT_MODEL,
                base_url=settings.OLLAMA_BASE_URL,
                temperature=0.7,
                tags=["file_doc"]
            )

        user_question = state.messages[-1].content if state.messages else ""
        system_prompt = f"""你是一个电商客服助手。用户上传了一个文件，文件内容如下：

<file_content>
{extracted_text}
</file_content>

请根据文件内容回答用户的问题。如果文件内容与电商产品相关，请结合产品信息回答。如果文件内容不足以回答问题，请说明暂时无法根据文件内容回答。

用户问题：{user_question}

回答要求：
1. 先说明已收到文件
2. 从文件中提取相关信息回答
3. 保持电商客服的友好语气
4. 不要 hallucinate，文件里没有的信息不要编造
"""

        messages = [{"role": "system", "content": system_prompt}]
        response = await model.ainvoke(messages)
        return {"messages": [response]}

    except Exception as e:
        logger.error(f"Document processing error: {str(e)}")
        return {"messages": [AIMessage(content="抱歉，文件读取失败了。")]}]


def _flatten_json(data, prefix="", max_depth=3, depth=0) -> str:
    """将 JSON 递归展平为可读文本"""
    if depth >= max_depth:
        return str(data)

    lines = []
    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, (dict, list)):
                lines.append(f"{full_key}:")
                lines.append(_flatten_json(value, full_key, max_depth, depth+1))
            else:
                lines.append(f"{full_key}: {value}")
    elif isinstance(data, list):
        for i, item in enumerate(data[:20]):  # 最多20项
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}[{i}]:")
                lines.append(_flatten_json(item, f"{prefix}[{i}]", max_depth, depth+1))
            else:
                lines.append(f"{prefix}[{i}]: {item}")
        if len(data) > 20:
            lines.append(f"...（共 {len(data)} 项，已截断）")
    else:
        lines.append(str(data))

    return "\n".join(lines)

async def create_research_plan(
    state: AgentState, *, config: RunnableConfig
) -> Dict[str, List[str] | str]:
    """通过查询本地知识库回答客户问题，执行任务分解，创建分布查询计划。

    Args:
        state (AgentState): 当前代理状态，包括对话历史。
        config (RunnableConfig): 用于配置计划生成的模型。

    Returns:
        Dict[str, List[str] | str]: 包含'steps'键的字典，其中包含研究步骤列表。
    """
    logger.info("------execute local knowledge base query------")

    # 使用大模型生成查询/多跳、并行查询计划
    if settings.AGENT_SERVICE == ServiceType.DEEPSEEK:
        model = ChatDeepSeek(api_key=settings.DEEPSEEK_API_KEY, model_name=settings.DEEPSEEK_MODEL, temperature=0.7, tags=["research_plan"])
    else:
        model = ChatOllama(model=settings.OLLAMA_AGENT_MODEL, base_url=settings.OLLAMA_BASE_URL, temperature=0.7, tags=["research_plan"])
    
    # 初始化必要参数
    # 1. Neo4j图数据库连接 - 使用配置中的连接信息
    try:
        neo4j_graph = get_neo4j_graph()
        logger.info("success to get Neo4j graph database connection")
    except Exception as e:
        logger.error(f"failed to get Neo4j graph database connection: {e}")

    # 2. 创建自定义检索器实例，根据 Graph Schema 创建 Cypher 示例，用来引导大模型生成正确的Cypher 查询语句
    cypher_retriever = NorthwindCypherRetriever()

    # step 3. 定义工具模式列表    
    from app.lg_agent.kg_sub_graph.kg_tools_list import cypher_query, predefined_cypher, microsoft_graphrag_query
    tool_schemas: List[type[BaseModel]] = [cypher_query, predefined_cypher, microsoft_graphrag_query]

    # 3. 预定义的Cypher查询 - 为电商场景定义有用的查询
    from app.lg_agent.kg_sub_graph.agentic_rag_agents.components.predefined_cypher.cypher_dict import predefined_cypher_dict

    # 定义电商经营范围
    scope_description = """
    个人电商经营范围：智能家居产品，包括但不限于：
    - 智能照明（灯泡、灯带、开关）
    - 智能安防（摄像头、门锁、传感器）
    - 智能控制（温控器、遥控器、集线器）
    - 智能音箱（语音助手、音响）
    - 智能厨电（电饭煲、冰箱、洗碗机）
    - 智能清洁（扫地机器人、洗衣机）
    - 智能空气净化器
    - 智能净水器
    - 智能窗帘
    - 智能电视
    - 智能加湿器
    - 智能开关
    - 智能空调
    - 智能马桶
    - 智能门铃
    - 智能门锁
    - 智能摄像头
    - 智能手环
    - 智能体重秤
    - 智能洗衣机

    不包含：服装、鞋类、体育用品、化妆品、食品等非智能家居产品。
    """

    # 创建多工具工作流
    multi_tool_workflow = create_multi_tool_workflow(
        llm=model,
        graph=neo4j_graph,
        tool_schemas=tool_schemas,
        predefined_cypher_dict=predefined_cypher_dict,
        cypher_example_retriever=cypher_retriever,
        scope_description=scope_description,
        llm_cypher_validation=True,
    )
    
    # return multi_tool_workflow
    # 准备输入状态
    last_message = state.messages[-1].content if state.messages else ""
    input_state = {
        "question": last_message,
        "data": [],
        "history": []
    }
    
    # 执行工作流
    response = await multi_tool_workflow.ainvoke(input_state)
    return {"messages": [AIMessage(content=response["answer"])]}

async def check_hallucinations(
    state: AgentState, *, config: RunnableConfig
) -> dict[str, Any]:
    """Analyze the user's query and checks if the response is supported by the set of facts based on the document retrieved,
    providing a binary score result.

    This function uses a language model to analyze the user's query and gives a binary score result.

    Args:
        state (AgentState): The current state of the agent, including conversation history.
        config (RunnableConfig): Configuration with the model used for query analysis.

    Returns:
        dict[str, Router]: A dictionary containing the 'router' key with the classification result (classification type and logic).
    """
    if settings.AGENT_SERVICE == ServiceType.DEEPSEEK:
        model = ChatDeepSeek(api_key=settings.DEEPSEEK_API_KEY, model_name=settings.DEEPSEEK_MODEL, temperature=0.7, tags=["hallucinations"])
    else:
        model = ChatOllama(model=settings.OLLAMA_AGENT_MODEL, base_url=settings.OLLAMA_BASE_URL, temperature=0.7, tags=["hallucinations"])
    
    system_prompt = CHECK_HALLUCINATIONS.format(
        documents=state.documents,
        generation=state.messages[-1]
    )

    messages = [
        {"role": "system", "content": system_prompt}
    ] + state.messages

    logger.info("---CHECK HALLUCINATIONS---")
    
    response = cast(GradeHallucinations, await model.with_structured_output(GradeHallucinations).ainvoke(messages))
    
    return {"hallucination": response} 


# 定义持久化存储，也可以使用SQLiteSaver()、PostgresSaver()等
# LangGraph官方地址：https://langchain-ai.github.io/langgraph/how-tos/persistence/
checkpointer = MemorySaver()

# 定义状态图
builder = StateGraph(AgentState, input=InputState)
# 添加节点
builder.add_node(analyze_and_route_query)
builder.add_node(respond_to_general_query)
builder.add_node(get_additional_info)
builder.add_node("create_research_plan", create_research_plan)  # 这里是子图
builder.add_node(create_image_query)
builder.add_node(create_file_query)

# 添加边
builder.add_edge(START, "analyze_and_route_query")
builder.add_conditional_edges("analyze_and_route_query", route_query)


graph = builder.compile(checkpointer=checkpointer)

# from IPython.display import Image, display
# display(Image(graph.get_graph().draw_mermaid_png()))