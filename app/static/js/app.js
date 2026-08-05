(function () {
  'use strict';

  // 顶部导航滚动阴影
  var header = document.querySelector('.site-header');
  var onScroll = function () {
    if (header) { header.classList.toggle('scrolled', window.scrollY > 8); }
  };
  window.addEventListener('scroll', onScroll, {passive: true});
  onScroll();

  // 回到顶部按钮
  var toTop = document.createElement('button');
  toTop.type = 'button';
  toTop.className = 'to-top';
  toTop.setAttribute('aria-label', '回到顶部');
  toTop.textContent = '\u2191';
  document.body.appendChild(toTop);
  var toggleTop = function () {
    toTop.classList.toggle('show', window.scrollY > 480);
  };
  window.addEventListener('scroll', toggleTop, {passive: true});
  toggleTop();
  toTop.addEventListener('click', function () {
    window.scrollTo({top: 0, behavior: 'smooth'});
  });

  // 滚动显现动画
  var targets = document.querySelectorAll(
    '.section, .page-header, .article, .survey-invite, .campus-access-note, ' +
    '.feature-card, .guide-card, .post-card, .resource-card, .tutor-card, ' +
    '.stat-card, .location-card, .survey-admin-card, .question-admin-card, .empty'
  );
  if (!targets.length) { return; }
  if (!('IntersectionObserver' in window)) {
    targets.forEach(function (el) { el.classList.add('in'); });
    return;
  }
  var seen = {};
  targets.forEach(function (el) {
    el.classList.add('reveal');
    var parentKey = el.parentElement ? el.parentElement.className : '';
    seen[parentKey] = (seen[parentKey] || 0) + 1;
    el.style.transitionDelay = ((seen[parentKey] - 1) % 6) * 40 + 'ms';
  });
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) { return; }
      var el = entry.target;
      el.classList.add('in');
      io.unobserve(el);
      el.addEventListener('transitionend', function done(e) {
        if (e.propertyName === 'transform') {
          el.style.transitionDelay = '';
          el.removeEventListener('transitionend', done);
        }
      });
    });
  }, {threshold: 0.06, rootMargin: '0px 0px -24px 0px'});
  targets.forEach(function (el) { io.observe(el); });

  // 亮暗模式切换（记住用户选择，默认暗色）
  var applyThemeIcon = function () {
    var isLight = document.documentElement.getAttribute('data-theme') === 'light';
    var btn = document.querySelector('.theme-toggle');
    if (btn) {
      btn.innerHTML = isLight ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="ico-moon"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>' : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="ico-sun"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';
      btn.setAttribute('aria-label', isLight ? '切换到暗色模式' : '切换到亮色模式');
    }
  };
  window.toggleTheme = function () {
    var el = document.documentElement;
    var next = el.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    el.setAttribute('data-theme', next);
    try { localStorage.setItem('theme', next); } catch (e) {}
    applyThemeIcon();
  };
  document.addEventListener('DOMContentLoaded', applyThemeIcon);
})();
