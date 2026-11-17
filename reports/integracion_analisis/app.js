const slides = [...document.querySelectorAll('.slide')];
const dots = [...document.querySelectorAll('.rail a')];
const counter = document.querySelector('#counter');
const progress = document.querySelector('#progress-bar');
const fullscreen = document.querySelector('#fullscreen');
let current = 0;

function activate(index) {
  current = Math.max(0, Math.min(slides.length - 1, index));
  dots.forEach((dot, i) => dot.classList.toggle('active', i === current));
  counter.textContent = `${String(current + 1).padStart(2, '0')} / ${String(slides.length).padStart(2, '0')}`;
  progress.style.width = `${((current + 1) / slides.length) * 100}%`;
  const dark = ['hero', 'climate-slide', 'join-slide', 'territory-slide', 'stability-slide', 'final'].some(name => slides[current].classList.contains(name));
  document.querySelector('.chrome').style.color = dark ? '#f4efe2' : '#183832';
  document.querySelector('.rail').style.color = dark ? '#f4efe2' : '#183832';
}

const observer = new IntersectionObserver(entries => {
  const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
  if (visible) activate(slides.indexOf(visible.target));
}, { threshold: [0.45, 0.7] });
slides.forEach(slide => observer.observe(slide));

function goTo(index) { slides[Math.max(0, Math.min(slides.length - 1, index))].scrollIntoView({ behavior: 'smooth' }); }
document.addEventListener('keydown', event => {
  if (['ArrowRight', 'ArrowDown', 'PageDown', ' '].includes(event.key)) { event.preventDefault(); goTo(current + 1); }
  if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(event.key)) { event.preventDefault(); goTo(current - 1); }
  if (event.key === 'Home') goTo(0);
  if (event.key === 'End') goTo(slides.length - 1);
});
fullscreen.addEventListener('click', async () => {
  if (!document.fullscreenElement) { await document.documentElement.requestFullscreen(); fullscreen.textContent = 'Salir de pantalla completa'; }
  else { await document.exitFullscreen(); }
});
document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement) fullscreen.textContent = 'Pantalla completa'; });

const territoryMedia = document.querySelector('#territory-media');
const territoryCaption = document.querySelector('#territory-caption');
const territoryOptions = {
  annual: ['../figures/cultivos_anual_2003_2025.gif', 'Animación anual de cultivos dominantes en México', 'Cultivo dominante municipal · evolución anual 2003—2025'],
  cycles: ['../figures/cultivos_ciclos_2003_2025.gif', 'Animación de cultivos dominantes por ciclo productivo', 'Cultivo dominante municipal · evolución por ciclos productivos'],
};
document.querySelectorAll('[data-media]').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('[data-media]').forEach(item => item.classList.toggle('active', item === button));
  const [src, alt, caption] = territoryOptions[button.dataset.media];
  territoryMedia.src = src; territoryMedia.alt = alt; territoryCaption.textContent = caption;
}));

const evidenceImage = document.querySelector('#evidence-image');
const evidenceCaption = document.querySelector('#evidence-caption');
const evidenceOptions = {
  stability: ['../figures/mapa_estabilidad_rendimiento_maiz.png', 'Mapa municipal de estabilidad del rendimiento de maíz', 'Maíz grano · verde = menor variabilidad histórica'],
  risk: ['../figures/siniestros_anomalias_climaticas.png', 'Relación entre siniestros y anomalías climáticas', 'Superficie siniestrada frente a anomalías municipales de clima'],
  series: ['../figures/series_superficie_produccion_rendimiento.png', 'Series de superficie, producción y rendimiento', 'Trayectoria productiva de los cultivos principales'],
};
document.querySelectorAll('[data-evidence]').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('[data-evidence]').forEach(item => item.classList.toggle('active', item === button));
  const [src, alt, caption] = evidenceOptions[button.dataset.evidence];
  evidenceImage.src = src; evidenceImage.alt = alt; evidenceCaption.textContent = caption;
}));
activate(0);
