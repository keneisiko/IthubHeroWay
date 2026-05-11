📐 AGENTS 2 — Полные спецификации
🔲 Корневой контейнер (Agents 2)
background: #F5F5F5
position: relative
size: 100% (full width & height)
🟣 Header (Heder)
width: 1180px
height: 82px
top: 26px
left: 50% (центрирован, transform: translateX(-50%))
border-radius: 24px
background: #9A33F4
box-shadow: 25px 25px 20px -20px rgba(0,0,0,0.45)
overflow: hidden
Логотип + заголовок (Frame2) — внутри Header
position: absolute
top: 11px
left: 0
gap: 3px
align-items: center

  Лого:
    width: 167px
    height: 60px

  Текст "Путь героя":
    font-family: TT Firs Neue Bold
    font-size: 28px
    color: #F5F5F5

  Разделитель (линия вертикальная):
    left: 157px
    top: 6px
    width: 48px (повёрнута 90°)
    height: 48px
    stroke: white
    stroke-width: 2px
Профиль пользователя (Frame1) — внутри Header
position: absolute
left: 887px
top: 17px
width: 276px
justify-content: space-between

  Имя пользователя:
    font-family: Montserrat SemiBold
    font-size: 22px
    color: #FFFFFF

  "Money:":
    font-family: Montserrat Medium
    font-size: 20px
    color: #FFD900

  "9.99":
    font-family: Montserrat SemiBold
    font-size: 20px
    color: #FFD900

  Монетка (круг):
    width: 18px
    height: 18px
    fill: #FFD900

  Аватар:
    width: 48px
    height: 48px
🟤 Табы "Агенты / Отряды" (Frame3)
position: absolute
left: calc(50% - 420px), transform: translateX(-50%)
top: 138px
width: 340px
background: #F5F5F5
border-radius: 24px
padding: 20px
box-shadow: 25px 25px 20px -20px rgba(0,0,0,0.45)
overflow: hidden
gap между кнопками: 20px (горизонтальный)

  Кнопка "Агенты":
    height: 63px
    background: #121212
    border-radius: 16px
    padding: 17px 20px
    border: 4px solid #F5F5F5
    box-shadow: 25px 25px 20px -20px rgba(0,0,0,0.45)
    font-family: Montserrat Bold
    font-size: 24px
    color: #F5F5F5

  Кнопка "Отряды":
    height: 63px
    background: #9A33F4
    border-radius: 16px
    padding: 17px 20px
    border: 4px solid #F5F5F5
    box-shadow: 25px 25px 20px -20px #9A33F4
    font-family: Montserrat Bold
    font-size: 24px
    color: #F5F5F5
🔘 Кнопка "Фильтры" (Frame4)
position: absolute
left: calc(50% + 360px), transform: translateX(-50%)
top: 138px
width: 220px
background: #F5F5F5
border-radius: 24px
padding: 20px
box-shadow: 25px 25px 20px -20px rgba(0,0,0,0.45)
overflow: hidden

  Кнопка "Фильтры":
    height: 63px
    background: #F5F5F5
    border-radius: 16px
    padding: 17px 20px
    border: 4px solid #9A33F4
    box-shadow: 25px 25px 20px -20px rgba(0,0,0,0.45)
    font-family: Montserrat Bold
    font-size: 24px
    color: #9A33F4
🟣 Главный блок рейтинга (Component / "Блок-Агентов/Рейтинг")
position: absolute
left: 370px
top: 261px
width: 1060px
background: #9A33F4
border-radius: 24px
padding: 20px
box-shadow: 25px 25px 20px -20px rgba(0,0,0,0.45)
overflow: hidden

  Заголовок "Топ 10 отрядов":
    font-family: TT Firs Neue Bold
    font-size: 28px
    color: #F5F5F5
    margin-bottom в gap: 16px
🔍 Поиск (Component1)
width: 560px
height: 46px
background: #F5F5F5
border-radius: 12px
box-shadow: 25px 25px 20px -14px rgba(0,0,0,0.45)
overflow: hidden

  Текст "Поиск":
    left: 11px
    top: 11px
    font-family: Montserrat SemiBold
    font-size: 20px
    color: #848484

  Иконка поиска (лупа):
    left: 514px
    top: 9px
    width: 25.67px
    height: 28px
    stroke: #848484
    stroke-width: 4px
    circle: cx=10.11, cy=10.11, r=8.11
    line: от (17.6, 17.11) до (25.67, 25.17)
📋 Таблица рейтинга (Component2)
width: 1020px
background: #F5F5F5
border-radius: 12px
padding: 20px
box-shadow: 25px 25px 20px -20px rgba(0,0,0,0.45)
gap между строками: 16px
Строка рейтинга (общая структура — повторяется 6 раз)
height: 78px
position: relative
width: 100%

  Карточка (белая часть):
    position: absolute
    inset: 0 0 0 6.63% (или 6.53%)
    background: #F5F5F5
    border-radius: 8px
    border: 4px solid #9A33F4
    box-shadow: 25px 25px 20px -20px rgba(0,0,0,0.45)
    padding: 14px
    layout: flex, justify-content: space-between, align-items: center

    Группа тегов (слева):
      gap: 12px

      Тег "Название отряда":
        height: 35px
        background: #121212
        border-radius: 48px
        padding: 4px 16px
        font-family: Montserrat SemiBold
        font-size: 16px
        color: #F5F5F5

      Тег "Дельта роста:":
        height: 35px
        background: #9A33F4
        border-radius: 48px
        padding: 4px 16px
        font-family: Montserrat SemiBold
        font-size: 16px
        color: #F5F5F5

      Тег "+47":
        height: 35px
        background: #F5F5F5
        border-radius: 48px
        padding: 4px 16px
        border: 4px solid #000000
        font-family: Montserrat SemiBold
        font-size: 20px
        color: #121212

    Кнопка "Рейтинг" (справа):
      height: 46px
      background: #121212
      border-radius: 4px
      padding: 8px 16px
      font-family: Montserrat Bold
      font-size: 24px
      color: #F5F5F5

  Значок номера (кружок слева):
    position: absolute
    top: 50%, transform: translateY(-50%)
    left: 0
    right: 94.9% (ширина ~5.1% от родителя)
    height: 50px
    border-radius: 25px
    padding: 2px 17px
    font-family: TT Firs Neue Bold (места 1,2,3) / Montserrat Bold (места 4,5,56)
    font-size: 36px (места 1,2,3) / 24px (места 4,5,56)
    color: #121212
Цвета кружков по местам:
1 место: background: #FFD900 (жёлтый)
2 место: background: #FF00EE (розовый/магента)
3 место: background: #38DDDD (голубой)
4 место: background: #848484 (серый)
5 место: background: #848484 (серый)
56 место: background: #F5F5F5, border: 4px solid #121212
Разделитель перед строкой "Мой отряд":
Линия горизонтальная:
  width: 963px
  stroke: #121212
  stroke-width: 4px
  stroke-linecap: round
Последняя строка "Мой отряд" (место 56):
Тег "Мой отряд" вместо "Название отряда"
border карточки: box-shadow: 25px 25px 20px -20px #9A33F4 (фиолетовый, не чёрный)
📱 Боковая навигация
position: absolute
left: calc(50% + 540px), transform: translate(-50%, -50%)
top: calc(50% - 816.5px)
width: 100px
background: #F5F5F5
border-radius: 24px
padding-top: 24px
padding-bottom: 24px
box-shadow: 25px 25px 20px -20px rgba(0,0,0,0.45)
overflow: hidden
gap между иконками: 20px

Каждая иконка-блок:
  width: 100px
  иконка контейнер: 48x48px
  фон-градиент: linear-gradient(to left, rgba(90,30,142,0), rgba(154,51,244,X), rgba(90,30,142,0))
  высота фон-блока: 52px

  Подпись:
    font-family: Montserrat SemiBold
    font-size: 16px
    color: #9A33F4
    text-align: center

Иконки (цвет fill): #9A33F4, кроме "Лидеры" — fill: #F5F5F5 (активный)
Навигационные пункты:
1. Главная   — иконка пятиугольник (Polygon 7)
2. Профиль   — иконка человек (круг + эллипс)
3. Квесты    — иконка список (3 линии + 3 круга)
4. Магазин   — иконка корзина (Vector 7 + 2 круга ø8px)
5. Лидеры    — иконка кубок (Vector 12), активный пункт
6. Отряды    — иконка 2 человека (2×Ellipse35 + 2×circle ø14)
🟣 Полоска прокрутки
position: absolute
left: 1543px
top: 569px
width: 14px
height: 64px
background: #9A33F4
border-radius: 4px
box-shadow: 5px 5px 17.1px 2px #9A33F4
🎨 Цветовая палитра
#9A33F4  — основной фиолетовый
#121212  — тёмный/чёрный
#F5F5F5  — светлый/белый
#FFD900  — золотой (1 место)
#FF00EE  — магента (2 место)
#38DDDD  — голубой (3 место)
#848484  — серый (4-5 место)
🔤 Шрифты
TT Firs Neue Bold   — заголовки, цифры мест 1-3
Montserrat Bold     — кнопки "Рейтинг", "Агенты", "Отряды"
Montserrat SemiBold — теги, имя пользователя, навигация
Montserrat Medium   — "Money:"