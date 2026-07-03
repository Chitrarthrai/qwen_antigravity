import type { ChangeEvent } from 'react';
import { useOutletContext } from 'react-router-dom';
import type { DashboardContextType } from '../components/Layout';

export default function AstExplorer() {
  const { 
    projects, 
    selectedProjPath, 
    setSelectedProjPath, 
    astNodes, 
    astEdges, 
    fetchAST, 
    astFilter, 
    setAstFilter 
  } = useOutletContext<DashboardContextType>();

  const handleProjChange = (e: ChangeEvent<HTMLSelectElement>) => {
    const path = e.target.value;
    setSelectedProjPath(path);
    fetchAST(path);
  };

  const filteredNodes = astNodes.filter(n => astFilter === 'ALL' || n.kind === astFilter);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-1 text-white">AST Explorer</h1>
        <p className="text-sm text-text-secondary">Querying code-review-graph indices inside selected project root</p>
      </div>

      <div className="bg-bg-secondary/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl flex gap-4 items-center">
        <span className="text-sm font-semibold">Select Project:</span>
        <select 
          value={selectedProjPath} 
          onChange={handleProjChange}
          className="bg-bg-tertiary text-white border border-white/5 px-4 py-2 rounded-xl outline-none flex-grow cursor-pointer"
        >
          {projects.map((p, idx) => (
            <option key={idx} value={p.path}>{p.project_name}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[240px_1fr] gap-6">
        {/* Filter Pane */}
        <div className="bg-bg-secondary/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl flex flex-col gap-3 h-fit">
          <h3 className="text-sm font-bold border-b border-white/5 pb-2 mb-1 text-white">Filters</h3>
          {(['ALL', 'File', 'Class', 'Function'] as const).map((f) => (
            <label key={f} className="flex items-center gap-2.5 cursor-pointer text-sm text-text-secondary hover:text-white">
              <input 
                type="radio" 
                name="ast-filter" 
                checked={astFilter === f}
                onChange={() => setAstFilter(f)}
                className="accent-accent-cyan cursor-pointer"
              />
              {f}s
            </label>
          ))}
        </div>

        {/* Nodes List */}
        <div className="bg-bg-secondary/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl flex flex-col gap-4">
          <div className="flex justify-between items-center border-b border-white/5 pb-3">
            <h3 className="text-base font-bold text-white">
              Index Nodes ({filteredNodes.length}) | Relations ({astEdges.length})
            </h3>
          </div>

          <div className="flex flex-col gap-2 max-h-[500px] overflow-y-auto pr-1">
            {filteredNodes.length === 0 ? (
              <div className="text-text-secondary text-center py-20 text-sm">
                No AST database or matches found. Ensure <code>code-review-graph</code> built successfully.
              </div>
            ) : (
              filteredNodes.map((n, idx) => (
                <div 
                  key={idx} 
                  className="flex items-center gap-3 px-4 py-2.5 rounded-lg bg-white/[0.01] hover:bg-white/[0.03] border border-transparent hover:border-accent-cyan/15 transition-all font-mono text-xs"
                >
                  <span className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase ${
                    n.kind === 'File' 
                      ? 'bg-color-info/10 text-color-info border border-color-info/20' 
                      : n.kind === 'Class' 
                      ? 'bg-accent-violet/10 text-[#c084fc] border border-accent-violet/20' 
                      : 'bg-color-success/10 text-color-success border border-color-success/20'
                  }`}>
                    {n.kind}
                  </span>
                  <span className="font-semibold text-white">{n.name}</span>
                  <span className="text-text-secondary/50 text-[10px] ml-auto">{n.file_path}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
