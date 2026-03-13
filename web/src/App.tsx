import { Routes, Route, Navigate } from 'react-router-dom';
import { Construction } from 'lucide-react';
import { isLoggedIn } from './utils/api';
import Layout from './components/Layout';
import LoginPage from './pages/Login';
import DashboardPage from './pages/Dashboard';
import SessionsPage from './pages/Sessions';
import TasksPage from './pages/Tasks';
import MemoryPage from './pages/Memory';
import ChatPage from './pages/Chat';
import SurvivalPage from './pages/Survival';
import OutputPage from './pages/Output';
import WorkflowsPage from './pages/Workflows';
import CapabilitiesPage from './pages/Capabilities';
import GuidePage from './pages/Guide';
import PromptEditorPage from './pages/PromptEditor';

function Placeholder({ name }: { name: string }) {
  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">{name}</h1>
      <div className="flex items-center gap-2 text-[var(--text-secondary)]">
        <Construction size={16} />
        <p>即将上线。</p>
      </div>
    </div>
  );
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!isLoggedIn()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route index element={<DashboardPage />} />
        <Route path="sessions" element={<SessionsPage />} />
        <Route path="sessions/:id" element={<SessionsPage />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="survival" element={<SurvivalPage />} />
        <Route path="output" element={<OutputPage />} />
        <Route path="workflows" element={<WorkflowsPage />} />
        <Route path="capabilities" element={<CapabilitiesPage />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="memory" element={<MemoryPage />} />
        <Route path="guide" element={<GuidePage />} />
        <Route path="prompt" element={<PromptEditorPage />} />
        <Route path="settings" element={<Placeholder name="设置" />} />
      </Route>
    </Routes>
  );
}
