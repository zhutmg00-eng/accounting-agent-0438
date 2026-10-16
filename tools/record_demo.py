"""
AuditMind 实机演示录屏工具（未剪辑、原速）

录制内容：启动后端 → 浏览器打开指挥舱 → 切换到 STRICT 严格在线模式 → 选中康美药业 →
点击“执行数智穿透研判” → DeepSeek 思维链逐 token 实时推送 → 结论卡片生成。

输出（tools/out/）：
  demo_live.mp4  原速视频（推荐插入 PPT）
  demo_live.gif  原速动图（循环播放）
画面顶部是录制时的系统时钟，底部是同一时钟下的后端日志与浏览器实际收到的 SSE 事件。

用法（仓库根目录）：
  set DEEPSEEK_API_KEY=sk-xxxx                 (PowerShell: $env:DEEPSEEK_API_KEY="sk-xxxx")
  set DEEPSEEK_MODEL=deepseek-flash            (以 /models 返回的模型 id 为准)
  set DEEPSEEK_REASONING_EFFORT=low            (可选，low 推理约 40~60 秒)
  uv pip install playwright pillow imageio-ffmpeg
  uv run playwright install chromium
  uv run python tools/record_demo.py [--case REAL_CSRC_001] [--mode STRICT_ONLINE]
"""
import argparse
import bisect
import asyncio
import datetime
import glob
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "out")
PORT = 8501
BASE = f"http://127.0.0.1:{PORT}/"

ap = argparse.ArgumentParser()
ap.add_argument("--case", default="REAL_CSRC_001")
ap.add_argument("--case-name", default="康美药业股份有限公司")
ap.add_argument("--mode", default="STRICT_ONLINE", choices=["MOCK", "ONLINE", "STRICT_ONLINE"])
ap.add_argument("--timeout", type=int, default=240, help="等待推理完成的最长秒数")
ap.add_argument("--gif-width", type=int, default=1280)
ap.add_argument("--gif-fps", type=int, default=8)
args = ap.parse_args()

if args.mode != "MOCK" and not os.getenv("DEEPSEEK_API_KEY"):
    sys.exit("请先设置环境变量 DEEPSEEK_API_KEY")

os.makedirs(OUT, exist_ok=True)
raw_dir = os.path.join(OUT, "raw")
shutil.rmtree(raw_dir, ignore_errors=True)
os.makedirs(raw_dir)

# ── 1. 启动后端，逐行记录日志（带系统时间） ──────────────────────────────
for f in glob.glob(os.path.join(ROOT, "data", "cases", "custom_cases", "*.json")):
    os.remove(f)
env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
server = subprocess.Popen([sys.executable, "main.py", "--no-browser"], cwd=ROOT, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
log_events = []


def pump():
    for raw in iter(server.stdout.readline, b""):
        log_events.append({"wall": time.time(), "line": raw.decode("utf-8", "ignore").rstrip()})


threading.Thread(target=pump, daemon=True).start()
for _ in range(180):
    try:
        urllib.request.build_opener(urllib.request.ProxyHandler({})).open(BASE + "api/health", timeout=2)
        break
    except Exception:
        time.sleep(1)
else:
    server.kill()
    sys.exit("后端未能启动，请先确认 uv run python main.py --no-browser 可以运行")

# ── 2. 浏览器录屏 ──────────────────────────────────────────────────────
HOOK = """
window.__ev=[];const _ES=window.EventSource;
window.EventSource=function(u,o){const es=new _ES(u,o);
 es.addEventListener('message',e=>{window.__ev.push({w:Date.now(),d:e.data.slice(0,400)})});return es;};
window.EventSource.prototype=_ES.prototype;
"""


async def record():
    from playwright.async_api import async_playwright
    marks = {}
    async with async_playwright() as p:
        exe = os.getenv("CHROME_PATH")
        b = await p.chromium.launch(executable_path=exe, args=["--no-proxy-server"]) if exe else await p.chromium.launch(args=["--no-proxy-server"])
        ctx = await b.new_context(viewport={"width": 1920, "height": 1080})
        await ctx.add_init_script(HOOK)
        pg = await ctx.new_page()
        marks["t0"] = time.time()
        shots = []
        stop = asyncio.Event()

        async def grab():
            # 连续截屏：每帧记录真实系统时间，合成时按时间戳放置，不插值、不加速
            n = 0
            while not stop.is_set():
                try:
                    w = time.time()
                    fp = os.path.join(raw_dir, f"{n:05d}.jpg")
                    await pg.screenshot(path=fp, type="jpeg", quality=85)
                    shots.append((w, fp))
                    n += 1
                except Exception:
                    await asyncio.sleep(0.05)

        grabber = asyncio.create_task(grab())
        await pg.goto(BASE + "?tab=cockpit")
        await pg.wait_for_timeout(2500)
        sel = pg.locator('select[aria-label="选择运行模式"]')
        marks["mode_box"] = await sel.bounding_box()
        marks["mode_click"] = time.time()
        await sel.select_option(args.mode)
        await pg.wait_for_timeout(1200)
        item = pg.get_by_text(args.case_name).first
        marks["case_box"] = await item.bounding_box()
        marks["case_click"] = time.time()
        await item.click()
        await pg.wait_for_timeout(1000)
        btn = pg.get_by_text("执行数智穿透研判").first
        marks["run_box"] = await btn.bounding_box()
        await btn.hover()
        await pg.wait_for_timeout(600)
        marks["run_click"] = time.time()
        await btn.click()
        try:
            await pg.get_by_text("阶段 5 / 5 · 已完成").first.wait_for(timeout=args.timeout * 1000)
        except Exception as e:
            print("等待完成超时：", e)
        marks["done"] = time.time()
        await pg.wait_for_timeout(1800)
        marks["sse"] = await pg.evaluate("window.__ev")
        marks["end"] = time.time()
        stop.set()
        await grabber
        marks["shots"] = shots
        await ctx.close()
        await b.close()
    return marks


try:
    marks = asyncio.run(record())
finally:
    server.terminate()
time.sleep(0.5)
json.dump({"marks": {k: v for k, v in marks.items() if k != "shots"}, "log": log_events, "n_shots": len(marks["shots"])}, open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# ── 3. 合成：顶栏时钟 + 原始画面 + 同一时钟的后端日志 / SSE 事件 ─────────────
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG = shutil.which("ffmpeg") or sys.exit("需要 ffmpeg：uv pip install imageio-ffmpeg")


def font(cands, size, index=0):
    for c in cands:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size, index=index if c.endswith(".ttc") else 0)
            except Exception:
                continue
    return ImageFont.load_default()


CJK = ["C:/Windows/Fonts/msyh.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
       "/System/Library/Fonts/PingFang.ttc"]
CJKB = ["C:/Windows/Fonts/msyhbd.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/System/Library/Fonts/PingFang.ttc"]
MONO = ["C:/Windows/Fonts/consola.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/System/Library/Fonts/Menlo.ttc"]

W = 1920
BAR_H, TERM_H = 52, 300
H = BAR_H + 1080 + TERM_H
f_bar, f_url, f_clock = font(CJKB, 24), font(CJK, 21), font(MONO, 21)
f_hd, f_t, f_ts = font(CJKB, 19), font(CJK, 21), font(MONO, 19)

t0 = marks["t0"]
START = max(0.0, (marks["case_click"] if args.mode == "MOCK" else marks["mode_click"]) - t0 - 0.6)
END = marks["end"] - t0


def local(w):
    return datetime.datetime.fromtimestamp(w)


tz = datetime.datetime.now().astimezone().strftime("UTC%z")

lines = []
for e in log_events:
    l = e["line"]
    if "auditmind.llm" in l:
        lines.append((e["wall"], "LLM", l.split(" - ", 1)[-1]))
    elif '"GET /api/audit' in l or '"GET /api/cases/' in l:
        req = l.split('"')[1].replace(" HTTP/1.1", "")
        lines.append((e["wall"], "HTTP", f"{req}  →  {l.split(chr(34))[2].strip()}"))
cot_first = None
cot_count = 0
for e in marks["sse"]:
    w = e["w"] / 1000
    d = e["d"]
    if d.startswith("[DONE]"):
        lines.append((w, "SSE", "[DONE] 推送结束"))
        continue
    try:
        j = json.loads(d)
    except Exception:
        if '"final_report"' in d:
            lines.append((w, "SSE", "final_report 结构化报告回传"))
        continue
    if "stage" in j and j.get("status") == "completed":
        lines.append((w, "SSE", f"stage {j['stage']} ✓ {j['title']} | {j['detail'][:52]}"))
    elif j.get("type") in ("cot_token", "answer_token"):
        cot_count += 1
        if cot_first is None:
            cot_first = w
            lines.append((w, "SSE", f"{j['type']} 首包到达，live={j.get('live')}"))
lines.sort(key=lambda x: x[0])
cot_times = sorted(e["w"] / 1000 for e in marks["sse"] if '"cot_token"' in e["d"] or '"answer_token"' in e["d"])

FPS = 10
shot_walls = [w for w, _ in marks["shots"]]
n_out = int((END - START) * FPS)
frames = []
for i in range(n_out):
    w = t0 + START + i / FPS
    k = bisect.bisect_right(shot_walls, w) - 1
    frames.append(marks["shots"][max(k, 0)][1])
comp_dir = os.path.join(OUT, "comp")
shutil.rmtree(comp_dir, ignore_errors=True)
os.makedirs(comp_dir)


def ripple(d, box, dt):
    if not box or not (0 <= dt <= 0.6):
        return
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2 + BAR_H
    r = 12 + dt * 80
    a = int(255 * (1 - dt / 0.6))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 214, 10, a), width=5)
    d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=(255, 214, 10, a))



for i, fp in enumerate(frames):
    wall = t0 + START + i / FPS
    img = Image.new("RGBA", (W, H), (16, 18, 22, 255))
    img.paste(Image.open(fp).convert("RGBA").resize((1920, 1080)), (0, BAR_H))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for k in ("mode", "case", "run"):
        ripple(od, marks.get(f"{k}_box"), wall - marks[f"{k}_click"])
    img = Image.alpha_composite(img, ov).convert("RGB")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, BAR_H], fill=(236, 237, 239))
    d.ellipse([20, 18, 36, 34], fill=(192, 31, 47))
    d.text((48, 10), "实机录屏 · 未剪辑 · 原速", font=f_bar, fill=(23, 26, 31))
    d.text((380, 13), f"{BASE}?tab=cockpit   ·   模式 {args.mode}", font=f_url, fill=(80, 86, 94))
    now = local(wall)
    clock = now.strftime("%Y-%m-%d %H:%M:%S.") + str(now.microsecond // 100000) + (f" {tz}" if tz else "")
    d.text((W - d.textlength(clock, font=f_clock) - 22, 14), clock, font=f_clock, fill=(23, 26, 31))
    y0 = BAR_H + 1080
    d.rectangle([0, y0, W, H], fill=(14, 15, 17))
    n_tok = bisect.bisect_right(cot_times, wall)
    hd = "后端服务日志（uvicorn / DeepSeek 调用）｜ 浏览器实际收到的 SSE 事件 · 同一时钟"
    d.text((22, y0 + 12), hd, font=f_hd, fill=(150, 156, 164))
    if n_tok:
        tk = f"已收到流式增量 {n_tok} 个"
        d.text((W - d.textlength(tk, font=f_hd) - 22, y0 + 12), tk, font=f_hd, fill=(130, 220, 150))
    shown = [l for l in lines if l[0] <= wall][-9:]
    for k, (lw, kind, txt) in enumerate(shown):
        yy = y0 + 46 + k * 27
        t = local(lw)
        d.text((22, yy + 2), t.strftime("%H:%M:%S.") + f"{t.microsecond // 1000:03d}", font=f_ts, fill=(120, 126, 134))
        col = {"HTTP": (110, 190, 255), "LLM": (255, 196, 90), "SSE": (130, 220, 150)}[kind]
        d.text((180, yy + 2), kind, font=f_ts, fill=col)
        d.text((250, yy), txt, font=f_t, fill=(225, 228, 232))
    img.save(os.path.join(comp_dir, f"{i:05d}.png"))

pattern = os.path.join(comp_dir, "%05d.png")
mp4 = os.path.join(OUT, "demo_live.mp4")
gif = os.path.join(OUT, "demo_live.gif")
subprocess.run([FFMPEG, "-v", "error", "-y", "-framerate", str(FPS), "-i", pattern, "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", mp4], check=True)
pal = os.path.join(OUT, "pal.png")
vf = f"fps={args.gif_fps},scale={args.gif_width}:-1:flags=lanczos"
subprocess.run([FFMPEG, "-v", "error", "-y", "-i", mp4, "-vf", vf + ",palettegen=max_colors=160:stats_mode=diff", pal], check=True)
subprocess.run([FFMPEG, "-v", "error", "-y", "-i", mp4, "-i", pal, "-lavfi",
                vf + "[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle", "-loop", "0", gif], check=True)
shutil.rmtree(comp_dir, ignore_errors=True)
print(f"完成：{mp4}\n      {gif}\n推理时长 {marks['done'] - marks['run_click']:.1f}s，流式增量 {cot_count} 个")
