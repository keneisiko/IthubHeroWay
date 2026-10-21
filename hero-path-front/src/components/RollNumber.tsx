const DIGITS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']

interface RollNumberProps {
  value: number | string
  className?: string
}

/**
 * Число-одометр: каждая цифра — лента 0…9, которая прокатывается до
 * нужного значения. При появлении ленты едут от нуля, при смене числа —
 * к новой цифре, младшие разряды чуть позже старших.
 */
export default function RollNumber({ value, className }: RollNumberProps) {
  const text = String(value)
  const chars = Array.from(text)

  return (
    <span className={`roll${className ? ` ${className}` : ''}`}>
      <span className="visually-hidden">{text}</span>
      <span className="roll__digits" aria-hidden="true">
        {chars.map((ch, i) => {
          // ключ от конца строки: при росте 99 → 100 единицы остаются единицами
          const key = chars.length - i
          if (!/\d/.test(ch)) return <span key={`s${key}`} className="roll__sep">{ch}</span>
          return (
            <span key={key} className="roll__col" style={{ '--i': i } as React.CSSProperties}>
              <span className="roll__strip" style={{ '--n': Number(ch) } as React.CSSProperties}>
                {DIGITS.map((d) => <span key={d}>{d}</span>)}
              </span>
              <span className="roll__sizer">{ch}</span>
            </span>
          )
        })}
      </span>
    </span>
  )
}
