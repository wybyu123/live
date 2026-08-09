import os
import re
import requests
import sys

# 强制无缓冲输出
sys.stdout.reconfigure(line_buffering=True) if hasattr(
    sys.stdout, "reconfigure"
) else None

# 输入与输出路径适配 GitHub 仓库结构
INPUT_FILE = "py/zhgxtv.txt"
BLACKLIST_FILE = "py/black_ips.txt"
WHITELIST_FILE = "py/white_ips.txt"  # 🟢 新增：白名单文件路径
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
    """🟢 新增：将本次运行成功的 IP 追加保存到白名单文件中（去重）"""
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
    if not os.path.exists(INPUT_FILE):
        print(f"[错误] 找不到输入文件: {INPUT_FILE}")
        return

    # 1. 加载黑名单和白名单
    blacklist = load_blacklist()
    whitelist = load_whitelist()
    print(f"🛡️ 从 {BLACKLIST_FILE} 加载了 {len(blacklist)} 个已知失效黑名单 IP。")
    print(f"⭐ 从 {WHITELIST_FILE} 加载了 {len(whitelist)} 个优质白名单 IP。")

    # 2. 读取 zhgxtv.txt 中的 IP 列表
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        file_ips = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    # 🟢 核心逻辑：将白名单中的 IP 与输入文件的 IP 强制合并并去重，确保白名单里的 IP 必定参与测速
    combined_raw_ips = list(set(file_ips).union(whitelist))
    print(f"📁 综合输入文件与白名单后，总共整合了 {len(combined_raw_ips)} 个唯一待测目标。")

    # 3. 运行前自动过滤黑名单中的 IP（如果白名单和黑名单冲突，可让白名单优先，这里按常规逻辑：如果在黑名单中且不在白名单，则过滤）
    filtered_ips = []
    skipped_by_blacklist = 0
    for ip_item in combined_raw_ips:
        clean_ip = ip_item.replace("http://", "").replace("https://", "").rstrip("/")
        # 如果在黑名单中，但不在白名单中，则跳过
        if clean_ip in blacklist and clean_ip not in whitelist:
            skipped_by_blacklist += 1
        else:
            filtered_ips.append(ip_item)

    print(f"🚫 已通过黑名单自动屏蔽 {skipped_by_blacklist} 个死 IP，实际待测: {len(filtered_ips)} 个。")

    all_channels = []
    new_failed_ips = []
    new_success_ips = []  # 🟢 记录本次运行成功的 IP
    success_count = 0

    print(f"\n🚀 开始批量处理 {len(filtered_ips)} 个有效地址...\n")

    for ip_item in filtered_ips:
        ip_port = ip_item.replace("http://", "").replace("https://", "").strip().rstrip("/")
        if not ip_port:
            continue
            
        base_host_key = ip_port
        print(f"🔍 正在检测: http://{ip_port} ...", end=" ")
        
        # 1. 尝试第二类系统 (ZHGXTV)
        type2_channels = parse_type2(ip_port)
        if type2_channels:
            print(f"✅ [识别为：ZHGXTV 系统] 有效提取 {len(type2_channels)} 个频道")
            all_channels.extend(type2_channels)
            success_count += 1
            new_success_ips.append(base_host_key)  # 记录成功
            continue
            
        # 2. 尝试第一类系统 (jsmpeg-streamer)
        type1_channels = parse_type1(ip_port)
        if type1_channels:
            print(f"✅ [识别为：jsmpeg-streamer 系统] 有效提取 {len(type1_channels)} 个频道")
            all_channels.extend(type1_channels)
            success_count += 1
            new_success_ips.append(base_host_key)  # 记录成功
            continue
            
        print("❌ [未识别或无有效频道]，加入黑名单")
        new_failed_ips.append(base_host_key)

    # 4. 运行结束后将新失败的 IP 回填至黑名单，将成功的 IP 回填至白名单
    if new_failed_ips:
        update_blacklist(new_failed_ips)
    
    if new_success_ips:
        update_whitelist(new_success_ips)  # 🟢 回填白名单

    print("-" * 50)
    print(f"🎉 任务处理完毕！成功响应的 IP 数: {success_count} 个")

    # 5. 生成标准的 TXT 和 M3U 播放列表文件
    if all_channels:
        with open(OUTPUT_TXT, 'w', encoding='utf-8') as f:
            f.write("ZHGXTV聚合,#genre#\n")
            for name, url in all_channels:
                f.write(f'{name},{url}\n')
        print(f"💾 已成功生成 TXT 文件: {OUTPUT_TXT}")

        with open(OUTPUT_M3U, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for name, url in all_channels:
                f.write(f'#EXTINF:-1,{name}\n')
                f.write(f'{url}\n')
        print(f"💾 已成功生成 M3U 文件: {OUTPUT_M3U} (共包含 {len(all_channels)} 个有效频道)")
    else:
        print("\n⚠️ 未成功提取到任何频道。")
    print("=" * 50)


if __name__ == "__main__":
    main()
