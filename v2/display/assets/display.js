// TFS v2 display behavior — 侧边栏交互 + 轨迹弹窗 + details 折叠 + 表格搜索

// ── 侧边栏：点击日期切 iframe ─────────────────────────────
function loadDate(date, target) {
  var frame = document.getElementById('daily-frame');
  if (!frame) {
    var wrap = document.querySelector('.display-frame-wrap') || document.body;
    frame = document.createElement('iframe');
    frame.id = 'daily-frame';
    frame.src = target || ('trend_dashboard_' + date + '.html');
    frame.style.width = '100%';
    frame.style.height = '100vh';
    frame.style.border = '0';
    wrap.innerHTML = '';
    wrap.appendChild(frame);
  } else {
    frame.src = target || ('trend_dashboard_' + date + '.html');
  }
  // 高亮当前日期项
  var items = document.querySelectorAll('.date-nav-card');
  items.forEach(function(item) {
    item.classList.remove('active');
    if (item.getAttribute('data-date') === date) {
      item.classList.add('active');
    }
  });
}

// ── 键盘快捷键 ↑↓ 切换日期、[ 折叠侧边栏 ─────────────────
document.addEventListener('keydown', function(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  var items = Array.prototype.slice.call(document.querySelectorAll('.date-nav-card'));
  if (!items.length) return;
  var current = document.querySelector('.date-nav-card.active') || items[0];
  var idx = items.indexOf(current);
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    var next = e.key === 'ArrowDown' ? Math.min(idx + 1, items.length - 1) : Math.max(idx - 1, 0);
    var item = items[next];
    var date = item.getAttribute('data-date');
    var target = item.getAttribute('data-target');
    loadDate(date, target);
  }
  if (e.key === '[') {
    var sidebar = document.querySelector('.display-sidebar');
    if (sidebar) sidebar.classList.toggle('collapsed');
  }
});

// ── 折叠按钮 ◀ ────────────────────────────────────────────
function toggleSidebar() {
  var sidebar = document.querySelector('.display-sidebar');
  if (sidebar) sidebar.classList.toggle('collapsed');
}

// ── 轨迹弹窗 ──────────────────────────────────────────────
function showTrajectory(code, states) {
  var overlay = document.getElementById('trajectory-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'trajectory-overlay';
    overlay.className = 'trajectory-overlay';
    overlay.onclick = hideTrajectory;
    document.body.appendChild(overlay);
  }
  var html = '<div class="trajectory-popup" onclick="event.stopPropagation()">';
  html += '<div class="trajectory-header"><span>轨迹 · ' + code + '</span><button onclick="hideTrajectory()">✕</button></div>';
  if (states && states.length) {
    html += '<div class="trajectory-body">';
    states.forEach(function(s, i) {
      var cls = {4:'up',5:'up',3:'mid',2:'down',1:'down'}[s] || 'mid';
      html += '<span class="traj-dot ' + cls + '" title="Day-' + (states.length - i) + '">' + s + '</span>';
    });
    html += '</div>';
  } else {
    html += '<div class="trajectory-body empty">暂无轨迹数据</div>';
  }
  html += '</div>';
  overlay.innerHTML = html;
  overlay.style.display = 'flex';
}

function hideTrajectory() {
  var overlay = document.getElementById('trajectory-overlay');
  if (overlay) overlay.style.display = 'none';
}

// ── details 全展开/全收起 ─────────────────────────────────
function toggleAllDetails(regionId, expand) {
  var region = document.querySelector('[data-region="' + regionId + '"]');
  if (!region) return;
  var details = region.querySelectorAll('details.widget-details');
  details.forEach(function(d) { d.open = expand; });
}

// ── 表格搜索过滤 ──────────────────────────────────────────
function filterTable(tableId, query) {
  var table = document.getElementById(tableId);
  if (!table) return;
  var rows = table.querySelectorAll('tbody tr');
  var q = query.toLowerCase().trim();
  rows.forEach(function(row) {
    var text = row.textContent.toLowerCase();
    row.style.display = (q === '' || text.indexOf(q) >= 0) ? '' : 'none';
  });
}

// ── 初始化：高亮指定日期（由 render_index 设置 data-default-date） ─
document.addEventListener('DOMContentLoaded', function() {
  var shell = document.querySelector('.display-shell');
  var defaultDate = shell ? shell.getAttribute('data-default-date') : null;
  if (!defaultDate) {
    var firstItem = document.querySelector('.date-nav-card');
    if (firstItem) defaultDate = firstItem.getAttribute('data-date');
  }
  if (defaultDate) {
    // 找到对应日期项并高亮
    var target = null;
    document.querySelectorAll('.date-nav-card').forEach(function(item) {
      item.classList.remove('active');
      if (item.getAttribute('data-date') === defaultDate) {
        target = item.getAttribute('data-target');
        item.classList.add('active');
      }
    });
    // 滚动 default date 到可见
    var active = document.querySelector('.date-nav-card.active');
    if (active && active.scrollIntoView) active.scrollIntoView({block: 'nearest'});
  }
});
