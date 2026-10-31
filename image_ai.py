"""图片查重与 AI 痕迹检测（本地启发式，不依赖外部模型）。

三件事：
1. dHash 感知哈希：判断两张图是不是同一张（含轻微压缩/裁剪）
2. AI 痕迹打分：EXIF、软件标记、尺寸、噪声一致性等启发式
3. 与站内商品图比对：找出「盗图 / 重复发布」
"""
import io
import math
import os

from PIL import Image, ImageChops, ImageFilter, ImageStat

AI_SOFTWARE = (
    "midjourney", "stable diffusion", "stablediffusion", "dall·e", "dall-e", "dalle",
    "firefly", "novelai", "comfyui", "automatic1111", "sd webui", "leonardo",
    "文心一格", "通义万相", "即梦", "liblib",
)

GEN_SIZES = {(512, 512), (768, 768), (1024, 1024), (1024, 1792), (1792, 1024),
             (1024, 1536), (1536, 1024), (832, 1216), (1216, 832)}


# ---------------------------------------------------------------- 哈希
def dhash(img, size=16):
    """差值哈希：返回 64/256 位整数。"""
    g = img.convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(g.getdata())
    bits = 0
    for row in range(size):
        base = row * (size + 1)
        for col in range(size):
            left = px[base + col]
            right = px[base + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def bits_of(value, size=16):
    return format(value, f"0{size * size}b")


def hamming(a, b, size=16):
    return bin(a ^ b).count("1")


def similarity(a, b, size=16):
    total = size * size
    return round(1 - hamming(a, b, size) / total, 3)


# ---------------------------------------------------------------- 元数据
def read_meta(img):
    meta = {"make": "", "model": "", "software": "", "datetime": "", "has_exif": False}
    try:
        exif = img.getexif()
    except Exception:
        return meta
    if not exif:
        return meta
    mapping = {271: "make", 272: "model", 305: "software", 306: "datetime"}
    for tag, key in mapping.items():
        try:
            val = exif.get(tag)
            if val:
                meta[key] = str(val).strip()
        except Exception:
            continue
    meta["has_exif"] = any(meta[k] for k in ("make", "model", "software", "datetime"))
    return meta


# ---------------------------------------------------------------- AI 痕迹
def noise_uniformity(img):
    """局部方差的离散程度：生成图往往噪声过于均匀。"""
    g = img.convert("L").resize((256, 256), Image.LANCZOS)
    edges = g.filter(ImageFilter.FIND_EDGES)
    stat = ImageStat.Stat(edges)
    std = stat.stddev[0]
    mean = stat.mean[0] or 1e-6
    return round(std / mean, 3)


def ai_traces(img, meta=None):
    """返回 (0-100 分, 理由列表)。分数越高越像 AI 生成。"""
    meta = meta or read_meta(img)
    score, reasons = 0, []

    software = (meta.get("software") or "").lower()
    for tool in AI_SOFTWARE:
        if tool in software:
            score += 55
            reasons.append(f"元数据里写着生成工具「{meta['software']}」")
            break

    if not meta.get("has_exif"):
        score += 12
        reasons.append("没有任何相机元数据（手机/相机拍的照片通常带 EXIF）")
    elif not meta.get("make") and not meta.get("model"):
        score += 8
        reasons.append("有元数据但没有相机厂商/机型")

    w, h = img.size
    if (w, h) in GEN_SIZES or (h, w) in GEN_SIZES:
        score += 15
        reasons.append(f"尺寸 {w}×{h} 是常见的生成分辨率")

    if w == h and w >= 1024 and w % 64 == 0:
        score += 6
        reasons.append("正方形且边长为 64 的整数倍（生成模型常见输出）")

    nu = noise_uniformity(img)
    if nu < 0.45:
        score += 14
        reasons.append(f"噪声分布过于均匀（指标 {nu}）")
    elif nu > 1.6:
        score += 6
        reasons.append(f"噪声分布异常（指标 {nu}）")

    if img.format == "PNG" or img.mode in ("RGBA", "LA", "P"):
        score += 10
        reasons.append("PNG / 带透明通道，常见于生成的素材图")

    return min(100, score), reasons


def verdict_of(score):
    if score >= 60:
        return "大概率是 AI 生成或合成图"
    if score >= 30:
        return "有 AI 生成的可疑痕迹"
    return "未发现明显的 AI 痕迹"


# ---------------------------------------------------------------- 比对
def compare(img_a, img_b):
    """判断两张图是否为同一张（容忍压缩与轻微裁剪）。"""
    ha, hb = dhash(img_a), dhash(img_b)
    sim = similarity(ha, hb)

    # 再用缩略图的灰度相关性做二次确认
    a = img_a.convert("L").resize((64, 64), Image.LANCZOS)
    b = img_b.convert("L").resize((64, 64), Image.LANCZOS)
    diff = ImageChops.difference(a, b)
    mad = ImageStat.Stat(diff).mean[0]
    corr = 1 - min(1.0, mad / 64.0)

    same = sim >= 0.88 or corr >= 0.97
    if sim >= 0.97:
        verdict = "是同一张图"
    elif same:
        verdict = "很可能是同一张（压缩或轻微裁剪）"
    elif sim >= 0.75:
        verdict = "有点像，但不是同一张"
    else:
        verdict = "不是同一张图"

    return {"same": same, "phash_sim": sim, "gray_corr": round(corr, 3),
            "distance": hamming(ha, hb), "verdict": verdict}


# ---------------------------------------------------------------- 站内查重
_CACHE = {}


def hash_of_file(path):
    if path in _CACHE:
        return _CACHE[path]
    try:
        with Image.open(path) as im:
            h = dhash(im.convert("RGB"))
        _CACHE[path] = h
        return h
    except Exception:
        return None


def find_duplicates(img, image_paths):
    """与站内已有图比对，返回 [(文件名, 相似度, 是否同一张)]，按相似度降序。"""
    target = dhash(img)
    out = []
    for name, path in image_paths:
        h = hash_of_file(path)
        if h is None:
            continue
        sim = similarity(target, h)
        out.append((name, sim, sim >= 0.88))
    out.sort(key=lambda x: x[1], reverse=True)
    return out[:5]


def load_image(stream):
    data = stream.read() if hasattr(stream, "read") else stream
    return Image.open(io.BytesIO(data)).convert("RGB")
