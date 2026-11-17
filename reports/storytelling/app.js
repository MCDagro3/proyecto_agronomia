const slides = [...document.querySelectorAll('.slide')];
const dots = [...document.querySelectorAll('.rail a')];
const counter = document.querySelector('#counter');
const progress = document.querySelector('#progress-bar');
const fullscreen = document.querySelector('#fullscreen');
const cropSelector = document.querySelector('#crop-selector');
const stabilityMap = document.querySelector('#stability-map');

let current = 0;

function activate(index) {
  current = Math.max(0, Math.min(slides.length - 1, index));
  dots.forEach((dot, i) => dot.classList.toggle('active', i === current));
  counter.textContent = `${String(current + 1).padStart(2, '0')} / ${String(slides.length).padStart(2, '0')}`;
  progress.style.width = `${((current + 1) / slides.length) * 100}%`;
  const isDark = slides[current].classList.contains('hero') || slides[current].classList.contains('dark-slide') || slides[current].classList.contains('cycles-slide') || slides[current].classList.contains('harvest') || slides[current].classList.contains('final');
  document.querySelector('.chrome').style.color = isDark ? '#f5f0e3' : '#17372c';
  document.querySelector('.rail').style.color = isDark ? '#f5f0e3' : '#17372c';
}

const observer = new IntersectionObserver((entries) => {
  const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
  if (visible) activate(slides.indexOf(visible.target));
}, { threshold: [0.45, 0.7] });

slides.forEach(slide => observer.observe(slide));

function goTo(index) {
  slides[Math.max(0, Math.min(slides.length - 1, index))].scrollIntoView({ behavior: 'smooth' });
}

document.addEventListener('keydown', (event) => {
  if (['ArrowRight', 'ArrowDown', 'PageDown', ' '].includes(event.key)) {
    event.preventDefault(); goTo(current + 1);
  }
  if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(event.key)) {
    event.preventDefault(); goTo(current - 1);
  }
  if (event.key === 'Home') goTo(0);
  if (event.key === 'End') goTo(slides.length - 1);
});

fullscreen.addEventListener('click', async () => {
  if (!document.fullscreenElement) {
    await document.documentElement.requestFullscreen();
    fullscreen.textContent = 'Salir de pantalla completa';
  } else {
    await document.exitFullscreen();
    fullscreen.textContent = 'Pantalla completa';
  }
});

document.addEventListener('fullscreenchange', () => {
  if (!document.fullscreenElement) fullscreen.textContent = 'Pantalla completa';
});

activate(0);

function median(values) {
  const ordered = [...values].sort((a, b) => a - b);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2;
}

function quantile(values, probability) {
  const ordered = [...values].sort((a, b) => a - b);
  return ordered[Math.min(ordered.length - 1, Math.floor((ordered.length - 1) * probability))];
}

function projectMunicipality(longitude, latitude) {
  return [
    35 + ((longitude + 118.5) / 32.5) * 920,
    565 - ((latitude - 14.0) / 19.5) * 520,
  ];
}

function stabilityColor(value, limit) {
  const ratio = Math.max(0, Math.min(1, value / Math.max(limit, 0.001)));
  return `hsl(${120 * (1 - ratio)} 62% 43%)`;
}

function drawMexicoBase(fragment) {
  const boundaries = window.ESTABILIDAD_CULTIVOS.limites_estatales || [];
  boundaries.forEach(ring => {
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const commands = ring.map(([longitude, latitude], index) => {
      const [x, y] = projectMunicipality(longitude, latitude);
      return `${index ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`;
    });
    path.setAttribute('d', `${commands.join(' ')} Z`);
    path.setAttribute('class', 'mexico-state');
    fragment.appendChild(path);
  });
}

function drawStabilityMap(crop) {
  const records = window.ESTABILIDAD_CULTIVOS.cultivos[crop] || [];
  stabilityMap.replaceChildren();
  if (!records.length) return;
  const cvs = records.map(record => record[2]);
  const limit = quantile(cvs, 0.95);
  const fragment = document.createDocumentFragment();
  drawMexicoBase(fragment);
  records.forEach(record => {
    const [longitude, latitude, cv, years, historicalYield, municipality, state] = record;
    const [x, y] = projectMunicipality(longitude, latitude);
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', x.toFixed(2));
    circle.setAttribute('cy', y.toFixed(2));
    circle.setAttribute('r', records.length > 1200 ? '2.7' : records.length > 500 ? '3.5' : '4.5');
    circle.setAttribute('fill', stabilityColor(cv, limit));
    circle.setAttribute('opacity', '.86');
    const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    title.textContent = `${municipality}, ${state} · CV ${cv.toFixed(2)} · ${years} años · ${historicalYield.toFixed(2)} t/ha`;
    circle.appendChild(title);
    fragment.appendChild(circle);
  });
  stabilityMap.appendChild(fragment);
  document.querySelector('#presence-count').textContent = records.length.toLocaleString('es-MX');
  document.querySelector('#median-cv').textContent = median(cvs).toFixed(2);
  document.querySelector('#median-yield').textContent = median(records.map(record => record[4])).toFixed(2);
  document.querySelector('#stability-reading').textContent = `${crop}: municipios con al menos ${window.ESTABILIDAD_CULTIVOS.minimo_anios} años de historia productiva. Coloca el cursor sobre un punto para consultar el municipio.`;
}

if (cropSelector && stabilityMap && window.ESTABILIDAD_CULTIVOS) {
  const crops = Object.entries(window.ESTABILIDAD_CULTIVOS.cultivos);
  crops.forEach(([crop, records]) => {
    const option = document.createElement('option');
    option.value = crop;
    option.textContent = `${crop} · ${records.length.toLocaleString('es-MX')} municipios`;
    cropSelector.appendChild(option);
  });
  cropSelector.addEventListener('change', () => drawStabilityMap(cropSelector.value));
  if (crops.length) drawStabilityMap(crops[0][0]);
}
