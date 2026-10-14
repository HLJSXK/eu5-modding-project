'use strict';
(() => {
  const ids = ['locations', 'markets', 'countries', 'dirty'];
  const inputs = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));
  const number = value => Math.round(value).toLocaleString('zh-CN');
  function update() {
    const n = Number(inputs.locations.value);
    inputs.markets.max = n;
    const m = Math.min(n, Number(inputs.markets.value));
    inputs.markets.value = m;
    const c = Number(inputs.countries.value);
    const d = Number(inputs.dirty.value) / 100;
    for (const id of ids) {
      document.getElementById(id + '-value').textContent = number(Number(inputs[id].value)) + (id === 'dirty' ? '%' : '');
    }
    const refresh = c / 12 + d * 11 * c / 12;
    document.getElementById('baskets').textContent = number(n * 7) + ' → ' + number(m * 7) + ' 份';
    document.getElementById('goods').textContent = number(n * 215) + ' → ' + number(m * 215) + ' 条';
    document.getElementById('refreshes').textContent = '≈ ' + number(refresh) + ' 国 · clean 的 ' + (1 + 11 * d).toFixed(1) + ' 倍';
    document.getElementById('vertices').textContent = n >= 5 ? '≤ ' + number(refresh * 209) + ' 组' : '0 · N < 5 跳过国家 solver';
    document.documentElement.dataset.atlasReady = 'true';
  }
  for (const input of Object.values(inputs)) input.addEventListener('input', update);
  for (const button of document.querySelectorAll('[data-dirty]')) {
    button.addEventListener('click', () => { inputs.dirty.value = button.dataset.dirty; update(); });
  }
  update();
})();
