import os
import re
import requests
import sys

# 强制无缓冲输出
sys.stdout.reconfigure(line_buffering=True) if hasattr(
    sys.stdout, "reconfigure"
) else None

# 【修改处】将输入源改为多个文件的列表，增加 py/zhgxtv2.txt
INPUT_FILES = ["py/zhgxtv.txt", "py/zhgxtv2.txt"]
BLACKLIST_FILE = "py/black_ips.txt"
WHITELIST_FILE = "py/white_ips.txt"
OUTPUT_TXT = "zhgxtv_live.txt"
OUTPUT_M3U = "zhgxtv_live.m3u"


def load_list_file(filepath):
    """通用函数：加载文本文件中的 IP 列表（支持黑名单/白名单）"""
    items = set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                item = line.strip()
                if item and not item.startswith("#"):
                    items.add(item)
    except FileNotFoundError:
        pass
    return items


def load_blacklist():
    return load_list_file(BLACKLIST_FILE)


def load_whitelist():
    return load_list_file(WHITELIST_FILE)


def update_blacklist(new_failed_ips):
    """将新失败的 IP 追加保存到黑名单文件中（去重）"""
    existing_blacklist = load_blacklist()
    added_count = 0
    
    for ip in new_failed_ips:
        if ip not in existing_blacklist:
            existing_blacklist.add(ip)
            added_count += 1

    if added_count > 0:
        with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
            for ip in sorted(existing_blacklist):
                f.write(ip + "\n")
        print(f"📝 已更新黑名单，新增吸纳 {added_count} 个失效目标至: {BLACKLIST_FILE}")


def update_whitelist(new_success_ips):
    """将本次运行成功的 IP 追加保存到白名单文件中（去重）"""
    existing_whitelist = load_whitelist()
    added_count = 0
    
    for ip in new_success_ips:
        if ip not in existing_whitelist:
            existing_whitelist.add(ip)
            added_count += 1

    if added_count > 0:
        with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
            for ip in sorted(existing_whitelist):
                f.write(ip + "\n")
        print(f"✨ 已更新白名单，新增沉淀 {added_count} 个优质目标至: {WHITELIST_FILE}")


def is_valid_channel(name):
    """
    清洗并校验频道名称是否合法
    """
    if not name:
        return False
    # 过滤明显的乱码特征
    if len(name) > 35 or re.search(r'[鏂板瀷鍐犵姸]', name):
        return False
    return True


def parse_type1(ip_port):
    """
    第一类系统 (jsmpeg-streamer)：通过 /streamer/list 获取 JSON 频道数据
    """
    channels = []
    api_url = f"http://{ip_port}/streamer/list"
    try:
        response = requests.get(api_url, timeout=4)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                for item in data:
                    key = item.get("key")
                    name = item.get("name")
                    if key:
                        channel_name = name.strip() if name else str(key)
                        play_url = f"http://{ip_port}/hls/{key}/index.m3u8"
                        if is_valid_channel(channel_name):
                            channels.append((channel_name, play_url))
    except Exception:
        pass
    return channels


def parse_type2(ip_port):
    """
    第二类系统 (ZHGXTV)：严格清洗，只保留形如 /hls/数字/index.m3u8 规范路径的链接
    """
    channels = []
    urls_to_try = [
        f"http://{ip_port}/ZHGXTV/Public/json/live_interface.txt",
        f"http://{ip_port}/live.m3u",
        f"http://{ip_port}/iptv.txt"
    ]
    
    encodings = ['utf-8', 'gbk', 'gb18030']
    
    for url in urls_to_try:
        try:
            response = requests.get(url, timeout=4)
            if response.status_code != 200 or not response.content:
                continue
                
            decoded_text = None
            for enc in encodings:
                try:
                    decoded_text = response.content.decode(enc)
                    if "," in decoded_text or "index.m3u8" in decoded_text:
                        break
                except UnicodeDecodeError:
                    continue
            
            if not decoded_text:
                continue
                
            invalid_keywords = [
                "python_", "process_", "api_request_count", "metrics", 
                "<!DOCTYPE", "<html", "<head", "error", "404 Not Found"
            ]
            if any(keyword in decoded_text for keyword in invalid_keywords):
                continue
                
            lines = decoded_text.splitlines()
            temp_channels = []
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                if "," in line:
                    parts = line.split(",", 1)
                elif "\t" in line:
                    parts = line.split("\t", 1)
                else:
                    continue
                    
                name = parts[0].strip()
                orig_url = parts[1].strip()
                
                name = re.sub(r'[\r\n\t]', '', name)
                if not name:
                    name = "未知频道"
                    
                if not is_valid_channel(name):
                    continue
                    
                if any(orig_url.lower().startswith(p) for p in ["udp://", "rtp://", "rtsp://"]):
                    continue
                    
                if "/pltv/" in orig_url.lower() or ".smil" in orig_url.lower():
                    continue

                if not re.search(r'/hls/\d+/index\.m3u8', orig_url, re.IGNORECASE):
                    continue
                    
                if orig_url.startswith("http:///"):
                    new_url = orig_url.replace("http:///", f"http://{ip_port}/", 1)
                else:
                    new_url = re.sub(r'https?://[^/]+', f'http://{ip_port}', orig_url)
                
                if new_url and re.search(r'/hls/\d+/index\.m3u8', new_url, re.IGNORECASE):
                    if not any(k in new_url.lower() for k in ["/metrics", "/api/video/", "china.com/api"]):
                        temp_channels.append((name, new_url))
                    
            if len(temp_channels) >= 2:
                channels.extend(temp_channels)
                break
        except Exception:
            continue
            
    return channels


def main():
    # 1. 加载黑名单和白名单
    blacklist = load_blacklist()
    whitelist = load_whitelist()
    print(f"🛡️ 从 {BLACKLIST_FILE} 加载了 {len(blacklist)} 个已知失效黑名单 IP。")
    print(f"⭐ 从 {WHITELIST_FILE} 加载了 {len(whitelist)} 个优质白名单 IP。")

    # 2. 【修改处】循环读取多个输入文件并合并去重
    file_ips_set = set()
    for file_path in INPUT_FILES:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    item = line.strip()
                    if item and not item.startswith("#"):
                        file_ips_set.add(item)
            print(f"📁 已从 {file_path} 加载目标。")
        else:
            print(f"[提示] 输入文件不存在，已跳过: {file_path}")

    # 综合输入文件与白名单去重
    combined_raw_ips = list(file_ips_set.union(whitelist))
    print(f"📦 多源合并去重后，总共整合了 {len(combined_raw_ips)} 个唯一待测目标。")

    # 3. 【新增规则】在输入整合阶段直接拦截所有带 ":5000" 端口的 IP 并加入黑名单
    port_5000_ips = []
    cleaned_raw_ips = []
    for ip_item in combined_raw_ips:
        clean_ip = ip_item.replace("http://", "").replace("https://", "").rstrip("/")
        if ":5000" in clean_ip:
            port_5000_ips.append(clean_ip)
        else:
            cleaned_raw_ips.append(ip_item)

    if port_5000_ips:
        print(f"🚫 发现 {len(port_5000_ips)} 个 5000 端口目标，已在输入阶段直接拦截并加入黑名单。")
        update_blacklist(port_5000_ips)
        # 重新加载黑名单，使刚才拉黑的生效
        blacklist = load_blacklist()

    # 4. 运行前自动过滤黑名单中的 IP
    filtered_ips = []
    skipped_by_blacklist = 0
    for ip_item in cleaned_raw_ips:
        clean_ip = ip_item.replace("http://", "").replace("https://", "").rstrip("/")
        if clean_ip in blacklist and clean_ip not in whitelist:
            skipped_by_blacklist += 1
        else:
            filtered_ips.append(ip_item)

    print(f"🚫 已通过黑名单自动屏蔽 {skipped_by_blacklist} 个死 IP，实际待测: {len(filtered_ips)} 个。")

    # 使用字典按 IP 源分组存储成功抓取的频道 {ip_port: [(name, url), ...]}
    grouped_channels = {}
    new_failed_ips = []
    new_success_ips = []  
    success_count = 0

    print(f"\n🚀 开始批量处理 {len(filtered_ips)} 个有效地址...\n")

    for ip_item in filtered_ips:
        ip_port = ip_item.replace("http://", "").replace("https://", "").strip().rstrip("/")
        if not ip_port:
            continue
            
        base_host_key = ip_port
        print(f"🔍 正在检测: http://{ip_port} ...", end=" ")
        
        current_channels = []
        # 1. 尝试第二类系统 (ZHGXTV)
        type2_channels = parse_type2(ip_port)
        if type2_channels:
            current_channels = type2_channels
            print(f"✅ [识别为：ZHGXTV 系统] 有效提取 {len(current_channels)} 个频道")
        else:
            # 2. 尝试第一类系统 (jsmpeg-streamer)
            type1_channels = parse_type1(ip_port)
            if type1_channels:
                current_channels = type1_channels
                print(f"✅ [识别为：jsmpeg-streamer 系统] 有效提取 {len(current_channels)} 个频道")

        if current_channels:
            grouped_channels[ip_port] = current_channels
            success_count += 1
            new_success_ips.append(base_host_key)
        else:
            print("❌ [未识别或无有效频道]，加入黑名单")
            new_failed_ips.append(base_host_key)

    # 5. 回填黑白名单
    if new_failed_ips:
        update_blacklist(new_failed_ips)
    if new_success_ips:
        update_whitelist(new_success_ips)  

    print("-" * 50)
    print(f"🎉 任务处理完毕！成功响应的 IP 数: {success_count} 个")

    # 6. 按 IP 源分组生成 TXT 和 M3U 文件
    if grouped_channels:
        # 生成 TXT 文件 (格式: 节点_IP,#genre#)
        with open(OUTPUT_TXT, 'w', encoding='utf-8') as f:
            for ip_port, channels in grouped_channels.items():
                group_name = f"iptv_{ip_port}"
                f.write(f"{group_name},#genre#\n")
                for name, url in channels:
                    f.write(f'{name},{url}\n')
        print(f"💾 已成功生成按IP分组的 TXT 文件: {OUTPUT_TXT}")

        # 生成 M3U 文件 (格式: #EXTINF:-1 tvg-group="节点_IP",频道名)
        with open(OUTPUT_M3U, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for ip_port, channels in grouped_channels.items():
                group_name = f"iptv_{ip_port}"
                for name, url in channels:
                    f.write(f'#EXTINF:-1 tvg-group="{group_name}",{name}\n')
                    f.write(f'{url}\n')
        
        total_channels_count = sum(len(ch) for ch in grouped_channels.values())
        print(f"💾 已成功生成按IP分组的 M3U 文件: {OUTPUT_M3U} (共包含 {len(grouped_channels)} 个IP源，{total_channels_count} 个有效频道)")
    else:
        print("\n⚠️ 未成功提取到任何频道。")
    print("=" * 50)


if __name__ == "__main__":
    main()
