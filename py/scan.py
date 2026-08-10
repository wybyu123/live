import os
import csv
import requests
import concurrent.futures
from urllib.parse import urlparse, urlunparse
import warnings

# 禁用 HTTPS 警告
warnings.filterwarnings("ignore")

# --- 动态路径与配置 ---
BASE_PATH = os.getcwd()
INPUT_FILE = os.path.join(BASE_PATH, "py", "txiptv.txt")
SUCCESS_FILE = os.path.join(BASE_PATH, "py", "1000_alive.txt")

# 新增：远程输入源地址
REMOTE_INPUT_URL = "https://nek.de5.net/py/1000_alive.txt"

TIMEOUT = 5        # 单次连接超时
MAX_WORKERS = 200  # 并发线程数

# 酒店源标准接口后缀（可根据你的实际情况调整）
TARGET_PATH = "/iptv/live/1000.json"
TARGET_PARAMS = "key=txipt"

def normalize_and_complete_url(url):
    """
    自动规范化输入：
    如果输入的 URL 没有包含目标接口路径，则自动拼接上去。
    """
    url = url.strip().replace("\t", "").replace(" ", "")
    if not url:
        return None
    
    # 如果没有以 http 开头，自动补全 http://
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url

    parsed = urlparse(url)
    
    # 如果输入的路径里没有包含核心接口，则强制拼上标准的酒店源路径和参数
    if TARGET_PATH not in parsed.path:
        netloc = parsed.netloc
        new_path = TARGET_PATH
        new_query = TARGET_PARAMS
        
        reconstructed = urlunparse((
            parsed.scheme,
            netloc,
            new_path,
            '',
            new_query,
            ''
        ))
        return reconstructed
    
    return url

def check_url(url):
    """测试单个URL是否可用并校验响应内容"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Viera; rv:34.0) Gecko/20100101 Firefox/34.0'}
        response = requests.get(url, timeout=TIMEOUT, verify=False, headers=headers)
        if response.status_code == 200:
            if "key" in response.text or "1000" in response.text or "[" in response.text or "{" in response.text:
                return url
    except:
        pass
    return None

def get_c_segment_urls(url):
    """生成该IP所属C段的所有目标URL"""
    urls = []
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc
        if ":" in netloc:
            ip, port = netloc.split(":")
        else:
            ip, port = netloc, "80"
        
        ip_parts = ip.split(".")
        if len(ip_parts) == 4:
            base_ip = ".".join(ip_parts[:3])
            for i in range(1, 255):
                new_ip = f"{base_ip}.{i}:{port}"
                new_url = urlunparse((
                    parsed.scheme,
                    new_ip,
                    TARGET_PATH,
                    '',
                    TARGET_PARAMS,
                    ''
                ))
                urls.append(new_url)
    except:
        pass
    return urls

def main():
    alive_urls = set()
    all_scan_tasks = []
    raw_lines = []

    # 1. 优先尝试从远程链接获取输入源
    print(f"🌐 正在尝试从远程获取输入源: {REMOTE_INPUT_URL}")
    try:
        resp = requests.get(REMOTE_INPUT_URL, timeout=10, verify=False)
        if resp.status_code == 200:
            remote_lines = [line.strip() for line in resp.text.splitlines() if line.strip() and not line.strip().startswith("#")]
            raw_lines.extend(remote_lines)
            print(f"✅ 成功从远程源加载了 {len(remote_lines)} 条记录")
        else:
            print(f"⚠️ 远程源响应异常 (状态码: {resp.status_code})，将回退检查本地文件...")
    except Exception as e:
        print(f"⚠️ 无法连接到远程源 ({e})，将回退检查本地文件...")

    # 2. 同时读取本地文件（如果存在则进行合并）
    if os.path.exists(INPUT_FILE):
        try:
            with open(INPUT_FILE, 'r', encoding='utf-8') as f:
                local_lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                raw_lines.extend(local_lines)
            print(f"📂 成功从本地文件 {INPUT_FILE} 加载了 {len(local_lines)} 条记录")
        except Exception as e:
            print(f"❌ 读取本地文件失败: {e}")
    else:
        print(f"ℹ️ 本地文件 {INPUT_FILE} 不存在，仅使用远程源数据。")

    if not raw_lines:
        print("❌ 错误：没有获取到任何有效的初始记录（远程和本地均为空或不可用）！")
        return

    print(f"【初始化】合并后原始记录总计: {len(raw_lines)} 条")

    # 3. 规范化并构造所有待扫描的任务池（包含主任务及 C 段扩展）
    for line in raw_lines:
        formatted_url = normalize_and_complete_url(line)
        if formatted_url:
            all_scan_tasks.append(formatted_url)
            # 顺便将该 IP 所在的 C 段所有 IP 也加入扫描池
            all_scan_tasks.extend(get_c_segment_urls(formatted_url))

    # 去重
    all_scan_tasks = list(set(all_scan_tasks))
    total_count = len(all_scan_tasks)
    print(f"【任务池】去重后总计待测试任务: {total_count} 个")
    print(f"【执行】并发线程数: {MAX_WORKERS}，请稍后...")

    # 4. 使用 ThreadPoolExecutor 全速扫描
    count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(check_url, url): url for url in all_scan_tasks}
        
        for future in concurrent.futures.as_completed(future_to_url):
            count += 1
            res = future.result()
            if res:
                alive_urls.add(res)
                print(f"[{count}/{total_count}] 找到存活源: {res}")
            
            if count % 500 == 0:
                print(f"进度: {count}/{total_count} (已发现 {len(alive_urls)} 个)")

    # 5. 保存结果
    os.makedirs(os.path.dirname(SUCCESS_FILE), exist_ok=True)
    with open(SUCCESS_FILE, 'w', encoding='utf-8') as f:
        for url in sorted(alive_urls):
            f.write(url + "\n")
    
    print(f"\n--- 扫描结束 ---")
    print(f"总计扫描任务: {total_count}")
    print(f"最终存活数量: {len(alive_urls)}")
    print(f"结果已保存至: {SUCCESS_FILE}")

if __name__ == "__main__":
    main()
