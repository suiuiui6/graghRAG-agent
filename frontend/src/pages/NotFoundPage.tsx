import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center h-[calc(100vh-52px)] gap-4">
      <div className="text-7xl font-extrabold bg-gradient-to-r from-accent to-indigo-500 bg-clip-text text-transparent">
        404
      </div>
      <h2 className="text-xl font-semibold">页面未找到</h2>
      <p className="text-text-muted text-sm">你访问的页面不存在或已被移除</p>
      <Link
        to="/upload"
        className="mt-4 py-2.5 px-8 bg-accent text-white rounded-full text-sm font-semibold hover:bg-accent-light transition-all"
      >
        返回首页
      </Link>
    </div>
  )
}
