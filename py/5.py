import os
import re
import requests

# 输入文件和输出文件路径
input_file = r"D:\python\valid_ips.txt"
output_m3u = r"D:\python\all_playlist.m3u"

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
                        channels.append((channel_name, play_url))
    except Exception:
        pass
    return channels

def parse_type2(ip_port):
    """
    第二类系统 (ZHGXTV)：使用 utf-8、gbk、gb18030 三种编码依次测试解析，防止乱码
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
                
            # 依次尝试不同的编码来解码网页内容
            decoded_text = None
            for enc in encodings:
                try:
                    decoded_text = response.content.decode(enc)
                    # 如果能成功解码且包含关键字符，说明编码猜对了
                    if "," in decoded_text or "index.m3u8" in decoded_text:
                        break
                except UnicodeDecodeError:
                    continue
            
            if not decoded_text:
                continue
                
            lines = decoded_text.splitlines()
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
                
                # 清洗频道名称
                name = re.sub(r'[\r\n\t]', '', name)
                if not name:
                    name = "未知频道"
                    
                # 替换内部占位 IP 为当前真实 IP:端口
                new_url = re.sub(r'https?://[^/]+/', f'http://{ip_port}/', orig_url)
                
                if "index.m3u8" in new_url or "http" in new_url:
                    channels.append((name, new_url))
                    
            if channels:
                break
        except Exception:
            continue
            
    return channels

def main():
    if not os.path.exists(input_file):
        print(f"找不到输入文件: {input_file}")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        ip_ports = [line.strip() for line in f if line.strip()]

    all_channels = []

    print(f"开始批量处理 {len(ip_ports)} 个有效地址...\n")

    for ip_port in ip_ports:
        print(f"正在检测: {ip_port} ...", end=" ")
        
        # 1. 尝试第二类系统
        type2_channels = parse_type2(ip_port)
        if type2_channels:
            print(f"[识别为：ZHGXTV 系统] 提取 {len(type2_channels)} 个频道")
            all_channels.extend(type2_channels)
            continue
            
        # 2. 尝试第一类系统
        type1_channels = parse_type1(ip_port)
        if type1_channels:
            print(f"[识别为：jsmpeg-streamer 系统] 提取 {len(type1_channels)} 个频道")
            all_channels.extend(type1_channels)
            continue
            
        print("[未识别或无有效频道]")

    # 生成标准的 M3U 播放列表文件
    if all_channels:
        with open(output_m3u, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for name, url in all_channels:
                f.write(f'#EXTINF:-1,{name}\n')
                f.write(f'{url}\n')
        print(f"\n生成完毕！共合并提取了 {len(all_channels)} 个可用直播源。")
        print(f"播放列表已保存到: {output_m3u}")
    else:
        print("\n未成功提取到任何频道。")

if __name__ == "__main__":
    main()