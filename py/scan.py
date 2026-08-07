import os
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

TIMEOUT = 5        # 单次连接超时
MAX_WORKERS = 200  # 并发线程数

def check_url(url):
    """测试单个URL是否可用"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Viera; rv:34.0) Gecko/20100101 Firefox/34.0'}
        response = requests.get(url, timeout=TIMEOUT, verify=False, headers=headers)
        if response.status_code == 200:
            if "key" in response.text or "1000" in response.text:
                return url
    except:
        pass
    return None

def get_c_segment_urls(url):
    """生成该IP所属C段的所有URL"""
    urls = []
    try:
        url = url.strip().replace("\t", "").replace(" ", "")
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
                new_url = urlunparse(parsed._replace(netloc=new_ip))
                urls.append(new_url)
    except:
        pass
    return urls

def main():
    alive_urls = set()
    all_scan_tasks = []

    # 1. 读取原始数据
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 错误：找不到文件 {INPUT_FILE}")
        return

    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            raw_urls = [line.strip().replace("\t", "").replace(" ", "") for line in f if line.strip()]
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return

    print(f"【初始化】原始记录: {len(raw_urls)} 条")

    # 2. 构造所有待扫描的任务池
    for url in raw_urls:
        all_scan_tasks.append(url)
        all_scan_tasks.extend(get_c_segment_urls(url))

    # 去重
    all_scan_tasks = list(set(all_scan_tasks))
    total_count = len(all_scan_tasks)
    print(f"【任务池】去重后总计待测试任务: {total_count} 个")
    print(f"【执行】并发线程数: {MAX_WORKERS}，请稍后...")

    # 3. 使用 ThreadPoolExecutor 全速扫描
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

    # 4. 保存结果
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
