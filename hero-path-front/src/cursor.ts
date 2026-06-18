export function initCursor() {
  const cursor = document.createElement('div')
  const cursorDot = document.createElement('div')

  cursor.style.cssText = `
    position: fixed; top: 0; left: 0; width: 40px; height: 40px;
    border: 2px solid rgba(154, 51, 244, 0.8); border-radius: 50%;
    pointer-events: none; z-index: 99999; transition: transform 0.15s ease, width 0.3s ease, height 0.3s ease, background 0.3s ease, opacity 0.3s ease;
    transform: translate(-50%, -50%); mix-blend-mode: difference;
  `
  cursorDot.style.cssText = `
    position: fixed; top: 0; left: 0; width: 6px; height: 6px;
    background: #9a33f4; border-radius: 50%; pointer-events: none;
    z-index: 99999; transform: translate(-50%, -50%); transition: transform 0.05s ease;
  `

  document.body.appendChild(cursor)
  document.body.appendChild(cursorDot)
  document.body.style.cursor = 'none'

  let mouseX = 0, mouseY = 0
  let curX = 0, curY = 0

  document.addEventListener('mousemove', (e) => {
    mouseX = e.clientX
    mouseY = e.clientY
    cursorDot.style.left = mouseX + 'px'
    cursorDot.style.top = mouseY + 'px'
  })

  // Магнитное притяжение к кнопкам
  document.querySelectorAll('button, a, .hover-lift').forEach(el => {
    el.addEventListener('mouseenter', () => {
      cursor.style.width = '60px'
      cursor.style.height = '60px'
      cursor.style.background = 'rgba(154, 51, 244, 0.15)'
      cursor.style.borderColor = '#9a33f4'
    })
    el.addEventListener('mouseleave', () => {
      cursor.style.width = '40px'
      cursor.style.height = '40px'
      cursor.style.background = 'transparent'
    })
  })

  // Частицы при клике
  document.addEventListener('click', (e) => {
    for (let i = 0; i < 8; i++) {
      const particle = document.createElement('div')
      const angle = (i / 8) * Math.PI * 2
      const velocity = 60 + Math.random() * 40
      const size = 4 + Math.random() * 6

      particle.style.cssText = `
        position: fixed; left: ${e.clientX}px; top: ${e.clientY}px;
        width: ${size}px; height: ${size}px; border-radius: 50%;
        background: hsl(${270 + Math.random() * 60}, 90%, 65%);
        pointer-events: none; z-index: 99998;
        transform: translate(-50%, -50%);
        transition: all 0.6s cubic-bezier(0.22, 1, 0.36, 1);
        opacity: 1;
      `
      document.body.appendChild(particle)

      requestAnimationFrame(() => {
        particle.style.left = `${e.clientX + Math.cos(angle) * velocity}px`
        particle.style.top = `${e.clientY + Math.sin(angle) * velocity}px`
        particle.style.opacity = '0'
        particle.style.transform = 'translate(-50%, -50%) scale(0)'
      })

      setTimeout(() => particle.remove(), 700)
    }
  })

  // Плавное следование курсора
  function animateCursor() {
    curX += (mouseX - curX) * 0.12
    curY += (mouseY - curY) * 0.12
    cursor.style.left = curX + 'px'
    cursor.style.top = curY + 'px'
    requestAnimationFrame(animateCursor)
  }
  animateCursor()
}