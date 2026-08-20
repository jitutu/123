(function () {
  const canvas = document.getElementById('mark-canvas');
  const stage = document.getElementById('paper-stage');
  const ctx = canvas.getContext('2d');
  const zoomLabel = document.getElementById('zoom-label');
  const saveStateEl = document.getElementById('save-state');

  let img = null;
  let scale = 1, offsetX = 0, offsetY = 0;
  let tool = 'hand';
  let side = 'front';
  let annotations = (typeof ANNOTATIONS !== 'undefined' && Array.isArray(ANNOTATIONS)) ? ANNOTATIONS.slice() : [];
  let drawing = null, isDrawing = false, penPoints = [];

  // ---------- 图片 ----------
  function loadImage(url) {
    const el = new Image();
    el.onload = () => { img = el; fit(); };
    el.src = url;
  }

  // ---------- 渲染 ----------
  function resizeCanvas() {
    canvas.width = stage.clientWidth;
    canvas.height = stage.clientHeight;
  }

  function fit() {
    if (!img) return;
    resizeCanvas();
    const w = stage.clientWidth, h = stage.clientHeight;
    scale = Math.min(w / img.width, h / img.height, 1);
    offsetX = (w - img.width * scale) / 2;
    offsetY = (h - img.height * scale) / 2;
    draw();
    updateZoomLabel();
  }

  function draw() {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.setTransform(scale, 0, 0, scale, offsetX, offsetY);
    if (img) ctx.drawImage(img, 0, 0);
    ctx.lineWidth = 2.5 / scale;
    ctx.strokeStyle = '#e11d48';
    ctx.fillStyle = '#e11d48';
    ctx.font = (20 / scale) + 'px sans-serif';
    annotations.forEach(a => drawAnnotation(a));
    if (drawing) drawAnnotation(drawing, true);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
  }

  function drawAnnotation(a, temp) {
    ctx.save();
    ctx.strokeStyle = a.color || '#e11d48';
    ctx.fillStyle = a.color || '#e11d48';
    ctx.lineWidth = (temp ? 2 : 2.5) / scale;
    switch (a.type) {
      case 'pen': {
        ctx.beginPath();
        a.points.forEach((p, i) => i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y));
        ctx.stroke();
        break;
      }
      case 'text':
        ctx.fillText(a.text, a.x, a.y);
        break;
      case 'tick': {
        const mx = a.x1 + (a.x2 - a.x1) * 0.35;
        const my = a.y1 + (a.y2 - a.y1) * 0.55;
        ctx.beginPath();
        ctx.moveTo(a.x1, a.y1); ctx.lineTo(mx, my); ctx.lineTo(a.x2, a.y2);
        ctx.stroke();
        break;
      }
      case 'cross':
        ctx.beginPath();
        ctx.moveTo(a.x1, a.y1); ctx.lineTo(a.x2, a.y2);
        ctx.moveTo(a.x1, a.y2); ctx.lineTo(a.x2, a.y1);
        ctx.stroke();
        break;
      case 'oval': {
        const cx = (a.x1 + a.x2) / 2, cy = (a.y1 + a.y2) / 2;
        const rx = Math.abs(a.x2 - a.x1) / 2, ry = Math.abs(a.y2 - a.y1) / 2;
        ctx.beginPath();
        ctx.ellipse(cx, cy, Math.max(rx, 1), Math.max(ry, 1), 0, 0, Math.PI * 2);
        ctx.stroke();
        break;
      }
      case 'underline':
        ctx.beginPath();
        ctx.moveTo(a.x1, a.y1); ctx.lineTo(a.x2, a.y2);
        ctx.stroke();
        break;
    }
    ctx.restore();
  }

  function updateZoomLabel() {
    zoomLabel.textContent = Math.round(scale * 100) + '%';
  }

  // ---------- 坐标转换 ----------
  function toImgXY(ev) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: (ev.clientX - rect.left - offsetX) / scale,
      y: (ev.clientY - rect.top - offsetY) / scale,
    };
  }

  // ---------- 交互 ----------
  let lastDrag = null;

  canvas.addEventListener('mousedown', e => {
    const p = toImgXY(e);
    if (tool === 'hand') {
      lastDrag = { x: e.clientX, y: e.clientY };
      return;
    }
    isDrawing = true;
    if (tool === 'pen') {
      penPoints = [p];
      drawing = { type: 'pen', points: penPoints };
    } else if (tool === 'text') {
      const text = prompt('请输入批注文字：');
      if (text) {
        annotations.push({ type: 'text', x: p.x, y: p.y, text: text.slice(0, 50) });
        queueSave();
      }
      isDrawing = false;
    } else {
      drawing = { type: tool, x1: p.x, y1: p.y, x2: p.x, y2: p.y };
    }
    draw();
  });

  canvas.addEventListener('mousemove', e => {
    if (tool === 'hand' && lastDrag) {
      offsetX += e.clientX - lastDrag.x;
      offsetY += e.clientY - lastDrag.y;
      lastDrag = { x: e.clientX, y: e.clientY };
      draw();
      return;
    }
    if (!isDrawing || !drawing) return;
    const p = toImgXY(e);
    if (drawing.type === 'pen') {
      penPoints.push(p);
    } else {
      drawing.x2 = p.x;
      drawing.y2 = p.y;
    }
    draw();
  });

  canvas.addEventListener('mouseup', () => {
    lastDrag = null;
    if (!isDrawing) return;
    isDrawing = false;
    if (drawing) {
      if (tool === 'eraser') {
        eraseNear(drawing);
      } else if (isValidShape(drawing)) {
        annotations.push(drawing);
        queueSave();
      }
      drawing = null;
    }
    draw();
  });

  canvas.addEventListener('wheel', e => {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const ix = (mx - offsetX) / scale, iy = (my - offsetY) / scale;
    const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
    scale = Math.min(6, Math.max(0.05, scale * factor));
    offsetX = mx - ix * scale;
    offsetY = my - iy * scale;
    draw();
    updateZoomLabel();
  }, { passive: false });

  function isValidShape(a) {
    if (a.type === 'text') return !!a.text;
    return Math.abs(a.x2 - a.x1) > 2 / scale && Math.abs(a.y2 - a.y1) > 2 / scale;
  }

  function eraseNear(target) {
    const cx = (target.x1 + target.x2) / 2, cy = (target.y1 + target.y2) / 2;
    const radius = Math.max(8 / scale, (Math.abs(target.x2 - target.x1) + Math.abs(target.y2 - target.y1)) / 2);
    let best = -1, bestDist = radius;
    annotations.forEach((a, i) => {
      const d = distToAnnotation(a, cx, cy);
      if (d <= bestDist) { bestDist = d; best = i; }
    });
    if (best >= 0) {
      annotations.splice(best, 1);
      queueSave();
    }
  }

  function distToAnnotation(a, x, y) {
    if (a.type === 'pen') {
      let min = Infinity;
      a.points.forEach(p => {
        const d = Math.hypot(p.x - x, p.y - y);
        if (d < min) min = d;
      });
      return min;
    }
    if (a.type === 'text') return Math.hypot(a.x - x, a.y - y);
    const cx = (a.x1 + a.x2) / 2, cy = (a.y1 + a.y2) / 2;
    const rx = Math.abs(a.x2 - a.x1) / 2 + 6 / scale, ry = Math.abs(a.y2 - a.y1) / 2 + 6 / scale;
    if (x >= cx - rx && x <= cx + rx && y >= cy - ry && y <= cy + ry) return 0;
    return Math.min(Math.hypot(x - (cx - rx), y - (cy - ry)), Math.hypot(x - (cx + rx), y - (cy + ry)));
  }

  // ---------- 批注保存 ----------
  let saveTimer;
  function queueSave() {
    setSaveState('批注保存中...');
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveAnnotations, 500);
  }

  async function saveAnnotations() {
    try {
      const resp = await fetch(SAVE_ANN_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paper_id: PAPER_ID, question_id: 0, data: JSON.stringify(annotations) }),
      });
      const r = await resp.json();
      setSaveState(r.ok ? '批注已同步' : '批注保存失败');
    } catch (e) {
      setSaveState('批注保存失败');
    }
  }

  function setSaveState(text) {
    saveStateEl.textContent = text;
  }

  // ---------- 工具栏 ----------
  document.querySelectorAll('.tool-btn[data-tool]').forEach(btn => {
    btn.addEventListener('click', () => {
      tool = btn.dataset.tool;
      document.querySelectorAll('.tool-btn[data-tool]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });

  document.getElementById('clear-ann').addEventListener('click', () => {
    if (confirm('确认清空本卷所有批注？')) {
      annotations = [];
      queueSave();
      draw();
    }
  });

  document.getElementById('zoom-in').addEventListener('click', () => {
    scale = Math.min(6, scale * 1.3);
    draw(); updateZoomLabel();
  });
  document.getElementById('zoom-out').addEventListener('click', () => {
    scale = Math.max(0.05, scale / 1.3);
    draw(); updateZoomLabel();
  });
  document.getElementById('zoom-fit').addEventListener('click', fit);

  document.getElementById('side-front').addEventListener('click', () => {
    side = 'front';
    document.getElementById('side-front').classList.add('active');
    document.getElementById('side-back').classList.remove('active');
    loadImage(FRONT_URL);
  });
  document.getElementById('side-back').addEventListener('click', () => {
    if (!BACK_URL) return;
    side = 'back';
    document.getElementById('side-back').classList.add('active');
    document.getElementById('side-front').classList.remove('active');
    loadImage(BACK_URL);
  });

  // ---------- 评分 ----------
  function saveScore(input) {
    const qid = parseInt(input.dataset.qid, 10);
    let val = parseFloat(input.value);
    if (isNaN(val)) val = 0;
    const q = QUESTIONS.find(x => x.id === qid);
    if (q && val > q.score) { val = q.score; input.value = val; }
    if (val < 0) { val = 0; input.value = 0; }

    return fetch(SAVE_SCORE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paper_id: PAPER_ID, question_id: qid, score: val }),
    }).then(r => r.json()).then(r => {
      if (r.ok) {
        const box = document.getElementById('scored-' + qid);
        const existing = box.querySelectorAll('.badge-green');
        existing.forEach(el => el.remove());
        const badge = document.createElement('span');
        badge.className = 'badge badge-green';
        badge.textContent = '已保存 ' + val + ' 分';
        box.appendChild(badge);
        setSaveState('第 ' + qid + ' 题得分已保存');
      } else {
        setSaveState('得分保存失败');
      }
    });
  }

  document.querySelectorAll('.score-box').forEach(input => {
    input.addEventListener('change', () => saveScore(input));
  });
  document.querySelectorAll('.score-save').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = document.querySelector('.score-box[data-qid="' + btn.dataset.qid + '"]');
      if (input) saveScore(input);
    });
  });

  // ---------- 客观题识别结果显示 ----------
  QUESTIONS.filter(q => q.type !== 'subjective').forEach(q => {
    const el = document.getElementById('rec-' + q.id);
    const rec = RECOGNIZED ? RECOGNIZED[String(q.no)] : null;
    if (rec && rec.answer && rec.answer.length) {
      const marks = rec.answer.join('');
      const ans = q.answer || '';
      let correct = false;
      if (q.type === 'multi') {
        correct = rec.answer.slice().sort().join('') === ans.split('').sort().join('');
      } else {
        correct = marks === ans;
      }
      el.textContent = '识别结果：' + marks;
      el.className = 'q-recognized ' + (correct ? 'q-correct' : 'q-wrong');
    } else {
      el.textContent = '识别结果：未识别/未涂';
      el.className = 'q-recognized';
    }
  });

  // ---------- 主观题答题区域 ----------
  document.querySelectorAll('.view-area').forEach(btn => {
    btn.addEventListener('click', () => {
      document.getElementById('area-img').src = AREA_URL_PREFIX + btn.dataset.qno;
      document.getElementById('area-modal').style.display = 'flex';
    });
  });
  document.getElementById('close-modal').addEventListener('click', () => {
    document.getElementById('area-modal').style.display = 'none';
  });
  document.getElementById('area-modal').addEventListener('click', e => {
    if (e.target.id === 'area-modal') document.getElementById('area-modal').style.display = 'none';
  });

  // ---------- 初始化 ----------
  loadImage(FRONT_URL);
})();
