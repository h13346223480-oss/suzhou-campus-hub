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
})();
