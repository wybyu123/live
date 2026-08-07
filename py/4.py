import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# 指定目标文件夹路径
target_dir = r"D:\volume\live2-main\hotel"
# 输出结果文件
output_file = "valid_ips.txt"

# 正则表达式：匹配 http://IP:端口/ 或 http://域名:端口/
ip_port_pattern = re.compile(r'https?://([a-zA-Z0-9.-]+:\d+)', re.IGNORECASE)

def extract_ip_ports():
    ip_ports = set()
    if not os.path.exists(target_dir):
        print(f"错误：指定的目录不存在 -> {target_dir}")
        return ip_ports

    print(f"正在从目录扫描 .m3u 文件: {target_dir}")
    
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            if file.lower().endswith('.m3u'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        # 查找所有匹配的 IP:端口
                        matches = ip_port_pattern.findall(content)
                        for match in matches:
                            ip_ports.add(match)
                except Exception as e:
                    print(f"读取文件出错 {file_path}: {e}")

    return list(ip_ports)

def test_single_endpoint(ip_port):
    # 尝试访问该 IP:端口 的根路径或常见接口
    url = f"http://{ip_port}/"
    try:
        # 设置 3 秒超时，避免卡死
        response = requests.get(url, timeout=3)
        # 只要能连上并返回响应（状态码 200~499 都说明服务器在线）
        if response.status_code < 500:
            return ip_port, True
    except requests.RequestException:
        pass
    return ip_port, False

def main():
    ip_ports = extract_ip_ports()
    total = len(ip_ports)
    print(f"共提取到 {total} 个独立的 IP:端口 组合，开始进行连通性测试...\n")

    valid_list = []

    # 使用线程池并发测试（10个线程，加快测试速度）
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_ip = {executor.submit(test_single_endpoint, ip): ip for ip in ip_ports}
        
        for future in as_completed(future_to_ip):
            ip_port, is_valid = future.result()
            if is_valid:
                print(f"[有效] {ip_port} 连通成功")
                valid_list.append(ip_port)
            else:
                print(f"[无效] {ip_port} 无法连接")

    # 将可用结果写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        for ip in valid_list:
            f.write(ip + '\n')

    print(f"\n测试完成！共检测了 {total} 个地址，其中有效可用 {len(valid_list)} 个。")
    print(f"有效 IP 和端口已保存到: {os.path.abspath(output_file)}")

if __name__ == "__main__":
    main()