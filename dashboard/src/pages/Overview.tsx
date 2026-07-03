import { useOutletContext } from 'react-router-dom';
import type { DashboardContextType } from '../components/Layout';

export default function Overview() {
  const { projects, reviews, atsScore } = useOutletContext<DashboardContextType>();

  return (
    <div className="flex flex-col gap-8">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight mb-1 text-white">Workspace Overview</h1>
          <p className="text-sm text-text-secondary">
            Reviewing and parsing projects recursively in <code className="bg-bg-tertiary px-1.5 py-0.5 rounded text-accent-cyan font-mono text-xs">/home/chitrarth/Chitrarth</code>
          </p>
        </div>
        <span className="inline-flex items-center px-4 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider bg-color-success/10 text-color-success border border-color-success/20">
          Watcher Active
        </span>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-bg-secondary/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl hover:border-accent-cyan/20 transition-all">
          <span className="text-xs text-text-secondary uppercase tracking-wider font-semibold block mb-2">Analyzed Projects</span>
          <span className="text-4xl font-extrabold text-accent-cyan">{projects.length}</span>
        </div>
        <div className="bg-bg-secondary/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl hover:border-accent-cyan/20 transition-all">
          <span className="text-xs text-text-secondary uppercase tracking-wider font-semibold block mb-2">Recent Findings</span>
          <span className="text-4xl font-extrabold text-accent-violet">{reviews.length}</span>
        </div>
        <div className="bg-bg-secondary/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl hover:border-accent-cyan/20 transition-all">
          <span className="text-xs text-text-secondary uppercase tracking-wider font-semibold block mb-2">Current ATS Score</span>
          <span className="text-4xl font-extrabold text-accent-gold">{atsScore ? `${atsScore}/100` : 'N/A'}</span>
        </div>
      </div>

      {/* Projects Grid */}
      <div>
        <h2 className="text-xl font-bold tracking-tight mb-4 text-white">Identified Projects</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {projects.map((p, idx) => (
            <div key={idx} className="bg-bg-secondary/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl flex flex-col gap-4 hover:border-accent-cyan/20 hover:-translate-y-0.5 transition-all">
              <div className="flex justify-between items-start">
                <h3 className="text-lg font-bold text-accent-cyan">{p.project_name}</h3>
                <span className="bg-bg-tertiary border border-white/5 px-2.5 py-1 rounded-md text-[10px] font-mono text-text-secondary">
                  SHA: {p.git_hash ? p.git_hash.slice(0, 7) : 'no-git'}
                </span>
              </div>

              <p className="text-sm text-text-secondary leading-relaxed">{p.summary}</p>
              
              {/* Tech Stack */}
              <div className="flex flex-wrap gap-1.5">
                {p.tech_stack.map((t, tIdx) => (
                  <span 
                    key={tIdx} 
                    className="text-[10px] font-mono bg-white/5 border border-white/5 text-text-primary px-2.5 py-0.5 rounded-md"
                  >
                    {t}
                  </span>
                ))}
              </div>

              {/* Highlights */}
              <div className="border-t border-white/5 pt-4 mt-auto">
                <span className="text-[10px] uppercase text-text-secondary/60 tracking-wider font-bold block mb-2">
                  Project Highlights
                </span>
                <ul className="list-disc pl-4 space-y-1">
                  {p.highlights.slice(0, 2).map((h, hIdx) => (
                    <li key={hIdx} className="text-xs text-text-secondary leading-relaxed">{h}</li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
