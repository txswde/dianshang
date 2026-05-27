#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
娴嬭瘯鍗曚釜鍥剧墖鎻忚堪鐢熸垚鍔熻兘鐨勭嫭绔嬭剼鏈?
"""

import os
import sys
import argparse
import logging
import json
from pathlib import Path
import time
import base64
import requests

# 閰嶇疆鏃ュ織
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('image_description_test.log')
    ]
)

log = logging.getLogger("image_description_test")

def generate_single_image_description(
    image_path, 
    output_file=None,
    api_key=os.getenv("OPENAI_API_KEY", ""),
    model="gpt-4o",
    max_retries=3,
    retry_delay=2,
    max_tokens=300,
    temperature=0.7
):
    """涓哄崟涓浘鐗囩敓鎴愭弿杩?""
    # 妫€鏌ュ浘鐗囨枃浠舵槸鍚﹀瓨鍦?
    if not image_path.exists() or not image_path.is_file():
        log.error(f"鍥剧墖鏂囦欢涓嶅瓨鍦ㄦ垨涓嶆槸鏂囦欢: {image_path}")
        return None
    
    log.info(f"寮€濮嬪鐞嗗浘鐗? {image_path}")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # 璇诲彇鍥剧墖骞惰浆鎹负base64
    try:
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode('utf-8')
        
        # 鏋勫缓璇锋眰
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "浣犳槸涓€涓笓涓氱殑鍥惧儚鎻忚堪鍔╂墜銆傝璇︾粏鎻忚堪鍥剧墖涓殑鍐呭锛屽寘鎷富瑕佸璞°€佸満鏅€侀鑹层€佸竷灞€绛夊叧閿俊鎭€傛弿杩板簲璇ュ瑙傘€佸噯纭€佸叏闈€?
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "璇疯缁嗘弿杩拌繖寮犲浘鐗囩殑鍐呭:"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        # 鍙戦€佽姹傚苟鑾峰彇鍝嶅簲
        for attempt in range(max_retries):
            try:
                log.info(f"鍙戦€丄PI璇锋眰 (灏濊瘯 {attempt+1}/{max_retries})")
                response = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    description = result["choices"][0]["message"]["content"]
                    log.info(f"鎴愬姛鐢熸垚鍥剧墖鎻忚堪")
                    
                    # 淇濆瓨缁撴灉
                    if output_file:
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump({str(image_path): description}, f, ensure_ascii=False, indent=2)
                        log.info(f"鎻忚堪宸蹭繚瀛樺埌: {output_file}")
                    
                    return description
                else:
                    log.error(f"API璇锋眰澶辫触: {response.status_code} - {response.text}")
                    if attempt < max_retries - 1:
                        log.info(f"绛夊緟 {retry_delay * (attempt + 1)} 绉掑悗閲嶈瘯...")
                        time.sleep(retry_delay * (attempt + 1))
            except Exception as e:
                log.error(f"澶勭悊鍥剧墖鏃跺嚭閿? {str(e)}")
                if attempt < max_retries - 1:
                    log.info(f"绛夊緟 {retry_delay * (attempt + 1)} 绉掑悗閲嶈瘯...")
                    time.sleep(retry_delay * (attempt + 1))
        
        log.error("鎵€鏈夊皾璇曞潎澶辫触")
        return "[鎻忚堪鐢熸垚澶辫触: 澶氭灏濊瘯鍚庝粛鐒跺け璐"
    
    except Exception as e:
        log.error(f"璇诲彇鍥剧墖澶辫触: {str(e)}")
        return f"[鎻忚堪鐢熸垚澶辫触: 鏃犳硶璇诲彇鍥剧墖 - {str(e)}]"


def main():
    """涓诲嚱鏁?""
    parser = argparse.ArgumentParser(description='娴嬭瘯鍗曚釜鍥剧墖鎻忚堪鐢熸垚鍔熻兘')
    parser.add_argument('--image_path', type=str, required=True, help='鍥剧墖鏂囦欢璺緞')
    parser.add_argument('--output_file', type=str, default='image_description.json', help='杈撳嚭鏂囦欢璺緞')
    parser.add_argument('--model', type=str, default='gpt-4o', help='浣跨敤鐨勬ā鍨嬪悕绉?)
    parser.add_argument('--max_tokens', type=int, default=300, help='鐢熸垚鎻忚堪鐨勬渶澶oken鏁?)
    parser.add_argument('--temperature', type=float, default=0.7, help='鐢熸垚鎻忚堪鐨勯殢鏈烘€э紝0-1涔嬮棿')
    
    args = parser.parse_args()
    
    # 妫€鏌ュ浘鐗囨枃浠?
    image_path = Path(args.image_path)
    if not image_path.exists():
        log.error(f"鍥剧墖鏂囦欢涓嶅瓨鍦? {image_path}")
        return 1
    
    # 璁剧疆杈撳嚭鏂囦欢
    output_file = Path(args.output_file)
    
    # 璁板綍鍙傛暟
    log.info(f"鍥剧墖鏂囦欢: {image_path}")
    log.info(f"杈撳嚭鏂囦欢: {output_file}")
    log.info(f"浣跨敤妯″瀷: {args.model}")
    log.info(f"鏈€澶oken鏁? {args.max_tokens}")
    log.info(f"娓╁害: {args.temperature}")
    
    # 寮€濮嬪鐞?
    start_time = time.time()
    log.info("寮€濮嬬敓鎴愬浘鐗囨弿杩?..")
    
    try:
        description = generate_single_image_description(
            image_path=image_path,
            output_file=output_file,
            model=args.model,
            max_tokens=args.max_tokens,
            temperature=args.temperature
        )
        
        if description:
            log.info(f"澶勭悊瀹屾垚锛屾弿杩板凡淇濆瓨鍒? {output_file}")
            log.info(f"鎻忚堪鍐呭:\n{description}")
        else:
            log.error("鐢熸垚鎻忚堪澶辫触")
        
        # 鎵撳嵃澶勭悊鏃堕棿
        elapsed_time = time.time() - start_time
        log.info(f"鎬诲鐞嗘椂闂? {elapsed_time:.2f} 绉?)
        
        return 0 if description else 1
    
    except Exception as e:
        log.error(f"澶勭悊杩囩▼涓嚭閿? {str(e)}")
        import traceback
        log.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main()) 