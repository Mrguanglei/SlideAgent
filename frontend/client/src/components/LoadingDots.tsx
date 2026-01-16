/**
 * 天工风格的加载动画 - 两个小球来回移动
 */
export default function LoadingDots() {
  return (
    <div className="flex items-center gap-2">
      <style>{`
        @keyframes slide-left {
          0%, 100% { transform: translateX(0); }
          50% { transform: translateX(-8px); }
        }
        @keyframes slide-right {
          0%, 100% { transform: translateX(0); }
          50% { transform: translateX(8px); }
        }
        .dot-left {
          animation: slide-left 1.2s ease-in-out infinite;
        }
        .dot-right {
          animation: slide-right 1.2s ease-in-out infinite;
        }
      `}</style>
      <div className="w-2 h-2 rounded-full bg-primary dot-left" />
      <div className="w-2 h-2 rounded-full bg-primary dot-right" />
    </div>
  );
}
