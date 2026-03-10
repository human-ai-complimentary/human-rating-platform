import { useState, useEffect } from 'react';
import { api } from '../api';
import type { DelegationTask, Session } from '../types';
import { SplitLayout } from './delegation/SplitLayout';
import { ContextPanel } from './delegation/ContextPanel';
import { ChatInterface } from './delegation/ChatInterface';
import { DelegationInterface } from './delegation/DelegationInterface';

interface DelegationViewProps {
  session: Session;
  experimentId: string;
  prolificId: string;
  onComplete: () => void;
}

function DelegationView({ session, experimentId, prolificId, onComplete }: DelegationViewProps) {
  const [task, setTask] = useState<DelegationTask | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session.delegation_task_id) {
      setError('No task assigned for this session.');
      setLoading(false);
      return;
    }

    api
      .getDelegationTask(session.delegation_task_id)
      .then((data) => setTask(data))
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load task'))
      .finally(() => setLoading(false));
  }, [session.delegation_task_id]);

  const handleComplete = async () => {
    try {
      await api.endSession(session.rater_id);
    } catch {
      // best-effort; proceed to completion regardless
    }
    onComplete();
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="text-gray-600">Loading task...</div>
      </div>
    );
  }

  if (error || !task) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="text-red-600">{error || 'Task not found.'}</div>
      </div>
    );
  }

  const InteractionPanel =
    session.experiment_type === 'delegation' ? (
      <DelegationInterface
        task={task}
        pid={prolificId}
        experimentId={Number(experimentId)}
        onComplete={handleComplete}
      />
    ) : (
      <ChatInterface
        task={task}
        pid={prolificId}
        experimentId={Number(experimentId)}
        onComplete={handleComplete}
      />
    );

  return (
    <SplitLayout
      leftPanel={<ContextPanel instructions={task.instructions} question={task.question} />}
      rightPanel={InteractionPanel}
    />
  );
}

export default DelegationView;
