/* Minimal SVG chart renderer.
   No external dependency: the app ships offline, so charts are drawn by hand
   into an <svg> element. One entry point, PlantIQ.chart(el, points, opts). */
(function (global) {
  'use strict';

  var NS = 'http://www.w3.org/2000/svg';

  function el(name, attrs) {
    var node = document.createElementNS(NS, name);
    for (var key in attrs) {
      if (Object.prototype.hasOwnProperty.call(attrs, key)) {
        node.setAttribute(key, attrs[key]);
      }
    }
    return node;
  }

  function niceStep(range, target) {
    if (range <= 0) return 1;
    var raw = range / target;
    var mag = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10));
    var norm = raw / mag;
    var step = norm > 5 ? 10 : norm > 2 ? 5 : norm > 1 ? 2 : 1;
    return step * mag;
  }

  function format(value) {
    if (value === null || value === undefined || isNaN(value)) return '--';
    var abs = Math.abs(value);
    if (abs >= 1000) return Math.round(value).toLocaleString();
    if (abs >= 100) return String(Math.round(value * 10) / 10);
    return String(Math.round(value * 100) / 100);
  }

  /* Axis labels take their precision from the tick step, not the magnitude,
     so a flat series near 400 does not print "400, 400, 400". */
  function formatTick(value, step) {
    if (value === null || value === undefined || isNaN(value)) return '--';
    var decimals = Math.max(0, Math.min(3, -Math.floor(Math.log(step) / Math.LN10)));
    var text = value.toFixed(decimals);
    if (decimals > 0 && text.indexOf('.') !== -1) {
      text = text.replace(/0+$/, '').replace(/\.$/, '');
    }
    return Math.abs(value) >= 10000 ? Number(text).toLocaleString() : text;
  }

  /* Draw a line/area chart of [{label, value}] into the container element. */
  function chart(container, points, opts) {
    opts = opts || {};
    container.innerHTML = '';
    container.classList.add('chart-shell');

    var height = opts.height || 220;
    var color = opts.color || 'var(--accent)';
    var unit = opts.unit || '';

    if (!points || points.length === 0) {
      var empty = document.createElement('div');
      empty.className = 'empty';
      empty.style.padding = '30px 12px';
      empty.innerHTML = '<p class="faint">No readings for this period.</p>';
      container.appendChild(empty);
      return;
    }

    var padL = 46, padR = 12, padT = 12, padB = 26;
    var width = Math.max(container.clientWidth || 480, 260);
    var innerW = width - padL - padR;
    var innerH = height - padT - padB;

    var values = points.map(function (p) { return p.value; });
    var lo = Math.min.apply(null, values);
    var hi = Math.max.apply(null, values);
    if (lo === hi) { lo = lo - 1; hi = hi + 1; }
    var step = niceStep(hi - lo, 4);
    var yMin = Math.floor(lo / step) * step;
    var yMax = Math.ceil(hi / step) * step;
    if (yMax === yMin) yMax = yMin + step;

    var svg = el('svg', {
      class: 'chart',
      viewBox: '0 0 ' + width + ' ' + height,
      preserveAspectRatio: 'none',
      height: height,
      role: 'img',
      'aria-label': (opts.label || 'Sensor') + ' chart'
    });
    svg.style.width = '100%';

    var x = function (i) {
      return points.length === 1
        ? padL + innerW / 2
        : padL + (i / (points.length - 1)) * innerW;
    };
    var y = function (v) {
      return padT + innerH - ((v - yMin) / (yMax - yMin)) * innerH;
    };

    /* horizontal grid + y labels */
    for (var g = yMin; g <= yMax + 1e-9; g += step) {
      var gy = y(g);
      svg.appendChild(el('line', {
        class: 'grid-line', x1: padL, x2: width - padR, y1: gy, y2: gy
      }));
      var lbl = el('text', {
        class: 'axis-text', x: padL - 7, y: gy + 3.5, 'text-anchor': 'end'
      });
      lbl.textContent = formatTick(g, step);
      svg.appendChild(lbl);
    }

    /* x labels: first, middle, last only, so they never collide */
    var marks = points.length <= 2 ? [0, points.length - 1]
      : [0, Math.floor((points.length - 1) / 2), points.length - 1];
    marks.forEach(function (i, n) {
      var t = el('text', {
        class: 'axis-text',
        x: x(i),
        y: height - 8,
        'text-anchor': n === 0 ? 'start' : n === marks.length - 1 ? 'end' : 'middle'
      });
      t.textContent = points[i].label || '';
      svg.appendChild(t);
    });

    /* area + line */
    var line = points.map(function (p, i) {
      return (i ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(p.value).toFixed(1);
    }).join(' ');

    var gradId = 'g' + Math.random().toString(36).slice(2, 9);
    var defs = el('defs');
    var grad = el('linearGradient', { id: gradId, x1: '0', y1: '0', x2: '0', y2: '1' });
    grad.appendChild(el('stop', { offset: '0%', 'stop-color': color, 'stop-opacity': '0.26' }));
    grad.appendChild(el('stop', { offset: '100%', 'stop-color': color, 'stop-opacity': '0' }));
    defs.appendChild(grad);
    svg.appendChild(defs);

    svg.appendChild(el('path', {
      d: line + ' L' + x(points.length - 1).toFixed(1) + ' ' + (padT + innerH) +
         ' L' + x(0).toFixed(1) + ' ' + (padT + innerH) + ' Z',
      fill: 'url(#' + gradId + ')', stroke: 'none'
    }));
    svg.appendChild(el('path', {
      d: line, fill: 'none', stroke: color, 'stroke-width': '2',
      'stroke-linejoin': 'round', 'stroke-linecap': 'round',
      'vector-effect': 'non-scaling-stroke'
    }));

    /* last point marker */
    var last = points.length - 1;
    svg.appendChild(el('circle', {
      cx: x(last), cy: y(points[last].value), r: '3.5',
      fill: color, stroke: 'var(--surface)', 'stroke-width': '2'
    }));

    container.appendChild(svg);

    /* hover readout */
    var tip = document.createElement('div');
    tip.className = 'chart-tip';
    container.appendChild(tip);

    var cursor = el('line', {
      x1: 0, x2: 0, y1: padT, y2: padT + innerH,
      stroke: 'var(--border-strong)', 'stroke-width': '1',
      'stroke-dasharray': '3 3', opacity: '0'
    });
    svg.appendChild(cursor);

    var hit = el('rect', {
      class: 'hit', x: padL, y: padT, width: innerW, height: innerH
    });
    svg.appendChild(hit);

    function locate(evt) {
      var box = svg.getBoundingClientRect();
      var scale = width / box.width;
      var px = (evt.clientX - box.left) * scale;
      var ratio = (px - padL) / innerW;
      var i = Math.round(ratio * (points.length - 1));
      return Math.max(0, Math.min(points.length - 1, i));
    }

    function show(evt) {
      var i = locate(evt);
      var p = points[i];
      cursor.setAttribute('opacity', '1');
      cursor.setAttribute('x1', x(i));
      cursor.setAttribute('x2', x(i));
      tip.textContent = p.label + '  ' + format(p.value) + (unit ? ' ' + unit : '');
      tip.style.left = (x(i) / width * 100) + '%';
      tip.style.top = (y(p.value) / height * 100) + '%';
      tip.classList.add('on');
    }

    function hide() {
      cursor.setAttribute('opacity', '0');
      tip.classList.remove('on');
    }

    hit.addEventListener('mousemove', show);
    hit.addEventListener('mouseleave', hide);
    hit.addEventListener('touchstart', function (e) { show(e.touches[0]); }, { passive: true });
    hit.addEventListener('touchmove', function (e) { show(e.touches[0]); }, { passive: true });
    hit.addEventListener('touchend', hide);
  }

  global.PlantIQ = global.PlantIQ || {};
  global.PlantIQ.chart = chart;
  global.PlantIQ.formatValue = format;
})(window);
