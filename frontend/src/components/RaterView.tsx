import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api';
import Timer from './Timer';
import QuestionCard from './QuestionCard';
import type { Session, Question } from '../types';

function RaterView() {
  const [searchParams] = useSearchParams();
  const [session, setSession] = useState<Session | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [questionsCompleted, setQuestionsCompleted] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [allDone, setAllDone] = useState(false);

  const experimentId = searchParams.get('experiment_id');
  const prolificId = searchParams.get('PROLIFIC_PID');
  const studyId = searchParams.get('STUDY_ID');
  const sessionId = searchParams.get('SESSION_ID');

  useEffect(() => {
    if (!experimentId || !prolificId) {
      setError('Missing experiment_id or PROLIFIC_PID in URL');
      setLoading(false);
      return;
    }

    api.startSession(experimentId, prolificId, studyId, sessionId)
      .then(data => {
        setSession(data);
        return loadNextQuestion(data.rater_id);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [experimentId, prolificId]);

  const loadNextQuestion = useCallback(async (raterId: number) => {
    try {
      setLoading(true);
      const q = await api.getNextQuestion(raterId);
      if (q === null || (typeof q === 'object' && Object.keys(q).length === 0)) {
        setAllDone(true);
      } else {
        setQuestion(q);
      }
    } catch (err) {
      if (err instanceof Error && err.message === 'Session expired') {
        setSessionExpired(true);
      } else {
        setError(err instanceof Error ? err.message : 'Unknown error');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSubmit = async (answer: string, confidence: number, timeStarted: string) => {
    if (!session || !question) return;

    try {
      await api.submitRating(session.rater_id, {
        question_id: question.id,
        answer,
        confidence,
        time_started: timeStarted,
      });
      setQuestionsCompleted(prev => prev + 1);
      await loadNextQuestion(session.rater_id);
    } catch (err) {
      if (err instanceof Error && err.message === 'Session expired') {
        setSessionExpired(true);
      } else {
        setError(err instanceof Error ? err.message : 'Unknown error');
      }
    }
  };

  const handleSessionExpired = () => {
    setSessionExpired(true);
  };

  const styles = {
    container: {
      maxWidth: '700px',
      margin: '0 auto',
      padding: '24px',
      minHeight: '100vh',
    },
    header: {
      background: '#fff',
      borderRadius: '12px',
      border: '1px solid #e0e0e0',
      padding: '20px 24px',
      marginBottom: '20px',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
    },
    experimentName: {
      fontSize: '18px',
      fontWeight: 600,
      color: '#333',
      margin: 0,
    },
    progress: {
      fontSize: '14px',
      color: '#666',
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
    },
    progressCount: {
      background: '#e3f2fd',
      color: '#4a90d9',
      padding: '4px 12px',
      borderRadius: '16px',
      fontWeight: 600,
    },
    completionCard: {
      background: '#fff',
      borderRadius: '12px',
      border: '1px solid #e0e0e0',
      padding: '60px 40px',
      textAlign: 'center' as const,
    },
    completionTitle: {
      fontSize: '32px',
      fontWeight: 600,
      color: '#27ae60',
      marginBottom: '16px',
    },
    completionText: {
      fontSize: '16px',
      color: '#666',
      marginBottom: '24px',
    },
    completionStats: {
      fontSize: '18px',
      color: '#333',
      marginBottom: '32px',
    },
    completionCount: {
      fontSize: '48px',
      fontWeight: 700,
      color: '#4a90d9',
      display: 'block',
      marginBottom: '8px',
    },
    redirectText: {
      fontSize: '14px',
      color: '#888',
    },
    redirectLink: {
      color: '#4a90d9',
      textDecoration: 'none',
    },
    errorCard: {
      background: '#fff',
      borderRadius: '12px',
      border: '1px solid #f5c6cb',
      padding: '40px',
      textAlign: 'center' as const,
    },
    errorText: {
      color: '#dc3545',
      fontSize: '16px',
    },
    loadingCard: {
      background: '#fff',
      borderRadius: '12px',
      border: '1px solid #e0e0e0',
      padding: '60px 40px',
      textAlign: 'center' as const,
      color: '#666',
    },
  };

  if (error) {
    return (
      <div style={styles.container}>
        <div style={styles.errorCard}>
          <p style={styles.errorText}>{error}</p>
        </div>
      </div>
    );
  }

  if (sessionExpired || allDone) {
    const completionUrl = session?.completion_url;

    if (completionUrl) {
      setTimeout(() => {
        window.location.href = completionUrl;
      }, 3000);
    }

    return (
      <div style={styles.container}>
        <div style={styles.completionCard}>
          <h1 style={styles.completionTitle}>
            {allDone ? 'All Done!' : 'Session Complete'}
          </h1>
          <p style={styles.completionText}>
            {allDone
              ? 'You have completed all available questions.'
              : 'Your session has ended.'}
          </p>
          <div style={styles.completionStats}>
            <span style={styles.completionCount}>{questionsCompleted}</span>
            questions completed
          </div>
          {completionUrl ? (
            <p style={styles.redirectText}>
              Redirecting you back to Prolific in 3 seconds...
              <br />
              <a href={completionUrl} style={styles.redirectLink}>
                Click here if not redirected
              </a>
            </p>
          ) : (
            <p style={styles.redirectText}>
              Thank you for your participation! You may now close this window.
            </p>
          )}
        </div>
      </div>
    );
  }

  if (loading || !session) {
    return (
      <div style={styles.container}>
        <div style={styles.loadingCard}>
          Loading...
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <Timer
        sessionEndTime={session.session_end_time}
        onExpire={handleSessionExpired}
      />

      <div style={styles.header}>
        <h2 style={styles.experimentName}>{session.experiment_name}</h2>
        <div style={styles.progress}>
          Completed:
          <span style={styles.progressCount}>{questionsCompleted}</span>
        </div>
      </div>

      {question && (
        <QuestionCard
          question={question}
          onSubmit={handleSubmit}
        />
      )}
    </div>
  );
}

export default RaterView;
