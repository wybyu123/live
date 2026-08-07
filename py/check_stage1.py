import concurrent.futures
import sys
import time
import requests

INPUT_FILE = "py/9003.txt"
OUTPUT_FILE = "py/valid_9003.txt"
TIMEOUT = 4
MAX_WORKERS = 20  # 降低并发数，防止 GitHub 运行中断


def check_single_ip(url):
  try:
    start_t = time.time()
    response = requests.get(url, timeout=TIMEOUT, allow_redirects=True)
    cost = round(time.time() - start_t, 2)
    response.encoding = response.apparent_encoding

    if response.status_code == 200:
      html_content = response.text
      keywords = [
          "data.db",
          "懒加载",
          "jsmpeg",
          "AAC转码",
          "live开关",
          "vod开关",
          "rtp://",
          "rtsp://",
          "网卡",
      ]
      if any(kw in html_content for kw in keywords):
        print(f"[✅ 阶段一有效] 耗时 {cost}s -> {url}")
        return url
  except Exception:
    pass
  return None


def main():
  print("=" * 50)
  print(" 🚀 【阶段一】开始执行：检测 9003.txt 已知 IP")
  print("=" * 50)

  try:
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
      lines = [
          line.strip()
          for line in f.readlines()
          if line.strip() and not line.startswith("#")
      ]
  except FileNotFoundError:
    print(f"[错误] 找不到文件 {INPUT_FILE}")
    return

  urls = [
      l if l.startswith("http://") or l.startswith("https://") else f"http://{l}"
      for l in lines
  ]
  total = len(urls)
  print(f"📊 加载总数: {total} 个 | 线程数: {MAX_WORKERS}")

  valid_ips = []
  with concurrent.futures.ThreadPoolExecutor(
      max_workers=MAX_WORKERS
  ) as executor:
    futures = [executor.submit(check_single_ip, u) for u in urls]
    for future in concurrent.futures.as_completed(futures):
      res = future.result()
      if res:
        valid_ips.append(res)

  # 写入文件供阶段二读取
  with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    for vip in valid_ips:
      f.write(vip + "\n")

  print(
      f"🎉 阶段一完成！发现有效源: {len(valid_ips)} 个，已保存至"
      f" {OUTPUT_FILE}"
  )


if __name__ == "__main__":
  main()
