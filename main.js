/* ============================================================
   MAIN.JS — Anthropic.com UI — Interactions & Animations
   ============================================================ */

(function () {
  'use strict';

  /* ──────────────────────────────────────────────────────────
     1. NAVIGATION — scroll-driven background toggle
  ────────────────────────────────────────────────────────── */
  const siteNav = document.getElementById('site-nav');

  function updateNavState() {
    if (window.scrollY > 40) {
      siteNav.classList.add('scrolled');
    } else {
      siteNav.classList.remove('scrolled');
    }
  }

  window.addEventListener('scroll', updateNavState, { passive: true });
  updateNavState(); // run once on load

  /* ──────────────────────────────────────────────────────────
     2. MOBILE HAMBURGER MENU
  ────────────────────────────────────────────────────────── */
  const hamburger = document.getElementById('hamburger');
  const mobileDrawer = document.getElementById('mobile-drawer');
  const mobileLinks = mobileDrawer.querySelectorAll('.mobile-nav-link, .mobile-cta');

  function openMenu() {
    hamburger.classList.add('open');
    mobileDrawer.classList.add('open');
    hamburger.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
  }

  function closeMenu() {
    hamburger.classList.remove('open');
    mobileDrawer.classList.remove('open');
    hamburger.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  hamburger.addEventListener('click', function () {
    if (hamburger.classList.contains('open')) {
      closeMenu();
    } else {
      openMenu();
    }
  });

  // Close drawer when a link is clicked
  mobileLinks.forEach(function (link) {
    link.addEventListener('click', closeMenu);
  });

  // Close on Escape
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && mobileDrawer.classList.contains('open')) {
      closeMenu();
      hamburger.focus();
    }
  });

  /* ──────────────────────────────────────────────────────────
     3. HERO CANVAS — particle animation
  ────────────────────────────────────────────────────────── */
  const canvas = document.getElementById('hero-canvas');
  if (canvas) {
    const ctx = canvas.getContext('2d');
    let W, H, particles, animId;

    // Respect reduced-motion preference
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    function resize() {
      W = canvas.width = canvas.offsetWidth;
      H = canvas.height = canvas.offsetHeight;
    }

    function createParticles(count) {
      particles = [];
      for (let i = 0; i < count; i++) {
        particles.push({
          x: Math.random() * W,
          y: Math.random() * H,
          r: Math.random() * 1.5 + 0.3,
          vx: (Math.random() - 0.5) * 0.35,
          vy: (Math.random() - 0.5) * 0.35,
          alpha: Math.random() * 0.5 + 0.1,
        });
      }
    }

    function drawLines() {
      const LINK_DIST = 130;
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < LINK_DIST) {
            const alpha = (1 - dist / LINK_DIST) * 0.12;
            ctx.strokeStyle = `rgba(212,104,30,${alpha})`;
            ctx.lineWidth = 0.8;
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
          }
        }
      }
    }

    function tick() {
      ctx.clearRect(0, 0, W, H);

      particles.forEach(function (p) {
        // Move
        p.x += p.vx;
        p.y += p.vy;

        // Wrap at edges
        if (p.x < 0) p.x = W;
        if (p.x > W) p.x = 0;
        if (p.y < 0) p.y = H;
        if (p.y > H) p.y = 0;

        // Draw dot
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(212,104,30,${p.alpha})`;
        ctx.fill();
      });

      drawLines();
      animId = requestAnimationFrame(tick);
    }

    function init() {
      resize();
      const count = Math.min(120, Math.floor((W * H) / 8000));
      createParticles(count);
      if (!prefersReducedMotion) {
        tick();
      } else {
        // Draw a single static frame for reduced-motion users
        createParticles(count);
        particles.forEach(function (p) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(212,104,30,${p.alpha})`;
          ctx.fill();
        });
      }
    }

    window.addEventListener('resize', function () {
      cancelAnimationFrame(animId);
      resize();
      createParticles(Math.min(120, Math.floor((W * H) / 8000)));
      if (!prefersReducedMotion) tick();
    }, { passive: true });

    init();
  }

  /* ──────────────────────────────────────────────────────────
     4. SCROLL-REVEAL — fade-in sections as they enter viewport
  ────────────────────────────────────────────────────────── */
  const revealEls = document.querySelectorAll(
    '.product-card, .news-card, .feature-row, .mission-copy, .cta-banner-inner, .section-header'
  );

  if ('IntersectionObserver' in window) {
    const revealObs = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('revealed');
            revealObs.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
    );

    revealEls.forEach(function (el) {
      el.classList.add('reveal-pending');
      revealObs.observe(el);
    });
  } else {
    // Fallback: reveal everything immediately
    revealEls.forEach(function (el) { el.classList.add('revealed'); });
  }

  /* ──────────────────────────────────────────────────────────
     5. SMOOTH SCROLL for anchor links
  ────────────────────────────────────────────────────────── */
  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
    anchor.addEventListener('click', function (e) {
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        const offset = parseInt(getComputedStyle(document.documentElement)
          .getPropertyValue('--nav-height') || '68', 10);
        const top = target.getBoundingClientRect().top + window.scrollY - offset;
        window.scrollTo({ top: top, behavior: 'smooth' });
      }
    });
  });
})();
