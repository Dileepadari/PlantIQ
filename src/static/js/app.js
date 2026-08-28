/* Shell behaviour: theme, mobile nav, chart mounting, live refresh. */
(function () {
  'use strict';

  var PlantIQ = window.PlantIQ = window.PlantIQ || {};

  /* ---------- theme ---------- */
  var STORE = 'plantiq-theme';

  function readTheme() {
    try { return localStorage.getItem(STORE); } catch (e) { return null; }
  }
  function writeTheme(value) {
    try { localStorage.setItem(STORE, value); } catch (e) { /* private mode */ }
  }
  function systemTheme() {
    return window.matchMedia &&
      window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  function activeTheme() {
    return document.documentElement.getAttribute('data-theme') || systemTheme();
  }
  function applyTheme(value) {
    document.documentElement.setAttribute('data-theme', value);
    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
      btn.setAttribute('aria-label', value === 'dark'
        ? 'Switch to light theme' : 'Switch to dark theme');
      btn.querySelectorAll('[data-icon-sun],[data-icon-moon]').forEach(function (icon) {
        var isSun = icon.hasAttribute('data-icon-sun');
        icon.style.display = (value === 'dark') === isSun ? '' : 'none';
      });
    });
    redrawCharts();
  }

  var stored = readTheme();
  if (stored === 'dark' || stored === 'light') {
    document.documentElement.setAttribute('data-theme', stored);
  }

  /* ---------- charts ---------- */
  var mounted = [];

  function mountCharts(root) {
    (root || document).querySelectorAll('[data-chart]').forEach(function (node) {
      var points;
      try { points = JSON.parse(node.getAttribute('data-chart') || '[]'); }
      catch (e) { points = []; }
      var entry = {
        node: node,
        points: points,
        opts: {
          color: node.getAttribute('data-color') || 'var(--accent)',
          height: parseInt(node.getAttribute('data-height'), 10) || 220,
          unit: node.getAttribute('data-unit') || '',
          label: node.getAttribute('data-label') || ''
        }
      };
      mounted.push(entry);
      PlantIQ.chart(node, points, entry.opts);
    });
  }

  function redrawCharts() {
    mounted.forEach(function (entry) {
      PlantIQ.chart(entry.node, entry.points, entry.opts);
    });
  }

  PlantIQ.setChartData = function (node, points) {
    for (var i = 0; i < mounted.length; i++) {
      if (mounted[i].node === node) {
        mounted[i].points = points;
        PlantIQ.chart(node, points, mounted[i].opts);
        return;
      }
    }
  };

  var resizeTimer;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(redrawCharts, 160);
  });

  /* ---------- live refresh of the metric tiles ---------- */
  function refreshMetrics() {
    var host = document.querySelector('[data-live-metrics]');
    if (!host) return;
    var count = host.getAttribute('data-live-metrics') || '20';

    fetch('/api/readings?count=' + encodeURIComponent(count), {
      headers: { 'Accept': 'application/json' }
    })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        var latest = data.latest || {};
        document.querySelectorAll('[data-metric-key]').forEach(function (tile) {
          var key = tile.getAttribute('data-metric-key');
          var value = latest[key];
          var out = tile.querySelector('[data-metric-value]');
          var fill = tile.querySelector('[data-metric-fill]');
          if (out) {
            out.textContent = value === null || value === undefined
              ? '--' : PlantIQ.formatValue(value);
          }
          if (fill) {
            var max = parseFloat(tile.getAttribute('data-metric-max')) || 100;
            var pct = value === null || value === undefined
              ? 0 : Math.max(0, Math.min(100, (value / max) * 100));
            fill.style.width = pct + '%';
          }
        });
        var stamp = document.querySelector('[data-updated]');
        if (stamp) {
          stamp.textContent = data.online
            ? 'Updated ' + new Date().toLocaleTimeString()
            : 'Sensor feed unreachable';
        }
        var chartNode = document.querySelector('[data-chart][data-series]');
        if (chartNode && data.series) {
          var key = chartNode.getAttribute('data-series');
          if (data.series[key]) PlantIQ.setChartData(chartNode, data.series[key]);
        }
      })
      .catch(function () { /* offline: leave the last rendered values in place */ });
  }

  /* ---------- boot ---------- */
  document.addEventListener('DOMContentLoaded', function () {
    applyTheme(activeTheme());
    mountCharts();

    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var next = activeTheme() === 'dark' ? 'light' : 'dark';
        writeTheme(next);
        applyTheme(next);
      });
    });

    var sidebar = document.querySelector('.sidebar');
    var scrim = document.querySelector('.scrim');
    function closeNav() {
      if (sidebar) sidebar.classList.remove('open');
      if (scrim) scrim.classList.remove('on');
    }
    document.querySelectorAll('[data-nav-toggle]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (!sidebar) return;
        var open = sidebar.classList.toggle('open');
        if (scrim) scrim.classList.toggle('on', open);
      });
    });
    if (scrim) scrim.addEventListener('click', closeNav);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeNav();
    });

    if (document.querySelector('[data-live-metrics]')) {
      setInterval(refreshMetrics, 30000);
    }
  });

  PlantIQ.mountCharts = mountCharts;
  PlantIQ.refreshMetrics = refreshMetrics;
})();
