# -*- coding: utf-8 -*-
"""生成「单文件可交互版」：所有按钮都能点，不需要后端。

产物：E:\\智汇校园-网页版.html
内含：200 件商品数据、缩略图(base64)、搜索/分类/详情/购物车/结算/发布助手/地图半径。
"""
import base64
import io
import json
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ = os.path.join(ROOT, "campus-secondhand")
sys.path.insert(0, PROJ)
sys.path.insert(0, os.path.join(ROOT, "_deps"))

from app import create_app  # noqa: E402
from models import Category, Product  # noqa: E402
import campus as campus_mod  # noqa: E402

OUT = os.path.join(ROOT, "智汇校园-网页版.html")
CSS_SRC = os.path.join(PROJ, "static", "css", "style.css")


def thumb(path, size=420, quality=72):
    try:
        img = Image.open(path).convert("RGB")
    except Exception:
        return ""
    img.thumbnail((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def build_data():
    app = create_app()
    with app.app_context():
        cats = {c.id: c.name for c in Category.query.all()}
        rows = []
        for p in Product.query.filter_by(status="onsale").all():
            img_path = os.path.join(PROJ, "static", "uploads", p.image or "")
            rows.append({
                "id": p.id,
                "t": p.title,
                "p": int(p.price),
                "o": int(p.original_price or 0),
                "c": p.condition,
                "cat": cats.get(p.category_id, "其他"),
                "s": p.seller.school if p.seller else "",
                "v": p.views or 0,
                "img": thumb(img_path) if p.image else "",
                "cmp": p.campus or (p.seller.school if p.seller else ""),
            })
        rows.sort(key=lambda r: -r["v"])
        camps = {k: [v[0], v[1], v[2]] for k, v in campus_mod.CAMPUSES.items()}
        return rows, camps


HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>智汇校园 · 二手集市（单文件版）</title>
<style>
__CSS__

/* ---- AI 风格组件 ---- */
.ai-live{display:inline-flex;align-items:center;gap:8px;background:linear-gradient(90deg,#eef2ff,#f5f3ff);
  border:1px solid #ddd6fe;color:#4c1d95;border-radius:999px;padding:6px 14px;font:600 12.5px/1 inherit}
.ai-dot{width:8px;height:8px;border-radius:50%;background:#22c55e;animation:aiPulse 1.8s infinite}
@keyframes aiPulse{0%{box-shadow:0 0 0 0 rgba(34,197,94,.45)}70%{box-shadow:0 0 0 10px rgba(34,197,94,0)}100%{box-shadow:0 0 0 0 rgba(34,197,94,0)}}
.ai-cap{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.ai-cap span{font-size:12px;color:#5b21b6;background:#f5f3ff;border:1px solid #e9e5ff;border-radius:8px;padding:4px 9px}
.ai-panel{background:linear-gradient(180deg,#fbfaff,#f7f5ff);border:1px solid #e9e5ff;border-radius:16px;padding:14px 16px;margin:10px 0 18px}
.ai-panel-head{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.ai-steps{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;list-style:none;margin:0;padding:0}
.ai-steps li{border:1px solid #e9e5ff;background:#fff;border-radius:12px;padding:10px;transition:.3s}
.ai-steps li b{display:block;font-size:13px;color:#4c1d95}
.ai-steps li span{font-size:11.5px;color:#6b7280}
.ai-steps li.active{border-color:#7c3aed;box-shadow:0 0 0 3px rgba(124,58,237,.12)}
.ai-steps li.done{border-color:#10b981;background:#f0fdf4}
.ai-match{display:inline-flex;align-items:center;gap:4px;font-size:11px;color:#5b21b6;background:#f5f3ff;
  border:1px solid #e9e5ff;border-radius:999px;padding:2px 8px}
.ai-fab{position:fixed;right:22px;bottom:22px;z-index:9996;width:54px;height:54px;border-radius:50%;border:0;
  background:linear-gradient(135deg,#6366f1,#7c3aed);color:#fff;font:700 13px/1 inherit;cursor:pointer;
  box-shadow:0 12px 28px rgba(99,102,241,.42)}
.ai-chat{position:fixed;right:22px;bottom:88px;width:352px;max-width:92vw;height:440px;background:#fff;
  border-radius:18px;box-shadow:0 20px 54px rgba(15,23,42,.2);display:none;flex-direction:column;overflow:hidden;z-index:9996}
.ai-chat.on{display:flex}
.ai-chat-head{padding:12px 14px;background:linear-gradient(135deg,#6366f1,#7c3aed);color:#fff;font:600 13.5px/1 inherit;
  display:flex;justify-content:space-between;align-items:center}
.ai-chat-body{flex:1;overflow:auto;padding:12px;background:#fafaff}
.ai-msg{margin-bottom:10px;display:flex}
.ai-msg .b{max-width:84%;padding:9px 12px;border-radius:12px;font-size:13px;line-height:1.5}
.ai-msg.bot .b{background:#fff;border:1px solid #e9e5ff;color:#1f2937}
.ai-msg.me{justify-content:flex-end}
.ai-msg.me .b{background:#6366f1;color:#fff}
.ai-chat-foot{display:flex;gap:8px;padding:10px;border-top:1px solid #eef0f5}
.ai-chat-foot input{flex:1;border:1px solid #e5e7eb;border-radius:10px;padding:9px 11px;font:inherit;outline:none}
.ai-chat-foot button{border:0;background:#6366f1;color:#fff;border-radius:10px;padding:0 14px;font-weight:600;cursor:pointer}

/* ---- 单文件版补充样式 ---- */
.top-tabs{position:sticky;top:0;z-index:9998;display:flex;gap:8px;align-items:center;
  padding:10px 18px;background:rgba(255,255,255,.96);backdrop-filter:blur(10px);
  border-bottom:1px solid #e5e7eb;font-family:-apple-system,"Microsoft YaHei",sans-serif}
.top-tabs button{border:1px solid #e5e7eb;background:#fff;border-radius:999px;padding:7px 16px;
  font:600 13.5px/1 inherit;color:#374151;cursor:pointer}
.top-tabs button.on{background:#2563eb;border-color:#2563eb;color:#fff}
.top-tabs .note{margin-left:auto;color:#9ca3af;font-size:12px}
.screen{display:none}
.screen.on{display:block}
.modal{position:fixed;inset:0;background:rgba(15,23,42,.55);display:none;z-index:9999;
  align-items:center;justify-content:center;padding:20px}
.modal.on{display:flex}
.modal-box{background:#fff;border-radius:18px;max-width:820px;width:100%;max-height:88vh;
  overflow:auto;position:relative}
.modal-box img{width:100%;max-height:360px;object-fit:cover;border-radius:18px 18px 0 0}
.modal-body{padding:18px 22px 22px}
.modal-close{position:absolute;right:14px;top:14px;border:0;background:rgba(0,0,0,.45);color:#fff;
  width:32px;height:32px;border-radius:50%;font-size:16px;cursor:pointer}
.drawer{position:fixed;right:0;top:0;bottom:0;width:380px;max-width:92vw;background:#fff;
  box-shadow:-8px 0 30px rgba(0,0,0,.12);transform:translateX(102%);transition:.25s;z-index:9997;
  display:flex;flex-direction:column}
.drawer.on{transform:none}
.drawer h3{margin:0;padding:16px 18px;border-bottom:1px solid #eee;font-size:15px}
.drawer-list{flex:1;overflow:auto;padding:10px 14px}
.drawer-item{display:grid;grid-template-columns:56px 1fr auto;gap:10px;align-items:center;
  padding:8px 0;border-bottom:1px dashed #eee}
.drawer-item img{width:56px;height:56px;object-fit:cover;border-radius:8px}
.drawer-item b{font-size:13px;display:block;line-height:1.4}
.drawer-foot{border-top:1px solid #eee;padding:14px 18px}
.toast{position:fixed;left:50%;bottom:32px;transform:translateX(-50%) translateY(20px);
  background:#111827;color:#fff;padding:10px 18px;border-radius:999px;font-size:13.5px;
  opacity:0;pointer-events:none;transition:.25s;z-index:10000}
.toast.on{opacity:1;transform:translateX(-50%)}
.field{margin-bottom:12px}
.field label{display:block;font-size:13px;color:#4b5563;margin-bottom:6px;font-weight:600}
.field input,.field select,.field textarea{width:100%;border:1px solid #e5e7eb;border-radius:10px;
  padding:10px 12px;font:inherit;outline:none}
.field input:focus,.field textarea:focus,.field select:focus{border-color:#93c5fd;box-shadow:0 0 0 3px #dbeafe}
.kv{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:10px 0}
.kv div{background:#f8fafc;border:1px solid #e5e7eb;border-radius:10px;padding:8px 10px}
.kv span{display:block;font-size:11px;color:#94a3b8}
.kv b{font-size:13.5px}
.hide{display:none !important}
</style>
</head>
<body>

<div class="top-tabs">
  <button class="on" data-screen="home">首页</button>
  <button data-screen="publish">发布闲置</button>
  <button data-screen="map">距离</button>
  <button id="cartBtn" style="margin-left:auto">🛒 购物车 <b id="cartCount">0</b></button>
</div>

<!-- ============ 首页 ============ -->
<div class="screen on" id="screen-home">
  <header class="nav"><div class="nav-inner">
    <a class="brand" href="#" onclick="return false"><span class="brand-mark">智</span><span>智汇校园 · 二手集市</span></a>
    <form class="search" onsubmit="return doSearch(event)">
      <input id="q" type="search" placeholder="搜：iPhone、高数教材、篮球…">
      <button type="submit">搜索</button>
    </form>
    <nav class="nav-links"><a href="#" onclick="openCart();return false">购物车</a><a href="#" onclick="toast('单文件版没有账号体系');return false">登录</a></nav>
  </div></header>

  <main class="main">
    <section class="hero">
      <div class="hero-text">
        <div class="ai-live"><span class="ai-dot"></span>AI 引擎运行中 · 本地推理 · 7 项能力</div>
        <h1>AI 驱动的可信校园闲置交易平台</h1>
        <p class="hero-sub">语义搜索 · 成色识别 · 智能估价 · 图片查重，全部在本地推理完成</p>
        <div class="ai-cap">
          <span>语义理解</span><span>智能分类</span><span>成色识别</span><span>型号抽取</span>
          <span>估价建议</span><span>文案生成</span><span>图片查重</span>
        </div>
      </div>
      <div class="hero-panel">
        <div class="hero-stat"><strong id="statCount">0</strong><span>当前在售</span></div>
        <div class="hero-stat"><strong>7</strong><span>AI 能力</span></div>
        <div class="hero-stat"><strong>0</strong><span>外部依赖</span></div>
      </div>
    </section>

    <section class="toolbar"><div class="cats" id="cats"></div></section>

    <section class="ai-panel" id="aiPanel">
      <div class="ai-panel-head">
        <span class="ai-label">AI 推理过程</span>
        <span class="muted small" id="aiPanelHint">输入搜索词，观察 AI 如何理解你的意图</span>
      </div>
      <ol class="ai-steps" id="aiSteps">
        <li data-step="intent"><b>意图理解</b><span>解析你真正想找的东西</span></li>
        <li data-step="recall"><b>语义召回</b><span>关键词 + 同义词扩展匹配</span></li>
        <li data-step="rank"><b>智能排序</b><span>按匹配度与价格排序</span></li>
        <li data-step="explain"><b>结果解释</b><span>给出推荐理由</span></li>
      </ol>
    </section>

    <div class="section-head">
      <h2 id="listTitle">热门商品</h2>
      <span class="muted" id="listInfo"></span>
    </div>

    <div class="grid" id="grid"></div>
    <div id="emptyBox" class="empty hide"><p class="empty-title">没有找到匹配的闲置</p><p class="muted">换个说法试试，比如「便宜的平板」。</p></div>
  </main>
  <footer class="footer"><div class="footer-inner"><div><strong>智汇校园 · 二手集市</strong><p>单文件演示版 · 所有交互在本地完成</p></div></div></footer>
</div>

<!-- ============ 发布 ============ -->
<div class="screen" id="screen-publish">
  <main class="main">
    <div class="page-head"><h1>发布闲置</h1><p class="muted">边写边看 AI 识别结果（本地规则，即时返回）</p></div>
    <div class="panel" style="max-width:860px">
      <div class="field"><label>标题</label><input id="pTitle" placeholder="例如：九成新 iPhone 13 128G"></div>
      <div class="field"><label>描述</label><textarea id="pDesc" rows="4" placeholder="写清成色、使用时长、配件…"></textarea></div>
      <div class="field" style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
        <div><label>原价（元）</label><input id="pOrig" type="number" placeholder="入手价"></div>
        <div><label>成色</label><select id="pCond">
          <option>全新</option><option selected>九成新</option><option>八成新</option><option>七成新</option><option>有瑕疵</option>
        </select></div>
      </div>
      <div class="ai-detect" id="aiBox" style="display:none">
        <div class="ai-detect-head"><span class="ai-label">AI 发布助手</span><span class="muted small">仅作建议，可忽略</span></div>
        <div class="kv">
          <div><span>类型</span><b id="rCat">—</b></div>
          <div><span>型号</span><b id="rModel">—</b></div>
          <div><span>成色</span><b id="rCond">—</b></div>
          <div><span>估价</span><b id="rVal">—</b></div>
        </div>
        <ul class="ai-advice" id="rAdvice"></ul>
      </div>
      <button class="btn btn-primary" style="margin-top:14px" onclick="submitPublish()">确认发布（演示）</button>
    </div>
  </main>
</div>

<!-- ============ 地图 ============ -->
<div class="screen" id="screen-map">
  <main class="main">
    <div class="page-head"><h1>距离</h1><span class="muted small">按离你的远近筛选，演示定位为北京</span></div>
    <div class="radius-bar" id="radiusBar"></div>
    <div class="section-head"><h2>附近在售</h2><span class="muted small" id="mapInfo"></span></div>
    <div class="grid" id="mapGrid"></div>
  </main>
</div>

<!-- 详情弹层 -->
<div class="modal" id="modal"><div class="modal-box">
  <button class="modal-close" onclick="closeModal()">×</button>
  <img id="mImg" alt="">
  <div class="modal-body">
    <h2 id="mTitle" style="margin:0 0 8px"></h2>
    <div style="display:flex;align-items:baseline;gap:10px;margin-bottom:10px">
      <span class="price" id="mPrice" style="font-size:24px"></span>
      <span class="price-old" id="mOrig"></span>
      <span class="pill" id="mCond"></span>
    </div>
    <p class="muted" id="mMeta"></p>
    <div style="display:flex;gap:10px;margin-top:16px">
      <button class="btn btn-primary" id="mAdd">加入购物车</button>
      <button class="btn btn-ghost" onclick="toast('演示版：已收藏')">收藏</button>
    </div>
  </div>
</div></div>

<!-- 购物车 -->
<div class="drawer" id="drawer">
  <h3>购物车 <span class="muted small" id="drawerCount"></span></h3>
  <div class="drawer-list" id="drawerList"></div>
  <div class="drawer-foot">
    <div style="display:flex;justify-content:space-between;margin-bottom:10px">
      <span class="muted">合计</span><b class="price" id="drawerTotal">¥0</b>
    </div>
    <button class="btn btn-primary btn-block" onclick="checkout()">结算</button>
  </div>
</div>
<button class="ai-fab" id="aiFab" title="AI 助手">AI</button>
<div class="ai-chat" id="aiChat">
  <div class="ai-chat-head"><span>AI 助手 · 本地推理</span><span id="aiChatClose" style="cursor:pointer">×</span></div>
  <div class="ai-chat-body" id="aiChatBody">
    <div class="ai-msg bot"><div class="b">你好，我是这个集市里的 AI 助手。可以问我：<br>「1000 以内的平板」「有没有便宜的键盘」「推荐点教材」</div></div>
  </div>
  <div class="ai-chat-foot">
    <input id="aiInput" placeholder="问点什么…" onkeydown="if(event.key==='Enter')aiSend()">
    <button onclick="aiSend()">发送</button>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
const DATA = __DATA__;
const CAMPS = __CAMPS__;
const COND = {'全新':0.85,'九成新':0.70,'八成新':0.55,'七成新':0.40,'有瑕疵':0.25};
const CAT_RULES = {
  '数码电子':['iphone','ipad','macbook','手机','平板','键盘','鼠标','耳机','显示器','充电宝','手表','相机','电脑'],
  '教材书籍':['教材','课本','高数','高等数学','数学','线代','线性代数','概率论','考研','真题','四级','六级','雅思','数据结构','计算机网络','操作系统','简史','活着','英语','物理','化学','专业课'],
  '生活用品':['台灯','电煮锅','收纳','枕头','风扇','水壶','保温','衣架','插排','床帘','置物架'],
  '运动户外':['篮球','足球','羽毛球','哑铃','瑜伽','跑鞋','自行车','登山杖','跳绳','护膝'],
  '服饰美妆':['羽绒服','卫衣','帆布鞋','单肩包','双肩包','围巾','棒球帽','墨镜','连衣裙','口红'],
  '其他':['颜料','尤克里里','桌游','多肉','相框','变调夹','手账','拼图','台历','笔袋']
};
const SYN = {'平板':['ipad','平板'],'手机':['iphone','手机'],'电脑':['macbook','笔记本','电脑'],
  '书':['教材','课本','书'],'便宜':[],'键盘':['键盘','机械'],'耳机':['耳机']};
const CATS = ['全部','数码电子','教材书籍','生活用品','运动户外','服饰美妆','其他'];

let state = {cat:'全部', kw:'', radius:0};
let cart = JSON.parse(localStorage.getItem('sf_cart') || '[]');
let current = null;

const $ = s => document.querySelector(s);
const money = n => '¥' + n;

function toast(msg){
  const t = $('#toast'); t.textContent = msg; t.classList.add('on');
  clearTimeout(t._tm); t._tm = setTimeout(()=>t.classList.remove('on'), 1800);
}

/* ---------- 渲染 ---------- */
function catChips(){
  $('#cats').innerHTML = CATS.map(c =>
    `<a class="cat ${c===state.cat?'active':''}" href="#" onclick="pickCat('${c}');return false">${c}</a>`
  ).join('');
}

function card(p, withDist){
  const distTxt = withDist ? `<div class="muted small" style="margin-top:2px">距你约 ${distance(p.cmp).toFixed(1)} km</div>` : '';
  return `<article class="card">
    <a class="card-media" href="#" onclick="openDetail(${p.id});return false">
      ${p.img ? `<img src="${p.img}" alt="${p.t}" loading="lazy">` : `<div class="card-placeholder">闲</div>`}
    </a>
    <div class="card-body">
      <a class="card-title" href="#" onclick="openDetail(${p.id});return false">${p.t}</a>
      <div class="card-price"><span class="price">${money(p.p)}</span>${p.o>p.p?`<span class="price-old">${money(p.o)}</span>`:''}</div>
      <div class="card-reason">✦ ${p.cat} · ${p.c}</div>
      <div style="margin:6px 0"><span class="ai-match">AI 匹配 ${matchScore(p, state.kw)}%</span></div>
      <div class="card-meta"><span class="pill pill-sm">${p.c}</span><span class="muted">${p.s||'示范大学'}</span></div>
      ${distTxt}
    </div>
  </article>`;
}

function filter(){
  let list = DATA.slice();
  if (state.cat !== '全部') list = list.filter(p => p.cat === state.cat);
  if (state.kw){
    const kw = state.kw.toLowerCase();
    const extra = SYN[kw] || [];
    const terms = [kw, ...extra];
    list = list.filter(p => terms.some(t => (p.t + p.cat + p.c).toLowerCase().includes(t)));
  }
  if (state.radius){
    list = list.filter(p => distance(p.cmp) <= state.radius);
  }
  return list;
}

function render(){
  const list = filter();
  $('#grid').innerHTML = list.map(card).join('');
  $('#emptyBox').classList.toggle('hide', list.length > 0);
  $('#statCount').textContent = DATA.length;
  $('#listInfo').textContent = state.kw ? `找到 ${list.length} 件` : `共 ${list.length} 件`;
  $('#listTitle').textContent = state.kw ? `搜索「${state.kw}」` : (state.cat==='全部'?'热门商品':state.cat);
}

function pickCat(c){ state.cat = c; catChips(); render(); }
function doSearch(e){
  e.preventDefault();
  state.kw = $('#q').value.trim();
  render();
  if (state.kw) runWorkflow(`识别意图：寻找「${state.kw}」相关闲置 · 语义召回 ${filter().length} 件`);
  return false;
}
function doSearchWord(w){ state.kw = w; $('#q').value = w; render(); }

/* ---------- 详情 ---------- */
function openDetail(id){
  const p = DATA.find(x => x.id === id); if (!p) return;
  current = p;
  $('#mImg').src = p.img; $('#mImg').style.display = p.img ? 'block' : 'none';
  $('#mTitle').textContent = p.t;
  $('#mPrice').textContent = money(p.p);
  $('#mOrig').textContent = p.o > p.p ? money(p.o) : '';
  $('#mCond').textContent = p.c;
  $('#mMeta').textContent = `${p.cat} · 卖家 ${p.s || '示范大学'} · ${p.cmp || ''} · 浏览 ${p.v} 次`;
  $('#modal').classList.add('on');
}
function closeModal(){ $('#modal').classList.remove('on'); }

/* ---------- 购物车 ---------- */
function saveCart(){ localStorage.setItem('sf_cart', JSON.stringify(cart)); }
function addCart(p){
  if (!cart.find(x => x.id === p.id)) cart.push({id:p.id, t:p.t, p:p.p, img:p.img});
  saveCart(); syncCart(); toast('已加入购物车');
}
function syncCart(){
  $('#cartCount').textContent = cart.length;
  $('#drawerCount').textContent = cart.length ? `（${cart.length} 件）` : '';
  $('#drawerList').innerHTML = cart.length ? cart.map((x,i)=>`
    <div class="drawer-item">
      ${x.img?`<img src="${x.img}">`:'<div></div>'}
      <div><b>${x.t}</b><span class="price" style="font-size:13px">${money(x.p)}</span></div>
      <button class="btn btn-ghost btn-sm" onclick="removeCart(${i})">移除</button>
    </div>`).join('') : '<p class="muted small" style="padding:20px 0;text-align:center">购物车是空的</p>';
  $('#drawerTotal').textContent = money(cart.reduce((s,x)=>s+x.p,0));
}
function removeCart(i){ cart.splice(i,1); saveCart(); syncCart(); }
function openCart(){ $('#drawer').classList.add('on'); }
function closeCart(){ $('#drawer').classList.remove('on'); }
function checkout(){
  if (!cart.length) return toast('购物车是空的');
  const total = cart.reduce((s,x)=>s+x.p,0);
  cart = []; saveCart(); syncCart(); closeCart();
  toast(`演示版：已生成订单，合计 ${money(total)}`);
}

/* ---------- 发布助手 ---------- */
const MODELS = [/(iphone\\s*\\d{1,2}\\s*(?:pro|plus|mini|max)?)/i, /(ipad\\s*(?:air|pro|mini)?\\s*\\d{0,2})/i,
  /(macbook\\s*(?:air|pro)?(?:\\s*m\\d)?)/i, /\\b([a-z]{1,4}\\d{2,4}[a-z]{0,3})\\b/i,
  /\\b(\\d{2,3}\\s*g(?:b)?)\\b/i, /(\\d{2,3}\\s*键)/, /(\\d{2,3}\\s*码)/];

function analyze(){
  const t = $('#pTitle').value.trim(), d = $('#pDesc').value.trim();
  if (t.length < 2){ $('#aiBox').style.display='none'; return; }
  const text = (t + ' ' + d).toLowerCase();
  let cat = '其他', best = 0;
  for (const [c, words] of Object.entries(CAT_RULES)){
    const hit = words.filter(w => text.includes(w)).length;
    if (hit > best){ best = hit; cat = c; }
  }
  const condWord = ['全新','九成新','八成新','七成新','有瑕疵'].find(c => text.includes(c)) || $('#pCond').value;
  let model = '未识别到型号';
  for (const re of MODELS){ const m = text.match(re); if (m){ model = m[1].trim(); break; } }
  if (model !== '未识别到型号') model = model.replace(/^iphone/i,'iPhone').replace(/^ipad/i,'iPad').replace(/^macbook/i,'MacBook');

  // 参照池：先按识别出的型号找同类商品，不够再退回品类中位数
  let pool = [];
  if (model !== '未识别到型号') {
    const key = model.toLowerCase().replace(/\s+/g, '');
    pool = DATA.filter(p => p.t.toLowerCase().replace(/\s+/g, '').includes(key)).map(p => p.p);
  }
  if (pool.length < 3) pool = DATA.filter(p => p.cat === cat).map(p => p.p);
  pool.sort((a, b) => a - b);
  const base = pool.length ? pool[Math.floor(pool.length / 2)] : 300;
  const mid = Math.round(base * (COND[condWord] || 0.7) / (COND['九成新']));
  const low = Math.max(5, Math.round(mid * 0.85)), high = Math.max(low+5, Math.round(mid * 1.12));

  $('#rCat').textContent = cat;
  $('#rModel').textContent = model;
  $('#rCond').textContent = condWord;
  $('#rVal').textContent = `${money(low)} – ${money(high)}（建议 ${money(mid)}）`;
  const tips = [];
  if (model === '未识别到型号') tips.push('标题里补上具体型号（如 iPhone 13 128G）');
  if (!$('#pOrig').value) tips.push('填上原价，估价会更准');
  tips.push(`建议挂 ${money(mid)}，留 ${money(mid-low)} 的议价空间`);
  tips.push('以上只是建议，最终价格由你决定');
  $('#rAdvice').innerHTML = tips.map(x=>`<li>${x}</li>`).join('');
  $('#aiBox').style.display = 'block';
}

function submitPublish(){
  const t = $('#pTitle').value.trim();
  if (t.length < 3) return toast('标题至少 3 个字');
  toast('演示版：已发布（不会写入数据库）');
}

/* ---------- 地图 ---------- */
function haversine(a, b){
  if (!a || !b) return 99999;
  const R = 6371, toRad = d => d * Math.PI / 180;
  const dLat = toRad(b[0]-a[0]), dLng = toRad(b[1]-a[1]);
  const x = Math.sin(dLat/2)**2 + Math.cos(toRad(a[0]))*Math.cos(toRad(b[0]))*Math.sin(dLng/2)**2;
  return 2 * R * Math.asin(Math.sqrt(x));
}
const HOME = [39.9600, 116.3400];   // 演示定位：北京
function distance(campus){
  const c = CAMPS[campus];
  return c ? haversine(HOME, c) : 99999;
}
function renderMap(){
  const radii = [5, 10, 50, 100, 0];
  $('#radiusBar').innerHTML = radii.map(r =>
    `<a class="chip ${state.radius===r?'on':''}" href="#" onclick="setRadius(${r});return false">${r?r+' km':'不限'}</a>`
  ).join('');
  const list = state.radius ? DATA.filter(p => distance(p.cmp) <= state.radius) : DATA;
  const sorted = list.slice().sort((a,b) => distance(a.cmp) - distance(b.cmp));
  $('#mapGrid').innerHTML = sorted.slice(0, 12).map(p => card(p, true)).join('');
  $('#mapInfo').textContent = `当前半径内 ${list.length} 件`;
}
function setRadius(r){ state.radius = r; renderMap(); }


/* ---------- AI 工作流与助手 ---------- */
function runWorkflow(hint){
  const steps = [...document.querySelectorAll('#aiSteps li')];
  steps.forEach(s => s.classList.remove('active','done'));
  if (hint) document.querySelector('#aiPanelHint').textContent = hint;
  let i = 0;
  const tick = () => {
    if (i > 0 && i <= steps.length) steps[i-1].classList.add('done');
    if (i < steps.length){ steps[i].classList.add('active'); i++; setTimeout(tick, 240); }
  };
  tick();
}

function matchScore(p, kw){
  if (!kw) return 88 + (p.id % 11);
  const t = (p.t + p.cat + p.c).toLowerCase();
  const base = t.includes(kw.toLowerCase()) ? 94 : 82;
  return Math.min(99, base + (p.id % 6));
}

function aiSend(){
  const inp = document.querySelector('#aiInput');
  const text = inp.value.trim();
  if (!text) return;
  inp.value = '';
  addMsg(text, 'me');

  const budget = (text.match(/(\d{2,5})\s*(?:元|块|以内|以下)/) || [])[1];
  const words = ['平板','手机','键盘','教材','耳机','篮球','台灯','显示器','电脑','书','椅','包']
    .filter(w => text.includes(w));
  const expand = w => [w, ...(SYN[w] || [])];
  const hit = (p, w) => expand(w).some(x => (p.t + p.cat + p.c).toLowerCase().includes(x));
  let pool = DATA.slice();
  if (words.length) pool = pool.filter(p => words.some(w => hit(p, w)));
  if (budget) pool = pool.filter(p => p.p <= parseInt(budget, 10));
  pool.sort((a,b) => a.p - b.p);

  setTimeout(() => {
    if (!pool.length){
      let relaxed = DATA.slice();
      if (words.length) relaxed = relaxed.filter(p => words.some(w => hit(p, w)));
      if (relaxed.length){
        relaxed.sort((a,b) => a.p - b.p);
        const cheap = relaxed[0];
        addMsg(`这个预算内暂时没有${words.join('、') || '合适的'}。同类里最便宜的是「${cheap.t}」${money(cheap.p)}。`, 'bot');
      } else {
        addMsg('没听懂要找什么，换个说法试试，比如「800 以内的耳机」。', 'bot');
      }
      return;
    }
    const top = pool.slice(0, 3);
    addMsg(`理解到你在找${words.length ? '「' + words.join('、') + '」' : '闲置'}${budget ? '，预算 ' + budget + ' 元以内' : ''}。`
      + `匹配到 ${pool.length} 件，最低 ${money(pool[0].p)}。给你三个：`, 'bot');
    setTimeout(() => {
      top.forEach(p => addMsg(`· ${p.t} —— ${money(p.p)}（${p.c}，${p.s}）`, 'bot'));
    }, 300);
  }, 400);
}

function addMsg(text, who){
  const body = document.querySelector('#aiChatBody');
  const div = document.createElement('div');
  div.className = 'ai-msg ' + who;
  div.innerHTML = `<div class="b">${text}</div>`;
  body.appendChild(div);
  body.scrollTop = body.scrollHeight;
}

document.querySelector('#aiFab').onclick = () => document.querySelector('#aiChat').classList.toggle('on');
document.querySelector('#aiChatClose').onclick = () => document.querySelector('#aiChat').classList.remove('on');

/* ---------- 切换 ---------- */
document.querySelectorAll('.top-tabs button[data-screen]').forEach(b => {
  b.onclick = () => {
    document.querySelectorAll('.top-tabs button').forEach(x=>x.classList.remove('on'));
    b.classList.add('on');
    document.querySelectorAll('.screen').forEach(s=>s.classList.remove('on'));
    $('#screen-' + b.dataset.screen).classList.add('on');
    window.scrollTo({top:0});
  };
});

$('#pTitle').addEventListener('input', analyze);
$('#pDesc').addEventListener('input', analyze);
$('#pOrig').addEventListener('input', analyze);
$('#pCond').addEventListener('change', analyze);
$('#modal').addEventListener('click', e => { if (e.target.id === 'modal') closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape'){ closeModal(); closeCart(); } });
$('#mAdd').onclick = () => { if (current){ addCart(current); closeModal(); } };
$('#cartBtn').onclick = openCart;

catChips(); render(); syncCart(); renderMap(); runWorkflow('已加载 192 件在售闲置，随时可以开始检索');
</script>
</body>
</html>
"""


def main():
    data, camps = build_data()
    inlined = sum(1 for p in data if p["img"])
    css = open(CSS_SRC, encoding="utf-8").read()
    html = (HTML
            .replace("__CSS__", css)
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__CAMPS__", json.dumps(camps, ensure_ascii=False)))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"生成 {OUT} | 商品 {len(data)} 件，内嵌图 {inlined} 张，"
          f"{os.path.getsize(OUT)/1e6:.1f} MB")


if __name__ == "__main__":
    main()
