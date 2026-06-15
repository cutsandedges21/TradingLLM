import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '../api'

export function LearnPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [md, setMd] = useState('')

  useEffect(() => {
    if (open && !md) api.learn().then((r) => setMd(r.markdown)).catch(() => {})
  }, [open, md])

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-obsidian/60 backdrop-blur-sm"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.aside
            initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 260 }}
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-2xl flex-col border-l border-line-strong bg-panel"
          >
            <div className="flex items-center justify-between border-b border-line px-6 py-4">
              <div>
                <div className="font-display text-lg">Learn to Trade</div>
                <div className="text-[11px] text-faint">from zero — read top to bottom</div>
              </div>
              <button onClick={onClose} className="rounded-lg border border-line p-2 text-muted transition-colors hover:text-ink">
                <X size={18} />
              </button>
            </div>
            <div className="prose-terminal flex-1 overflow-y-auto px-7 py-5">
              {md ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{md}</ReactMarkdown>
              ) : (
                <div className="text-faint">Loading…</div>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}
