import { useOutletContext } from 'react-router-dom';
import type { DashboardContextType } from '../components/Layout';

export default function ResumeOptimizer() {
  const {
    jdText,
    setJdText,
    atsScore,
    matchedKeywords,
    missingKeywords,
    recommendations,
    loading,
    runScoreResume,
    runOptimizeResume,
    scoreReport
  } = useOutletContext<DashboardContextType>();

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-1 text-white">ATS Resume Optimizer</h1>
        <p className="text-sm text-text-secondary">Tailor your LaTeX resume dynamically to custom Job Descriptions and track matches</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Job Description card */}
        <div className="bg-bg-secondary/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl flex flex-col gap-4">
          <h3 className="text-base font-bold border-b border-white/5 pb-2 text-white">Target Job Description</h3>
          <textarea 
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            placeholder="Paste target Job Description text here..."
            className="w-full h-64 bg-bg-tertiary border border-white/5 rounded-xl p-4 font-sans text-sm outline-none resize-none text-white focus:border-accent-cyan/30 transition-all"
          />

          <div className="flex gap-4">
            <button 
              className="flex-1 flex items-center justify-center gap-2 bg-gradient-to-r from-accent-cyan to-accent-violet hover:brightness-110 active:scale-95 text-black font-semibold py-3 px-4 rounded-xl shadow-lg transition-all text-sm disabled:opacity-50 disabled:pointer-events-none"
              onClick={runScoreResume}
              disabled={loading.scoring}
            >
              {loading.scoring ? <div className="w-4 h-4 border-2 border-black/10 border-t-black rounded-full animate-spin" /> : null}
              Calculate ATS Score
            </button>
            <button 
              className="flex-1 flex items-center justify-center gap-2 bg-bg-tertiary hover:bg-white/5 border border-white/5 active:scale-95 text-white py-3 px-4 rounded-xl transition-all text-sm disabled:opacity-50 disabled:pointer-events-none"
              onClick={runOptimizeResume}
              disabled={loading.optimizing}
            >
              {loading.optimizing ? <div className="w-4 h-4 border-2 border-white/10 border-t-white rounded-full animate-spin" /> : null}
              Tailor Keywords
            </button>
          </div>
        </div>

        {/* Match score and improvements */}
        <div className="flex flex-col gap-6">
          {/* Score gauge card */}
          <div className="bg-bg-secondary/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl flex flex-col items-center gap-4 text-center">
            <span className="text-xs text-text-secondary uppercase tracking-wider font-semibold">Compatibility Match Score</span>
            
            {/* Animated Gauge */}
            <div className="relative w-40 h-20 overflow-hidden flex justify-center items-end">
              {/* Track */}
              <div className="absolute top-0 left-0 w-40 h-40 rounded-full border-16 border-bg-tertiary border-b-transparent border-r-transparent -rotate-45" />
              {/* Fill */}
              <div 
                className={`absolute top-0 left-0 w-40 h-40 rounded-full border-16 border-transparent transition-all duration-1000 -rotate-45`}
                style={{
                  borderTopColor: atsScore >= 85 ? '#00e676' : atsScore >= 70 ? '#ffa726' : '#ff1744',
                  transform: `rotate(${Math.min(180, (atsScore / 100) * 180 - 45)}deg)`
                }}
              />
              <span className="text-3xl font-extrabold relative z-10 -top-1">
                {atsScore ? `${atsScore}` : '0'}<span className="text-base text-text-secondary font-normal">%</span>
              </span>
            </div>

            <span className="text-xs text-text-secondary">
              {atsScore >= 85 ? '🟢 Shortlist Ready' : atsScore >= 70 ? '🟡 Needs Tailoring' : '🔴 Low compatibility'}
            </span>
          </div>

          {/* Recommendations Card */}
          <div className="bg-bg-secondary/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl flex flex-col gap-4 flex-grow">
            <h3 className="text-sm font-bold border-b border-white/5 pb-2 text-white">Actionable Improvements</h3>
            <div className="flex flex-col gap-2.5 max-h-48 overflow-y-auto pr-1">
              {recommendations.length === 0 ? (
                <div className="text-text-secondary text-xs text-center py-6">
                  No recommendations parsed. Run evaluation to check.
                </div>
              ) : (
                recommendations.map((r, idx) => (
                  <div key={idx} className="text-xs text-text-secondary flex gap-2.5 leading-relaxed">
                    <span className="text-accent-cyan">•</span>
                    <span>{r}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Detailed collapsible report */}
      {scoreReport && (
        <div className="bg-bg-secondary/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl flex flex-col gap-3">
          <h3 className="text-sm font-bold border-b border-white/5 pb-2 text-white">Detailed Report Details</h3>
          <pre className="font-mono text-[10px] text-text-secondary whitespace-pre-wrap max-h-48 overflow-y-auto bg-black/20 p-4 rounded-xl border border-white/5">
            {scoreReport}
          </pre>
        </div>
      )}

      {/* Keywords matching grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="bg-bg-secondary/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl">
          <h3 className="text-sm font-bold mb-4 text-color-success">Matched Keywords ({matchedKeywords.length})</h3>
          <div className="flex flex-wrap gap-1.5 max-h-40 overflow-y-auto pr-1">
            {matchedKeywords.length === 0 ? (
              <span className="text-xs text-text-secondary">None identified yet.</span>
            ) : (
              matchedKeywords.map((k, idx) => (
                <span 
                  key={idx} 
                  className="text-[10px] font-mono bg-color-success/5 text-color-success border border-color-success/15 px-2.5 py-0.5 rounded-md"
                >
                  {k}
                </span>
              ))
            )}
          </div>
        </div>

        <div className="bg-bg-secondary/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl">
          <h3 className="text-sm font-bold mb-4 text-color-danger">Missing Keywords ({missingKeywords.length})</h3>
          <div className="flex flex-wrap gap-1.5 max-h-40 overflow-y-auto pr-1">
            {missingKeywords.length === 0 ? (
              <span className="text-xs text-text-secondary">None identified yet.</span>
            ) : (
              missingKeywords.map((k, idx) => (
                <span 
                  key={idx} 
                  className="text-[10px] font-mono bg-color-danger/5 text-color-danger border border-color-danger/15 px-2.5 py-0.5 rounded-md"
                >
                  {k}
                </span>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
