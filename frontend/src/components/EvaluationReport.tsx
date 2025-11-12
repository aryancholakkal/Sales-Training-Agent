import React from 'react';
import { EvaluationCategoryFeedback, EvaluationResponse, Persona, Product } from '../services/api';
import { LoadingSpinner } from './Icons';

interface EvaluationReportProps {
  evaluation: EvaluationResponse | null;
  status: 'idle' | 'loading' | 'success' | 'error';
  error?: string | null;
  onRetry: () => void;
  onRestart: () => void;
  onDownload: () => void;
  persona?: Persona | null;
  product?: Product | null;
}

const formatTimestamp = (timestamp: string) => {
  try {
    const date = new Date(timestamp);
    return date.toLocaleString();
  } catch (e) {
    return timestamp;
  }
};

const ScoreBar: React.FC<{ feedback: EvaluationCategoryFeedback }> = ({ feedback }) => {
  const width = `${Math.min(100, Math.max(0, (feedback.score / 20) * 100))}%`;

  return (
    <div className="bg-brand-dark border border-slate-700 rounded-xl p-4">
      <div className="flex items-center justify-between text-brand-light">
        <span className="font-semibold">{feedback.category}</span>
        <span className="text-sm text-brand-accent">{feedback.score}/20</span>
      </div>
      <div className="mt-3 h-2 bg-slate-700 rounded-full">
        <div className="h-full rounded-full bg-gradient-to-r from-brand-secondary to-brand-primary" style={{ width }} />
      </div>
      <p className="mt-3 text-sm text-slate-300 leading-relaxed">{feedback.comment}</p>
    </div>
  );
};

export const EvaluationReport: React.FC<EvaluationReportProps> = ({
  evaluation,
  status,
  error,
  onRetry,
  onRestart,
  onDownload,
  persona,
  product,
}) => {
  if (status === 'idle') {
    return null;
  }

  if (status === 'loading') {
    return (
      <div className="mt-8 w-full max-w-4xl mx-auto p-8 bg-slate-800 rounded-2xl shadow-2xl text-center">
        <LoadingSpinner className="w-10 h-10 mx-auto mb-4" />
  <h3 className="text-2xl font-semibold text-white">Evaluating your conversation...</h3>
        <p className="mt-2 text-sm text-slate-300">This usually takes just a few seconds.</p>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="mt-8 w-full max-w-4xl mx-auto p-8 bg-slate-800 rounded-2xl shadow-2xl text-center">
        <h3 className="text-2xl font-semibold text-white mb-4">We couldn&apos;t complete the evaluation</h3>
        <p className="text-sm text-red-400 mb-6">{error || 'Something went wrong while generating your report.'}</p>
        <div className="flex flex-wrap gap-3 justify-center">
          <button
            onClick={onRetry}
            className="px-6 py-2 bg-brand-secondary hover:bg-brand-primary text-white font-semibold rounded-full transition-colors"
          >
            Try Again
          </button>
          <button
            onClick={onRestart}
            className="px-6 py-2 bg-slate-700 hover:bg-slate-600 text-white font-semibold rounded-full transition-colors"
          >
            Start New Simulation
          </button>
        </div>
      </div>
    );
  }

  if (!evaluation) {
    return null;
  }

  return (
    <section className="mt-8 w-full max-w-5xl mx-auto space-y-6">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl p-8">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h2 className="text-3xl font-bold text-brand-light">Sales Evaluation Report</h2>
            <p className="text-sm text-slate-400 mt-1">Generated {formatTimestamp(evaluation.created_at)}</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              onClick={onDownload}
              className="px-6 py-2 bg-brand-secondary hover:bg-brand-primary text-white font-semibold rounded-full transition-colors"
            >
              Download Report
            </button>
            <button
              onClick={onRestart}
              className="px-6 py-2 bg-slate-700 hover:bg-slate-600 text-white font-semibold rounded-full transition-colors"
            >
              Start New Simulation
            </button>
          </div>
        </div>
        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-brand-dark border border-slate-700 rounded-xl p-6 flex flex-col justify-between">
            <p className="text-sm text-brand-accent uppercase tracking-widest">Overall Score</p>
            <p className="mt-3 text-5xl font-black text-white">{evaluation.overall_score}</p>
            <p className="text-xs text-slate-400 mt-4">Maximum score: 100 points (5 categories × 20)</p>
          </div>
          <div className="bg-brand-dark border border-slate-700 rounded-xl p-6">
            <p className="text-sm text-brand-accent uppercase tracking-widest">Summary</p>
            <p className="mt-3 text-sm text-slate-300 leading-relaxed">{evaluation.summary_feedback}</p>
            {persona || product ? (
              <div className="mt-4 text-xs text-slate-400 space-y-1">
                {persona ? <p>Persona: <span className="text-slate-200">{persona.name}</span></p> : null}
                {product ? <p>Product: <span className="text-slate-200">{product.name}</span></p> : null}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-xl font-semibold text-brand-light mb-4">Category Breakdown</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {evaluation.detailed_feedback.map((feedback) => (
            <ScoreBar key={feedback.category} feedback={feedback} />
          ))}
        </div>
      </div>
    </section>
  );
};
