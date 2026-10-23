import { useCallback, useMemo, useRef, useState } from 'react'
import { Radar } from 'react-chartjs-2'
import type { Chart as ChartType } from 'chart.js'
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
} from 'chart.js'
import SkillHistory from './SkillHistory'
import RadarHud from './RadarHud'
import SkillSummary from './SkillSummary'
import '../styles/profile-radar.css'

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip)

/**
 * Пятиугольник характеристик — один на профиль и главную.
 *
 * На главной жил свой упрощённый радар в процентах от 100, в профиле —
 * этот, в баллах до 20 с подписями вершин и историей по оси. Один и тот
 * же студент видел на двух экранах разные фигуры и разные числа.
 */

// Порядок как в макете: от верхней вершины по часовой стрелке
const AXIS_KEYS = ['Мощность', 'Фокус', 'Отдача', 'Ритм', 'Связь'] as const
const AXES = AXIS_KEYS.map((key) => ({ key }))
const MAX = 20

const radarBaseOptions = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    r: {
      beginAtZero: true,
      max: MAX,
      // в макете пятиугольник состоит ровно из 5 колец
      ticks: { display: false, stepSize: 4 },
      grid: { color: 'rgba(154, 51, 244, 0.55)', lineWidth: 3, circular: false },
      angleLines: { color: 'rgba(154, 51, 244, 0.55)', lineWidth: 3 },
      pointLabels: { display: false },
    },
  },
  layout: { padding: 0 },
  elements: { line: { tension: 0.12 } },
  animation: { duration: 900, easing: 'easeOutQuart' as const },
  plugins: { legend: { display: false }, tooltip: { enabled: false } },
} as const

// Габариты пилюли со значением: она стоит в вершине пятиугольника,
// поэтому подпись оси нужно отодвинуть за её пределы
const VALUE_PILL = { halfWidth: 27, halfHeight: 17.5 }
const AXIS_LABEL_GAP = 12
// ширина подсказки оси — совпадает с .axis-tip в profile-radar.css
const TIP_WIDTH = 148

interface Point {
  x: number
  y: number
}

// Подпись оси: точка привязки у вершины и направление, куда её отодвинуть
interface AxisAnchor extends Point {
  ux: number
  uy: number
}

export interface CharacteristicItem {
  pillar: string
  label: string
  current: number
  peak: number
  history: number[]
}

// Цвета графика: фирменные фиолетовые или чёрно-белые для тем космоса и плёнки
const TONES = {
  brand: {
    grid: 'rgba(154, 51, 244, 0.55)',
    fill: 'rgba(154, 51, 244, 0.18)',
    line: '#9A33F4',
    point: '#f5f5f5',
    peakFill: 'rgba(154, 51, 244, 0.08)',
    peakLine: 'rgba(154, 51, 244, 0.65)',
  },
  cosmos: {
    grid: 'rgba(255, 255, 255, 0.22)',
    fill: 'rgba(255, 255, 255, 0.12)',
    line: '#ffffff',
    point: '#0b0b10',
    peakFill: 'rgba(255, 255, 255, 0.04)',
    peakLine: 'rgba(255, 255, 255, 0.5)',
  },
  film: {
    grid: 'rgba(255, 255, 255, 0.16)',
    fill: 'rgba(192, 192, 192, 0.16)',
    line: '#e6e6e6',
    point: '#000000',
    peakFill: 'rgba(255, 255, 255, 0.03)',
    peakLine: 'rgba(192, 192, 192, 0.45)',
  },
} as const

interface Props {
  characteristics: CharacteristicItem[]
  tone?: keyof typeof TONES
  className?: string
  style?: React.CSSProperties
}

export default function CharacteristicsRadar({ characteristics, tone = 'brand', className = '', style }: Props) {
  const colors = TONES[tone]
  const [activeAxis, setActiveAxis] = useState<string | null>(null)
  const [hoveredAxis, setHoveredAxis] = useState<string | null>(null)
  // сторона подсказки оси: наружу от графика, а если там край экрана — над подписью
  const [tipSide, setTipSide] = useState<'left' | 'right' | 'above'>('right')

  const getSkill = useCallback((key: string) => {
    const item = characteristics.find(c => c.label === key)
    return {
      current: item?.current ?? 0,
      peak: item?.peak ?? 0,
      history: item?.history ?? [0, 0, 0, 0, 0, 0],
    }
  }, [characteristics])

  const radarData = {
    labels: [...AXIS_KEYS],
    datasets: [
      {
        label: 'Текущий',
        data: AXIS_KEYS.map(k => getSkill(k).current),
        backgroundColor: colors.fill,
        borderColor: colors.line,
        borderWidth: 5,
        pointBackgroundColor: colors.point,
        pointBorderColor: colors.line,
        pointBorderWidth: 5,
        pointRadius: 9,
        pointHoverRadius: 12,
      },
      {
        label: 'Пик',
        data: AXIS_KEYS.map(k => getSkill(k).peak),
        backgroundColor: colors.peakFill,
        borderColor: colors.peakLine,
        borderWidth: 3,
        borderDash: [8, 7],
        pointRadius: 0,
        pointHoverRadius: 0,
      },
    ],
  }

  // Подписи значений стоят ровно на вершинах графика, поэтому координаты
  // берём у самого чарта после отрисовки и после каждого ресайза.
  const chartRef = useRef<ChartType<'radar'> | null>(null)
  const [vertices, setVertices] = useState<{ current: Point[]; peak: Point[]; center: Point | null }>({ current: [], peak: [], center: null })
  const [axisAnchors, setAxisAnchors] = useState<AxisAnchor[]>([])

  const syncVertices = useCallback(() => {
    const chart = chartRef.current
    if (!chart) return
    const scale = chart.scales.r as unknown as {
      xCenter: number
      yCenter: number
      drawingArea: number
      getPointPosition: (i: number, d: number) => { x: number; y: number }
    }
    if (!scale) return

    // Пик подписан прямо на своей вершине, текущее значение — в углу
    // пятиугольника, как в макете.
    setVertices({
      current: AXES.map((_, i) => scale.getPointPosition(i, scale.drawingArea)),
      peak: chart.getDatasetMeta(1).data.map((point) => ({ x: point.x, y: point.y })),
      center: { x: scale.xCenter, y: scale.yCenter },
    })

    // Подпись оси уводим за пилюлю: считаем, насколько та выступает
    // вдоль луча, и добавляем зазор.
    setAxisAnchors(AXES.map((_, i) => {
      const outer = scale.getPointPosition(i, scale.drawingArea)
      const dx = outer.x - scale.xCenter
      const dy = outer.y - scale.yCenter
      const length = Math.hypot(dx, dy) || 1
      const ux = dx / length
      const uy = dy / length
      const pillReach = Math.abs(ux) * VALUE_PILL.halfWidth + Math.abs(uy) * VALUE_PILL.halfHeight
      const point = scale.getPointPosition(i, scale.drawingArea + pillReach + AXIS_LABEL_GAP)
      return { x: point.x, y: point.y, ux, uy }
    }))
  }, [])

  const radarOptions = useMemo(() => ({
    ...radarBaseOptions,
    scales: {
      r: {
        ...radarBaseOptions.scales.r,
        grid: { ...radarBaseOptions.scales.r.grid, color: colors.grid },
        angleLines: { ...radarBaseOptions.scales.r.angleLines, color: colors.grid },
      },
    },
    animation: { ...radarBaseOptions.animation, onComplete: syncVertices },
    onResize: syncVertices,
  }), [syncVertices, colors])

  const selectedAxis = activeAxis ?? 'Мощность'
  const activeHistory = getSkill(selectedAxis).history
  const closeHistory = useCallback(() => setActiveAxis(null), [])

  // Пустой пятиугольник не рисуем — на пол-экрана он только путает.
  if (characteristics.length === 0) return null

  return (
    <section className={`profile-radar${className ? ` ${className}` : ''}`} style={style}>
      <div className="profile-radar__chart">
        <RadarHud
          geo={vertices.center && vertices.current[0] ? {
            cx: vertices.center.x,
            cy: vertices.center.y,
            r: Math.hypot(vertices.current[0].x - vertices.center.x, vertices.current[0].y - vertices.center.y),
          } : null}
          values={AXES.map(({ key }) => getSkill(key).current)}
          max={MAX}
        />
        <Radar ref={chartRef} data={radarData} options={radarOptions} />

        {/* луч к выбранной оси: видно, о какой характеристике история */}
        {activeAxis && vertices.center && (() => {
          const i = AXES.findIndex((a) => a.key === activeAxis)
          const end = vertices.current[i]
          if (!end) return null
          return (
            <svg className="profile-radar__beam" aria-hidden="true">
              <line key={activeAxis} x1={vertices.center.x} y1={vertices.center.y} x2={end.x} y2={end.y} pathLength={1} />
            </svg>
          )
        })()}

        {/* Пик подписываем, только когда он читается: у выбранной оси или
            если вершина отошла от центра. Иначе подписи с маленькими
            значениями слипались в одну кучу посередине. */}
        {vertices.peak.map((point, i) => {
          const key = AXES[i].key
          const skill = getSkill(key)
          const center = vertices.center
          const far = center ? Math.hypot(point.x - center.x, point.y - center.y) > 64 : true
          // у самой вершины пик лёг бы на подпись текущего значения
          const corner = vertices.current[i]
          const clear = corner ? Math.hypot(point.x - corner.x, point.y - corner.y) > 46 : true
          const show = (activeAxis === key && clear) || (far && clear && skill.peak !== skill.current)
          return (
            <span
              key={`peak-${i}`}
              className={`profile-radar__value profile-radar__value--inner${show ? '' : ' profile-radar__value--hidden'}${activeAxis === key ? ' profile-radar__value--focus' : ''}`}
              style={{ left: point.x, top: point.y }}
              aria-hidden={!show}
            >
              {skill.peak}
            </span>
          )
        })}

        {vertices.current.map((point, i) => (
          <span
            key={`current-${i}`}
            className={`profile-radar__value${activeAxis === AXES[i].key ? ' profile-radar__value--focus' : ''}${activeAxis && activeAxis !== AXES[i].key ? ' profile-radar__value--dim' : ''}`}
            style={{ left: point.x, top: point.y }}
          >
            {getSkill(AXES[i].key).current}
          </span>
        ))}

        {axisAnchors.map((anchor, i) => {
          const key = AXES[i].key
          const skill = getSkill(key)
          const isActive = activeAxis === key
          const isHovered = hoveredAxis === key
          return (
            <button
              type="button"
              key={key}
              aria-pressed={isActive}
              className={`profile-radar__axis${isActive ? ' profile-radar__axis--active' : ''}`}
              style={{
                left: anchor.x,
                top: anchor.y,
                // сдвигаем подпись на половину её размера наружу от вершины
                transform: `translate(calc(-50% + ${anchor.ux * 50}%), calc(-50% + ${anchor.uy * 50}%))`,
              }}
              onMouseEnter={(e) => {
                const rect = e.currentTarget.getBoundingClientRect()
                const outward = anchor.ux < -0.05 ? 'left' : 'right'
                const room = outward === 'left' ? rect.left : window.innerWidth - rect.right
                setTipSide(room >= TIP_WIDTH + 24 ? outward : 'above')
                setHoveredAxis(key)
              }}
              onMouseLeave={() => setHoveredAxis(null)}
              onClick={() => setActiveAxis(cur => cur === key ? null : key)}
            >
              <span className="profile-radar__axis-icon" aria-hidden="true" />
              <span>{key}</span>
              {/* у выбранной оси всё это уже есть в карточке истории */}
              {!isActive && (
                // наружу от пятиугольника и вбок от подписи: снизу и сверху
                // подсказка легла бы на линии графика
                <span className={`axis-tip axis-tip--${isHovered ? tipSide : anchor.ux < -0.05 ? 'left' : 'right'}${isHovered ? ' axis-tip--show' : ''}`} aria-hidden="true">
                  <span className="axis-tip__num"><b>{skill.current}</b> / {MAX}</span>
                  <span className="axis-tip__bar">
                    <i style={{ transform: `scaleX(${Math.min(skill.current, MAX) / MAX})` }} />
                    <em style={{ left: `${(Math.min(skill.peak, MAX) / MAX) * 100}%` }} />
                  </span>
                  <span className="axis-tip__peak">лучшее {skill.peak}</span>
                </span>
              )}
            </button>
          )
        })}
      </div>

      <SkillSummary
        skills={AXES.map(({ key }) => ({ key, value: getSkill(key).current, peak: getSkill(key).peak }))}
        max={MAX}
        onPick={(key) => setActiveAxis((cur) => (cur === key ? null : key))}
      />

      <SkillHistory
        axis={selectedAxis}
        values={activeHistory}
        current={getSkill(selectedAxis).current}
        peak={getSkill(selectedAxis).peak}
        max={MAX}
        visible={Boolean(activeAxis)}
        onClose={closeHistory}
      />
    </section>
  )
}
