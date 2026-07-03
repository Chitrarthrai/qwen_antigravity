import { useState, useEffect } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { LayoutDashboard, Code2, GitGraph, FileText, Terminal } from 'lucide-react';

export interface ProjectProfile {
  project_name: string;
  summary: string;
  tech_stack: string[];
  highlights: string[];
  git_hash: string;
  path: string;
}

export interface ASTNode {
  id: string;
  name: string;
  kind: string;
  file_path: string;
}

export interface ASTEdge {
  source: string;
  target: string;
  kind: string;
}

export interface ReviewFinding {
  filename: string;
  project: string;
  mtime: number;
  content: string;
}

export interface DashboardContextType {
  projects: ProjectProfile[];
  fetchProjects: () => Promise<void>;
  selectedProjPath: string;
  setSelectedProjPath: (path: string) => void;
  astNodes: ASTNode[];
  astEdges: ASTEdge[];
  fetchAST: (path: string) => Promise<void>;
  astFilter: 'ALL' | 'File' | 'Class' | 'Function';
  setAstFilter: (filter: 'ALL' | 'File' | 'Class' | 'Function') => void;
  reviews: ReviewFinding[];
  fetchReviews: () => Promise<void>;
  scoreReport: string;
  fetchScoreReport: () => Promise<void>;
  jdText: string;
  setJdText: (text: string) => void;
  atsScore: number;
  matchedKeywords: string[];
  missingKeywords: string[];
  recommendations: string[];
  loading: Record<string, boolean>;
  runProjectReview: (mode: 'review' | 'analyze') => Promise<void>;
  runScoreResume: () => Promise<void>;
  runOptimizeResume: () => Promise<void>;
  showMsg: (text: string, type?: 'success' | 'error') => void;
}

export default function Layout() {
  const [projects, setProjects] = useState<ProjectProfile[]>([]);
  const [selectedProjPath, setSelectedProjPath] = useState<string>('');
  const [astNodes, setAstNodes] = useState<ASTNode[]>([]);
  const [astEdges, setAstEdges] = useState<ASTEdge[]>([]);
  const [astFilter, setAstFilter] = useState<'ALL' | 'File' | 'Class' | 'Function'>('ALL');
  const [reviews, setReviews] = useState<ReviewFinding[]>([]);
  const [scoreReport, setScoreReport] = useState<string>('');
  const [jdText, setJdText] = useState<string>('');
  
  // Scoring parameters state
  const [atsScore, setAtsScore] = useState<number>(0);
  const [matchedKeywords, setMatchedKeywords] = useState<string[]>([]);
  const [missingKeywords, setMissingKeywords] = useState<string[]>([]);
  const [recommendations, setRecommendations] = useState<string[]>([]);
  
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  // Live Logs state
  const [showLogs, setShowLogs] = useState<boolean>(false);
  const [logs, setLogs] = useState<string[]>([]);

  useEffect(() => {
    fetchProjects();
    fetchReviews();
    fetchScoreReport();
  }, []);

  // Polling logic for live logs
  useEffect(() => {
    let intervalId: any;
    if (showLogs) {
      const fetchLogs = async () => {
        try {
          const res = await fetch('/api/logs');
          const data = await res.json();
          setLogs(data.logs || []);
        } catch (e) {
          console.error("Error fetching logs", e);
        }
      };
      
      fetchLogs(); // Initial fetch
      intervalId = setInterval(fetchLogs, 1500);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [showLogs]);

  const showMsg = (text: string, type: 'success' | 'error' = 'success') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 5000);
  };

  const fetchProjects = async () => {
    try {
      const res = await fetch('/api/projects');
      const data = await res.json();
      setProjects(data);
      if (data.length > 0 && !selectedProjPath) {
        setSelectedProjPath(data[0].path);
        fetchAST(data[0].path);
      }
    } catch (e) {
      console.error("Error fetching projects", e);
    }
  };

  const fetchAST = async (path: string) => {
    if (!path) return;
    try {
      const res = await fetch(`/api/project/ast?path=${encodeURIComponent(path)}`);
      const data = await res.json();
      setAstNodes(data.nodes || []);
      setAstEdges(data.edges || []);
    } catch (e) {
      console.error("Error fetching AST data", e);
    }
  };

  const fetchReviews = async () => {
    try {
      const res = await fetch('/api/reviews');
      const data = await res.json();
      setReviews(data);
    } catch (e) {
      console.error("Error fetching reviews", e);
    }
  };

  const fetchScoreReport = async () => {
    try {
      const res = await fetch('/api/score-report');
      const data = await res.json();
      const content = data.content || '';
      setScoreReport(content);
      
      // Parse ATS Score, keywords, and recommendations from report markdown
      const scoreMatch = content.match(/Overall ATS Score:\s*\*\*(\d+)\/100\*\*/);
      if (scoreMatch) {
        setAtsScore(parseInt(scoreMatch[1]));
      } else {
        setAtsScore(0);
      }

      // Parse keywords
      const matchedKeywordsMatch = content.match(/### ✅ Matched Keywords \(\d+\)\s*\n([^\n]+)/);
      if (matchedKeywordsMatch) {
        setMatchedKeywords(matchedKeywordsMatch[1].split(' ').map((k: string) => k.replace(/`/g, '')));
      } else {
        setMatchedKeywords([]);
      }

      const missingKeywordsMatch = content.match(/### ❌ Missing\/Weak Keywords \(\d+\)\s*\n([^\n]+)/);
      if (missingKeywordsMatch) {
        setMissingKeywords(missingKeywordsMatch[1].split(',').map((k: string) => k.replace(/`/g, '').trim()));
      } else {
        setMissingKeywords([]);
      }

      // Parse recommendations (numbered list at bottom)
      const recsMatch = content.match(/## 🚀 Actionable Recommendations to Hit 100\/100\s*\n\n([\s\S]+)/);
      if (recsMatch) {
        const lines = recsMatch[1].split('\n').filter((l: string) => l.trim().length > 0);
        setRecommendations(lines.map((l: string) => l.replace(/^\d+\.\s*\*\*/, '').replace(/\*\*/g, '').trim()));
      } else {
        setRecommendations([]);
      }
    } catch (e) {
      console.error("Error fetching score report", e);
    }
  };

  const runProjectReview = async (mode: 'review' | 'analyze') => {
    const act = mode === 'review' ? 'runReview' : 'runAnalysis';
    setLoading(prev => ({ ...prev, [act]: true }));
    setShowLogs(true);
    try {
      const res = await fetch('/api/run-review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode })
      });
      const data = await res.json();
      showMsg(data.message);
      // Wait a moment and fetch again
      setTimeout(() => {
        fetchProjects();
        fetchReviews();
      }, 5000);
    } catch (e) {
      showMsg("Failed to start analysis", "error");
    } finally {
      setLoading(prev => ({ ...prev, [act]: false }));
    }
  };

  const runScoreResume = async () => {
    setLoading(prev => ({ ...prev, scoring: true }));
    setShowLogs(true);
    try {
      const res = await fetch('/api/score-resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jd_text: jdText })
      });
      const data = await res.json();
      showMsg(data.message);
      
      // Wait for execution and refresh
      setTimeout(() => {
        fetchScoreReport();
      }, 15000);
    } catch (e) {
      showMsg("Failed to run resume scoring", "error");
    } finally {
      setLoading(prev => ({ ...prev, scoring: false }));
    }
  };

  const runOptimizeResume = async () => {
    setLoading(prev => ({ ...prev, optimizing: true }));
    setShowLogs(true);
    try {
      const res = await fetch('/api/optimize-resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jd_text: jdText })
      });
      const data = await res.json();
      showMsg(data.message);
    } catch (e) {
      showMsg("Failed to run resume optimization", "error");
    } finally {
      setLoading(prev => ({ ...prev, optimizing: false }));
    }
  };

  const contextValue: DashboardContextType = {
    projects,
    fetchProjects,
    selectedProjPath,
    setSelectedProjPath,
    astNodes,
    astEdges,
    fetchAST,
    astFilter,
    setAstFilter,
    reviews,
    fetchReviews,
    scoreReport,
    fetchScoreReport,
    jdText,
    setJdText,
    atsScore,
    matchedKeywords,
    missingKeywords,
    recommendations,
    loading,
    runProjectReview,
    runScoreResume,
    runOptimizeResume,
    showMsg
  };

  return (
    <div className="flex min-h-screen bg-bg-primary text-white">
      {/* Sidebar Navigation */}
      <aside className="w-64 bg-bg-secondary border-r border-white/5 p-6 flex flex-col gap-8 flex-shrink-0 z-10">
        <div className="flex flex-col gap-2 pb-4 border-b border-white/5">
          <div className="flex items-center gap-2 text-accent-cyan">
            <Terminal size={20} />
            <h2 className="text-lg font-extrabold tracking-tight bg-gradient-to-r from-accent-cyan to-accent-violet bg-clip-text text-transparent">
              QWEN-ANTIGRAVITY
            </h2>
          </div>
          <span className="text-[10px] text-accent-cyan uppercase tracking-widest font-bold">
            Control Dashboard
          </span>
        </div>

        <nav className="flex flex-col gap-1.5 flex-grow">
          <NavLink 
            to="/" 
            className={({ isActive }) => 
              `flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm ${
                isActive 
                  ? 'text-white bg-white/5 border-l-3 border-accent-cyan bg-accent-cyan/5' 
                  : 'text-text-secondary hover:text-white hover:bg-white/5'
              }`
            }
          >
            <LayoutDashboard size={20} /> Overview
          </NavLink>
          <NavLink 
            to="/ast" 
            className={({ isActive }) => 
              `flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm ${
                isActive 
                  ? 'text-white bg-white/5 border-l-3 border-accent-cyan bg-accent-cyan/5' 
                  : 'text-text-secondary hover:text-white hover:bg-white/5'
              }`
            }
          >
            <GitGraph size={20} /> AST Explorer
          </NavLink>
          <NavLink 
            to="/review" 
            className={({ isActive }) => 
              `flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm ${
                isActive 
                  ? 'text-white bg-white/5 border-l-3 border-accent-cyan bg-accent-cyan/5' 
                  : 'text-text-secondary hover:text-white hover:bg-white/5'
              }`
            }
          >
            <Code2 size={20} /> Code Review Feed
          </NavLink>
          <NavLink 
            to="/resume" 
            className={({ isActive }) => 
              `flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm ${
                isActive 
                  ? 'text-white bg-white/5 border-l-3 border-accent-cyan bg-accent-cyan/5' 
                  : 'text-text-secondary hover:text-white hover:bg-white/5'
              }`
            }
          >
            <FileText size={20} /> Resume Optimizer
          </NavLink>

          <div className="pt-4 mt-4 border-t border-white/5">
            <button 
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm border ${
                showLogs 
                  ? 'bg-accent-cyan/10 border-accent-cyan/30 text-accent-cyan' 
                  : 'bg-transparent border-transparent text-text-secondary hover:text-white hover:bg-white/5'
              }`}
              onClick={() => setShowLogs(!showLogs)}
            >
              <Terminal size={20} /> Console Output
            </button>
          </div>
        </nav>

        {/* Global triggers */}
        <div className="flex flex-col gap-2.5">
          <button 
            className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-accent-cyan to-accent-violet hover:from-accent-cyan hover:to-accent-violet hover:brightness-110 active:scale-95 text-black font-semibold py-3 px-4 rounded-xl shadow-lg shadow-accent-cyan/15 transition-all text-sm disabled:opacity-50 disabled:pointer-events-none"
            onClick={() => runProjectReview('review')}
            disabled={loading.runReview}
          >
            {loading.runReview ? <div className="w-4 h-4 border-2 border-black/10 border-t-black rounded-full animate-spin" /> : <Code2 size={16} />}
            Run Code Review
          </button>
          <button 
            className="w-full flex items-center justify-center gap-2 bg-bg-tertiary hover:bg-white/5 border border-white/5 active:scale-95 text-white py-3 px-4 rounded-xl transition-all text-xs disabled:opacity-50 disabled:pointer-events-none"
            onClick={() => runProjectReview('analyze')}
            disabled={loading.runAnalysis}
          >
            {loading.runAnalysis ? <div className="w-4 h-4 border-2 border-white/10 border-t-white rounded-full animate-spin" /> : <GitGraph size={14} />}
            Build Tech Specs
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className={`flex-grow p-10 overflow-y-auto h-screen transition-all ${showLogs ? 'pb-96' : ''}`}>
        {/* Floating Message Banner */}
        {message && (
          <div 
            className={`fixed top-6 right-6 px-6 py-3 rounded-xl font-semibold shadow-2xl z-50 flex items-center gap-3 animate-fade-in text-black ${
              message.type === 'success' ? 'bg-color-success' : 'bg-danger'
            }`}
          >
            {message.text}
          </div>
        )}
        
        {/* Outlet for children components */}
        <Outlet context={contextValue} />
      </main>

      {/* Logs Console Panel */}
      {showLogs && (
        <div className="fixed bottom-0 right-0 left-64 h-80 bg-bg-secondary/95 backdrop-blur-md border-t border-white/10 z-40 flex flex-col font-mono shadow-2xl">
          <div className="flex items-center justify-between px-6 py-3 border-b border-white/5 bg-black/20">
            <div className="flex items-center gap-2 text-accent-cyan">
              <Terminal size={16} className="animate-pulse" />
              <span className="text-xs font-bold uppercase tracking-wider">Live System Logs</span>
            </div>
            <div className="flex items-center gap-3">
              <button 
                onClick={() => setLogs([])}
                className="text-[10px] text-text-secondary hover:text-white transition-all bg-white/5 px-2.5 py-1 rounded-md"
              >
                Clear Buffer
              </button>
              <button 
                onClick={() => setShowLogs(false)}
                className="text-xs text-text-secondary hover:text-white transition-all"
              >
                ✕ Close
              </button>
            </div>
          </div>
          <div className="flex-grow p-6 overflow-y-auto text-xs text-green-400 flex flex-col gap-1 select-text scrollbar-thin">
            {logs.length === 0 ? (
              <span className="text-white/40 italic">Waiting for logs...</span>
            ) : (
              logs.map((log, idx) => (
                <div key={idx} className="whitespace-pre-wrap leading-relaxed">
                  {log.trim()}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
