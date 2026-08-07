import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# 文件路径
target_file = r"D:\python\valid_ips.txt"

def test_endpoint(ip_port):
    """测试单个 IP:端口 是否能正常访问"""
    url = f"http://{ip_port}/"
    try:
        # 设置 3 秒超时
        response = requests.get(url, timeout=3)
        # 只要服务器返回了响应（状态码小于 500），就认为存活
        if response.status_code < 500:
            return ip_port, True
    except requests.RequestException:
        pass
    return ip_port, False

def main():
    if not os.path.exists(target_file):
        print(f"错误：找不到文件 -> {target_file}")
        return

    # 1. 读取文件中的所有 IP
    with open(target_file, 'r', encoding='utf-8') as f:
        ip_list = [line.strip() for line in f if line.strip()]

    total = len(ip_list)
    if total == 0:
        print("文件内容为空，无需检测。")
        return

    print(f"开始检测 {total} 个 IP/端口 的连通性...\n")

    valid_ips = []

    # 2. 使用多线程并发检测（最多 10 个线程，提高检测速度）
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_ip = {executor.submit(test_endpoint, ip): ip for ip in ip_list}
        
        for future in as_completed(future_to_ip):
            ip_port, is_valid = future.result()
            if is_valid:
                print(f"[有效] {ip_port} 访问成功")
                valid_ips.append(ip_port)
            else:
                print(f"[无效] {ip_port} 无法连接，已剔除")

    # 3. 将过滤后的有效 IP 回填覆盖原文件
    with open(target_file, 'w', encoding='utf-8') as f:
        for ip in valid_ips:
            f.write(ip + '\n')

    print(f"\n检测完成！")
    print(f"原共有 {total} 个地址，清理后剩余可用 {len(valid_ips)} 个。")
    print(f"有效地址已成功回填并保存至: {target_file}")

if __name__ == "__main__":
    main()