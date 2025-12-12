// static/ui.js
document.addEventListener('mousemove', e => {
  document.querySelectorAll('.card').forEach(card => {
    const r = card.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    card.style.transform = `translateY(-4px) rotateX(${y*2}deg) rotateY(${x*3}deg)`;
    card.style.transition = 'transform .08s linear';
  });
});
document.addEventListener('mouseleave', () => {
  document.querySelectorAll('.card').forEach(card => card.style.transform = '');
});
