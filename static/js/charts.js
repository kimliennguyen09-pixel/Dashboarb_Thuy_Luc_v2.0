function emptyChart(el, message = 'Không có dữ liệu phù hợp với bộ lọc.') {
  el.innerHTML = `<div class="empty-state"><strong>Không có dữ liệu</strong><span>${message}</span></div>`;
}

function bars(el, items, valueKey, danger = false) {
  if (!items?.length) return emptyChart(el);
  const max = Math.max(...items.map(x => Math.abs(x[valueKey])), 1);
  el.innerHTML = items.map(x => `<div class="bar-row"><span class="bar-label">${x.Label}</span><div class="bar-track"><div class="bar-fill ${danger ? 'danger' : ''}" style="width:${Math.max(2, Math.abs(x[valueKey]) / max * 100)}%"></div></div><span class="bar-value">${Number(x[valueKey]).toLocaleString('vi-VN', {maximumFractionDigits: 2})}</span></div>`).join('');
}

function donut(el, total, risks) {
  if (!total) return emptyChart(el);
  const critical = risks.Critical / total * 100;
  const warning = risks.Warning / total * 100;
  el.innerHTML = `<div class="donut" style="background:conic-gradient(var(--red) 0 ${critical}%,var(--orange) ${critical}% ${critical + warning}%,var(--green) ${critical + warning}% 100%)"><div class="donut-center"><strong>${total}</strong><small>TỔNG SỐ NÚT</small></div></div>`;
}
