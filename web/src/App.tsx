import { Routes, Route, Navigate } from 'react-router-dom';
import { isLoggedIn } from './utils/api';
import Layout from './components/Layout';
import LoginPage from './pages/Login';
import DashboardPage from './pages/Dashboard';
import TasksPage from './pages/Tasks';
import MemoryPage from './pages/Memory';
import SurvivalPage from './pages/Survival';
import OutputPage from './pages/Output';
import WorkflowsPage from './pages/Workflows';
import CapabilitiesPage from './pages/Capabilities';
import GuidePage from './pages/Guide';
import PromptEditorPage from './pages/PromptEditor';
import ScheduledTasksPage from './pages/ScheduledTasks';
import SupervisorPage from './pages/Supervisor';
import KnowledgePage from './pages/Knowledge';
import ExtensionsPage from './pages/Extensions';
import SettingsPage from './pages/Settings';
import DigitalHumansPage from './pages/DigitalHumans';
import DiscoveriesPage from './pages/Discoveries';
import IdentityPromptsPage from './pages/IdentityPrompts';

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
        <Route path="survival" element={<SurvivalPage />} />
        <Route path="output" element={<OutputPage />} />
        <Route path="workflows" element={<WorkflowsPage />} />
        <Route path="capabilities" element={<CapabilitiesPage />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="memory" element={<MemoryPage />} />
        <Route path="guide" element={<GuidePage />} />
        <Route path="prompt" element={<PromptEditorPage />} />
        <Route path="scheduled" element={<ScheduledTasksPage />} />
        <Route path="supervisor" element={<SupervisorPage />} />
        <Route path="knowledge" element={<KnowledgePage />} />
        <Route path="extensions" element={<ExtensionsPage />} />
        <Route path="digital_humans" element={<DigitalHumansPage />} />
        <Route path="discoveries" element={<DiscoveriesPage />} />
        <Route path="identity_prompts" element={<IdentityPromptsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
