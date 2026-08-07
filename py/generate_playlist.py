import sys
import time
from playwright.sync_api import sync_playwright

# 强制无缓冲输出
sys.stdout.reconfigure(line_buffering=True) if hasattr(
    sys.stdout, "reconfigure"
) else None

INPUT_FILE = "py/valid_9003.txt"
OUTPUT_TXT = "live.txt"
OUTPUT_M3U = "live.m3u"
TIMEOUT = 10000  # 毫秒

BLACK_LIST = {
    "key",
    "name",
    "source",
    "netcard_in",
    "out",
    "outcar",
    "vodpath",
    "resolution",
    "lazy",
    "aac",
    "status",
    "live_switch",
    "vod_switch",
    "players",
    "启动",
    "停止",
    "删除",
    "opt",
    "提交",
    "aac转码",
    "live开关",
    "vod开关",
    "true",
    "false",
}


def clean_channel_name(name):
  """清理频道名称：去掉空格，屏蔽并删除“高清”字样"""
  if not name:
    return ""
  # 屏蔽/去除“高清”字样（支持各种格式，如 高清、 -高清、 HD 等）
  name = name.replace("高清", "").replace("HD", "").replace("hd", "")
  return name.strip()


def get_channel_sort_key(ch_name):
  """为频道定义排序权重：

  1. 央视 (CCTV) 且 1-17 之间的排最前面，按数字排序
  2. 卫视频道排在中间
  3. 其他频道排在最后
  """
  name = ch_name.upper()

  # 匹配 CCTV 或者是中央频道
  if "CCTV" in name or "央视" in name:
    # 提取数字
    import re

    nums = re.findall(r"\d+", name)
    if nums:
      num = int(nums[0])
      if 1 <= num <= 17:
        return (1, num, ch_name)  # 权重 1：排在最前，按央视编号排序
    return (2, 0, ch_name)  # 其他 CCTV / 央视综合排在央视数字后面

  # 卫视频道排中间
  if "卫视" in name:
    return (3, 0, ch_name)

  # 其他频道排最后
  return (4, 0, ch_name)


def fetch_channels_with_browser(p, base_url):
  channels = []
  base_url = base_url.rstrip("/")

  browser = p.chromium.launch(
      headless=True,
      args=[
          "--no-sandbox",
          "--disable-setuid-sandbox",
          "--disable-dev-shm-usage",
      ],
  )
  context = browser.new_context(viewport={"width": 1280, "height": 800})
  page = context.new_page()

  try:
    page.goto(base_url, timeout=TIMEOUT, wait_until="networkidle")

    try:
      page.wait_for_selector("table tr", timeout=5000)
    except Exception:
      time.sleep(2)

    extracted_data = page.evaluate("""() => {
            const rows = document.querySelectorAll('table tr');
            let results = [];
            rows.forEach(row => {
                const cells = row.querySelectorAll('td');
                if (cells.length >= 2) {
                    const keyA = cells[0].querySelector('a');
                    const keyText = keyA ? keyA.innerText.trim() : cells[0].innerText.trim();
                    const nameText = cells[1] ? cells[1].innerText.trim() : '';
                    
                    if (keyText && nameText) {
                        results.push({ key: keyText, name: nameText });
                    }
                }
            });
            return results;
        }""")

    for item in extracted_data:
      key = str(item.get("key", "")).strip()
      raw_name = str(item.get("name", "")).strip()

      if not key or not raw_name:
        continue

      name_lower = raw_name.lower()
      key_lower = key.lower()

      if name_lower in BLACK_LIST or key_lower in BLACK_LIST:
        continue
      if any(
          w in raw_name
          for w in ["转码", "开关", "进程", "懒加载", "true", "false"]
      ):
        continue
      if any(
          w in key for w in ["转码", "开关", "进程", "懒加载", "true", "false"]
      ):
        continue

      if "\n" in key or len(key) > 15:
        continue

      # 清理频道名（去“高清”）
      clean_name = clean_channel_name(raw_name)
      if not clean_name:
        continue

      stream_url = f"{base_url}/hls/{key}/index.m3u8"
      channels.append({"name": clean_name, "url": stream_url})

    # 对抓取到的频道进行排序：央视(1-17)优先 -> 卫视居中 -> 其他靠后
    channels.sort(key=lambda x: get_channel_sort_key(x["name"]))

  except Exception as e:
    print(f"[浏览器访问异常] {base_url} -> {e}")
  finally:
    browser.close()

  return channels


def main():
  print("=" * 50)
  print(" 🚀 启动 Playwright 抓取 IPTV 列表（已启用央视优先排序与去高清功能）...")
  print("=" * 50)

  try:
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
      ips = [
          line.strip()
          for line in f
          if line.strip() and not line.startswith("#")
      ]
  except FileNotFoundError:
    print(f"[错误] 找不到输入文件: {INPUT_FILE}")
    return

  print(f"📁 从 {INPUT_FILE} 加载了 {len(ips)} 个有效 IP 目标。")

  grouped_channels = {}
  success_ip_count = 0

  with sync_playwright() as p:
    for ip_url in ips:
      target_url = (
          ip_url
          if ip_url.startswith("http://") or ip_url.startswith("https://")
          else f"http://{ip_url}"
      )

      print(f"🌐 正在用浏览器打开: {target_url} ...")
      channels = fetch_channels_with_browser(p, target_url)

      if channels and len(channels) >= 2:
        success_ip_count += 1
        print(
            f"[✅ 渲染成功并采纳] {target_url} -> 成功提取并排序 {len(channels)}"
            " 个真实频道"
        )
        grouped_channels[target_url] = channels
      else:
        print(f"[⚠️ 过滤空壳/配置项网页] {target_url} -> 无有效频道，已丢弃")

  print("-" * 50)
  print(f"🎉 浏览器解析完毕！")
  print(f"📡 成功响应且有真实内容的 IP 数: {success_ip_count} 个")

  # 生成 TXT 文件
  with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
    for ip_target, channels in grouped_channels.items():
      f.write(f"{ip_target},#genre#\n")
      for ch in channels:
        f.write(f"{ch['name']},{ch['url']}\n")
  print(f"💾 已成功生成 TXT 文件: {OUTPUT_TXT}")

  # 生成 M3U 文件
  with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    for ip_target, channels in grouped_channels.items():
      for ch in channels:
        f.write(
            f'#EXTINF:-1 tvg-name="{ch["name"]}" group-title="{ip_target}"'
            f' tvg-logo="",{ch["name"]}\n'
        )
        f.write(f"{ch['url']}\n")
  print(f"💾 已成功生成 M3U 文件: {OUTPUT_M3U}")
  print("=" * 50)


if __name__ == "__main__":
  main()
