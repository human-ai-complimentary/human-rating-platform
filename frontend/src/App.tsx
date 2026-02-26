import { Routes, Route } from 'react-router-dom';
import { SignedIn, SignedOut, SignInButton, SignUpButton } from '@clerk/clerk-react';
import RaterView from './components/RaterView';
import AdminView from './components/AdminView';
import ExperimentDetailPage from './components/ExperimentDetailPage';

function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/rate" element={<RaterView />} />
        <Route
          path="/admin"
          element={
            <>
              <SignedIn>
                <AdminView />
              </SignedIn>
              <SignedOut>
                <RequireSignIn message="You must sign in to access the admin panel." />
              </SignedOut>
            </>
          }
        />
        <Route
          path="/admin/experiments/:experimentId"
          element={
            <>
              <SignedIn>
                <ExperimentDetailPage />
              </SignedIn>
              <SignedOut>
                <RequireSignIn message="You must sign in to access this page." />
              </SignedOut>
            </>
          }
        />
      </Routes>
    </>
  );
}

function Home() {
  return (
    <div className="container">
      <div className="card">
        <h1>Human Rating Platform</h1>
        <SignedOut>
          <p>Please sign in or sign up to continue.</p>
          <div style={{ marginTop: '20px', display: 'flex', gap: 12 }}>
            <SignInButton />
            <SignUpButton />
          </div>
        </SignedOut>
        <SignedIn>
          <p>You are signed in.</p>
          <div style={{ marginTop: '20px' }}>
            <a href="/admin" style={{ marginRight: '20px' }}>
              <button>Go to Admin Panel</button>
            </a>
          </div>
        </SignedIn>
      </div>
    </div>
  );
}

function RequireSignIn({ message }: { message: string }) {
  return (
    <div className="container">
      <div className="card" style={{ textAlign: 'center' }}>
        <p style={{ fontSize: 20, marginBottom: 16 }}>{message}</p>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
          <SignInButton />
          <SignUpButton />
        </div>
      </div>
    </div>
  );
}

export default App;
