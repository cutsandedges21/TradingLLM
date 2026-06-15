import { ShaderBackground } from './ShaderBackground'

export function Background() {
  return (
    <>
      {/* Animated plasma-grid base layer (WebGL). */}
      <ShaderBackground />

      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        {/* Legibility scrim: darkens the animation so ivory type stays crisp. */}
        <div
          className="absolute inset-0"
          style={{
            background:
              'radial-gradient(120% 120% at 50% 40%, rgba(8,10,15,0.62), rgba(8,10,15,0.86))',
          }}
        />
        {/* Signal-cyan ambient glows for depth (match the ATLAS palette). */}
        <div
          className="absolute -top-48 right-[-8%] h-[62vh] w-[62vh] rounded-full"
          style={{
            background: 'radial-gradient(circle, rgba(79,224,205,0.12), transparent 62%)',
            filter: 'blur(40px)',
          }}
        />
        <div
          className="absolute bottom-[-28%] left-[-12%] h-[55vh] w-[55vh] rounded-full"
          style={{
            background: 'radial-gradient(circle, rgba(52,211,154,0.05), transparent 62%)',
            filter: 'blur(56px)',
          }}
        />
        <div
          className="absolute inset-0"
          style={{
            background:
              'radial-gradient(130% 85% at 50% -12%, rgba(220,228,245,0.04), transparent 55%)',
          }}
        />
      </div>
    </>
  )
}
