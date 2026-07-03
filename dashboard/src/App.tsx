import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Overview from './pages/Overview';
import AstExplorer from './pages/AstExplorer';
import CodeReview from './pages/CodeReview';
import ResumeOptimizer from './pages/ResumeOptimizer';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Overview />} />
          <Route path="ast" element={<AstExplorer />} />
          <Route path="review" element={<CodeReview />} />
          <Route path="resume" element={<ResumeOptimizer />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
