import { Routes, Route } from 'react-router-dom';
import RaterView from './components/RaterView';
import AdminView from './components/AdminView';
import ExperimentDetailPage from './components/ExperimentDetailPage';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/rate" element={<RaterView />} />
      <Route path="/admin" element={<AdminView />} />
      <Route path="/admin/experiments/:experimentId" element={<ExperimentDetailPage />} />
    </Routes>
  );
}

function Home() {
  return (
    <div className="container">
      <div className="card">
        <h1>Human Rating Platform</h1>
        <p>Welcome to the Human Rating Platform.</p>
        <div style={{ marginTop: '20px' }}>
          <a href="/admin" style={{ marginRight: '20px' }}>
            <button>Admin Panel</button>
          </a>
        </div>
      </div>
    </div>
  );
}

export default App;
