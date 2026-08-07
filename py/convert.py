import requests
import os
import re
from urllib.parse import urlparse

# --- 配置区 ---
INPUT_FILE = "py/1000_alive.txt"
M3U_FILE = "py/all_channels.m3u"
TIMEOUT = 5

def get_base_url(url):
    """提取基础前缀，如 http://1.192.12.116:9901"""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

def parse_hotel_json(url):
    """解析并补全播放地址"""
    base_prefix = get_base_url(url)
    ip_only = urlparse(url).netloc.split(':')[0]
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Viera; rv:34.0) Gecko/20100101 Firefox/34.0'}
        response = requests.get(url, timeout=TIMEOUT, headers=headers)
        if response.status_code == 200:
            data = response.json()
            channels = []
            
            # 兼容各种酒店源嵌套结构
            items = []
            if isinstance(data, list): items = data
            elif 'data' in data: items = data['data']
            elif 'list' in data: items = data['list']
            
            for item in items:
                name = item.get('name') or item.get('title') or item.get('ChannelName')
                raw_path = item.get('url') or item.get('playUrl') or item.get('ChannelUrl')
                
                if name and raw_path:
                    # --- 核心逻辑：补全 IP 地址 ---
                    if raw_path.startswith('/'):
                        full_url = base_prefix + raw_path
                    elif raw_path.startswith('http'):
                        full_url = raw_path
                    else:
                        full_url = base_prefix + '/' + raw_path
                        
                    channels.append({"name": name, "url": full_url, "group": ip_only})
            return channels
    except Exception as e:
        print(f"解析失败 {url}: {e}")
    return []

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"错误：找不到存活源文件 {INPUT_FILE}")
        return

    all_m3u_lines = ["#EXTM3U"]
    
    with open(INPUT_FILE, 'r') as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"正在修复并补全 {len(urls)} 个源的播放地址...")

    for url in urls:
        ip_only = urlparse(url).netloc.split(':')[0]
        channels = parse_hotel_json(url)
        
        if not channels: 
            continue

        # 改造点：删除了创建 iptv_results 目录和写入独立 txt 的逻辑
        for ch in channels:
            # 仅写入统一的 M3U 缓存数组
            all_m3u_lines.append(f'#EXTINF:-1 tvg-name="{ch["name"]}" group-title="{ch["group"]}",{ch["name"]}')
            all_m3u_lines.append(ch['url'])
        
        print(f"✅ 已完成解析并并入 M3U: {ip_only}")

    # 确保保存全量 m3u 的文件夹存在
    os.makedirs(os.path.dirname(M3U_FILE), exist_ok=True)
    with open(M3U_FILE, 'w', encoding='utf-8') as f_m3u:
        f_m3u.write("\n".join(all_m3u_lines))

    print(f"\n全部完成！总 M3U 文件已更新至: {M3U_FILE}")

if __name__ == "__main__":
    main()
