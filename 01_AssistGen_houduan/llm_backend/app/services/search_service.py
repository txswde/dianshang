from typing import List, Dict, AsyncGenerator, Optional, Callable
import json
import asyncio
from app.tools.search import SearchTool
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.logger import get_logger
from app.tools.definitions import SEARCH_TOOL, TOOL_DEFINITIONS
from app.services.function_tools import ToolRegistry, FunctionTool
from app.prompts.search_prompts import SEARCH_SYSTEM_PROMPT, SEARCH_SUMMARY_PROMPT, format_search_context
from datetime import datetime

logger = get_logger(service="search")

class SearchService:
    def __init__(self):
        logger.info("Initializing SearchService...")
        self.client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL
        )
        self.model = settings.DEEPSEEK_MODEL
        self.search_tool = SearchTool()
        
        # 鍒濆鍖栧伐鍏锋敞鍐屼腑蹇?        self.tool_registry = ToolRegistry()
        
        # 娉ㄥ唽鎼滅储宸ュ叿 - 鐩存帴浣跨敤瀹氫箟濂界殑鎻忚堪
        self.tool_registry.register(FunctionTool(
            **SEARCH_TOOL,  # 灞曞紑宸ュ叿瀹氫箟
            handler=self._handle_search
        ))
        
        # 鐢熸垚宸ュ叿鎻忚堪鎻愮ず
        self.tools_description = self._generate_tools_description()

    def _generate_tools_description(self) -> str:
        """Generate a textual description of registered tools."""
        tool_descriptions = []
        
        for tool_def in self.tool_registry.get_tools_definition():
            func = tool_def["function"]
            name = func["name"]
            desc = func["description"]
            params = []
            
            # 鑾峰彇蹇呴渶鍙傛暟鍙婂叾鎻忚堪
            for param_name, param_info in func["parameters"]["properties"].items():
                if param_name in func["parameters"].get("required", []):
                    params.append(f"{param_name}: {param_info['description']}")
            
            tool_desc = (
                f"{name}: {desc}"
                f"{'; required params: ' if params else ''}"
                f"{', '.join(params)}"
            )
            tool_descriptions.append(tool_desc)
        
        return (
            "Available tools:\n\n" + 
            "\n".join(tool_descriptions)
        )

    async def _handle_search(self, query: str) -> List[Dict]:
        """Handle a search request."""
        return await asyncio.to_thread(self.search_tool.search, query)

    async def _call_with_tool(self, query: str) -> Dict:
        """Call the model and return the selected tool call."""
        try:
            logger.info(f"Calling model with query: {query}")
            

            logger.info(f"Messages: {query}")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=query,
                tools=self.tool_registry.get_tools_definition(),
                tool_choice="auto"
            )
            
            logger.info(f"Model response: {response.choices[0]}")
            return response.choices[0]
            
        except Exception as e:
            logger.error(f"Error in _call_with_tool: {str(e)}", exc_info=True)
            raise

    async def generate_stream(
        self, 
        query: str,
        user_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        on_complete: Optional[Callable] = None
    ) -> AsyncGenerator[str, None]:
        """Stream a response with optional web search."""
        try:
            logger.info(f"Starting search generation for query: {query}")
            
            # 浣跨敤鏍煎紡鍖栫殑绯荤粺鎻愮ず
            messages = [
                {
                    "role": "system",
                    "content": SEARCH_SYSTEM_PROMPT.format(
                        tools_description=self.tools_description
                    )
                },
                {
                    "role": "user",
                    "content": query
                }
            ]

            # 绗竴姝ワ細鑾峰彇宸ュ叿璋冪敤
            choice = await self._call_with_tool(messages)
            logger.info(f"Tool call response: {choice}")
            
            # 鏍规嵁finish_reason鍐冲畾澶勭悊鏂瑰紡
            if choice.finish_reason == "tool_calls":
                # 闇€瑕佹悳绱㈢殑鎯呭喌
                tool_calls = choice.message.tool_calls
                if tool_calls:
                    tool_call = tool_calls[0]
                    logger.info(f"Processing tool call: {tool_call}")
                    
                    try:
                        # 鎵ц宸ュ叿璋冪敤
                        search_results = await self.tool_registry.execute_tool(
                            tool_call.function.name,
                            tool_call.function.arguments
                        )
                        logger.info(f"Got {len(search_results)} search results")
                        
                        if search_results:
                            context = []
                            for result in search_results:
                                context.append(
                                    f"Source: {result['title']}\n"
                                    f"URL: {result['url']}\n"
                                    f"Content: {result['snippet']}\n"
                                )
                            
                            # 鏋勯€犲甫涓婁笅鏂囩殑鎻愮ず
                            context_prompt = SEARCH_SUMMARY_PROMPT.format(
                                context="\n---\n".join(context),
                                query=query,
                                cur_date=datetime.now().strftime("%Y-%m-%d")
                            )
                            
                            # 鍏堣繑鍥炰竴涓被鍨嬫爣璇嗭紝鍛婅瘔鍓嶇杩欐槸鎼滅储缁撴灉
                            yield f"data: {json.dumps({'type': 'search_start'}, ensure_ascii=False)}\n\n"
                            
                            # 杩斿洖鎼滅储缁撴灉
                            search_data = {
                                "type": "search_results",  # 淇濇寔鍘熸湁鐨勭被鍨嬫爣璇?                                "total": len(search_results),
                                "query": json.loads(tool_call.function.arguments)["query"],
                                "results": [
                                    {
                                        "title": result["title"],
                                        "url": result["url"],
                                        "snippet": result["snippet"]
                                    }
                                    for result in search_results
                                ]
                            }
                            yield f"data: {json.dumps(search_data, ensure_ascii=False)}\n\n"
                            
                            stream = await self.client.chat.completions.create(
                                model=self.model,
                                messages=[
                                    {"role": "system", "content": context_prompt}
                                ],
                                stream=True
                            )
                            async for chunk in stream:      

                                if chunk.choices[0].delta.content:
                                    content = json.dumps(chunk.choices[0].delta.content, ensure_ascii=False)
                                    yield f"data: {content}\n\n"
             
                    except Exception as e:
                        pass
                
            elif choice.finish_reason == "stop":
                # 鐩存帴鍥炵瓟鐨勬儏鍐碉紝浣跨敤娴佸紡鍝嶅簲
                logger.info("Model chose to answer directly, streaming response...")
                
                # 鍏堣繑鍥炰竴涓被鍨嬫爣璇嗭紝鍛婅瘔鍓嶇杩欐槸鐩存帴鍥炵瓟
                yield f"data: {json.dumps({'type': 'direct_answer'}, ensure_ascii=False)}\n\n"
                
                # 浣跨敤娴佸紡API閲嶆柊鐢熸垚鍥炵瓟
                stream_response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    stream=True
                )
                
                full_response = []
                async for chunk in stream_response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response.append(content)
                        data = json.dumps({
                            "type": "direct_content",
                            "content": content
                        }, ensure_ascii=False)
                        yield f"data: {data}\n\n"
                
                if on_complete and user_id is not None and conversation_id is not None:
                    complete_response = "".join(full_response)
                    await on_complete(user_id, conversation_id, [{"role": "user", "content": query}], complete_response)
                
        except Exception as e:
            logger.error(f"Error in generate_stream: {str(e)}", exc_info=True)
            raise
