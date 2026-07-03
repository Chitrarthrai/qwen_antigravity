import { useOutletContext } from 'react-router-dom';
import type { DashboardContextType } from '../components/Layout';

export default function CodeReview() {
  const { reviews } = useOutletContext<DashboardContextType>();

  const renderSimpleDiff = (content: string) => {
    const lines = content.split('\n');
    let isInsideDiff = false;
    const diffLines: { text: string; type: 'normal' | 'added' | 'removed' }[] = [];

    for (const line of lines) {
      if (line.includes('```')) {
        isInsideDiff = !isInsideDiff;
        continue;
      }
      if (isInsideDiff) {
        if (line.startsWith('-')) {
          diffLines.push({ text: line, type: 'removed' });
        } else if (line.startsWith('+')) {
          diffLines.push({ text: line, type: 'added' });
        } else {
          diffLines.push({ text: line, type: 'normal' });
        }
      }
    }

    if (diffLines.length === 0) {
      return (
        <pre className="font-mono text-xs text-text-secondary whitespace-pre-wrap break-all">
          {content.slice(0, 450)}...
        </pre>
      );
    }

    return (
      <div className="bg-[#05060b] border border-white/5 rounded-xl p-4 overflow-x-auto max-h-96">
        {diffLines.map((l, idx) => (
          <div 
            key={idx} 
            className={`font-mono text-xs px-2 py-0.5 whitespace-pre leading-relaxed border-l-3 ${
              l.type === 'added' 
                ? 'bg-color-success/5 text-[#b9f6ca] border-color-success' 
                : l.type === 'removed' 
                ? 'bg-color-danger/5 text-[#ff8a80] border-color-danger' 
                : 'text-text-secondary border-transparent'
            }`}
          >
            {l.text}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-1 text-white">Code Review Feed</h1>
        <p className="text-sm text-text-secondary">Live feed of bugs, security risks, and optimization issues reported by local Qwen</p>
      </div>

      <div className="flex flex-col gap-6">
        {reviews.length === 0 ? (
          <div className="bg-bg-secondary/40 backdrop-blur-md border border-white/5 rounded-2xl p-16 shadow-xl flex flex-col items-center justify-center text-center">
            <div className="w-12 h-12 bg-color-success/10 text-color-success rounded-full flex items-center justify-center text-xl mb-4 border border-color-success/20">
              ✓
            </div>
            <h2 className="text-lg font-bold text-white mb-1">All Projects Clean!</h2>
            <p className="text-sm text-text-secondary max-w-sm">No automated code review issues or warnings are currently logged.</p>
          </div>
        ) : (
          reviews.map((r, idx) => (
            <div key={idx} className="bg-bg-secondary/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl flex flex-col gap-4">
              <div className="flex justify-between items-center border-b border-white/5 pb-4">
                <div>
                  <h3 className="text-base font-bold text-accent-cyan mb-0.5">{r.project}</h3>
                  <span className="text-[10px] text-text-secondary/50 font-mono">File: {r.filename}</span>
                </div>
                <span className="inline-flex items-center px-3 py-1 rounded-full text-[10px] font-semibold bg-color-danger/10 text-color-danger border border-color-danger/20">
                  Requires Action
                </span>
              </div>

              <div className="text-sm text-text-secondary leading-relaxed">
                {renderSimpleDiff(r.content)}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
