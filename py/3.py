import os
import re

# 指定要清理的目标文件夹路径
target_dir = r"D:\volume\live2-main\hotel"

# 正则表达式匹配形如 http://.../hls/数字/index.m3u8 的链接
hls_pattern = re.compile(r'https?://[^\s]+/hls/\d+/index\.m3u8', re.IGNORECASE)

def clean_m3u_files():
    if not os.path.exists(target_dir):
        print(f"错误：指定的目录不存在 -> {target_dir}")
        return

    print(f"开始扫描目录: {target_dir}")
    deleted_count = 0
    kept_count = 0

    # 递归遍历文件夹
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            if file.lower().endswith('.m3u'):
                file_path = os.path.join(root, file)
                
                try:
                    # 读取文件内容
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # 检查是否包含目标格式的 hls 链接
                    if hls_pattern.search(content):
                        # 包含：保留
                        kept_count += 1
                    else:
                        # 不包含：删除
                        print(f"删除文件 (不包含指定hls格式): {file_path}")
                        os.remove(file_path)
                        deleted_count += 1
                except Exception as e:
                    print(f"处理文件出错 {file_path}: {e}")

    print(f"\n清理完成！共保留了 {kept_count} 个有效文件，删除了 {deleted_count} 个不符合条件的文件。")

if __name__ == "__main__":
    clean_m3u_files()