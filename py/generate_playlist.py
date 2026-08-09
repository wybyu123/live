import sys
import time
import requests
from playwright.sync_api import sync_playwright

# 强制无缓冲输出
sys.stdout.reconfigure(line_buffering=True) if hasattr(
    sys.stdout, "reconfigure"
) else None

INPUT_FILE = "py/jsmpeg.txt"
BLACKLIST_FILE = "py/black_ips2.txt"  # 黑名单文件路径
WHITELIST_FILE = "py/whitelist_ips.txt"  # 【新增】白名单文件路径
OUTPUT_TXT = "live.txt"
OUTPUT_M3U = "live.m3u"
TIMEOUT = 15000  # 浏览器超时毫秒

BLACK_LIST_KEYWORDS = {
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


def load_file_set(filepath):
    """通用：加载文本文件中的内容并返回去重集合（跳过 # 注释）"""
    items_set = set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                item = line.strip()
                if item and not item.startswith("#"):
                    items_set.add(item)
    except FileNotFoundError:
        pass
    return items_set


def load_blacklist():
    """加载黑名单文件中的 IP"""
    return load_file_set(BLACKLIST_FILE)


def load_whitelist():
    """【新增】加载白名单文件中的 IP"""
    return load_file_set(WHITELIST_FILE)


def update_blacklist(new_failed_ips, whitelist):
    """将新失败的 IP 追加保存到黑名单文件中（过滤掉白名单中的 IP）"""
    existing_blacklist = load_blacklist()
    added_count = 0
    
    for ip in new_failed_ips:
        # 【白名单保护】如果 IP 在白名单中，绝不加入黑名单
        if ip in whitelist:
            print(f"🛡️ [白名单保护] {ip} 预检/抓取失败，但因其在白名单中，已免于拉黑。")
            continue

        if ip not in existing_blacklist:
            existing_blacklist.add(ip)
            added_count += 1

    if added_count > 0:
        with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
            for ip in sorted(existing_blacklist):
                f.write(ip + "\n")
        print(f"📝 已更新黑名单，新吸纳 {added_count} 个失效目标至: {BLACKLIST_FILE}")


def update_whitelist(successful_ips):
    """【新增】将本次成功采集的优质 IP 自动追加保存到白名单文件中（去重）"""
    existing_whitelist = load_whitelist()
    added_count = 0

    for ip in successful_ips:
        if ip not in existing_whitelist:
            existing_whitelist.add(ip)
            added_count += 1

    if added_count > 0:
        with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
            for ip in sorted(existing_whitelist):
                f.write(ip + "\n")
        print(f"🌟 已更新白名单，新增收录 {added_count} 个优质高可用目标至: {WHITELIST_FILE}")


def clean_channel_name(name):
    """清理频道名称：去掉空格，屏蔽并删除“高清”字样"""
    if not name:
        return ""
    name = name.replace("高清", "").replace("HD", "").replace("hd", "")
    return name.strip()


def get_channel_sort_key(ch_name):
    """为频道定义排序权重：
    1. 央视 (CCTV) 且 1-17 之间的排最前面，按数字排序
    2. 卫视频道排在中间
    3. 其他频道排在最后
    """
    name = ch_name.upper()

    if "CCTV" in name or "央视" in name:
        import re
        nums = re.findall(r"\d+", name)
        if nums:
            num = int(nums[0])
            if 1 <= num <= 17:
                return (1, num, ch_name)
        return (2, 0, ch_name)

    if "卫视" in name:
        return (3, 0, ch_name)

    return (4, 0, ch_name)


def test_ip_status(target_url):
    """前置预检：快速测试 IP 源是否可以正常访问（超时设为 5 秒）"""
    try:
        response = requests.get(target_url, timeout=5)
        if response.status_code < 400:
            return True
    except Exception:
        pass
    return False


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

            if name_lower in BLACK_LIST_KEYWORDS or key_lower in BLACK_LIST_KEYWORDS:
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

            clean_name = clean_channel_name(raw_name)
            if not clean_name:
                continue

            stream_url = f"{base_url}/hls/{key}/index.m3u8"
            channels.append({"name": clean_name, "url": stream_url})

        channels.sort(key=lambda x: get_channel_sort_key(x["name"]))

    except Exception as e:
        print(f"[浏览器访问异常] {base_url} -> {e}")
    finally:
        browser.close()

    return channels


def main():
    print("=" * 50)
    print(" 🚀 启动 IPTV 自动化抓取（已启用黑/白名单双向联动机制）...")
    print("=" * 50)

    # 1. 加载黑名单与白名单
    blacklist = load_blacklist()
    whitelist = load_whitelist()
    print(f"🛡️ 从 {BLACKLIST_FILE} 加载了 {len(blacklist)} 个已知失效黑名单 IP。")
    print(f"🌟 从 {WHITELIST_FILE} 加载了 {len(whitelist)} 个免检/受保护白名单 IP。")

    # 2. 读取输入文件
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            raw_ips = [
                line.strip()
                for line in f
                if line.strip() and not line.startswith("#")
            ]
    except FileNotFoundError:
        print(f"[错误] 找不到输入文件: {INPUT_FILE}")
        return

    print(f"📁 从 {INPUT_FILE} 总共加载了 {len(raw_ips)} 个原始目标。")

    # 3. 运行前自动过滤黑名单中的 IP
    filtered_ips = []
    skipped_by_blacklist = 0
    for ip_item in raw_ips:
        clean_ip = ip_item.replace("http://", "").replace("https://", "").rstrip("/")
        if clean_ip in blacklist:
            skipped_by_blacklist += 1
        else:
            filtered_ips.append(ip_item)

    print(f"🚫 已通过黑名单自动屏蔽 {skipped_by_blacklist} 个死 IP，实际待测: {len(filtered_ips)} 个。")

    grouped_channels = {}
    success_ip_count = 0
    new_failed_ips = []
    successful_ips = []  # 【新增】用于记录本次成功采集的 IP 列表

    with sync_playwright() as p:
        for ip_url in filtered_ips:
            target_url = (
                ip_url
                if ip_url.startswith("http://") or ip_url.startswith("https://")
                else f"http://{ip_url}"
            )

            base_host_key = target_url.replace("http://", "").replace("https://", "").rstrip("/")

            # 步骤 1：HTTP 状态预检（5秒超时）
            print(f"🔍 预检连通性: {target_url} ...", end=" ")
            if not test_ip_status(target_url):
                print("❌ [连接失败/超时]，跳过抓取")
                new_failed_ips.append(base_host_key)
                continue
            print("✅ [连通正常]，开始深度抓取")

            # 步骤 2：通过 Playwright 抓取频道
            channels = fetch_channels_with_browser(p, target_url)

            if channels and len(channels) >= 2:
                success_ip_count += 1
                print(
                    f"[✅ 采纳成功] {target_url} -> 成功提取并排序 {len(channels)}"
                    " 个真实频道"
                )
                grouped_channels[target_url] = channels
                successful_ips.append(base_host_key)  # 【新增】记录成功采集的 IP
            else:
                print(f"[⚠️ 过滤空壳页面] {target_url} -> 无有效频道，已丢弃")
                new_failed_ips.append(base_host_key)

    # 4. 运行结束后：将新失败的 IP 回填至黑名单（自动避开白名单）
    if new_failed_ips:
        update_blacklist(new_failed_ips, whitelist)

    # 5. 【新增】运行结束后：将本次成功采集的高质量 IP 自动追加保存至白名单
    if successful_ips:
        update_whitelist(successful_ips)

    print("-" * 50)
    print(f"🎉 任务处理完毕！")
    print(f"📡 有效且成功采集的 IP 数: {success_ip_count} 个")

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
