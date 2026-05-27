from typing import Any, Callable, Coroutine, Dict, List
import asyncio
import os
from pathlib import Path
from pydantic import BaseModel, Field

# 瀵煎叆GraphRAG鐩稿叧妯″潡
import app.graphrag.graphrag.api as api
from app.graphrag.graphrag.config.load_config import load_config
from app.graphrag.graphrag.callbacks.noop_query_callbacks import NoopQueryCallbacks
from app.graphrag.graphrag.utils.storage import load_table_from_storage
from app.graphrag.graphrag.storage.file_pipeline_storage import FilePipelineStorage
from app.lg_agent.kg_sub_graph.kg_neo4j_conn import get_neo4j_graph
from app.core.logger import get_logger
from langchain_ollama import ChatOllama
from langchain_deepseek import ChatDeepSeek
from app.core.config import settings, ServiceType
from app.lg_agent.kg_sub_graph.agentic_rag_agents.retrievers.cypher_examples.northwind_retriever import NorthwindCypherRetriever
from app.lg_agent.kg_sub_graph.agentic_rag_agents.components.cypher_tools.utils import create_text2cypher_generation_node, create_text2cypher_validation_node, create_text2cypher_execution_node



# 鑾峰彇鏃ュ織璁板綍鍣?
logger = get_logger(service="cypher_tools")

# 瀹氫箟GraphRAG鏌ヨ鐨勮緭鍏ョ姸鎬佺被鍨?
class CypherQueryInputState(BaseModel):
    task: str
    query: str
    steps: List[str]

# 瀹氫箟GraphRAG鏌ヨ鐨勮緭鍑虹姸鎬佺被鍨?
class CypherQueryOutputState(BaseModel):
    task: str
    query: str
    errors: List[str]
    records: Dict[str, Any]
    steps: List[str]

# 瀹氫箟GraphRAG API鍖呰鍣?

def create_cypher_query_node(
) -> Callable[
    [CypherQueryInputState],
    Coroutine[Any, Any, Dict[str, List[CypherQueryOutputState] | List[str]]],
]:
    """
    鍒涘缓 Text2Cypher 鏌ヨ鑺傜偣锛岀敤浜嶭angGraph宸ヤ綔娴併€?

    杩斿洖
    -------
    Callable[[CypherQueryInputState], Dict[str, List[CypherQueryOutputState] | List[str]]]
        鍚嶄负`cypher_query`鐨凩angGraph鑺傜偣銆?
    """

    async def cypher_query(
        state: Dict[str, Any],
    ) -> Dict[str, List[CypherQueryOutputState] | List[str]]:
        """
        鎵цText2Cypher鏌ヨ骞惰繑鍥炵粨鏋溿€?
        """
        errors = list()
        # 鑾峰彇鏌ヨ鏂囨湰
        query = state.get("task", "")
        if not query:
            errors.append("鏈彁渚涙煡璇㈡枃鏈?)
 
        # 浣跨敤澶фā鍨嬫墽琛屾煡璇?澶氳烦/骞惰鏌ヨ璁″垝
        # 1. 鏍规嵁.env鏂囦欢涓瑼GENT_SERVICE鐨勮缃紝閫夋嫨浣跨敤DeepSeek鎴朞llama鍚姩鐨勬ā鍨嬫湇鍔?
        if settings.AGENT_SERVICE == ServiceType.DEEPSEEK:
            model = ChatDeepSeek(api_key=settings.DEEPSEEK_API_KEY, model_name=settings.DEEPSEEK_MODEL, temperature=0.7, tags=["research_plan"])
        else:
            model = ChatOllama(model=settings.OLLAMA_AGENT_MODEL, base_url=settings.OLLAMA_BASE_URL, temperature=0.7, tags=["research_plan"])

        # 2. 鑾峰彇Neo4j鍥炬暟鎹簱杩炴帴
        try:
            neo4j_graph = get_neo4j_graph()
            logger.info("success to get Neo4j graph database connection")
        except Exception as e:
            logger.error(f"failed to get Neo4j graph database connection: {e}")

        # step 2. 鍒涘缓鑷畾涔夋绱㈠櫒瀹炰緥锛屾牴鎹?Graph Schema 鍒涘缓 Cypher 绀轰緥锛岀敤鏉ュ紩瀵煎ぇ妯″瀷鐢熸垚姝ｇ‘鐨凜ypher 鏌ヨ璇彞
        cypher_retriever = NorthwindCypherRetriever()

        # Step 3.鏍规嵁鑷畾涔夌殑 Cypher 绀轰緥锛屽紩瀵煎ぇ妯″瀷鐢熸垚 褰撳墠杈撳叆 闂鐨?Cypher 鏌ヨ璇彞
        cypher_generation = create_text2cypher_generation_node(
            llm=model, graph=neo4j_graph, cypher_example_retriever=cypher_retriever
        )

        cypher_result = await cypher_generation(state)
        logger.info(f"[DEBUG] Generated Cypher: {cypher_result}")
        #  TODO: Example 1. 鐩存帴浣跨敤澶фā鍨嬬敓鎴?Cypher 鏌ヨ璇彞
        """
        # 瀹夎渚濊禆
        pip install neo4j-graphrag
        
        from neo4j_graphrag.retrievers import Text2CypherRetriever
        from neo4j_graphrag.llm import OpenAILLM
        import time
        import pandas as pd
        from neo4j import GraphDatabase

        NEO4J_URI="bolt://localhost"
        NEO4J_USERNAME="neo4j"
        NEO4J_PASSWORD=os.getenv("NEO4J_PASSWORD", "")
        NEO4J_DATABASE="neo4j"

        driver = GraphDatabase.driver(
            NEO4J_URI, 
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
            )

        # 杩欓噷鍙互濉啓 DeepSeek 妯″瀷
        client = OpenAILLM(api_key=os.getenv("DEEPSEEK_API_KEY", ""), base_url="https://api.deepseek.com", model_name='deepseek-chat')

        
        # 瀹氫箟鐢ㄦ埛杈撳叆锛?
        examples = [
        "USER INPUT: 'Which actors starred in the Matrix?' QUERY: MATCH (p:Person)-[:ACTED_IN]->(m:Movie) WHERE m.title = 'The Matrix' RETURN p.name"
        ]

        # 鍒濆鍖栨绱㈠櫒
        retriever = Text2CypherRetriever(
            driver=driver,
            llm=client,
            neo4j_schema=neo4j_schema,  # 鍙互閫氳繃 retrieve_and_parse_schema_from_graph_for_prompts 鑾峰彇鍔ㄦ€佺殑Schema
            examples=examples,
        )

        
        # 鎵ц妫€绱細
        query_text = "muyu 閮芥湁鍝簺鏈嬪弸锛?
        print(retriever.search(query_text=query_text))
        """

        # step 4. 楠岃瘉鐢熸垚鐨?Cypher 鏌ヨ璇彞鏄惁姝ｇ‘
        validate_cypher = create_text2cypher_validation_node(
            llm=model,
            graph=neo4j_graph,
            llm_validation=True,
            cypher_statement=cypher_result
        )

        # step 5. 鑾峰彇鎵цCypher鏌ヨ鐨勫叏閮ㄤ俊鎭?
        execute_info = await validate_cypher(state=state)
        logger.info(f"[DEBUG] Validated Cypher Statement: {execute_info.get('statement', 'N/A')}")
        logger.info(f"[DEBUG] Validation Errors: {execute_info.get('errors', [])}")

        # step 6. 鎵ц Cypher 鏌ヨ璇彞
        execute_cypher = create_text2cypher_execution_node(
            graph=neo4j_graph, cypher=execute_info
        )

        final_result = await execute_cypher(state)
        logger.info(f"[DEBUG] Execution records: {final_result.get('cyphers', [{}])[0].get('records', 'N/A') if final_result.get('cyphers') else 'N/A'}")

        # 灏佽 鍗曟瀛愪换鍔℃墽琛岀殑 杈撳嚭缁撴灉骞堕€氳繃Pydantic妯″瀷闄愬畾鏍煎紡
        return {
            "cyphers": [
                CypherQueryOutputState(
                        **{
                            "task": state.get("task", ""),
                            "query": query,
                            "statement": "",
                            "parameters":"",
                            "errors": errors,
                            "records": {"result": final_result["cyphers"][0]["records"]} if final_result.get("cyphers") and len(final_result["cyphers"]) > 0 else {"result": []},
                            "steps": ["execute_cypher_query"],
                        }
                    )
                ],
                "steps": ["execute_cypher_query"],
            }
  
    return cypher_query

