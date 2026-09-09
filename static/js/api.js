const API = {
  async request(path, options = {}) {
    const response = await fetch(path, options);
    const type = response.headers.get('content-type') || '';
    const payload = type.includes('application/json') ? await response.json() : null;
    if (!response.ok) throw new Error(payload?.message || `API trả lỗi ${response.status}`);
    return payload;
  },
  get(path) { return this.request(path); },
  summary(params = '') { return this.get('/api/summary' + params); },
  nodes(params = '') { return this.get('/api/nodes' + params); },
  charts(params = '') { return this.get('/api/charts' + params); },
  node(id) { return this.get('/api/nodes/' + encodeURIComponent(id)); },
  upload(file) {
    const body = new FormData();
    body.append('file', file);
    return this.request('/api/data/upload', {method: 'POST', body});
  },
  exportUrl(chart, params = '') {
    const query = new URLSearchParams(params.startsWith('?') ? params.slice(1) : params);
    query.set('chart', chart);
    return '/api/charts/export.csv?' + query.toString();
  }
};
