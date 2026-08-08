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
HOTELS_DIR = os.path.join(BASE_PATH, "hotels")  # 单独分类存放的文件夹
TIMEOUT = 8         # 超时时间
MAX_RETRIES = 2     # 失败后自动重试次数

def get_base_url(url):
    """提取基础前缀，如 http://1.192.12.116:9901"""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

def get_ip_location(ip):
    """通过免费接口查询 IP 属地（省份），失败时返回未知"""
    try:
        # 使用 ip-api.com 的中文查询接口
        url = f"http://ip-api.com/json/{ip}?lang=zh-CN"
        response = requests.get(url, timeout=4)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                # 返回省份，如 "上海"、"江苏"、"广东"
                region = data.get('regionName', '').strip()
                if region:
                    # 去掉常见的“省”、“市”、“自治区”等后缀，让文件名更精简（可选）
                    region = region.replace('省', '').replace('市', '').replace('自治区', '').replace('壮族', '').replace('回族', '').replace('维吾尔', '')
                    return region
    except Exception:
        pass
    return "未知属地"

def parse_hotel_json(url):
    """解析 JSON 并智能转换组播或标准 HTTP 播放地址"""
    base_prefix = get_base_url(url)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Connection': 'keep-alive'
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, timeout=TIMEOUT, headers=headers, verify=False)
            if response.status_code == 200:
                try:
                    data = response.json()
                except Exception:
                    continue

                items = []
                if isinstance(data, list): 
                    items = data
                elif isinstance(data, dict):
                    items = data.get('data') or data.get('list') or data.get('channels') or []
                
                channels = []
                netloc_identifier = urlparse(url).netloc  # 获取包含端口的完整地址
                
                for item in items:
                    name = item.get('name') or item.get('title') or item.get('ChannelName')
                    raw_path = item.get('url') or item.get('playUrl') or item.get('ChannelUrl')
                    chid = item.get('chid')  # 获取 chid 字段，用于组播转换
                    
                    if name and raw_path:
                        raw_path = str(raw_path).strip()
                        
                        # --- 核心转换逻辑 ---
                        if raw_path.startswith('udp://'):
                            if chid is not None:
                                full_url = f"{base_prefix}/tsfile/live/{chid}_1.m3u8?key=txiptv&playlive=1&authid=0"
                            else:
                                continue
                        elif raw_path.startswith('/'):
                            full_url = base_prefix + raw_path
                        elif raw_path.startswith('http'):
                            full_url = raw_path
                        else:
                            full_url = base_prefix + '/' + raw_path
                            
                        channels.append({"name": name, "url": full_url, "group": netloc_identifier})
                return channels
        except Exception as e:
            if attempt == MAX_RETRIES:
                print(f"⚠️ 解析失败 {url} (已重试 {MAX_RETRIES} 次): {e}")
            else:
                time.sleep(1)
    return []

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 错误：找不到存活源文件 {INPUT_FILE}")
        return

    # 创建 hotels 目录
    os.makedirs(HOTELS_DIR, exist_ok=True)

    all_m3u_lines = ["#EXTM3U"]
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"📡 正在修复并转换 {len(urls)} 个源的播放地址...")

    success_count = 0
    for url in urls:
        parsed_url = urlparse(url)
        ip = parsed_url.hostname          # 仅提取 IP
        netloc_identifier = parsed_url.netloc  # 例如 42.237.164.228:9901
        
        channels = parse_hotel_json(url)
        if not channels: 
            continue

        # 查询 IP 属地
        location = get_ip_location(ip)

        # 为当前 IP 源生成独立的 M3U 内容
        single_m3u_lines = ["#EXTM3U"]
        for ch in channels:
            # 总表条目
            all_m3u_lines.append(f'#EXTINF:-1 tvg-name="{ch["name"]}" group-title="{ch["group"]}",{ch["name"]}')
            all_m3u_lines.append(ch['url'])
            
            # 单独表条目
            single_m3u_lines.append(f'#EXTINF:-1 tvg-name="{ch["name"]}" group-title="{ch["group"]}",{ch["name"]}')
            single_m3u_lines.append(ch['url'])

        # 保存为独立的单个 M3U 文件，格式：属地-IP_端口.m3u (例如 上海-42.237.164.228_9901.m3u)
        safe_netloc = netloc_identifier.replace(":", "_")
        filename = f"{location}-{safe_netloc}.m3u"
        single_file_path = os.path.join(HOTELS_DIR, filename)
        
        with open(single_file_path, 'w', encoding='utf-8') as f_single:
            f_single.write("\n".join(single_m3u_lines))

        success_count += 1
        print(f"✅ [{success_count}] [{location}] 已生成文件: {filename} (频道数: {len(channels)})")
        
        # 稍微停顿一下，防止频繁请求 IP 查询接口触发限制
        time.sleep(0.5)

    # 保存总 M3U 文件
    os.makedirs(os.path.dirname(M3U_FILE), exist_ok=True)
    with open(M3U_FILE, 'w', encoding='utf-8') as f_m3u:
        f_m3u.write("\n".join(all_m3u_lines))

    print(f"\n🎉 全部完成！")
    print(f"📂 总 M3U 文件: {M3U_FILE}")
    print(f"📂 单独源文件目录: {HOTELS_DIR}")
    print(f"📈 成功解析源数量: {success_count}/{len(urls)}")

if __name__ == "__main__":
    main()
