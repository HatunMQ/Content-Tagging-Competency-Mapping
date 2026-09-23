import { useState } from "react";
import { Routes, Route } from "react-router-dom";
import TopNav from "./components/TopNav.jsx";
import Sidebar from "./components/Sidebar.jsx";
import LearningPlatform from "./pages/LearningPlatform.jsx";
import FieldContent from "./pages/FieldContent.jsx";
import MyLearning from "./pages/MyLearning.jsx";
import ProgressDashboard from "./pages/ProgressDashboard.jsx";
import InfraDashboard from "./pages/InfraDashboard.jsx";
import QuizPage from "./pages/QuizPage.jsx";

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="app-shell">
      <TopNav onMenuClick={() => setSidebarOpen(true)} />
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <Routes>
        <Route path="/" element={<LearningPlatform />} />
        <Route path="/field/:fieldName" element={<FieldContent />} />
        <Route path="/my-learning" element={<MyLearning />} />
        <Route path="/progress" element={<ProgressDashboard />} />
        <Route path="/infra" element={<InfraDashboard />} />
        <Route path="/quiz/:quizId" element={<QuizPage />} />
      </Routes>
    </div>
  );
}
