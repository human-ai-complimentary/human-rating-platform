import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api';
import type { FakeStudyDetail } from '../types';

function FakeStudyDetailPage() {
  const { studyId } = useParams<{ studyId: string }>();
  const [study, setStudy] = useState<FakeStudyDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!studyId) {
      setError('Fake study not found');
      setLoading(false);
      return;
    }

    api.getFakeStudyDetail(studyId)
      .then((data) => setStudy(data))
      .catch((err) => setError(err instanceof Error ? err.message : 'Unknown error'))
      .finally(() => setLoading(false));
  }, [studyId]);

  const styles = {
    container: {
      maxWidth: '980px',
      margin: '0 auto',
      padding: '24px',
    },
    section: {
      background: '#fff',
      borderRadius: '8px',
      border: '1px solid #e0e0e0',
      padding: '20px',
      marginBottom: '20px',
    },
    title: {
      margin: '0 0 8px 0',
      fontSize: '28px',
      fontWeight: 600,
      color: '#333',
    },
    subtitle: {
      margin: 0,
      fontSize: '14px',
      color: '#666',
      lineHeight: 1.5,
    },
    row: {
      display: 'grid',
      gridTemplateColumns: '180px 1fr',
      gap: '12px',
      padding: '10px 0',
      borderBottom: '1px solid #eee',
      alignItems: 'start',
    },
    label: {
      fontSize: '12px',
      fontWeight: 600,
      textTransform: 'uppercase' as const,
      letterSpacing: '0.5px',
      color: '#666',
    },
    value: {
      fontSize: '14px',
      color: '#333',
      lineHeight: 1.5,
      wordBreak: 'break-word' as const,
    },
    code: {
      fontFamily: 'monospace',
      background: '#f8f9fa',
      borderRadius: '4px',
      padding: '2px 6px',
    },
    status: {
      display: 'inline-block',
      padding: '4px 10px',
      borderRadius: '999px',
      background: '#fff3cd',
      color: '#856404',
      fontWeight: 600,
      fontSize: '12px',
    },
    link: {
      color: '#4a90d9',
      textDecoration: 'none',
    },
    note: {
      background: '#f0f7ff',
      border: '1px solid #cfe2ff',
      color: '#0b5394',
      borderRadius: '8px',
      padding: '14px 16px',
      fontSize: '14px',
      marginBottom: '20px',
      lineHeight: 1.5,
    },
  };

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.section}>Loading...</div>
      </div>
    );
  }

  if (error || !study) {
    return (
      <div style={styles.container}>
        <div style={styles.section} data-testid="fake-study-error">
          {error ?? 'Fake study not found'}
        </div>
      </div>
    );
  }

  const detailRows: Array<{ label: string; value: ReactNode }> = [
    { label: 'Study ID', value: study.study_id },
    { label: 'Status', value: <span style={styles.status}>{study.study_status}</span> },
    { label: 'Places', value: String(study.places_requested) },
    { label: 'Reward', value: `${study.reward} cents` },
    { label: 'Estimated Time', value: `${study.estimated_completion_time} minutes` },
    { label: 'Devices', value: study.device_compatibility.join(', ') },
    { label: 'Created', value: new Date(study.created_at).toLocaleString() },
    { label: 'Description', value: study.description },
    {
      label: 'External Study URL',
      value: <span style={styles.code}>{study.external_study_url}</span>,
    },
    {
      label: 'Completion URL',
      value: study.completion_url ? (
        <span style={styles.code}>{study.completion_url}</span>
      ) : 'Not available',
    },
  ];

  return (
    <div style={styles.container} data-testid="fake-study-detail-page">
      <div style={styles.note}>
        This is a local fake Prolific study. Review it to rehearse the draft and publish flow
        without spending money or calling the real Prolific API.
      </div>

      <div style={styles.section}>
        <h1 style={styles.title}>Fake Study Review</h1>
        <p style={styles.subtitle}>
          <Link style={styles.link} to={`/admin/experiments/${study.experiment_id}`}>
            {study.experiment_name}
          </Link>
          {' · '}
          {study.is_pilot ? 'Pilot study' : `Round ${study.round_number}`}
        </p>
      </div>

      <div style={styles.section}>
        {detailRows.map(({ label, value }, index) => (
          <div
            key={label}
            style={{
              ...styles.row,
              borderBottom: index === detailRows.length - 1 ? 'none' : '1px solid #eee',
            }}
          >
            <div style={styles.label}>{label}</div>
            <div style={styles.value}>{value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default FakeStudyDetailPage;
