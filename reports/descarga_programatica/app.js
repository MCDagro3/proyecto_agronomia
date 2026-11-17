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
  const dark = ['hero', 'geo-slide', 'nasa-slide', 'resilience-slide', 'final'].some(name => slides[current].classList.contains(name));
  document.querySelector('.chrome').style.color = dark ? '#f5f0e3' : '#12362d';
  document.querySelector('.rail').style.color = dark ? '#f5f0e3' : '#12362d';
}

const observer = new IntersectionObserver(entries => {
  const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
  if (visible) activate(slides.indexOf(visible.target));
}, { threshold: [0.45, 0.7] });
slides.forEach(slide => observer.observe(slide));

function goTo(index) {
  slides[Math.max(0, Math.min(slides.length - 1, index))].scrollIntoView({ behavior: 'smooth' });
}
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
activate(0);
