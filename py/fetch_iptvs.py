import json
import os
import requests
from collections import defaultdict

# 目标网址
target_url = "https://iptvs.pes.im"
output_json_file = "iptvs_data.json"

def fetch_and_process_iptvs():
    print(f"正在请求网址: {target_url} ...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(target_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            json_data = response.json()
            current_dir = os.path.dirname(os.path.abspath(__file__))
            
            # 1. 保存完整的 JSON 文件
            json_path = os.path.join(current_dir, output_json_file)
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=4)
            print(f"[成功] 完整 JSON 数据已保存至: {json_path}")
            
            # 2. 提取 results 列表并按 matchType 分类
            results = json_data.get("results", [])
            if not results:
                print("[提示] JSON 数据中未找到 results 列表。")
                return

            # 使用 defaultdict 按 matchType 归类 link
            categorized_links = defaultdict(list)
            for item in results:
                match_type = item.get("matchType", "unknown")
                link = item.get("link")
                if link:
                    categorized_links[match_type].append(link)
                    
            # 3. 针对每一个 matchType 分类生成对应的 txt 文件
            for match_type, links in categorized_links.items():
                txt_filename = f"{match_type}.txt"
                txt_path = os.path.join(current_dir, txt_filename)
                
                # 写入文件，每个链接占一行，且去重保持顺序
                unique_links = sorted(list(set(links)), key=links.index)
                with open(txt_path, 'w', encoding='utf-8') as f:
                    for link in unique_links:
                        f.write(link + '\n')
                        
                print(f"[分类生成] 已生成 {txt_filename}，包含 {len(unique_links)} 个可用链接。")
                
        else:
            print(f"[错误] 请求失败，服务器返回状态码: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"[错误] 网络请求发生异常: {e}")
    except ValueError:
        print("[错误] 服务器返回的内容不是有效的 JSON 格式。")

if __name__ == "__main__":
    fetch_and_process_iptvs()
