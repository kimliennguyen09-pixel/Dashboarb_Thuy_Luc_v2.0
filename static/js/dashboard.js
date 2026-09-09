let allNodes = [], page = 1, sortKey = 'Flow (Total Out) (L/s)', sortDir = -1;
let activeChartParams = '';
const pageSize = 15;
const riskVI = {Critical: 'Nguy cấp', Warning: 'Cảnh báo', Normal: 'Bình thường'};
const fmt = (n, d = 2) => Number(n).toLocaleString('vi-VN', {maximumFractionDigits: d});

function chartParams() {
  const params = new URLSearchParams();
  const values = {q: document.querySelector('#chart-search').value.trim(), risk: document.querySelector('#chart-risk').value, min_flood_depth: document.querySelector('#chart-min-depth').value, max_flood_depth: document.querySelector('#chart-max-depth').value, limit: document.querySelector('#chart-limit').value};
  Object.entries(values).forEach(([key, value]) => { if (value !== '' && !(key === 'risk' && value === 'all')) params.set(key, value); });
  return '?' + params.toString();
}

async function loadAll() {
  try {
    const [summary, nodes] = await Promise.all([API.summary(), API.nodes()]);
    allNodes = nodes.items;
    renderSummary(summary);
    renderTable();
    await loadCharts(activeChartParams);
    document.querySelector('#updated').textContent = 'Cập nhật ' + new Date().toLocaleTimeString('vi-VN');
    document.querySelector('#dataset-status').textContent = `API: Active · Dataset: ${summary.total_nodes} nodes`;
  } catch (error) { showSystemError(error.message); }
}

async function loadCharts(params = '') {
  const message = document.querySelector('#chart-filter-message');
  try {
    const charts = await API.charts(params);
    activeChartParams = params;
    bars(document.querySelector('#flow-chart'), charts.top_flow, 'Flow (Total Out) (L/s)');
    bars(document.querySelector('#hgl-chart'), charts.lowest_hgl_margin, 'HGL Margin (m)', true);
    bars(document.querySelector('#flood-chart'), charts.flood_depth, 'Depth (Flooding) (m)', true);
    message.className = 'form-message ' + (charts.empty ? 'error' : 'success');
    message.textContent = charts.empty ? charts.message : `Đang hiển thị dữ liệu từ ${charts.count} nút phù hợp.`;
  } catch (error) { message.className = 'form-message error'; message.textContent = error.message; }
}

function showSystemError(text) {
  const alert = document.querySelector('#system-alert');
  alert.innerHTML = `<span>!</span><div><strong>Không kết nối được API</strong><small>${text}</small></div>`;
  alert.classList.add('warn');
}

function renderSummary(s) {
  const cards = [['Tổng số nút', s.total_nodes, 'nút', 'var(--cyan)'], ['Nút bị ngập', s.flooded_nodes, 'nút', 'var(--red)'], ['Ngập sâu lớn nhất', fmt(s.max_flood_depth), 'm', 'var(--orange)'], ['Lưu lượng lớn nhất', fmt(s.max_flow), 'L/s', 'var(--blue)'], ['Biên HGL thấp nhất', fmt(s.min_hgl_margin), 'm', 'var(--violet)']];
  document.querySelector('#kpis').innerHTML = cards.map(x => `<article class="panel kpi" style="color:${x[3]}"><div class="kpi-label">${x[0]}</div><div class="kpi-value">${x[1]}</div><div class="kpi-unit">${x[2]}</div></article>`).join('');
  donut(document.querySelector('#risk-donut'), s.total_nodes, s.risks);
  document.querySelector('#risk-legend').innerHTML = [['Critical', 'var(--red)'], ['Warning', 'var(--orange)'], ['Normal', 'var(--green)']].map(([k, c]) => `<div class="legend-row"><i style="background:${c}"></i><span>${riskVI[k]}</span><b>${s.risks[k]} nút</b></div>`).join('');
  const affected = s.risks.Critical + s.risks.Warning;
  const alert = document.querySelector('#system-alert');
  alert.classList.toggle('warn', Boolean(affected));
  alert.innerHTML = `<span>●</span><div><strong>${affected ? `Phát hiện ${affected} nút cần theo dõi` : 'Hệ thống vận hành ổn định'}</strong><small>Phân loại dựa trên chiều sâu ngập, trạng thái tràn, tỷ lệ đầy và biên an toàn HGL.</small></div>`;
  document.querySelector('#insight').innerHTML = `<div class="insight-box">${affected} / ${s.total_nodes} nút thuộc nhóm cần theo dõi. Nút có biên HGL thấp cần được ưu tiên rà soát cao độ, điều kiện biên và khả năng tải của tuyến hạ lưu.</div><div class="metric-list"><div>Tỷ lệ cần theo dõi <b>${fmt(s.total_nodes ? affected / s.total_nodes * 100 : 0, 1)}%</b></div><div>Nút đang tràn <b>${s.overflowing}</b></div><div>Q ra cực đại <b>${fmt(s.max_flow)} L/s</b></div></div>`;
  const severe = s.flood_levels.High + s.flood_levels['Very High'];
  document.querySelector('#flood-warning').innerHTML = `<div class="warning-level critical"><strong>${severe} nút ngập sâu</strong><span>&gt; 0,30 m — ưu tiên xử lý ngay</span></div><div class="warning-level warning"><strong>${s.flood_levels.Moderate} nút ngập trung bình</strong><span>0,10–0,30 m — theo dõi và kiểm tra</span></div><div class="warning-level normal"><strong>${s.total_nodes - s.flooded_nodes} nút không ngập</strong><span>Chưa ghi nhận chiều sâu ngập</span></div><p class="assessment-note">Chiều sâu ngập trung bình tại các nút bị ngập là <b>${fmt(s.avg_flood_depth)} m</b>.</p>`;
}

function filtered() {
  const q = document.querySelector('#search').value.trim().toLowerCase(), risk = document.querySelector('#risk-filter').value;
  return allNodes.filter(n => (risk === 'all' || n.Risk === risk) && (!q || String(n.ID).toLowerCase().includes(q) || String(n.Label).toLowerCase().includes(q))).sort((a, b) => { const av = a[sortKey], bv = b[sortKey]; return (typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv))) * sortDir; });
}

function renderTable() {
  const rows = filtered(), pages = Math.max(1, Math.ceil(rows.length / pageSize)); page = Math.min(page, pages);
  const shown = rows.slice((page - 1) * pageSize, page * pageSize);
  document.querySelector('#node-rows').innerHTML = shown.length ? shown.map(n => `<tr><td><a href="/node?id=${encodeURIComponent(n.ID)}">${n.ID}</a></td><td>${fmt(n['Elevation (Rim) (m)'])}</td><td>${fmt(n['Elevation (Invert) (m)'])}</td><td>${fmt(n['Flow (Total Out) (L/s)'])}</td><td>${fmt(n['Depth (Out) (m)'])}</td><td class="flood-depth">${fmt(n['Depth (Flooding) (m)'])}</td><td>${fmt(n['Fill Ratio (%)'], 1)}</td><td>${fmt(n['HGL Margin (m)'])}</td><td><span class="status ${n.Risk}">${riskVI[n.Risk]}</span></td><td class="reason">${n['Warning Reasons'].join('; ') || 'Không có cảnh báo'}</td></tr>`).join('') : '<tr><td colspan="10"><div class="empty-state"><strong>Không có nút phù hợp</strong><span>Hãy thay đổi từ khóa hoặc trạng thái lọc.</span></div></td></tr>';
  document.querySelector('#row-count').textContent = `Hiển thị ${shown.length} / ${rows.length} nút`;
  document.querySelector('#pagination').innerHTML = rows.length ? Array.from({length: pages}, (_, i) => i + 1).filter(p => p === 1 || p === pages || Math.abs(p - page) <= 1).map(p => `<button class="${p === page ? 'active' : ''}" onclick="page=${p};renderTable()">${p}</button>`).join('') : '';
}

function setupNavigation() {
  const links = [...document.querySelectorAll('.sidebar nav a[data-section]')];
  const sections = links.map(link => document.getElementById(link.dataset.section)).filter(Boolean);
  const activate = id => links.forEach(link => link.classList.toggle('active', link.dataset.section === id));
  links.forEach(link => link.addEventListener('click', () => activate(link.dataset.section)));
  let scheduled = false;
  const updateFromScroll = () => {
    const marker = window.scrollY + window.innerHeight * 0.35;
    let current = sections[0];
    sections.forEach(section => { if (section.offsetTop <= marker) current = section; });
    activate(current.id);
    scheduled = false;
  };
  window.addEventListener('scroll', () => {
    if (!scheduled) { scheduled = true; window.requestAnimationFrame(updateFromScroll); }
  }, {passive: true});
  updateFromScroll();
}

document.querySelector('#search').addEventListener('input', () => { page = 1; renderTable(); });
document.querySelector('#risk-filter').addEventListener('change', () => { page = 1; renderTable(); });
document.querySelectorAll('th[data-sort]').forEach(th => th.addEventListener('click', () => { sortDir = sortKey === th.dataset.sort ? -sortDir : -1; sortKey = th.dataset.sort; renderTable(); }));
document.querySelector('#apply-chart-filter').addEventListener('click', () => loadCharts(chartParams()));
document.querySelector('#reset-chart-filter').addEventListener('click', () => { ['#chart-search', '#chart-min-depth', '#chart-max-depth'].forEach(id => document.querySelector(id).value = ''); document.querySelector('#chart-risk').value = 'all'; document.querySelector('#chart-limit').value = '12'; loadCharts(''); });
document.querySelectorAll('.export-chart').forEach(button => button.addEventListener('click', () => { window.location.href = API.exportUrl(button.dataset.chart, activeChartParams); }));
document.querySelector('#upload-form').addEventListener('submit', async event => {
  event.preventDefault();
  const file = document.querySelector('#csv-file').files[0], message = document.querySelector('#upload-message');
  if (!file) { message.className = 'form-message error'; message.textContent = 'Vui lòng chọn file CSV.'; return; }
  message.className = 'form-message'; message.textContent = 'Đang kiểm tra và tải dữ liệu…';
  try { const result = await API.upload(file); message.className = 'form-message success'; message.textContent = result.message; event.target.reset(); activeChartParams = ''; await loadAll(); }
  catch (error) { message.className = 'form-message error'; message.textContent = error.message; }
});

setupNavigation();
loadAll();
