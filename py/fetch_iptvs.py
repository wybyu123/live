import json
import os
import requests
from collections import defaultdict

# 目标网址
target_url = "https://iptvs.pes.im"
output_json_file = "iptvs_data.json"

# 🔗 第二输入源地址（支持 GitHub 仓库的 raw 直连地址或任何标准 JSON 接口）
# 请将此处的 URL 替换为你实际的第二输入源直链地址
SECOND_SOURCE_URL = "https://raw.githubusercontent.com/wybyu123/123/main/iptvs_data.json"

def fetch_and_process_iptvs():
    print(f"正在请求主网址: {target_url} ...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    combined_results = []
    version_str = "1.1"
    existing_storage_data = []

    try:
        # ================= 1. 获取并解析主源数据 =================
        response = requests.get(target_url, headers=headers, timeout=10)
        if response.status_code == 200:
            json_data = response.json()
            version_str = json_data.get("message", {}).get("version", version_str)
            existing_storage_data = json_data.get("storageData", [])
            
            main_results = json_data.get("results", [])
            combined_results.extend(main_results)
            print(f"[成功] 从主源成功获取 {len(main_results)} 条记录。")
        else:
            print(f"[错误] 主源请求失败，服务器返回状态码: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"[错误] 主源网络请求发生异常: {e}")
    except ValueError:
        print("[错误] 主源返回的内容不是有效的 JSON 格式。")

    # ================= 2. 获取并引入第二输入源数据 =================
    print(f"正在请求第二输入源: {SECOND_SOURCE_URL} ...")
    try:
        sec_response = requests.get(SECOND_SOURCE_URL, headers=headers, timeout=10)
        if sec_response.status_code == 200:
            sec_json_data = sec_response.json()
            sec_results = sec_json_data.get("results", [])
            if sec_results:
                combined_results.extend(sec_results)
                print(f"[成功] 从第二输入源成功引入 {len(sec_results)} 条记录。")
            else:
                print("[提示] 第二输入源中未找到 results 列表或列表为空。")
        else:
            print(f"[提示] 第二输入源请求失败，状态码: {sec_response.status_code}，将仅使用主源数据继续。")
    except Exception as e:
        print(f"[提示] 第二输入源请求或解析异常: {e}，将仅使用主源数据继续。")

    if not combined_results:
        print("[错误] 合并后的 results 列表为空，终止后续生成。")
        return

    # ================= 3. 数据去重与清洗（基于 host 或 link 避免重复） =================
    unique_results = []
    seen_identifiers = set()
    for item in combined_results:
        # 优先使用 host 作为去重主键，其次退化为 link
        identifier = item.get("host") or item.get("link")
        if identifier and identifier not in seen_identifiers:
            seen_identifiers.add(identifier)
            unique_results.append(item)

    total_count = len(unique_results)

    # ================= 4. 构建并保存最终的 iptvs_data.json =================
    final_output_data = {
        "storageSummary": {
            "totalStoredCount": total_count
        },
        "message": {
            "version": version_str
        },
        "storageData": existing_storage_data,
        "results": unique_results
    }

    json_path = os.path.join(current_dir, output_json_file)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(final_output_data, f, ensure_ascii=False, indent=4)
    print(f"[成功] 合并后的完整 JSON 数据已保存至: {json_path}（总计有效记录: {total_count} 条）")

    # ================= 5. 按 matchType 分类生成对应的 txt 文件 =================
    categorized_links = defaultdict(list)
    for item in unique_results:
        match_type = item.get("matchType", "unknown")
        link = item.get("link")
        if link:
            categorized_links[match_type].append(link)

    for match_type, links in categorized_links.items():
        txt_filename = f"{match_type}.txt"
        txt_path = os.path.join(current_dir, txt_filename)
        
        unique_links = sorted(list(set(links)), key=links.index)
        with open(txt_path, 'w', encoding='utf-8') as f:
            for link in unique_links:
                f.write(link + '\n')
                
        print(f"[分类生成] 已生成 {txt_filename}，包含 {len(unique_links)} 个可用链接。")

if __name__ == "__main__":
    fetch_and_process_iptvs()
