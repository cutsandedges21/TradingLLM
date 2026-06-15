import { useEffect, useRef } from 'react'
import { animate, motion, useMotionValue, useTransform } from 'motion/react'

export function AnimatedNumber({
  value,
  format,
}: {
  value: number
  format: (n: number) => string
}) {
  const mv = useMotionValue(value)
  const rendered = useTransform(mv, (v) => format(v))
  const first = useRef(true)

  useEffect(() => {
    const controls = animate(mv, value, {
      duration: first.current ? 0.9 : 0.5,
      ease: [0.16, 1, 0.3, 1],
    })
    first.current = false
    return () => controls.stop()
  }, [value, mv])

  return <motion.span>{rendered}</motion.span>
}
