import json
import os
import requests

# 目标网址
target_url = "https://iptvs.pes.im"
# 输出文件名（保存在脚本同级目录下）
output_json_file = "iptvs_data.json"

def fetch_and_save_json():
    print(f"正在请求网址: {target_url} ...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        # 发送 HTTP GET 请求，设置 10 秒超时
        response = requests.get(target_url, headers=headers, timeout=10)
        
        # 检查请求是否成功 (状态码 200)
        if response.status_code == 200:
            # 尝试解析为 JSON，确保数据格式正确
            json_data = response.json()
            
            # 获取脚本所在的当前文件夹路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(current_dir, output_json_file)
            
            # 将 JSON 数据写入同级目录的文件中（ensure_ascii=False 保证中文正常显示，indent=4 美化排版）
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=4)
                
            print(f"[成功] 数据已成功抓取并保存至: {file_path}")
        else:
            print(f"[错误] 请求失败，服务器返回状态码: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"[错误] 网络请求发生异常: {e}")
    except ValueError:
        print("[错误] 服务器返回的内容不是有效的 JSON 格式。")

if __name__ == "__main__":
    fetch_and_save_json()
