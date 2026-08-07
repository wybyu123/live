import os
import requests
import warnings
from urllib.parse import urlparse
import time

# 禁用安全请求警告
warnings.filterwarnings("ignore")

# --- 动态路径与配置 ---
BASE_PATH = os.getcwd()
INPUT_FILE = os.path.join(BASE_PATH, "py", "1000_alive.txt")
M3U_FILE = os.path.join(BASE_PATH, "py", "all_channels.m3u")
TIMEOUT = 8        # 适当将超时时间从 5 秒放宽到 8 秒，应对云端网络延迟
MAX_RETRIES = 2    # 失败后自动重试次数

def get_base_url(url):
    """提取基础前缀，如 http://1.192.12.116:9901"""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

def parse_hotel_json(url):
    """解析并补全播放地址（增加重试与更完善的请求头）"""
    base_prefix = get_base_url(url)
    ip_only = urlparse(url).netloc.split(':')[0]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Connection': 'keep-alive'
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, timeout=TIMEOUT, headers=headers, verify=False)
            if response.status_code == 200:
                # 尝试解析 JSON
                try:
                    data = response.json()
                except Exception:
                    # 如果返回的不是标准 JSON，尝试清理或跳过
                    continue

                items = []
                if isinstance(data, list): 
                    items = data
                elif isinstance(data, dict):
                    items = data.get('data') or data.get('list') or data.get('channels') or []
                
                channels = []
                for item in items:
                    name = item.get('name') or item.get('title') or item.get('ChannelName')
                    raw_path = item.get('url') or item.get('playUrl') or item.get('ChannelUrl')
                    
                    if name and raw_path:
                        raw_path = str(raw_path).strip()
                        if raw_path.startswith('/'):
                            full_url = base_prefix + raw_path
                        elif raw_path.startswith('http'):
                            full_url = raw_path
                        else:
                            full_url = base_prefix + '/' + raw_path
                            
                        channels.append({"name": name, "url": full_url, "group": ip_only})
                return channels
        except Exception as e:
            if attempt == MAX_RETRIES:
                print(f"⚠️ 解析失败 {url} (已重试 {MAX_RETRIES} 次): {e}")
            else:
                time.sleep(1) # 重试前小憩
    return []

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 错误：找不到存活源文件 {INPUT_FILE}")
        return

    all_m3u_lines = ["#EXTM3U"]
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"📡 正在修复并补全 {len(urls)} 个源的播放地址...")

    success_count = 0
    for url in urls:
        ip_only = urlparse(url).netloc.split(':')[0]
        channels = parse_hotel_json(url)
        
        if not channels: 
            continue

        for ch in channels:
            all_m3u_lines.append(f'#EXTINF:-1 tvg-name="{ch["name"]}" group-title="{ch["group"]}",{ch["name"]}')
            all_m3u_lines.append(ch['url'])
        
        success_count += 1
        print(f"✅ [{success_count}] 已完成解析并并入 M3U: {ip_only} (包含频道数: {len(channels)})")

    # 确保保存全量 m3u 的文件夹存在
    os.makedirs(os.path.dirname(M3U_FILE), exist_ok=True)
    with open(M3U_FILE, 'w', encoding='utf-8') as f_m3u:
        f_m3u.write("\n".join(all_m3u_lines))

    print(f"\n🎉 全部完成！总 M3U 文件已更新至: {M3U_FILE}，成功解析源数量: {success_count}/{len(urls)}")

if __name__ == "__main__":
    main()
