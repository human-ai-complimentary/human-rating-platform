import ReactMarkdown from 'react-markdown';

interface ContextPanelProps {
  instructions: string;
  question: string;
}

export function ContextPanel({ instructions, question }: ContextPanelProps) {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
          Instructions
        </h2>
        <p className="text-gray-700 leading-relaxed">{instructions}</p>
      </div>
      <div>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
          Question
        </h2>
        <div className="text-gray-900 leading-relaxed prose prose-sm max-w-none">
          <ReactMarkdown>{question}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
