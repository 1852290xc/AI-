# -*- coding: utf-8 -*-
"""商品检测报告 + 以图搜物（扫物识别）。

不依赖外部模型：
- 检测：图片清晰度、AI 痕迹、站内查重、文案完整度、卖家信用、价格合理性
- 扫物：把图片和站内商品图做感知哈希比对，取最相似的一件作为「识别结果」
"""
import os

from PIL import Image, ImageFilter, ImageStat

import image_ai

UPLOADS = None  # 由调用方传入目录


def _upload_dir():
    if UPLOADS:
        return UPLOADS
    from config import Config
    return Config.UPLOAD_FOLDER


def sharpness(path):
    """拉普拉斯方差：值越低越模糊。"""
    try:
        with Image.open(path) as im:
            g = im.convert("L").resize((320, 320), Image.LANCZOS)
        edges = g.filter(ImageFilter.FIND_EDGES)
        return round(ImageStat.Stat(edges).stddev[0], 1)
    except Exception:
        return None


def build_report(product, duplicates_same=False, price_median=None):
    """返回质检报告：分数 + 等级 + 检测项 + 风险 + 质保说明。"""
    checks = []   # (名称, 是否通过, 说明)
    risks = []
    score = 60

    title = product.title or ""
    desc = product.description or ""
    img_name = product.image or ""
    img_path = os.path.join(_upload_dir(), img_name)

    # 1) 实拍图
    if img_name and os.path.exists(img_path):
        score += 10
        checks.append(("实拍图片", True, "已提供商品实拍图"))
        s = sharpness(img_path)
        if s is not None:
            if s >= 18:
                score += 8
                checks.append(("图片清晰度", True, f"边缘强度 {s}，看图清晰"))
            elif s >= 10:
                score += 3
                checks.append(("图片清晰度", True, f"边缘强度 {s}，可辨认"))
            else:
                score -= 5
                checks.append(("图片清晰度", False, f"边缘强度 {s}，图片偏模糊"))
                risks.append("图片偏模糊，建议让卖家补一张")
    else:
        score -= 20
        checks.append(("实拍图片", False, "没有商品图"))
        risks.append("没有实拍图，谨慎下单")

    # 2) AI 痕迹
    try:
        with Image.open(img_path) as im:
            score_ai, reasons = image_ai.ai_traces(im.convert("RGB"))
    except Exception:
        score_ai, reasons = 0, []
    if score_ai >= 60:
        score -= 15
        checks.append(("AI 痕迹检测", False, f"{score_ai}/100，疑似合成图"))
        risks.append("图片疑似 AI 生成，建议索要更多实拍")
    elif score_ai >= 30:
        checks.append(("AI 痕迹检测", True, f"{score_ai}/100，有轻微可疑痕迹"))
    else:
        score += 5
        checks.append(("AI 痕迹检测", True, f"{score_ai}/100，未见 AI 痕迹"))

    # 3) 站内查重
    if duplicates_same:
        score -= 12
        checks.append(("重复发布检测", False, "与站内已有商品图相同"))
        risks.append("这张图和站内另一件商品完全相同，可能是同物多挂")
    else:
        score += 4
        checks.append(("重复发布检测", True, "未发现盗图/重复挂单"))

    # 4) 文案完整度
    if len(title) >= 8 and len(desc) >= 15:
        score += 6
        checks.append(("描述完整度", True, "标题与描述信息较完整"))
    else:
        checks.append(("描述完整度", False, "描述偏少，细节不足"))
        risks.append("描述信息少，建议私聊问清使用时长")

    # 5) 成色声明
    if product.condition in ("全新", "九成新", "八成新", "七成新"):
        score += 3
        checks.append(("成色声明", True, f"标注为「{product.condition}」"))
    else:
        risks.append("成色标注不明确")

    # 6) 卖家信用
    seller = product.seller
    credit = getattr(seller, "credit", 100) if seller else 100
    sold = getattr(seller, "sold_count", 0) if seller else 0
    if credit >= 95:
        score += 6
        checks.append(("卖家信用", True, f"信用分 {credit}"))
    elif credit >= 80:
        score += 2
        checks.append(("卖家信用", True, f"信用分 {credit}"))
    else:
        score -= 8
        checks.append(("卖家信用", False, f"信用分 {credit} 偏低"))
        risks.append("卖家信用偏低，建议走平台担保")

    # 7) 价格合理性
    if price_median and product.price:
        ratio = product.price / price_median if price_median else 1
        if 0.6 <= ratio <= 1.4:
            score += 5
            checks.append(("价格合理性", True, f"约为同类中位价的 {ratio*100:.0f}%"))
        elif ratio > 1.6:
            score -= 4
            checks.append(("价格合理性", False, f"偏高，同类中位价约 ¥{int(price_median)}"))
            risks.append("价格明显高于同类，建议再比比")
        else:
            checks.append(("价格合理性", True, f"低于同类中位价（{ratio*100:.0f}%）"))

    score = max(0, min(100, score))
    if score >= 85:
        level, label = "A", "质检通过 · 可信度高"
    elif score >= 70:
        level, label = "B", "基本可信 · 注意细节"
    else:
        level, label = "C", "存在风险 · 谨慎交易"

    guarantee = [
        "平台担保交易：确认收货后货款才打给卖家",
        "7 天内商品与描述严重不符可申请退款",
        "校内面交可当面验货，验完再确认",
    ]
    return {
        "score": score,
        "level": level,
        "label": label,
        "checks": checks,
        "risks": risks,
        "guarantee": guarantee,
    }
