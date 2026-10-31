/* 智汇校园 · 前端交互
   1) 发布页实时 AI 辅助（防抖 300ms）
   2) 收藏异步切换
   3) 图片上传预览
   4) 聊天发送 / 轮询 / 自动滚底
   5) AI 助手对话
   6) 标签页切换
*/
(function () {
  "use strict";

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  function debounce(fn, wait) {
    let timer = null;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), wait);
    };
  }

  async function postJSON(url, data) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data || {}),
    });
    return res.json();
  }

  /* ---------------------------------------------------------- 发布页 */
  const form = $("#publishForm");
  if (form) {
    const title = $("#fTitle");
    const desc = $("#fDesc");
    const cond = $("#fCond");
    const original = $("#fOriginal");
    const price = $("#fPrice");
    const catBox = $("#aiCategory");
    const priceBox = $("#aiPrice");
    const tagBox = $("#aiTags");
    const warn = $("#aiModerate");
    const copyCard = $("#aiCopyCard");
    const copyText = $("#aiCopyText");

    const setHint = (box, label, text, hit) => {
      if (!box) return;
      box.querySelector(".ai-label").textContent = label;
      box.querySelector(".ai-body").textContent = text;
      box.classList.toggle("hit", !!hit);
    };

    const runClassify = debounce(async () => {
      const t = title.value.trim();
      if (t.length < 2) {
        setHint(catBox, "AI 分类", "输入标题后自动判断品类", false);
        return;
      }
      try {
        const r = await postJSON("/ai/classify", { title: t, description: desc.value });
        setHint(catBox, "AI 分类", `${r.category} · 置信度 ${Math.round(r.confidence * 100)}%`, true);
      } catch (e) { /* 静默失败，不打断用户 */ }
    }, 300);

    const runTags = debounce(async () => {
      const t = title.value.trim();
      if (!t) return;
      try {
        const r = await postJSON("/ai/tags", { title: t, description: desc.value });
        if (r.tags && r.tags.length) {
          setHint(tagBox, "AI 标签", r.tags.join(" · "), true);
        }
      } catch (e) {}
    }, 400);

    const runModerate = debounce(async () => {
      const text = `${title.value} ${desc.value}`.trim();
      if (!text) { warn.hidden = true; return; }
      try {
        const r = await postJSON("/ai/moderate", { text });
        if (!r.passed) {
          warn.hidden = false;
          warn.textContent = `⚠ ${r.message}`;
        } else {
          warn.hidden = true;
        }
      } catch (e) {}
    }, 400);

    const runPrice = debounce(async () => {
      const v = parseFloat(original.value || "0");
      if (!v) { setHint(priceBox, "AI 定价", "填写原价与成色后给出参考区间", false); return; }
      try {
        const r = await postJSON("/ai/price", { original_price: v, condition: cond.value });
        setHint(priceBox, "AI 定价", `建议 ${r.low}–${r.high} 元（${r.condition}，约 ${(r.discount * 10).toFixed(1)} 折）`, true);
        if (!price.value) price.placeholder = `建议挂 ¥${r.suggest}`;
      } catch (e) {}
    }, 250);

    const runCopy = debounce(async () => {
      const t = title.value.trim();
      if (t.length < 3) return;
      try {
        const cls = await postJSON("/ai/classify", { title: t, description: desc.value });
        const r = await postJSON("/ai/copy", {
          title: t, category: cls.category, condition: cond.value, original_price: original.value,
        });
        copyCard.hidden = false;
        copyText.textContent = r.copy;
        copyCard.dataset.copy = r.copy;
      } catch (e) {}
    }, 700);

    if (title) {
      title.addEventListener("input", () => { runClassify(); runTags(); runModerate(); runCopy(); });
      title.addEventListener("blur", runCopy);
    }
    if (desc) desc.addEventListener("input", () => { runTags(); runModerate(); runCopy(); });
    if (cond) cond.addEventListener("change", () => { runPrice(); runCopy(); });
    if (original) original.addEventListener("input", runPrice);

    const btnUse = $("#btnUseCopy");
    if (btnUse) {
      btnUse.addEventListener("click", () => {
        const text = copyCard.dataset.copy || "";
        if (!text) return;
        desc.value = desc.value ? `${desc.value}\n${text}` : text;
        desc.dispatchEvent(new Event("input"));
        btnUse.textContent = "已采纳 ✓";
        setTimeout(() => (btnUse.textContent = "一键采纳"), 1500);
      });
    }

    const file = $("#fImage");
    if (file) {
      file.addEventListener("change", () => {
        const f = file.files && file.files[0];
        const box = $("#preview");
        const img = $("#previewImg");
        if (!f) { box.hidden = true; return; }
        if (f.size > 5 * 1024 * 1024) {
          alert("图片超过 5MB，请压缩后再上传");
          file.value = "";
          box.hidden = true;
          return;
        }
        img.src = URL.createObjectURL(f);
        box.hidden = false;
        checkImage(f);
      });
    }
  }


  /* ---------------------------------------------------------- 定位 */
  const locBtn = document.getElementById("locBtn");
  if (locBtn) {
    locBtn.addEventListener("click", () => {
      if (locBtn.dataset.on === "1") { return; }
      if (!navigator.geolocation) {
        alert("当前浏览器不支持定位，可以直接浏览全部商品");
        return;
      }
      locBtn.textContent = "定位中…";
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          try {
            const r = await postJSON("/api/location", {
              lat: pos.coords.latitude, lng: pos.coords.longitude,
            });
            if (r.ok) { location.reload(); }
            else { locBtn.textContent = "📍 开启定位"; alert(r.message || "定位失败"); }
          } catch (e) { locBtn.textContent = "📍 开启定位"; }
        },
        () => {
          locBtn.textContent = "📍 开启定位";
          alert("没有拿到定位权限。商品照常浏览，只是不按距离排序。");
        },
        { timeout: 8000, maximumAge: 600000 },
      );
    });
  }

  const locClear = document.getElementById("locClear");
  if (locClear) {
    locClear.addEventListener("click", async () => {
      try {
        await fetch("/api/location", { method: "DELETE" });
      } catch (e) {}
      location.reload();
    });
  }

  /* ---------------------------------------------------------- 购物车 */
  const cartBtn = $("#cartBtn");
  if (cartBtn) {
    cartBtn.addEventListener("click", async () => {
      cartBtn.disabled = true;
      try {
        const r = await postJSON(`/cart/add/${cartBtn.dataset.pid}`);
        cartBtn.textContent = r.ok ? "已加入购物车 ✓" : r.message;
        if (r.ok) {
          const badge = document.querySelector(".nav-badge");
          if (badge) badge.textContent = r.count;
        }
        setTimeout(() => { cartBtn.textContent = "加入购物车"; cartBtn.disabled = false; }, 1600);
      } catch (e) {
        cartBtn.textContent = "请先登录";
        setTimeout(() => { cartBtn.textContent = "加入购物车"; cartBtn.disabled = false; }, 1600);
      }
    });
  }



  async function checkImage(file) {
    const panel = document.getElementById("imgCheck");
    const body = document.getElementById("imgCheckBody");
    if (!panel || !body) return;
    panel.hidden = false;
    body.innerHTML = '<p class="muted small">检测中…</p>';

    const fd = new FormData();
    fd.append("file", file);
    const refUrl = panel.dataset.reference;
    if (refUrl) {
      try {
        const blob = await (await fetch(refUrl)).blob();
        fd.append("reference", blob, "reference.jpg");
      } catch (e) {}
    }

    let data;
    try {
      const res = await fetch("/ai/image-check", { method: "POST", body: fd });
      data = await res.json();
    } catch (e) {
      body.innerHTML = '<p class="warn-text">检测失败，稍后再试</p>';
      return;
    }
    if (!data.ok) {
      body.innerHTML = '<p class="warn-text">' + (data.message || "检测失败") + "</p>";
      return;
    }

    const d = data.duplicates && data.duplicates[0];
    const dupLine = (d && d.same)
      ? '<p class="warn-text">⚠ 查重命中：与已有商品「' + (d.title || d.image) + '」是同一张图（相似度 ' +
        Math.round(d.sim * 100) + '%）</p>'
      : (d ? '<p class="muted small">查重：与库内最相似的图只有 ' + Math.round(d.sim * 100) + '% 相似，不构成重复</p>'
           : '<p class="muted small">查重：库里还没有可比的图片</p>');

    const ai = data.ai;
    const aiClass = ai.score >= 60 ? "warn-text" : (ai.score >= 30 ? "muted" : "muted small");
    const aiLine = '<p class="' + aiClass + '">AI 痕迹：' + ai.verdict + '（' + ai.score + '/100）' +
      (ai.reasons.length ? " · " + ai.reasons.slice(0, 2).join("；") : "") + "</p>";

    let cmpLine = "";
    if (data.compare) {
      cmpLine = '<p class="' + (data.compare.same ? "warn-text" : "muted small") + '">与参考图比对：' +
        data.compare.verdict + "（相似度 " + Math.round(data.compare.phash_sim * 100) + "%）</p>";
    }

    body.innerHTML = dupLine + aiLine + cmpLine;
  }

  /* ---------------------------------------------------------- AI 发布助手 */
  const det = document.getElementById("aiDetect");
  if (det) {
    const dTitle = document.getElementById("fTitle");
    const dDesc = document.getElementById("fDesc");
    const dOrig = document.getElementById("fOriginal");
    const dCat = document.getElementById("detCat");
    const dModel = document.getElementById("detModel");
    const dCond = document.getElementById("detCond");
    const dValue = document.getElementById("detValue");
    const dSource = document.getElementById("detSource");
    const dAdvice = document.getElementById("detAdvice");
    let latest = null;

    let condTouched = false;
    const condSel = document.getElementById("fCond");
    if (condSel) condSel.addEventListener("change", () => { condTouched = true; });

    const render = (r) => {
      latest = r;
      det.hidden = false;
      // 用户没手动改过成色时，跟随 AI 判断（仍可改回）
      if (!condTouched && r.condition && condSel && condSel.value !== r.condition) {
        condSel.value = r.condition;
        condSel.dispatchEvent(new Event("change", { bubbles: true }));
        condTouched = false;
      }
      dCat.textContent = r.category + " · " + Math.round(r.confidence * 100) + "%";
      dModel.textContent = (r.model && r.model.length) ? r.model.join(" / ") : "未识别到型号";
      dCond.textContent = r.condition || "未判断出成色";
      dValue.textContent = "¥" + r.value.low + " – " + r.value.high + "（建议 ¥" + r.value.mid + "）";
      dSource.textContent = r.value.source;
      dAdvice.innerHTML = (r.advice || []).map((t) => "<li>" + t + "</li>").join("");
    };

    const runAnalyze = debounce(async () => {
      const t = (dTitle.value || "").trim();
      if (t.length < 2) { return; }
      try {
        const r = await postJSON("/ai/analyze", {
          title: t,
          description: dDesc.value,
          original_price: dOrig.value,
          has_image: !!(document.getElementById("fImage").files || []).length,
        });
        if (r && r.ok) render(r);
      } catch (e) {}
    }, 500);

    [dTitle, dDesc, dOrig].forEach((el) => el && el.addEventListener("input", runAnalyze));

    det.addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-adopt]");
      if (!btn || !latest) return;
      const kind = btn.dataset.adopt;
      if (kind === "category") {
        const sel = document.getElementById("fCat");
        const opt = Array.from(sel.options).find((o) => o.textContent.includes(latest.category));
        if (opt) sel.value = opt.value;
      } else if (kind === "condition") {
        const sel = document.getElementById("fCond");
        if (latest.condition) sel.value = latest.condition;
      } else if (kind === "price") {
        const inp = document.getElementById("fPrice");
        if (!inp.value) inp.value = latest.value.mid;
        inp.placeholder = "建议 " + latest.value.mid;
      }
      btn.textContent = "已采用 ✓";
      setTimeout(() => { btn.textContent = btn.dataset.original || "采用"; }, 1500);
    });
  }

  /* ---------------------------------------------------------- 收藏 */
  const favBtn = $("#favBtn");
  if (favBtn) {
    favBtn.addEventListener("click", async () => {
      favBtn.disabled = true;
      try {
        const r = await postJSON(`/product/${favBtn.dataset.pid}/favorite`);
        if (r.ok) {
          favBtn.dataset.on = r.favorited ? "1" : "0";
          favBtn.textContent = r.favorited ? "已收藏" : "收藏";
          favBtn.classList.toggle("active", r.favorited);
        }
      } catch (e) {
        alert("操作失败，请重新登录后再试");
      } finally {
        favBtn.disabled = false;
      }
    });
  }

  /* ---------------------------------------------------------- 聊天 */
  const chatPage = $("#chatPage");
  if (chatPage) {
    const peer = chatPage.dataset.peer;
    const body = $("#chatBody");
    const input = $("#chatText");
    const sendBtn = $("#chatSend");
    const warn = $("#chatWarn");
    let lastId = parseInt(chatPage.dataset.last || "0", 10);

    const scrollBottom = () => { body.scrollTop = body.scrollHeight; };
    scrollBottom();

    function addBubble(msg, mine) {
      const row = document.createElement("div");
      row.className = `bubble-row${mine ? " mine" : ""}`;
      row.innerHTML = `<div class="bubble ${mine ? "bubble-mine" : "bubble-other"}">${msg}
        <span class="bubble-time">刚刚</span></div>`;
      body.appendChild(row);
      scrollBottom();
    }

    async function send() {
      const text = input.value.trim();
      if (!text) return;
      sendBtn.disabled = true;
      try {
        const r = await postJSON("/message/send", { to: peer, content: text });
        if (r.ok) {
          addBubble(r.message.content, true);
          input.value = "";
          warn.hidden = true;
        } else if (r.blocked) {
          warn.hidden = false;
          warn.textContent = `⚠ ${r.message}`;
        } else {
          warn.hidden = false;
          warn.textContent = r.message || "发送失败";
        }
      } catch (e) {
        warn.hidden = false;
        warn.textContent = "网络异常，消息未发送";
      } finally {
        sendBtn.disabled = false;
        input.focus();
      }
    }

    sendBtn.addEventListener("click", send);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });

    // 每 5 秒拉一次新消息
    setInterval(async () => {
      try {
        const res = await fetch(`/message/poll/${peer}?since=${lastId}`);
        const list = await res.json();
        list.forEach((m) => {
          lastId = Math.max(lastId, m.id);
          if (!m.mine) addBubble(m.content, false);
        });
      } catch (e) {}
    }, 5000);
  }

  /* ---------------------------------------------------------- AI 助手 */
  const asBody = $("#assistantBody");
  if (asBody) {
    const input = $("#assistantText");
    const sendBtn = $("#assistantSend");

    const add = (text, mine) => {
      const row = document.createElement("div");
      row.className = `bubble-row${mine ? " mine" : ""}`;
      row.innerHTML = `<div class="bubble ${mine ? "bubble-mine" : "bubble-other"}">${text}</div>`;
      asBody.appendChild(row);
      asBody.scrollTop = asBody.scrollHeight;
    };

    async function ask(q) {
      if (!q.trim()) return;
      add(q, true);
      input.value = "";
      try {
        const r = await postJSON("/ai/chat", { question: q });
        add(r.answer, false);
      } catch (e) {
        add("网络异常，暂时无法回答。", false);
      }
    }

    sendBtn.addEventListener("click", () => ask(input.value));
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") ask(input.value); });
    $$(".chip").forEach((c) => c.addEventListener("click", () => ask(c.dataset.q)));
  }

  /* ---------------------------------------------------------- tabs */
  $$("[data-tabs]").forEach((group) => {
    const tabs = $$(".tab", group);
    tabs.forEach((t) => {
      t.addEventListener("click", () => {
        tabs.forEach((x) => x.classList.remove("active"));
        t.classList.add("active");
        const target = t.dataset.tab;
        $$(".tab-panel").forEach((p) => p.classList.toggle("active", p.dataset.panel === target));
      });
    });
  });
})();


/* ---------- 分类收放 ---------- */
function toggleTaxo(){
  const panel = document.getElementById("taxoPanel");
  const txt = document.getElementById("taxoTxt");
  const arrow = document.getElementById("taxoArrow");
  if (!panel) return;
  const collapsed = panel.classList.toggle("collapsed");
  txt.textContent = collapsed ? "展开" : "收起";
  arrow.textContent = collapsed ? "▾" : "▴";
  try { localStorage.setItem("taxo_collapsed", collapsed ? "1" : "0"); } catch (e) {}
}
document.addEventListener("DOMContentLoaded", function(){
  try {
    if (localStorage.getItem("taxo_collapsed") === "1") toggleTaxo();
  } catch (e) {}
});
