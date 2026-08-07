import concurrent.futures
import re
import sys
import time
import requests

# 核心改进：强制 Python 标准输出无缓冲，确保日志实时打印到屏幕
sys.stdout.reconfigure(line_buffering=True) if hasattr(
    sys.stdout, "reconfigure"
) else None

INPUT_FILE = "py/9003.txt"
OUTPUT_FILE = "py/valid_9003.txt"
TIMEOUT = 3
MAX_WORKERS = 100  # 100 线程高并发
BATCH_SIZE = 500  # 每批处理 500 个 IP


def check_single_ip(url):
  """单个IP深度检测：状态码200 + 基础前端特征 + 包含有效的key/name频道数据"""
  try:
    response = requests.get(url, timeout=TIMEOUT, allow_redirects=True)
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
        has_content_data = bool(
            re.search(
                r'(?:key\s*[:=]|name\s*[:=]|channel|channels|list|items|url)',
                html_content,
                re.IGNORECASE,
            )
        )
        if has_content_data:
          return url
  except Exception:
    pass
  return None


def main():
  print("=" * 50, flush=True)
  print(" 🚀 【阶段二】35万 C端全量地毯式复活扫描启动（实时打印版）...", flush=True)
  print("=" * 50, flush=True)

  seed_ips = set()
  try:
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
      for line in f:
        l = line.strip()
        if l and not l.startswith("#"):
          seed_ips.add(l)
  except FileNotFoundError:
    print(f"[错误] 找不到输入文件: {INPUT_FILE}", flush=True)
    return

  if not seed_ips:
    print(f"[提示] {INPUT_FILE} 中没有有效的种子 IP。", flush=True)
    return

  print(f"📁 成功加载原始种子 IP 共 {len(seed_ips)} 个", flush=True)
  print("🔄 正在对所有种子提取 C 段并生成 1-255 全量目标矩阵...", flush=True)

  expanded_urls = set()
  c_net_count = set()
  ip_port_pattern = re.compile(
      r"^(?:https?://)?(\d{1,3}\.\d{1,3}\.\d{1,3})\.(\d{1,3})(?::(\d+))?(?:/.*)?$"
  )

  for item in seed_ips:
    match = ip_port_pattern.match(item)
    if match:
      net_prefix, _, port = match.groups()
      port = port if port else "9003"
      c_net_count.add(net_prefix)
      for i in range(1, 256):
        expanded_urls.add(f"http://{net_prefix}.{i}:{port}")

  targets = list(expanded_urls)
  total_targets = len(targets)

  print(f"🌐 独立 C 网段数: {len(c_net_count)} 个", flush=True)
  print(
      f"📊 待测总目标数: {total_targets} 个 IP (实时监控已开启)", flush=True
  )
  print("-" * 50, flush=True)

  stage2_valid = set()
  for s in seed_ips:
    formatted_s = (
        s if s.startswith("http://") or s.startswith("https://") else f"http://{s}"
    )
    stage2_valid.add(formatted_s)

  start_time = time.time()
  completed_count = 0

  with concurrent.futures.ThreadPoolExecutor(
      max_workers=MAX_WORKERS
  ) as executor:
    for i in range(0, total_targets, BATCH_SIZE):
      batch_targets = targets[i : i + BATCH_SIZE]
      future_to_url = {
          executor.submit(check_single_ip, u): u for u in batch_targets
      }

      for future in concurrent.futures.as_completed(future_to_url):
        completed_count += 1
        res = future.result()
        if res:
          print(f"\n[✨ 成功复活有效源] -> {res}", flush=True)
          stage2_valid.add(res)

      # 每一批次完成后，利用 flush=True 强制立刻刷出日志
      percent = (completed_count / total_targets) * 100
      elapsed = round(time.time() - start_time, 1)
      print(
          f"📊 进度: {percent:.1f}%  {completed_count}/{total_targets}"
          f"  | 已耗时: {elapsed}s  | 当前有效源总数: {len(stage2_valid)} 个",
          flush=True,
      )

  all_results = sorted(list(stage2_valid))

  with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    for vip in all_results:
      f.write(vip + "\n")

  print("=" * 50, flush=True)
  print("🎉 35万 C端全量复活扫描全部完成！", flush=True)
  print(f"📦 最终保存有效源总数: {len(all_results)} 个", flush=True)
  print(f"💾 结果已全部写入: {OUTPUT_FILE}", flush=True)
  print("=" * 50, flush=True)


if __name__ == "__main__":
  main()
