(function () {
  const canvas = document.getElementById('tpl-canvas');
  const stage = document.getElementById('tpl-stage');
  const ctx = canvas.getContext('2d');
  const listEl = document.getElementById('region-list');
  const hintEl = document.getElementById('current-hint');

  const COLORS = {
    front: '#2563eb', back: '#7c3aed', barcode: '#dc2626',
    ocr: '#db2777', digits: '#ea580c', objective: '#16a34a', subjective: '#d97706',
  };

  let img = null;
  let scale = 1;   // 显示尺寸 / 原图尺寸
  let offsetX = 0, offsetY = 0;

  const data = {
    front_area: initialData.front_area || null,
    back_area: initialData.back_area || null,
    barcode_area: initialData.barcode_area || null,
    objective_area: initialData.objective_area || {},
    subjective_area: initialData.subjective_area || {},
  };

  let mode = 'front';
  let objectiveType = 'single';
  let currentQno = null;      // 正在框选的主观题题号
  let currentObjective = null; // 正在框选的客观题对象 {qno,type,options,optionIndex}
  let digitMode = false;
  let currentDigitIndex = -1;

  // ---------- 图片加载与绘制 ----------
  function fitStage() {
    const w = stage.clientWidth, h = stage.clientHeight;
    if (!img) return;
    scale = Math.min((w - 8) / img.width, (h - 8) / img.height, 1);
    canvas.width = img.width * scale;
    canvas.height = img.height * scale;
    offsetX = (w - canvas.width) / 2;
    offsetY = (h - canvas.height) / 2;
    render();
  }

  function toImgXY(ev) {
    const rect = canvas.getBoundingClientRect();
    const x = (ev.clientX - rect.left) / scale;
    const y = (ev.clientY - rect.top) / scale;
    return { x: Math.max(0, x), y: Math.max(0, y) };
  }

  function render() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (img) ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    // 已框选对象
    drawRegion(data.front_area, COLORS.front, '正面');
    drawRegion(data.back_area, COLORS.back, '反面');
    if (data.barcode_area) {
      const bc = data.barcode_area;
      if (bc.mode === 'digits') {
        (bc.digits || []).forEach((d, i) => drawRegion(d.area, COLORS.digits, '数位' + (i + 1)));
      } else if (bc.area) {
        drawRegion(bc.area, COLORS[bc.mode] || COLORS.barcode, bc.mode === 'ocr' ? 'OCR' : '条码');
      }
    }
    for (const qno in data.objective_area) {
      const q = data.objective_area[qno];
      for (const lab in q.options) {
        drawRegion(q.options[lab], COLORS.objective, 'Q' + qno + '-' + lab);
      }
    }
    for (const qno in data.subjective_area) {
      const s = data.subjective_area[qno];
      if (s && s.area) drawRegion(s.area, COLORS.subjective, '主观' + qno);
    }
  }

  function drawRegion(area, color, label) {
    if (!area) return;
    const x = area.x1 * scale, y = area.y1 * scale;
    const w = (area.x2 - area.x1) * scale, h = (area.y2 - area.y1) * scale;
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, w, h);
    ctx.fillStyle = color;
    ctx.globalAlpha = 0.15;
    ctx.fillRect(x, y, w, h);
    ctx.globalAlpha = 1;
    ctx.font = '12px sans-serif';
    const tw = ctx.measureText(label).width;
    ctx.fillStyle = color;
    ctx.fillRect(x, y - 18, tw + 8, 18);
    ctx.fillStyle = '#fff';
    ctx.fillText(label, x + 4, y - 5);
  }

  // ---------- 框选交互 ----------
  let dragging = false, start = null, current = null;

  canvas.addEventListener('mousedown', e => {
    dragging = true;
    start = toImgXY(e);
    current = { ...start };
  });
  canvas.addEventListener('mousemove', e => {
    if (!dragging) return;
    current = toImgXY(e);
    render();
    if (start && current) {
      const x = start.x * scale, y = start.y * scale;
      ctx.strokeStyle = '#facc15';
      ctx.lineWidth = 2;
      ctx.strokeRect(x, y, (current.x - start.x) * scale, (current.y - start.y) * scale);
    }
  });
  canvas.addEventListener('mouseup', () => {
    if (!dragging || !start || !current) { dragging = false; return; }
    dragging = false;
    const area = {
      x1: Math.round(Math.min(start.x, current.x)),
      y1: Math.round(Math.min(start.y, current.y)),
      x2: Math.round(Math.max(start.x, current.x)),
      y2: Math.round(Math.max(start.y, current.y)),
    };
    if (area.x2 - area.x1 < 4 || area.y2 - area.y1 < 4) { render(); return; }
    handleRegion(area);
    render();
  });

  function handleRegion(area) {
    if (digitMode) {
      if (!data.barcode_area || data.barcode_area.mode !== 'digits') {
        data.barcode_area = { mode: 'digits', digits: [] };
      }
      const list = data.barcode_area.digits;
      list[currentDigitIndex] = { area };
      currentDigitIndex++;
      if (currentDigitIndex < (data.barcode_area.digitCount || list.length)) {
        showHint('请框选第 ' + (currentDigitIndex + 1) + ' 个数字位区域');
      } else {
        digitMode = false;
        currentDigitIndex = -1;
        showHint('数字涂卡位已全部框选完成');
      }
      refreshList();
      return;
    }

    if (currentObjective) {
      const labels = currentObjective.type === 'judge' ? ['对', '错'] : ['A', 'B', 'C', 'D'];
      const label = labels[currentObjective.optionIndex];
      currentObjective.options[label] = area;
      currentObjective.optionIndex++;
      if (currentObjective.optionIndex >= labels.length) {
        data.objective_area[currentObjective.qno] = {
          type: currentObjective.type,
          options: currentObjective.options,
        };
        showHint('第 ' + currentObjective.qno + ' 题配置完成');
        currentObjective = null;
      } else {
        showHint('第 ' + currentObjective.qno + ' 题：请框选选项 ' + labels[currentObjective.optionIndex]);
      }
      refreshList();
      return;
    }

    switch (mode) {
      case 'front': data.front_area = area; showHint('正面区域已框选'); break;
      case 'back': data.back_area = area; showHint('反面区域已框选'); break;
      case 'barcode': data.barcode_area = { mode: 'barcode', area }; showHint('条码区域已框选'); break;
      case 'ocr': data.barcode_area = { mode: 'ocr', area }; showHint('OCR 区域已框选'); break;
      case 'subjective':
        if (currentQno) {
          if (!data.subjective_area[currentQno]) data.subjective_area[currentQno] = {};
          data.subjective_area[currentQno].area = area;
          showHint('主观题 ' + currentQno + ' 答题区域已框选');
          currentQno = null;
        }
        break;
    }
    refreshList();
  }

  // ---------- 工具按钮 ----------
  document.querySelectorAll('.tool-btn[data-mode]').forEach(btn => {
    btn.addEventListener('click', () => {
      mode = btn.dataset.mode;
      currentQno = null;
      currentObjective = null;
      setModeButton(btn);
      if (mode === 'digits') {
        document.getElementById('digit-config').style.display = 'block';
        digitMode = false;
        showHint('请设置位数并点击"开始框选"');
      } else if (mode === 'subjective') {
        currentQno = nextQno(data.subjective_area);
        data.subjective_area[currentQno] = { area: null };
        showHint('请框选主观题 ' + currentQno + ' 的答题区域');
        refreshList();
      } else {
        document.getElementById('digit-config').style.display = 'none';
        showHint(modeLabel(mode));
      }
    });
  });

  document.querySelectorAll('.tool-btn[data-obj]').forEach(btn => {
    btn.addEventListener('click', () => {
      objectiveType = btn.dataset.obj;
      const qno = nextQno(data.objective_area);
      currentObjective = { qno, type: objectiveType, options: {}, optionIndex: 0 };
      mode = 'objective';
      setModeButton(btn);
      const labels = objectiveType === 'judge' ? ['对', '错'] : ['A', 'B', 'C', 'D'];
      showHint('第 ' + qno + ' 题（' + (objectiveType === 'judge' ? '判断' : objectiveType === 'multi' ? '多选' : '单选') + '）：请框选选项 ' + labels[0]);
    });
  });

  document.getElementById('digit-start').addEventListener('click', () => {
    const n = parseInt(document.getElementById('digit-count').value, 10) || 5;
    data.barcode_area = { mode: 'digits', digits: [], digitCount: n };
    digitMode = true;
    currentDigitIndex = 0;
    showHint('数字涂卡模式：请框选第 1 个数字位区域');
    refreshList();
  });

  function setModeButton(activeBtn) {
    document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
    activeBtn.classList.add('active');
  }

  function nextQno(obj) {
    let max = 0;
    for (const k in obj) {
      const n = parseInt(k, 10);
      if (!isNaN(n) && n > max) max = n;
    }
    return max + 1;
  }

  function modeLabel(m) {
    return { front: '请在图上拖拽框选答题卡正面区域', back: '请在图上拖拽框选反面区域（可空）',
      barcode: '请在图上框选准考证条形码区域', ocr: '请在图上框选准考证号 OCR 区域' }[m] || '';
  }

  function showHint(text) {
    hintEl.style.display = 'block';
    hintEl.textContent = text;
  }

  // ---------- 已框选列表 ----------
  function refreshList() {
    listEl.innerHTML = '';
    const add = (text, color, removeFn) => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;justify-content:space-between;align-items:center;padding:6px 8px;margin:4px 0;border-radius:6px;background:#f8fafc;border-left:3px solid ' + color;
      const span = document.createElement('span');
      span.textContent = text;
      const del = document.createElement('button');
      del.textContent = '删除';
      del.className = 'btn btn-danger btn-sm';
      del.onclick = removeFn;
      row.appendChild(span); row.appendChild(del);
      listEl.appendChild(row);
    };
    if (data.front_area) add('正面区域', COLORS.front, () => { data.front_area = null; refreshList(); render(); });
    if (data.back_area) add('反面区域', COLORS.back, () => { data.back_area = null; refreshList(); render(); });
    if (data.barcode_area) {
      const bc = data.barcode_area;
      if (bc.mode === 'digits') add('数字涂卡（' + (bc.digits || []).length + ' 位）', COLORS.digits, () => { data.barcode_area = null; refreshList(); render(); });
      else add(bc.mode === 'ocr' ? '准考证 OCR' : '准考证条码', COLORS.barcode, () => { data.barcode_area = null; refreshList(); render(); });
    }
    for (const qno in data.objective_area) {
      const q = data.objective_area[qno];
      const cnt = Object.keys(q.options || {}).length;
      add('客观题 ' + qno + '（' + ({ single: '单选', multi: '多选', judge: '判断' }[q.type] || q.type) + ' ' + cnt + '/'
        + (q.type === 'judge' ? 2 : 4) + '）', COLORS.objective, () => { delete data.objective_area[qno]; refreshList(); render(); });
    }
    for (const qno in data.subjective_area) {
      const s = data.subjective_area[qno];
      add('主观题 ' + qno + (s && s.area ? '' : '（未框选）'), COLORS.subjective, () => { delete data.subjective_area[qno]; refreshList(); render(); });
    }
  }

  // ---------- 保存 ----------
  document.getElementById('save-tpl').addEventListener('click', async () => {
    const payload = {
      front_area: data.front_area,
      back_area: data.back_area,
      barcode_area: data.barcode_area,
      objective_area: data.objective_area,
      subjective_area: data.subjective_area,
    };
    try {
      const resp = await fetch('/admin/exam/' + EXAM_ID + '/save_template', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const r = await resp.json();
      if (r.ok) {
        showHint('模板配置已保存成功');
        alert('模板配置已保存成功');
      } else {
        showHint('保存失败');
      }
    } catch (e) {
      showHint('保存失败：' + e.message);
    }
  });

  // ---------- 初始化 ----------
  const imgEl = new Image();
  imgEl.onload = () => {
    img = imgEl;
    fitStage();
    refreshList();
    showHint('请选择左侧工具开始框选答题卡区域');
  };
  imgEl.src = TEMPLATE_IMAGE;
  window.addEventListener('resize', fitStage);
})();
